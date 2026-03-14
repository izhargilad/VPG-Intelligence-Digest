import React, { useEffect, useState, useMemo } from 'react'

/* ─── Constants ──────────────────────────────────────────────────── */

const MOMENTUM_BADGES = {
  spike: { label: 'SPIKE', color: 'bg-red-600 text-white' },
  rising: { label: 'RISING', color: 'bg-orange-500 text-white' },
  new: { label: 'NEW', color: 'bg-blue-600 text-white' },
  stable: { label: 'STABLE', color: 'bg-gray-400 text-white' },
  declining: { label: 'DECLINING', color: 'bg-gray-300 text-gray-700' },
}

const TYPE_LABELS = {
  bu_signal_type: 'BU + Signal Type',
  signal_type: 'Signal Type',
  business_unit: 'Business Unit',
  competitor: 'Competitor',
  industry: 'Industry',
}

const TREND_TYPE_ICONS = {
  rising: { icon: '🔥', label: 'RISING', color: 'text-orange-600', bg: 'bg-orange-50 border-orange-300' },
  declining: { icon: '📉', label: 'DECLINING', color: 'text-red-600', bg: 'bg-red-50 border-red-300' },
  new: { icon: '✨', label: 'NEW', color: 'text-blue-600', bg: 'bg-blue-50 border-blue-300' },
  persistent: { icon: '🔄', label: 'PERSISTENT', color: 'text-gray-600', bg: 'bg-gray-50 border-gray-300' },
}

const CHART_COLORS = [
  '#2E75B6', '#E8792F', '#059669', '#DC2626', '#8B5CF6',
  '#F59E0B', '#06B6D4', '#EC4899', '#1B2A4A', '#10B981',
]

const SENTIMENT_STYLES = {
  positive: { icon: '📈', bg: 'bg-green-50', border: 'border-green-400', text: 'text-green-700' },
  neutral: { icon: '➡️', bg: 'bg-gray-50', border: 'border-gray-300', text: 'text-gray-600' },
  negative: { icon: '📉', bg: 'bg-red-50', border: 'border-red-400', text: 'text-red-700' },
}

/* ─── SVG Sparkline ──────────────────────────────────────────────── */

