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
}

function MiniBarChart({ data, valueKey, maxHeight = 60, barWidth = 18 }) {
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
              className="bg-vpg-blue rounded-t"
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

export default function Trends() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedTrend, setSelectedTrend] = useState(null)
  const [history, setHistory] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [activeFilter, setActiveFilter] = useState('all')

  useEffect(() => {
    fetch('/api/trends?limit=50')
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false))
  }, [])

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

  // Suggested trends to follow
  const suggestedTrends = [
    ...risingTrends.slice(0, 3).map(t => ({
      ...t,
      suggestion: 'Rising activity — monitor for emerging opportunity or threat',
    })),
    ...allTrends
      .filter(t => t.type === 'competitor' && t.count >= 2)
      .slice(0, 2)
      .map(t => ({
        ...t,
        suggestion: 'Competitor showing increased visibility — track competitive moves',
      })),
    ...allTrends
      .filter(t => t.avg_score >= 7.5)
      .slice(0, 2)
      .map(t => ({
        ...t,
        suggestion: 'High-impact signals — strategic attention recommended',
      })),
  ]

  // Deduplicate suggestions by key
  const seen = new Set()
  const uniqueSuggestions = suggestedTrends.filter(t => {
    if (seen.has(t.key)) return false
    seen.add(t.key)
    return true
  })

  return (
    <div>
      <h2 className="text-2xl font-bold text-vpg-navy mb-6">Trends & Insights</h2>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-red-500">
          <div className="text-2xl font-bold text-red-600">{risingTrends.length}</div>
          <div className="text-xs text-gray-500 uppercase tracking-wide">Rising / Spike</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-blue-500">
          <div className="text-2xl font-bold text-blue-600">{newTrends.length}</div>
          <div className="text-xs text-gray-500 uppercase tracking-wide">New Trends</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-gray-400">
          <div className="text-2xl font-bold text-gray-600">{decliningTrends.length}</div>
          <div className="text-xs text-gray-500 uppercase tracking-wide">Declining</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-vpg-blue">
          <div className="text-2xl font-bold text-vpg-blue">{allTrends.length}</div>
          <div className="text-xs text-gray-500 uppercase tracking-wide">Total Tracked</div>
        </div>
      </div>

      {/* Suggested Trends */}
      {uniqueSuggestions.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h3 className="text-lg font-semibold text-vpg-navy mb-4">Suggested Trends to Watch</h3>
          <div className="space-y-3">
            {uniqueSuggestions.map(t => {
              const badge = MOMENTUM_BADGES[t.momentum] || MOMENTUM_BADGES.stable
              return (
                <div
                  key={t.key}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-blue-50 cursor-pointer transition-colors"
                  onClick={() => loadHistory(t.key)}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${badge.color}`}>
                        {badge.label}
                      </span>
                      <span className="font-medium text-sm text-vpg-navy">{t.label}</span>
                      <span className="text-xs text-gray-400">{TYPE_LABELS[t.type] || t.type}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{t.suggestion}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold text-vpg-navy">{t.count} signals</div>
                    <div className="text-xs text-gray-500">avg {(t.avg_score || 0).toFixed(1)}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-4">
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

      {/* Trends Table */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden mb-6">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Trend</th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Category</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Momentum</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">Signals</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-600 uppercase">WoW %</th>
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
                      <span className={t.change_pct > 0 ? 'text-green-600' : t.change_pct < 0 ? 'text-red-600' : 'text-gray-400'}>
                        {t.change_pct > 0 ? '+' : ''}{t.change_pct}%
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3 text-center text-sm">{(t.avg_score || 0).toFixed(1)}</td>
                  <td className="px-4 py-3 text-center text-xs text-gray-500">{t.first_seen || '—'}</td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => loadHistory(t.key)}
                      className="text-xs text-vpg-blue hover:underline"
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

      {/* Trend History Detail */}
      {selectedTrend && (
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-vpg-navy">
              Trend History: {allTrends.find(t => t.key === selectedTrend)?.label || selectedTrend}
            </h3>
            <button
              onClick={() => { setSelectedTrend(null); setHistory(null) }}
              className="text-sm text-gray-400 hover:text-gray-600"
            >
              Close
            </button>
          </div>

          {historyLoading ? (
            <div className="text-sm text-gray-400">Loading history...</div>
          ) : history && history.length > 0 ? (
            <div>
              <div className="grid grid-cols-2 gap-8">
                <div>
                  <p className="text-xs text-gray-500 uppercase font-semibold mb-2">Signal Count (Week over Week)</p>
                  <MiniBarChart data={history} valueKey="count" maxHeight={80} barWidth={28} />
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase font-semibold mb-2">Average Score (Week over Week)</p>
                  <ScoreChart data={history} maxHeight={80} barWidth={28} />
                </div>
              </div>

              <table className="w-full mt-6">
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
    </div>
  )
}
