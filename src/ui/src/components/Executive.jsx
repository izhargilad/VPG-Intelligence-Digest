import React, { useEffect, useState } from 'react'

const SIGNAL_TYPE_LABELS = {
  'competitive-threat': { label: 'Competitive Threat', icon: '⚠', color: '#E53935' },
  'revenue-opportunity': { label: 'Revenue Opportunity', icon: '💰', color: '#43A047' },
  'market-shift': { label: 'Market Shift', icon: '🎯', color: '#1E88E5' },
  'partnership-signal': { label: 'Partnership', icon: '🤝', color: '#7B1FA2' },
  'customer-intelligence': { label: 'Customer Intel', icon: '📊', color: '#F57C00' },
  'technology-trend': { label: 'Tech Trend', icon: '🚀', color: '#0097A7' },
  'trade-tariff': { label: 'Trade/Tariff', icon: '🌍', color: '#455A64' },
}

const TREND_ARROWS = { up: '↑', down: '↓', stable: '→' }
const PRIORITY_LABELS = { 1: 'CRITICAL', 2: 'HIGH', 3: 'MEDIUM' }
const PRIORITY_COLORS = { 1: 'bg-red-600', 2: 'bg-orange-500', 3: 'bg-blue-500' }

/** Map signal count to a blue intensity for the heatmap cards */
function heatmapBg(count, maxCount) {
  if (maxCount === 0) return '#EBF4FF'
  const ratio = Math.min(count / maxCount, 1)
  // Interpolate from #EBF4FF (light) to #2E75B6 (dark)
  const r = Math.round(235 + (46 - 235) * ratio)
  const g = Math.round(244 + (117 - 244) * ratio)
  const b = Math.round(255 + (182 - 255) * ratio)
  return `rgb(${r},${g},${b})`
}

function textColorForBg(count, maxCount) {
  if (maxCount === 0) return 'text-vpg-navy'
  const ratio = count / maxCount
  return ratio > 0.55 ? 'text-white' : 'text-vpg-navy'
}

