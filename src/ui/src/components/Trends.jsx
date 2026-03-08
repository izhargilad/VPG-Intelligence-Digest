import React, { useEffect, useState } from 'react'

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

const SENTIMENT_COLORS = {
  positive: { bg: 'bg-green-50', border: 'border-green-400', text: 'text-green-700', bar: 'bg-green-500' },
  neutral: { bg: 'bg-gray-50', border: 'border-gray-300', text: 'text-gray-600', bar: 'bg-gray-400' },
  negative: { bg: 'bg-red-50', border: 'border-red-400', text: 'text-red-700', bar: 'bg-red-500' },
}

/* ─── Mini Charts ─────────────────────────────────────────────── */

function MiniBarChart({ data, valueKey, maxHeight = 60, barWidth = 18, color = 'bg-vpg-blue' }) {
  if (!data || data.length === 0) return null
  const maxVal = Math.max(...data.map(d => d[valueKey] || 0), 1)

  return (
    <div className="flex items-end gap-1" style={{ height: maxHeight }}>
      {data.map((point, idx) => {
        const val = point[valueKey] || 0
        const h = Math.max((val / maxVal) * maxHeight, 2)
        return (
          <div key={idx} className="flex flex-col items-center" style={{ width: barWidth }}>
            <div
              className={`${color} rounded-t`}
              style={{ width: barWidth - 4, height: h }}
              title={`W${point.week}: ${val}`}
            />
            <span className="text-[9px] text-gray-400 mt-0.5">W{point.week}</span>
          </div>
        )
      })}
    </div>
  )
}

function ScoreChart({ data, maxHeight = 60, barWidth = 18 }) {
  if (!data || data.length === 0) return null
  const maxVal = Math.max(...data.map(d => d.avg_score || 0), 1)

  return (
    <div className="flex items-end gap-1" style={{ height: maxHeight }}>
      {data.map((point, idx) => {
        const val = point.avg_score || 0
        const h = Math.max((val / maxVal) * maxHeight, 2)
        const color = val >= 8 ? 'bg-orange-500' : val >= 6 ? 'bg-vpg-blue' : 'bg-gray-400'
        return (
          <div key={idx} className="flex flex-col items-center" style={{ width: barWidth }}>
            <div
              className={`${color} rounded-t`}
              style={{ width: barWidth - 4, height: h }}
              title={`W${point.week}: ${val.toFixed(1)}`}
            />
            <span className="text-[9px] text-gray-400 mt-0.5">W{point.week}</span>
          </div>
        )
      })}
    </div>
  )
}

/* ─── Horizontal Bar ──────────────────────────────────────────── */

function HorizontalBar({ value, max, color = 'bg-vpg-blue', height = 8 }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div className="w-full bg-gray-100 rounded-full overflow-hidden" style={{ height }}>
      <div className={`${color} rounded-full h-full transition-all`} style={{ width: `${pct}%` }} />
    </div>
  )
}

/* ─── Sentiment Card ─────────────────────────────────────────── */

