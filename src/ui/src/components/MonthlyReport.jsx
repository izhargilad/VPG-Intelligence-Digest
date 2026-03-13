import React, { useState, useEffect } from 'react'

const API = '/api'

export default function MonthlyReport() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [year, setYear] = useState(null)
  const [month, setMonth] = useState(null)

  const load = (y, m) => {
    setLoading(true)
    const params = y && m ? `?year=${y}&month=${m}` : ''
    fetch(`${API}/reports/monthly${params}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(() => load(), [])

  if (loading) return <div className="p-6 text-gray-500">Generating monthly report...</div>
  if (!data) return <div className="p-6 text-gray-500">Could not generate report.</div>

  const { period, signal_stats, feedback_stats, pipeline_stats, source_rankings, bu_coverage, action_stats, trend_highlights } = data

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-vpg-navy">Monthly Effectiveness Report</h2>
          <p className="text-sm text-gray-500">{period?.month_name} {period?.year}</p>
        </div>
        <div className="flex gap-2 items-center">
          <select className="border rounded px-2 py-1 text-sm" value={month || ''} onChange={e => setMonth(parseInt(e.target.value))}>
            <option value="">Month</option>
            {[...Array(12)].map((_, i) => <option key={i} value={i + 1}>{new Date(2000, i).toLocaleString('default', { month: 'long' })}</option>)}
          </select>
          <select className="border rounded px-2 py-1 text-sm" value={year || ''} onChange={e => setYear(parseInt(e.target.value))}>
            <option value="">Year</option>
            <option value="2026">2026</option>
            <option value="2025">2025</option>
          </select>
          <button onClick={() => load(year, month)} className="bg-vpg-blue text-white px-3 py-1 rounded text-sm">Generate</button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-5 gap-4">
        <div className="bg-white rounded-lg shadow-sm p-4 text-center">
          <div className="text-2xl font-bold text-vpg-navy">{signal_stats?.total_collected || 0}</div>
          <div className="text-xs text-gray-500">Signals Collected</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 text-center">
          <div className="text-2xl font-bold text-vpg-blue">{signal_stats?.total_scored || 0}</div>
          <div className="text-xs text-gray-500">Scored</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 text-center">
          <div className="text-2xl font-bold text-green-600">{signal_stats?.avg_score || 0}</div>
          <div className="text-xs text-gray-500">Avg Score</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 text-center">
          <div className="text-2xl font-bold text-amber-600">{feedback_stats?.positive_rate || 0}%</div>
          <div className="text-xs text-gray-500">Feedback Positive</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 text-center">
          <div className="text-2xl font-bold text-vpg-accent">{action_stats?.action_rate || 0}%</div>
          <div className="text-xs text-gray-500">Action Rate</div>
        </div>
      </div>

      {/* Pipeline Impact */}
      <div className="bg-gradient-to-r from-vpg-navy to-vpg-blue text-white rounded-lg p-6">
        <h3 className="font-semibold mb-2">Estimated Pipeline Influence</h3>
        <div className="text-3xl font-bold">{pipeline_stats?.estimated_pipeline_influence || '$0'}</div>
        <div className="text-sm opacity-80 mt-1">
          {pipeline_stats?.pipeline_runs || 0} pipeline runs | {pipeline_stats?.high_impact_signals || 0} high-impact signals
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Signal Type Breakdown */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="font-semibold text-vpg-navy mb-4">Signals by Type</h3>
          <div className="space-y-2">
            {(signal_stats?.by_type || []).map((t, i) => (
              <div key={i} className="flex items-center justify-between text-sm border-b pb-2">
                <span className="capitalize">{(t.type || '').replace(/-/g, ' ')}</span>
                <div className="flex gap-3">
                  <span className="text-gray-500">{t.count} signals</span>
                  <span className="font-medium">avg {t.avg_score}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Action Stats */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="font-semibold text-vpg-navy mb-4">Action Tracking</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm">Handled / Actioned</span>
              <span className="font-bold text-green-600">{action_stats?.handled || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Dismissed</span>
              <span className="font-bold text-gray-500">{action_stats?.dismissed || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Unactioned</span>
              <span className="font-bold text-amber-600">{action_stats?.unactioned || 0}</span>
            </div>
            <div className="bg-gray-100 rounded-full h-4 mt-2 overflow-hidden">
              <div className="bg-green-500 h-full" style={{ width: `${action_stats?.action_rate || 0}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* BU Coverage */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="font-semibold text-vpg-navy mb-4">Business Unit Coverage</h3>
        <div className="grid grid-cols-3 gap-3">
          {(bu_coverage || []).map((bu, i) => (
            <div key={i} className={`border rounded-lg p-3 ${bu.status === 'no-coverage' ? 'border-red-200 bg-red-50' : 'border-gray-200'}`}>
              <div className="font-medium text-sm">{bu.bu_name}</div>
              <div className="flex justify-between mt-1 text-xs">
                <span>{bu.signal_count} signals</span>
                <span>avg {bu.avg_score}</span>
                {bu.status === 'no-coverage' && <span className="text-red-600 font-medium">No coverage</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Source Rankings */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="font-semibold text-vpg-navy mb-4">Top Sources</h3>
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left px-3 py-2 font-medium text-gray-600">Source</th>
              <th className="text-center px-3 py-2 font-medium text-gray-600">Tier</th>
              <th className="text-center px-3 py-2 font-medium text-gray-600">Signals</th>
              <th className="text-center px-3 py-2 font-medium text-gray-600">Avg Score</th>
              <th className="text-center px-3 py-2 font-medium text-gray-600">Quality Rate</th>
            </tr>
          </thead>
          <tbody>
            {(source_rankings || []).slice(0, 10).map((s, i) => (
              <tr key={i} className="border-t">
                <td className="px-3 py-2">{s.source}</td>
                <td className="px-3 py-2 text-center">{s.tier}</td>
                <td className="px-3 py-2 text-center">{s.signal_count}</td>
                <td className="px-3 py-2 text-center">{s.avg_score}</td>
                <td className="px-3 py-2 text-center">
                  <span className={`px-2 py-0.5 rounded text-xs ${s.quality_rate >= 50 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                    {s.quality_rate}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Trend Highlights */}
      {(trend_highlights || []).length > 0 && (
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="font-semibold text-vpg-navy mb-4">Trending This Month</h3>
          <div className="grid grid-cols-2 gap-3">
            {trend_highlights.map((t, i) => (
              <div key={i} className="flex items-center gap-3 border rounded p-3">
                <span className={`text-sm px-2 py-0.5 rounded font-medium ${t.momentum === 'spike' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>
                  {t.momentum}
                </span>
                <span className="text-sm font-medium">{t.topic}</span>
                <span className="text-xs text-gray-500 ml-auto">{t.wow_change > 0 ? '+' : ''}{t.wow_change}% WoW</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