export default function Executive({ onNavigate }) {
  const [data, setData] = useState(null)
  const [busUnits, setBusUnits] = useState([])
  const [industries, setIndustries] = useState([])
  const [loading, setLoading] = useState(true)
  const [exportError, setExportError] = useState(null)
  const [filters, setFilters] = useState({ bu_id: '', industry_id: '', start_date: '', end_date: '' })

  const loadData = () => {
    setLoading(true)
    const fp = new URLSearchParams()
    if (filters.bu_id) fp.set('bu_id', filters.bu_id)
    if (filters.industry_id) fp.set('industry_id', filters.industry_id)
    if (filters.start_date) fp.set('start_date', filters.start_date)
    if (filters.end_date) fp.set('end_date', filters.end_date)
    const qs = fp.toString() ? `?${fp}` : ''

    fetch(`/api/executive/dashboard${qs}`)
      .then(r => r.json())
      .then(d => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    Promise.all([
      fetch('/api/business-units').then(r => r.json()),
      fetch('/api/industries').then(r => r.json()),
    ]).then(([buData, indData]) => {
      setBusUnits(buData.business_units || [])
      setIndustries(indData.industries || [])
    })
  }, [])

  useEffect(loadData, [filters])

  const handleExport = async (format) => {
    setExportError(null)
    try {
      const params = new URLSearchParams()
      if (filters.bu_id) params.set('bu_id', filters.bu_id)
      if (filters.industry_id) params.set('industry_id', filters.industry_id)
      if (filters.start_date) params.set('start_date', filters.start_date)
      if (filters.end_date) params.set('end_date', filters.end_date)
      const resp = await fetch(`/api/export/${format}?${params}`)
      if (!resp.ok) {
        const err = await resp.json()
        setExportError(err.detail || `Export failed (${resp.status})`)
        return
      }
      const blob = await resp.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = resp.headers.get('content-disposition')?.split('filename=')[1] || `export.${format}`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (e) {
      setExportError(`Export failed: ${e.message}`)
    }
  }

  const selectBU = (buId) => {
    setFilters({ ...filters, bu_id: buId })
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading executive dashboard...</div>

  if (!data) return (
    <div className="bg-white rounded-lg shadow-sm p-8 text-center text-gray-500">
      No data available. Run the pipeline first to generate intelligence.
    </div>
  )

  const isSingleBU = data.mode === 'single-bu'

  return (
    <div>
      {/* Header + Export */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-2xl font-bold text-vpg-navy">Executive Dashboard</h2>
          <p className="text-sm text-gray-500 mt-1">
            {isSingleBU
              ? `${data.bu_header?.bu_name} — strategic briefing`
              : 'Cross-BU activity overview'}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => handleExport('excel')}
            className="bg-green-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-green-700">
            Export Excel
          </button>
          <button onClick={() => handleExport('pptx')}
            className="bg-vpg-accent text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-orange-600">
            Export PPT
          </button>
        </div>
      </div>

      {exportError && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 mb-4 text-sm flex justify-between items-start">
          <div><strong>Export Error:</strong> {exportError}</div>
          <button onClick={() => setExportError(null)} className="text-red-400 hover:text-red-600 ml-4">&times;</button>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm p-4 mb-5">
        <div className="grid grid-cols-4 gap-3">
          <div>
            <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Business Unit</label>
            <select value={filters.bu_id} onChange={e => setFilters({ ...filters, bu_id: e.target.value })}
              className="w-full border rounded px-2 py-1.5 text-xs">
              <option value="">All BUs</option>
              {busUnits.map(bu => <option key={bu.id} value={bu.id}>{bu.short_name || bu.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Industry</label>
            <select value={filters.industry_id} onChange={e => setFilters({ ...filters, industry_id: e.target.value })}
              className="w-full border rounded px-2 py-1.5 text-xs">
              <option value="">All Industries</option>
              {industries.map(ind => <option key={ind.id} value={ind.id}>{ind.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">From</label>
            <input type="date" value={filters.start_date}
              onChange={e => setFilters({ ...filters, start_date: e.target.value })}
              className="w-full border rounded px-2 py-1.5 text-xs" />
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">To</label>
            <input type="date" value={filters.end_date}
              onChange={e => setFilters({ ...filters, end_date: e.target.value })}
              className="w-full border rounded px-2 py-1.5 text-xs" />
          </div>
        </div>
      </div>

      {isSingleBU ? <SingleBUView data={data} filters={filters} selectBU={selectBU} /> : <AllBUView data={data} selectBU={selectBU} />}
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════
   ALL-BU OVERVIEW
   ═══════════════════════════════════════════════════════════════════════ */

function AllBUView({ data, selectBU }) {
  const heatmap = data.bu_heatmap || []
  const topActions = data.top_actions || []
  const alerts = data.alerts || []
  const competitors = data.competitor_pulse || []
  const maxSignals = Math.max(...heatmap.map(h => h.signal_count), 1)

  return (
    <>
      {/* ── BU Activity Heatmap (3×3 grid) ──────────────── */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-vpg-navy mb-3">BU Activity Heatmap</h3>
        <div className="grid grid-cols-3 gap-3">
          {heatmap.map(bu => {
            const bg = heatmapBg(bu.signal_count, maxSignals)
            const textCls = textColorForBg(bu.signal_count, maxSignals)
            const stInfo = SIGNAL_TYPE_LABELS[bu.top_signal_type] || {}
            return (
              <button
                key={bu.bu_id}
                onClick={() => selectBU(bu.bu_id)}
                className={`rounded-lg p-4 text-left transition-all hover:scale-[1.02] hover:shadow-md ${
                  bu.has_critical ? 'ring-2 ring-red-600' : ''
                }`}
                style={{ backgroundColor: bg }}
              >
                <div className={`text-sm font-bold ${textCls} leading-tight`}>{bu.bu_short}</div>
                <div className="flex items-center gap-2 mt-2">
                  <span className={`text-2xl font-bold ${textCls}`}>{bu.signal_count}</span>
                  <span className={`text-xs font-semibold ${
                    bu.trend === 'up' ? 'text-green-700' : bu.trend === 'down' ? 'text-red-700' : (textCls === 'text-white' ? 'text-blue-200' : 'text-gray-500')
                  }`}>
                    {TREND_ARROWS[bu.trend]} {bu.trend_pct !== 0 ? `${bu.trend_pct > 0 ? '+' : ''}${bu.trend_pct}%` : ''}
                  </span>
                </div>
                <div className="mt-2 flex items-center gap-1.5">
                  {stInfo.icon && (
                    <span className="text-xs px-1.5 py-0.5 rounded-full text-white"
                      style={{ backgroundColor: stInfo.color }}>
                      {stInfo.icon} {stInfo.label}
                    </span>
                  )}
                </div>
                {bu.has_critical && (
                  <div className="mt-2 text-[10px] font-bold text-red-700 uppercase tracking-wide">
                    Critical action needed
                  </div>
                )}
              </button>
            )
          })}
        </div>
        {heatmap.length === 0 && (
          <div className="text-center py-8 text-gray-400 text-sm bg-white rounded-lg">
            No signal data. Run the pipeline to collect intelligence.
          </div>
        )}
      </div>

      {/* ── Top 5 Actions + Alerts (side by side) ───────── */}
      <div className="grid grid-cols-5 gap-5 mb-6">
        {/* Top 5 Actions */}
        <div className="col-span-3 bg-white rounded-lg shadow-sm p-5">
          <h3 className="text-lg font-semibold text-vpg-navy mb-3">Top 5 Actions Needed</h3>
          {topActions.length > 0 ? (
            <div className="space-y-2.5">
              {topActions.map((a, i) => {
                const st = SIGNAL_TYPE_LABELS[a.signal_type] || {}
                return (
                  <div key={a.id} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                    <div className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold"
                      style={{ backgroundColor: st.color || '#64748B' }}>
                      {st.icon || (i + 1)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-vpg-navy leading-snug truncate">{a.headline}</div>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        {a.bus.map(b => (
                          <span key={b} className="text-[9px] px-1.5 py-0.5 rounded bg-vpg-navy text-white font-medium">
                            {b.replace('vpg-', '').replace(/-/g, ' ')}
                          </span>
                        ))}
                        {a.industries.slice(0, 2).map(ind => (
                          <span key={ind} className="text-[9px] px-1.5 py-0.5 rounded bg-gray-200 text-gray-600">
                            {ind.replace(/-/g, ' ')}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className={`flex-shrink-0 text-sm font-bold px-2 py-0.5 rounded ${
                      a.score >= 8 ? 'bg-green-100 text-green-700' :
                      a.score >= 7 ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {a.score}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="text-center py-6 text-gray-400 text-sm">
              No signals with score &ge; 7.0 found in the selected period.
            </div>
          )}
        </div>

        {/* Alerts */}
        <div className="col-span-2 bg-white rounded-lg shadow-sm p-5">
          <h3 className="text-lg font-semibold text-vpg-navy mb-3">Alerts</h3>
          {alerts.length > 0 ? (
            <div className="space-y-2.5">
              {alerts.map((al, i) => (
                <div key={i} className="p-3 bg-gray-50 rounded-lg border-l-3"
                  style={{ borderLeftColor: al.priority === 1 ? '#DC2626' : '#F59E0B', borderLeftWidth: '3px' }}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[9px] px-1.5 py-0.5 rounded text-white font-bold ${PRIORITY_COLORS[al.priority] || 'bg-gray-500'}`}>
                      {PRIORITY_LABELS[al.priority] || 'INFO'}
                    </span>
                    <span className="text-[9px] text-gray-400 uppercase">{al.type.replace(/-/g, ' ')}</span>
                  </div>
                  <div className="text-xs font-medium text-vpg-navy leading-snug">{al.title}</div>
                  {al.action && (
                    <div className="text-[10px] text-gray-500 mt-1 line-clamp-2">{al.action}</div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6 text-gray-400 text-sm">
              No critical or high-priority alerts.
            </div>
          )}
        </div>
      </div>

      {/* ── Competitor Pulse (enhanced) ──────────────────── */}
      <CompetitorPulse competitors={competitors} />
    </>
  )
}


/* ═══════════════════════════════════════════════════════════════════════
   SINGLE-BU DEEP VIEW
   ═══════════════════════════════════════════════════════════════════════ */

function SingleBUView({ data, filters, selectBU }) {
  const header = data.bu_header || {}
  const industries = data.industry_breakdown || []
  const topActions = data.top_actions || []
  const competitors = data.competitor_pulse || []
  const recs = data.bu_recommendations || []
  const alerts = data.alerts || []

  return (
    <>
      {/* ── BU Header ───────────────────────────────────── */}
      <div className="rounded-lg p-5 mb-5 text-white" style={{ backgroundColor: header.color || '#1B2A4A' }}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xl font-bold">{header.bu_name}</h3>
            <div className="flex items-center gap-4 mt-2 text-sm opacity-90">
              <span className="font-semibold text-lg">{header.signal_count} signals</span>
              <span className={`font-bold ${
                header.trend_pct > 0 ? 'text-green-300' : header.trend_pct < 0 ? 'text-red-300' : 'text-blue-200'
              }`}>
                {header.trend_pct > 0 ? '↑' : header.trend_pct < 0 ? '↓' : '→'}
                {header.trend_pct !== 0 ? ` ${Math.abs(header.trend_pct)}% vs prior period` : ' stable'}
              </span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs opacity-70 uppercase">Avg Score</div>
            <div className="text-2xl font-bold">{header.avg_score}</div>
          </div>
        </div>
        {header.top_industries && header.top_industries.length > 0 && (
          <div className="mt-3 flex items-center gap-2 text-sm">
            <span className="opacity-70">Top industries:</span>
            {header.top_industries.map(ind => (
              <span key={ind.name} className="bg-white/20 rounded px-2 py-0.5 text-xs font-medium">
                {ind.name} ({ind.count})
              </span>
            ))}
          </div>
        )}
        <button onClick={() => selectBU('')}
          className="mt-3 text-xs underline opacity-70 hover:opacity-100">
          ← Back to All BUs
        </button>
      </div>

      {/* ── Industry Breakdown ──────────────────────────── */}
      {industries.length > 0 && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-vpg-navy mb-3">Industry Breakdown</h3>
          <div className="grid grid-cols-3 gap-3">
            {industries.map(ind => (
              <div key={ind.industry_id}
                className="bg-white rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow cursor-pointer border border-gray-100">
                <div className="text-sm font-bold text-vpg-navy">{ind.industry_name}</div>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-lg font-bold text-vpg-blue">{ind.signal_count}</span>
                  <span className="text-xs text-gray-400">signals</span>
                  <span className={`text-xs font-semibold ml-auto ${
                    ind.trending === 'up' ? 'text-green-600' :
                    ind.trending === 'down' ? 'text-red-600' : 'text-gray-400'
                  }`}>
                    {TREND_ARROWS[ind.trending]}
                    {ind.trend_pct !== 0 ? ` ${ind.trend_pct > 0 ? '+' : ''}${ind.trend_pct}%` : ''}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-2 text-[10px]">
                  <span className={`${
                    ind.trending === 'up' ? 'text-green-600' :
                    ind.trending === 'down' ? 'text-red-600' : 'text-gray-400'
                  }`}>
                    {ind.trending === 'up' ? '🔥 Trending up' :
                     ind.trending === 'down' ? '📉 Declining' : '→ Stable'}
                  </span>
                </div>
                {ind.top_signal && (
                  <div className="mt-2 text-[10px] text-gray-500 truncate" title={ind.top_signal}>
                    Top: "{ind.top_signal}"
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── What Needs Attention + Competitor Moves (side by side) */}
      <div className="grid grid-cols-2 gap-5 mb-6">
        {/* What Needs Attention */}
        <div className="bg-white rounded-lg shadow-sm p-5">
          <h3 className="text-lg font-semibold text-vpg-navy mb-3">What Needs Attention</h3>
          {topActions.length > 0 ? (
            <div className="space-y-3">
              {topActions.map(a => {
                const st = SIGNAL_TYPE_LABELS[a.signal_type] || {}
                return (
                  <div key={a.id} className="p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-start gap-2">
                      <span className="text-xs px-1.5 py-0.5 rounded text-white flex-shrink-0"
                        style={{ backgroundColor: st.color || '#64748B' }}>
                        {st.icon}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-vpg-navy leading-snug">{a.headline}</div>
                        {a.what_summary && (
                          <div className="text-[10px] text-gray-500 mt-1 line-clamp-2">{a.what_summary}</div>
                        )}
                        {a.quick_win && (
                          <div className="text-[10px] text-vpg-blue mt-1 font-medium">Quick win: {a.quick_win}</div>
                        )}
                      </div>
                      <span className={`flex-shrink-0 text-sm font-bold ${
                        a.score >= 8 ? 'text-green-600' : 'text-vpg-blue'
                      }`}>{a.score}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="text-center py-6 text-gray-400 text-sm">
              No high-priority signals for this BU.
            </div>
          )}
        </div>

        {/* Competitor Moves */}
        <div className="bg-white rounded-lg shadow-sm p-5">
          <h3 className="text-lg font-semibold text-vpg-navy mb-3">This Period's Competitor Moves</h3>
          {competitors.length > 0 ? (
            <div className="space-y-2">
              {competitors.map(c => (
                <div key={c.competitor} className="flex items-center gap-3 p-2.5 bg-gray-50 rounded-lg">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-vpg-navy flex items-center gap-2">
                      {c.competitor}
                      {c.is_new && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-green-100 text-green-700 font-bold">NEW</span>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-gray-500">{c.signal_count} signals</div>
                  <div className={`text-sm font-bold ${
                    c.trend === 'up' ? 'text-red-600' : c.trend === 'down' ? 'text-green-600' : 'text-gray-400'
                  }`}>
                    {TREND_ARROWS[c.trend]}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6 text-gray-400 text-sm">No competitor activity detected.</div>
          )}
        </div>
      </div>

      {/* ── AI Recommendations (filtered to BU) ─────────── */}
      {recs.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm p-5 mb-6">
          <h3 className="text-lg font-semibold text-vpg-navy mb-3">AI Recommendations</h3>
          <div className="space-y-3">
            {recs.map((r, i) => (
              <div key={i} className="p-4 bg-gray-50 rounded-lg border-l-3"
                style={{ borderLeftColor: r.priority === 1 ? '#DC2626' : r.priority === 2 ? '#F59E0B' : '#2E75B6', borderLeftWidth: '3px' }}>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className={`text-[9px] px-1.5 py-0.5 rounded text-white font-bold ${PRIORITY_COLORS[r.priority] || 'bg-blue-500'}`}>
                    {PRIORITY_LABELS[r.priority] || 'INFO'}
                  </span>
                  <span className="text-[9px] text-gray-400 uppercase">{r.type.replace(/-/g, ' ')}</span>
                </div>
                <div className="text-sm font-medium text-vpg-navy">{r.title}</div>
                <div className="text-xs text-gray-500 mt-1">{r.description}</div>
                {r.action && (
                  <div className="text-xs text-vpg-blue font-medium mt-2">Action: {r.action}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Alerts ──────────────────────────────────────── */}
      {alerts.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm p-5">
          <h3 className="text-lg font-semibold text-vpg-navy mb-3">Alerts</h3>
          <div className="space-y-2.5">
            {alerts.map((al, i) => (
              <div key={i} className="p-3 bg-gray-50 rounded-lg border-l-3"
                style={{ borderLeftColor: al.priority === 1 ? '#DC2626' : '#F59E0B', borderLeftWidth: '3px' }}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-[9px] px-1.5 py-0.5 rounded text-white font-bold ${PRIORITY_COLORS[al.priority] || 'bg-gray-500'}`}>
                    {PRIORITY_LABELS[al.priority] || 'INFO'}
                  </span>
                </div>
                <div className="text-xs font-medium text-vpg-navy">{al.title}</div>
                {al.action && <div className="text-[10px] text-gray-500 mt-1">{al.action}</div>}
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}


/* ═══════════════════════════════════════════════════════════════════════
   COMPETITOR PULSE (shared)
   ═══════════════════════════════════════════════════════════════════════ */

function CompetitorPulse({ competitors }) {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? competitors : competitors.slice(0, 5)
  const maxCount = Math.max(...competitors.map(c => c.signal_count), 1)

  return (
    <div className="bg-white rounded-lg shadow-sm p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-vpg-navy">Competitor Pulse</h3>
        {competitors.length > 5 && (
          <button onClick={() => setExpanded(!expanded)}
            className="text-xs text-vpg-blue hover:underline">
            {expanded ? 'Show top 5' : `Show all ${competitors.length}`}
          </button>
        )}
      </div>
      {competitors.length > 0 ? (
        <div className="space-y-2">
          {visible.map(comp => (
            <div key={comp.competitor} className="flex items-center gap-3 p-2.5 bg-gray-50 rounded-lg">
              <div className="w-32 flex-shrink-0">
                <div className="text-sm font-medium text-vpg-navy flex items-center gap-1.5">
                  {comp.competitor}
                  {comp.is_new && (
                    <span className="text-[8px] px-1 py-0.5 rounded bg-green-100 text-green-700 font-bold">NEW</span>
                  )}
                </div>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-gray-200 rounded-full h-3.5 overflow-hidden">
                    <div className="h-full rounded-full bg-vpg-blue transition-all"
                      style={{ width: `${Math.min((comp.signal_count / maxCount) * 100, 100)}%` }} />
                  </div>
                  <span className="text-sm font-semibold text-vpg-navy w-8 text-right">{comp.signal_count}</span>
                </div>
              </div>
              <div className="flex items-center gap-2 w-20 justify-end flex-shrink-0">
                <span className="text-xs text-gray-400">Avg {comp.avg_score}</span>
                <span className={`text-sm font-bold ${
                  comp.trend === 'up' ? 'text-red-600' : comp.trend === 'down' ? 'text-green-600' : 'text-gray-400'
                }`}>
                  {TREND_ARROWS[comp.trend]}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-4 text-gray-400 text-sm">
          No competitor signals detected.
        </div>
      )}
    </div>
  )
}