function SentimentCard({ item, maxSignals }) {
  const sc = SENTIMENT_COLORS[item.sentiment] || SENTIMENT_COLORS.neutral
  return (
    <div className={`rounded-lg border ${sc.border} ${sc.bg} p-3`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-gray-900 truncate">{item.name}</span>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
          item.sentiment === 'positive' ? 'bg-green-200 text-green-800' :
          item.sentiment === 'negative' ? 'bg-red-200 text-red-800' :
          'bg-gray-200 text-gray-700'
        }`}>
          {item.sentiment === 'positive' ? '▲ Positive' :
           item.sentiment === 'negative' ? '▼ Negative' : '● Neutral'}
        </span>
      </div>
      <div className="mb-2">
        <HorizontalBar value={item.signal_count} max={maxSignals} color={sc.bar} />
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-xs font-bold text-gray-800">{item.signal_count}</div>
          <div className="text-[9px] text-gray-500">Signals</div>
        </div>
        <div>
          <div className={`text-xs font-bold ${
            item.avg_score >= 8 ? 'text-orange-600' :
            item.avg_score >= 6 ? 'text-vpg-blue' : 'text-gray-500'
          }`}>{item.avg_score}</div>
          <div className="text-[9px] text-gray-500">Avg Score</div>
        </div>
        <div>
          <div className="flex justify-center gap-1 text-[9px]">
            {item.opportunities > 0 && <span className="text-green-600">+{item.opportunities}</span>}
            {item.threats > 0 && <span className="text-red-600">-{item.threats}</span>}
            {!item.opportunities && !item.threats && <span className="text-gray-400">—</span>}
          </div>
          <div className="text-[9px] text-gray-500">Opp / Threat</div>
        </div>
      </div>
    </div>
  )
}

/* ─── WoW Tooltip ─────────────────────────────────────────────── */

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
          <p>Measures the percentage change in signal count between the current week and the previous week for this trend.</p>
          <p className="mt-1 text-gray-300">
            <span className="text-green-400">+50%</span> = 50% more signals this week vs. last<br/>
            <span className="text-red-400">-30%</span> = 30% fewer signals this week vs. last
          </p>
        </div>
      )}
    </th>
  )
}

/* ─── Main Component ──────────────────────────────────────────── */

export default function Trends() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sentiment, setSentiment] = useState(null)
  const [selectedTrend, setSelectedTrend] = useState(null)
  const [history, setHistory] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [activeFilter, setActiveFilter] = useState('all')
  const [sentimentView, setSentimentView] = useState('bu')
  const [dateRange, setDateRange] = useState({ start: '', end: '' })

  const loadTrends = () => {
    setLoading(true)
    const params = new URLSearchParams({ limit: '50' })
    if (dateRange.start) params.set('start_date', dateRange.start)
    if (dateRange.end) params.set('end_date', dateRange.end)
    fetch(`/api/trends?${params}`)
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false))
  }

  const loadSentiment = () => {
    fetch('/api/trends/sentiment')
      .then(r => r.json())
      .then(setSentiment)
      .catch(() => setSentiment(null))
  }

  useEffect(loadTrends, [dateRange])
  useEffect(loadSentiment, [])

  const loadHistory = (trendKey) => {
    setSelectedTrend(trendKey)
    setHistoryLoading(true)
    fetch(`/api/trends/${encodeURIComponent(trendKey)}/history?weeks=12`)
      .then(r => r.json())
      .then(d => setHistory(d.history || []))
      .finally(() => setHistoryLoading(false))
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading trends...</div>

  const allTrends = data?.trends || []
  const risingTrends = allTrends.filter(t => t.momentum === 'rising' || t.momentum === 'spike')
  const newTrends = allTrends.filter(t => t.momentum === 'new')
  const decliningTrends = allTrends.filter(t => t.momentum === 'declining')

  // Group trends by type for the filter
  const trendTypes = [...new Set(allTrends.map(t => t.type))]

  const filteredTrends = activeFilter === 'all'
    ? allTrends
    : allTrends.filter(t => t.type === activeFilter)

  const buSentiment = sentiment?.bu_sentiment || []
  const indSentiment = sentiment?.industry_sentiment || []
  const maxBuSignals = Math.max(...buSentiment.map(b => b.signal_count), 1)
  const maxIndSignals = Math.max(...indSentiment.map(i => i.signal_count), 1)

  return (
    <div>
      {/* Header with date filters */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-vpg-navy">Trends & Insights</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Dates reflect when signals were published, not when they were collected
          </p>
        </div>
        <div className="flex items-center gap-2">
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
          {(dateRange.start || dateRange.end) && (
            <button
              onClick={() => setDateRange({ start: '', end: '' })}
              className="text-xs text-red-500 hover:text-red-700 font-medium"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* ── Top Section: Summary Cards + Momentum Overview ── */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-red-500">
          <div className="text-2xl font-bold text-red-600">{risingTrends.length}</div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wide">Rising / Spike</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-blue-500">
          <div className="text-2xl font-bold text-blue-600">{newTrends.length}</div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wide">New Trends</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-gray-400">
          <div className="text-2xl font-bold text-gray-600">{decliningTrends.length}</div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wide">Declining</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-vpg-blue">
          <div className="text-2xl font-bold text-vpg-blue">{allTrends.length}</div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wide">Total Tracked</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-vpg-accent">
          <div className="text-2xl font-bold text-vpg-accent">
            {allTrends.filter(t => t.avg_score >= 7.5).length}
          </div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wide">High Impact</div>
        </div>
      </div>

      {/* ── Sentiment / Momentum Section ── */}
      {(buSentiment.length > 0 || indSentiment.length > 0) && (
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-vpg-navy">Sentiment & Momentum</h3>
            <div className="flex gap-1 bg-gray-100 rounded-lg p-0.5">
              {[
                { key: 'bu', label: 'By Business Unit' },
                { key: 'industry', label: 'By Industry' },
              ].map(tab => (
                <button
                  key={tab.key}
                  onClick={() => setSentimentView(tab.key)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    sentimentView === tab.key
                      ? 'bg-vpg-navy text-white shadow-sm'
                      : 'text-gray-600 hover:text-gray-800'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {sentimentView === 'bu' && (
            buSentiment.length > 0 ? (
              <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {buSentiment.map(bu => (
                  <SentimentCard key={bu.id} item={bu} maxSignals={maxBuSignals} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400 text-center py-4">No BU sentiment data available yet.</p>
            )
          )}

          {sentimentView === 'industry' && (
            indSentiment.length > 0 ? (
              <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {indSentiment.map(ind => (
                  <SentimentCard key={ind.id} item={ind} maxSignals={maxIndSignals} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400 text-center py-4">No industry sentiment data available yet. Run the pipeline to populate industry associations.</p>
            )
          )}
        </div>
      )}

      {/* ── Trend History Detail (shows when a trend is selected) ── */}
      {selectedTrend && (
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-vpg-navy">
              Trend History: {allTrends.find(t => t.key === selectedTrend)?.label || selectedTrend}
            </h3>
            <button
              onClick={() => { setSelectedTrend(null); setHistory(null) }}
              className="text-sm text-gray-400 hover:text-gray-600"
            >
              Close &times;
            </button>
          </div>

          {historyLoading ? (
            <div className="text-sm text-gray-400">Loading history...</div>
          ) : history && history.length > 0 ? (
            <div>
              <div className="grid grid-cols-2 gap-8 mb-6">
                <div>
                  <p className="text-xs text-gray-500 uppercase font-semibold mb-2">Signal Count (Week over Week)</p>
                  <MiniBarChart data={history} valueKey="count" maxHeight={80} barWidth={28} />
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase font-semibold mb-2">Average Score (Week over Week)</p>
                  <ScoreChart data={history} maxHeight={80} barWidth={28} />
                </div>
              </div>

              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="text-left px-3 py-2 text-xs font-semibold text-gray-600">Week</th>
                    <th className="text-center px-3 py-2 text-xs font-semibold text-gray-600">Year</th>
                    <th className="text-center px-3 py-2 text-xs font-semibold text-gray-600">Signals</th>
                    <th className="text-center px-3 py-2 text-xs font-semibold text-gray-600">Avg Score</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h, idx) => (
                    <tr key={idx} className="border-b last:border-0">
                      <td className="px-3 py-2 text-sm">Week {h.week}</td>
                      <td className="px-3 py-2 text-sm text-center">{h.year}</td>
                      <td className="px-3 py-2 text-sm text-center font-semibold">{h.count}</td>
                      <td className="px-3 py-2 text-sm text-center">{(h.avg_score || 0).toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-sm text-gray-400">No history data available for this trend.</div>
          )}
        </div>
      )}

      {/* ── Filter Tabs ── */}
      <div className="flex gap-2 mb-4 flex-wrap">
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

      {/* ── Trends Table ── */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden mb-6">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Trend</th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Category</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Momentum</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Signals</th>
              <WoWHeader />
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Avg Score</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">First Seen</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">History</th>
            </tr>
          </thead>
          <tbody>
            {filteredTrends.map(t => {
              const badge = MOMENTUM_BADGES[t.momentum] || MOMENTUM_BADGES.stable
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
                  <td className="px-4 py-3 text-center text-xs text-gray-500">{t.first_seen || '—'}</td>
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