function Sparkline({ data, width = 120, height = 40, color = '#2E75B6' }) {
  if (!data || data.length === 0) return null
  const values = data.map(d => d.count || 0)
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const range = max - min || 1

  const points = values.map((v, i) => {
    const x = (i / Math.max(values.length - 1, 1)) * width
    const y = height - ((v - min) / range) * (height - 4) - 2
    return `${x},${y}`
  }).join(' ')

  const fillPoints = `0,${height} ${points} ${width},${height}`

  return (
    <svg width={width} height={height} className="inline-block">
      <polygon points={fillPoints} fill={color} fillOpacity="0.15" />
      <polyline points={points} fill="none" stroke={color} strokeWidth="2"
                strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

/* ─── Multi-line Chart (SVG) ─────────────────────────────────────── */

function MultiLineChart({ weeks, series, height = 300 }) {
  const [hoveredPoint, setHoveredPoint] = useState(null)
  const [visibleSeries, setVisibleSeries] = useState(() => new Set(series.map(s => s.id)))

  const width = 700
  const padding = { top: 20, right: 20, bottom: 40, left: 50 }
  const chartW = width - padding.left - padding.right
  const chartH = height - padding.top - padding.bottom

  const maxVal = useMemo(() => {
    let m = 0
    series.forEach(s => {
      if (visibleSeries.has(s.id)) {
        s.data.forEach(d => { if (d.count > m) m = d.count })
      }
    })
    return m || 1
  }, [series, visibleSeries])

  const toggleSeries = (id) => {
    setVisibleSeries(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (!weeks || weeks.length === 0) {
    return <div className="text-center text-gray-400 py-8">No signal volume data available.</div>
  }

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ maxHeight: height }}>
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map(pct => {
          const y = padding.top + chartH * (1 - pct)
          const val = Math.round(maxVal * pct)
          return (
            <g key={pct}>
              <line x1={padding.left} y1={y} x2={padding.left + chartW} y2={y}
                    stroke="#E2E8F0" strokeDasharray="3 3" />
              <text x={padding.left - 8} y={y + 4} textAnchor="end"
                    fill="#64748B" fontSize="11">{val}</text>
            </g>
          )
        })}

        {/* X axis labels */}
        {weeks.map((w, i) => {
          const x = padding.left + (i / Math.max(weeks.length - 1, 1)) * chartW
          return (
            <text key={w} x={x} y={height - 8} textAnchor="middle"
                  fill="#64748B" fontSize="11">{w}</text>
          )
        })}

        {/* Lines */}
        {series.map((s, si) => {
          if (!visibleSeries.has(s.id)) return null
          const color = CHART_COLORS[si % CHART_COLORS.length]
          const points = s.data.map((d, i) => {
            const x = padding.left + (i / Math.max(weeks.length - 1, 1)) * chartW
            const y = padding.top + chartH * (1 - d.count / maxVal)
            return { x, y, ...d }
          })
          const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
          return (
            <g key={s.id}>
              <path d={pathD} fill="none" stroke={color} strokeWidth="2" />
              {points.map((p, i) => (
                <circle key={i} cx={p.x} cy={p.y} r="3" fill={color}
                        className="cursor-pointer"
                        onMouseEnter={() => setHoveredPoint({ series: s.name, week: weeks[i], ...p })}
                        onMouseLeave={() => setHoveredPoint(null)} />
              ))}
            </g>
          )
        })}

        {/* Tooltip */}
        {hoveredPoint && (
          <g>
            <rect x={Math.min(hoveredPoint.x + 10, width - 160)}
                  y={Math.max(hoveredPoint.y - 40, 5)}
                  width="150" height="45" rx="4" fill="white" stroke="#E2E8F0" />
            <text x={Math.min(hoveredPoint.x + 18, width - 152)}
                  y={Math.max(hoveredPoint.y - 22, 22)} fontSize="11" fill="#1B2A4A" fontWeight="bold">
              {hoveredPoint.series}
            </text>
            <text x={Math.min(hoveredPoint.x + 18, width - 152)}
                  y={Math.max(hoveredPoint.y - 6, 38)} fontSize="11" fill="#64748B">
              {hoveredPoint.week}: {hoveredPoint.count} signals, avg {(hoveredPoint.avg_score || 0).toFixed(1)}
            </text>
          </g>
        )}
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mt-3 justify-center">
        {series.map((s, i) => (
          <button key={s.id} onClick={() => toggleSeries(s.id)}
                  className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full border transition-all ${
                    visibleSeries.has(s.id) ? 'opacity-100' : 'opacity-40'
                  }`}>
            <span className="w-3 h-3 rounded-full inline-block"
                  style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }} />
            {s.name}
          </button>
        ))}
      </div>
    </div>
  )
}

/* ─── Horizontal Fill Bar ────────────────────────────────────────── */

function FillBar({ value, max, color = 'bg-vpg-blue', height = 8 }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div className="w-full bg-gray-100 rounded-full overflow-hidden" style={{ height }}>
      <div className={`${color} rounded-full h-full transition-all`} style={{ width: `${pct}%` }} />
    </div>
  )
}

/* ─── WoW Tooltip ─────────────────────────────────────────────────── */

function WoWHeader() {
  const [showTip, setShowTip] = useState(false)
  return (
    <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase relative">
      <span
        className="cursor-help border-b border-dashed border-gray-400"
        onMouseEnter={() => setShowTip(true)}
        onMouseLeave={() => setShowTip(false)}
      >
        WoW %
      </span>
      {showTip && (
        <div className="absolute z-50 top-full left-1/2 -translate-x-1/2 mt-1 w-64 bg-gray-900 text-white text-[11px] rounded-lg p-3 shadow-lg text-left font-normal normal-case">
          <p className="font-semibold mb-1">Week-over-Week Change %</p>
          <p>Measures the percentage change in signal count between the current period and the prior period.</p>
        </div>
      )}
    </th>
  )
}

/* ─── Main Component ──────────────────────────────────────────────── */

export default function Trends() {
  // Core state
  const [loading, setLoading] = useState(true)
  const [dateRange, setDateRange] = useState({ start: '', end: '' })
  const [buFilter, setBuFilter] = useState('')
  const [industryFilter, setIndustryFilter] = useState('')

  // Data sections
  const [trendAlerts, setTrendAlerts] = useState([])
  const [industryMomentum, setIndustryMomentum] = useState([])
  const [signalVolume, setSignalVolume] = useState({ weeks: [], series: [] })
  const [competitorTrends, setCompetitorTrends] = useState([])
  const [keywordData, setKeywordData] = useState(null)

  // Keyword table state
  const [activeFilter, setActiveFilter] = useState('all')
  const [selectedTrend, setSelectedTrend] = useState(null)
  const [history, setHistory] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(false)

  // BU list for filter dropdown
  const [buList, setBuList] = useState([])

  // Load BUs
  useEffect(() => {
    fetch('/api/business-units')
      .then(r => r.json())
      .then(data => setBuList(data.business_units || []))
      .catch(() => {})
  }, [])

  // Build query params
  const buildParams = (extra = {}) => {
    const params = new URLSearchParams()
    if (buFilter) params.set('bu_code', buFilter)
    if (dateRange.start) params.set('start_date', dateRange.start)
    if (dateRange.end) params.set('end_date', dateRange.end)
    Object.entries(extra).forEach(([k, v]) => { if (v) params.set(k, v) })
    return params.toString()
  }

  // Load all sections
  const loadData = () => {
    setLoading(true)
    const qs = buildParams()

    Promise.all([
      fetch(`/api/trends/alerts?${qs}&limit=5`).then(r => r.json()).catch(() => ({ alerts: [] })),
      fetch(`/api/trends/industry-momentum?${qs}`).then(r => r.json()).catch(() => ({ industries: [] })),
      fetch(`/api/trends/signal-volume?${buildParams()}&weeks=12`).then(r => r.json()).catch(() => ({ weeks: [], series: [] })),
      fetch(`/api/trends/competitor-trends?${qs}`).then(r => r.json()).catch(() => ({ competitors: [] })),
      fetch(`/api/trends?${buildParams({ limit: '50' })}`).then(r => r.json()).catch(() => ({ trends: [] })),
    ]).then(([alerts, momentum, volume, competitors, keywords]) => {
      setTrendAlerts(alerts.alerts || [])
      setIndustryMomentum(momentum.industries || [])
      setSignalVolume(volume)
      setCompetitorTrends(competitors.competitors || [])
      setKeywordData(keywords)
    }).finally(() => setLoading(false))
  }

  useEffect(loadData, [dateRange, buFilter])

  // Generate new trend alerts
  const handleGenerateAlerts = () => {
    const qs = buildParams()
    fetch(`/api/trends/alerts/generate?${qs}`, { method: 'POST' })
      .then(r => r.json())
      .then(() => loadData())
      .catch(() => {})
  }

  // Load trend history
  const loadHistory = (trendKey) => {
    setSelectedTrend(trendKey)
    setHistoryLoading(true)
    fetch(`/api/trends/${encodeURIComponent(trendKey)}/history?weeks=12`)
      .then(r => r.json())
      .then(d => setHistory(d.history || []))
      .finally(() => setHistoryLoading(false))
  }

  // Export handlers
  const handleExportExcel = () => {
    window.open(`/api/export/trends/excel?${buildParams()}`, '_blank')
  }
  const handleExportPptx = () => {
    window.open(`/api/export/trends/pptx?${buildParams()}`, '_blank')
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading trends...</div>

  // Keyword table filtering
  const allTrends = keywordData?.trends || []
  const trendTypes = [...new Set(allTrends.map(t => t.type))]
  const filteredTrends = activeFilter === 'all'
    ? allTrends
    : allTrends.filter(t => t.type === activeFilter)

  const maxIndustrySignals = Math.max(...industryMomentum.map(i => i.signal_count), 1)

  return (
    <div>
      {/* ── Header with Filters ── */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold text-vpg-navy">Trends & Strategic Intelligence</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Dates reflect when signals were published, not when they were collected
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={buFilter}
            onChange={e => setBuFilter(e.target.value)}
            className="border rounded px-2 py-1 text-xs"
          >
            <option value="">All BUs</option>
            {buList.map(bu => (
              <option key={bu.id} value={bu.id}>{bu.short_name || bu.name}</option>
            ))}
          </select>

          <label className="text-xs text-gray-500">From:</label>
          <input
            type="date" value={dateRange.start}
            onChange={e => setDateRange({ ...dateRange, start: e.target.value })}
            className="border rounded px-2 py-1 text-xs"
          />
          <label className="text-xs text-gray-500">To:</label>
          <input
            type="date" value={dateRange.end}
            onChange={e => setDateRange({ ...dateRange, end: e.target.value })}
            className="border rounded px-2 py-1 text-xs"
          />
          {(dateRange.start || dateRange.end || buFilter) && (
            <button
              onClick={() => { setDateRange({ start: '', end: '' }); setBuFilter('') }}
              className="text-xs text-red-500 hover:text-red-700 font-medium"
            >
              Clear
            </button>
          )}

          <div className="border-l pl-2 ml-1 flex gap-1">
            <button onClick={handleExportExcel}
                    className="text-xs bg-green-600 text-white px-2 py-1 rounded hover:bg-green-700">
              Export Excel
            </button>
            <button onClick={handleExportPptx}
                    className="text-xs bg-vpg-accent text-white px-2 py-1 rounded hover:opacity-90">
              Export PPT
            </button>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════ */}
      {/* SECTION 1: WHAT'S MOVING — Trend Alert Cards                  */}
      {/* ═══════════════════════════════════════════════════════════════ */}
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-vpg-navy">What's Moving</h3>
          <button onClick={handleGenerateAlerts}
                  className="text-xs bg-vpg-blue text-white px-3 py-1.5 rounded hover:opacity-90">
            Refresh Alerts
          </button>
        </div>

        {trendAlerts.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {trendAlerts.map(alert => {
              const tt = TREND_TYPE_ICONS[alert.trend_type] || TREND_TYPE_ICONS.persistent
              const change = alert.change_percent || 0
              const arrow = change > 0 ? '↑' : change < 0 ? '↓' : '→'
              return (
                <div key={alert.id} className={`rounded-lg border p-4 ${tt.bg}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className={`text-xs font-bold ${tt.color} uppercase`}>
                      {tt.icon} {tt.label}: {alert.industry_name || alert.industry || ''}
                    </span>
                    <span className={`text-sm font-bold ${change > 0 ? 'text-green-600' : change < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                      {arrow}{Math.abs(change).toFixed(0)}%
                    </span>
                  </div>
                  <div className="text-sm font-semibold text-vpg-navy mb-1">
                    {alert.trend_name}
                  </div>
                  <div className="text-xs text-gray-600 mb-2">
                    {alert.signal_count} signals over {alert.period_weeks} week{alert.period_weeks !== 1 ? 's' : ''}
                    {alert.companies && alert.companies.length > 0 && (
                      <span> from {alert.companies.slice(0, 3).join(', ')}</span>
                    )}
                  </div>
                  {alert.top_signal_headline && (
                    <div className="text-xs text-gray-500 italic mb-2 truncate" title={alert.top_signal_headline}>
                      "{alert.top_signal_headline}"
                    </div>
                  )}
                  <div className="flex items-center justify-between mt-2">
                    {alert.bu_code && (
                      <span className="text-[10px] bg-vpg-navy text-white px-2 py-0.5 rounded">
                        {alert.bu_code}
                      </span>
                    )}
                    <button className="text-xs text-vpg-blue hover:underline font-medium">
                      View Signals →
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-400">
            <p>No trend alerts generated yet.</p>
            <p className="text-xs mt-1">Click "Refresh Alerts" to generate from current signals.</p>
          </div>
        )}
      </div>

      {/* ═══════════════════════════════════════════════════════════════ */}
      {/* SECTION 2: INDUSTRY MOMENTUM                                  */}
      {/* ═══════════════════════════════════════════════════════════════ */}
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 className="text-lg font-semibold text-vpg-navy mb-4">Industry Momentum</h3>

        {industryMomentum.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {industryMomentum.map(ind => {
              const ss = SENTIMENT_STYLES[ind.sentiment] || SENTIMENT_STYLES.neutral
              const changePct = ind.change_percent || 0
              return (
                <div key={ind.id} className={`rounded-lg border ${ss.border} ${ss.bg} p-4 cursor-pointer hover:shadow-md transition-shadow`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-semibold text-gray-900 truncate">{ind.name}</span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      changePct > 0 ? 'bg-green-200 text-green-800' :
                      changePct < 0 ? 'bg-red-200 text-red-800' :
                      'bg-gray-200 text-gray-700'
                    }`}>
                      {changePct > 0 ? '↑' : changePct < 0 ? '↓' : '→'}{Math.abs(changePct).toFixed(0)}%
                    </span>
                  </div>

                  {/* Fill bar */}
                  <div className="mb-2">
                    <div className="flex items-center justify-between text-[10px] text-gray-500 mb-0.5">
                      <span>{ind.signal_count} signals</span>
                    </div>
                    <FillBar value={ind.signal_count} max={maxIndustrySignals}
                             color={ind.sentiment === 'positive' ? 'bg-green-500' :
                                    ind.sentiment === 'negative' ? 'bg-red-500' : 'bg-gray-400'} />
                  </div>

                  {/* Sparkline */}
                  {ind.sparkline && ind.sparkline.length > 1 && (
                    <div className="mb-2">
                      <Sparkline data={ind.sparkline} width={140} height={32}
                                 color={ind.sentiment === 'positive' ? '#059669' :
                                        ind.sentiment === 'negative' ? '#DC2626' : '#64748B'} />
                    </div>
                  )}

                  {/* Stats row */}
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div>
                      <div className={`text-xs font-bold ${ss.text}`}>
                        {ind.sentiment === 'positive' ? '📈' : ind.sentiment === 'negative' ? '📉' : '➡️'} {ind.sentiment.charAt(0).toUpperCase() + ind.sentiment.slice(1)}
                      </div>
                      <div className="text-[9px] text-gray-500">Sentiment</div>
                    </div>
                    <div>
                      <div className="flex justify-center gap-1 text-[10px]">
                        {ind.opportunities > 0 && <span className="text-green-600 font-semibold">{ind.opportunities}</span>}
                        {(ind.opportunities > 0 && ind.threats > 0) && <span className="text-gray-400">/</span>}
                        {ind.threats > 0 && <span className="text-red-600 font-semibold">{ind.threats}</span>}
                        {!ind.opportunities && !ind.threats && <span className="text-gray-400">—</span>}
                      </div>
                      <div className="text-[9px] text-gray-500">Opp / Threat</div>
                    </div>
                    <div>
                      <div className={`text-xs font-bold ${
                        (ind.avg_score || 0) >= 8 ? 'text-orange-600' :
                        (ind.avg_score || 0) >= 6 ? 'text-vpg-blue' : 'text-gray-500'
                      }`}>
                        {(ind.avg_score || 0).toFixed(1)}
                        {ind.score_change ? (
                          <span className={`text-[9px] ml-0.5 ${ind.score_change > 0 ? 'text-green-600' : 'text-red-600'}`}>
                            ({ind.score_change > 0 ? '+' : ''}{ind.score_change.toFixed(1)})
                          </span>
                        ) : null}
                      </div>
                      <div className="text-[9px] text-gray-500">Avg Score</div>
                    </div>
                  </div>

                  {/* Top competitor */}
                  {ind.top_competitor && (
                    <div className="mt-2 text-[10px] text-gray-500">
                      Top competitor: <span className="font-semibold text-gray-700">{ind.top_competitor}</span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <p className="text-sm text-gray-400 text-center py-6">No industry momentum data available. Run the pipeline to populate.</p>
        )}
      </div>

      {/* ═══════════════════════════════════════════════════════════════ */}
      {/* SECTION 3: SIGNAL VOLUME OVER TIME                            */}
      {/* ═══════════════════════════════════════════════════════════════ */}
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 className="text-lg font-semibold text-vpg-navy mb-4">
          Signal Volume Over Time
          <span className="text-xs text-gray-400 font-normal ml-2">
            {buFilter ? '(by industry)' : '(by business unit)'}
          </span>
        </h3>
        <MultiLineChart
          weeks={signalVolume.weeks || []}
          series={signalVolume.series || []}
          height={320}
        />
      </div>

      {/* ═══════════════════════════════════════════════════════════════ */}
      {/* SECTION 4: COMPETITOR TREND TABLE                             */}
      {/* ═══════════════════════════════════════════════════════════════ */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden mb-6">
        <div className="px-6 py-4 border-b">
          <h3 className="text-lg font-semibold text-vpg-navy">Competitor Trends</h3>
        </div>
        {competitorTrends.length > 0 ? (
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-6 py-2.5 text-xs font-semibold text-gray-600 uppercase">Competitor</th>
                <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">This Period</th>
                <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Prior Period</th>
                <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Change</th>
                <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Trend</th>
              </tr>
            </thead>
            <tbody>
              {competitorTrends.map(c => (
                <tr key={c.name} className="border-b last:border-0 hover:bg-gray-50 cursor-pointer">
                  <td className="px-6 py-3 text-sm font-medium text-vpg-navy">{c.name}</td>
                  <td className="px-4 py-3 text-center text-sm font-semibold">{c.this_period}</td>
                  <td className="px-4 py-3 text-center text-sm text-gray-500">{c.prior_period}</td>
                  <td className="px-4 py-3 text-center text-sm">
                    <span className={c.change_percent > 0 ? 'text-green-600 font-medium' :
                                     c.change_percent < 0 ? 'text-red-600 font-medium' : 'text-gray-400'}>
                      {c.change_percent > 0 ? '+' : ''}{c.change_percent}%
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center text-lg">
                    {c.trend === 'rising' ? '📈' : c.trend === 'declining' ? '📉' : '➡️'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="px-6 py-8 text-center text-gray-400">No competitor data for the selected period.</div>
        )}
      </div>

      {/* ═══════════════════════════════════════════════════════════════ */}
      {/* SECTION 5: KEYWORD MOMENTUM TABLE                             */}
      {/* ═══════════════════════════════════════════════════════════════ */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden mb-6">
        <div className="px-6 py-4 border-b">
          <h3 className="text-lg font-semibold text-vpg-navy">Keyword Momentum</h3>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2 px-6 py-3 flex-wrap border-b">
          <button
            onClick={() => setActiveFilter('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              activeFilter === 'all' ? 'bg-vpg-navy text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            All ({allTrends.length})
          </button>
          {trendTypes.map(type => (
            <button
              key={type}
              onClick={() => setActiveFilter(type)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                activeFilter === type ? 'bg-vpg-navy text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {TYPE_LABELS[type] || type} ({allTrends.filter(t => t.type === type).length})
            </button>
          ))}
        </div>

        {/* Trend History Detail */}
        {selectedTrend && (
          <div className="px-6 py-4 bg-gray-50 border-b">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold text-vpg-navy">
                History: {allTrends.find(t => t.key === selectedTrend)?.label || selectedTrend}
              </h4>
              <button
                onClick={() => { setSelectedTrend(null); setHistory(null) }}
                className="text-sm text-gray-400 hover:text-gray-600"
              >
                Close ×
              </button>
            </div>
            {historyLoading ? (
              <div className="text-sm text-gray-400">Loading...</div>
            ) : history && history.length > 0 ? (
              <div className="flex gap-8">
                <div>
                  <p className="text-[10px] text-gray-500 uppercase font-semibold mb-1">Signal Count</p>
                  <Sparkline data={history.map(h => ({ count: h.count }))} width={200} height={50} />
                </div>
                <div className="flex-1 overflow-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left px-2 py-1 text-gray-500">Week</th>
                        <th className="text-center px-2 py-1 text-gray-500">Signals</th>
                        <th className="text-center px-2 py-1 text-gray-500">Avg Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map((h, i) => (
                        <tr key={i} className="border-b last:border-0">
                          <td className="px-2 py-1">W{h.week} '{String(h.year).slice(2)}</td>
                          <td className="px-2 py-1 text-center font-semibold">{h.count}</td>
                          <td className="px-2 py-1 text-center">{(h.avg_score || 0).toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-400">No history data available.</div>
            )}
          </div>
        )}

        {/* Table */}
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Trend</th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Category</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Momentum</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Signals</th>
              <WoWHeader />
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Avg Score</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Action</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">History</th>
            </tr>
          </thead>
          <tbody>
            {filteredTrends.map(t => {
              const badge = MOMENTUM_BADGES[t.momentum] || MOMENTUM_BADGES.stable
              // Smart action suggestion
              let action = 'Monitor'
              if (t.momentum === 'spike' || t.momentum === 'rising') {
                action = t.type === 'competitor' ? 'Defensive brief' : 'Create content'
              } else if (t.momentum === 'new') {
                action = 'Investigate'
              } else if (t.momentum === 'declining') {
                action = 'Monitor'
              }
              return (
                <tr key={t.key} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-vpg-navy">{t.label}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                      {TYPE_LABELS[t.type] || t.type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${badge.color}`}>
                      {badge.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center text-sm font-semibold">{t.count}</td>
                  <td className="px-4 py-3 text-center text-sm">
                    {t.change_pct != null ? (
                      <span className={t.change_pct > 0 ? 'text-green-600 font-medium' : t.change_pct < 0 ? 'text-red-600 font-medium' : 'text-gray-400'}>
                        {t.change_pct > 0 ? '+' : ''}{t.change_pct}%
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`text-sm font-medium ${
                      (t.avg_score || 0) >= 8 ? 'text-orange-600' :
                      (t.avg_score || 0) >= 6 ? 'text-vpg-blue' : 'text-gray-500'
                    }`}>
                      {(t.avg_score || 0).toFixed(1)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                      action === 'Create content' ? 'bg-green-100 text-green-700' :
                      action === 'Investigate' ? 'bg-blue-100 text-blue-700' :
                      action === 'Defensive brief' ? 'bg-red-100 text-red-700' :
                      action === 'Target outreach' ? 'bg-orange-100 text-orange-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {action}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => loadHistory(t.key)}
                      className="text-xs text-vpg-blue hover:underline font-medium"
                    >
                      View
                    </button>
                  </td>
                </tr>
              )
            })}
            {filteredTrends.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-12 text-center text-gray-400">
                  No trends tracked yet. Run the pipeline to start collecting data.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
