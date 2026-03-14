import React, { useState, useEffect } from 'react'

export default function SourceHealth() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/sources/health')
      .then(r => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Checking source health...</div>

  const statusColors = {
    healthy: 'bg-green-100 text-green-800',
    unhealthy: 'bg-red-100 text-red-800',
    stale: 'bg-yellow-100 text-yellow-800',
    inactive: 'bg-gray-100 text-gray-600',
  }

  const statusIcons = {
    healthy: '●',
    unhealthy: '●',
    stale: '●',
    inactive: '○',
  }

  const summary = data?.summary || {}

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Source Health Dashboard</h2>
        <p className="text-sm text-gray-500 mt-1">Monitor reliability and activity of all data sources</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow-sm p-4 text-center">
          <div className="text-2xl font-bold text-green-600">{summary.healthy || 0}</div>
          <div className="text-xs text-gray-500">Healthy</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 text-center">
          <div className="text-2xl font-bold text-red-600">{summary.unhealthy || 0}</div>
          <div className="text-xs text-gray-500">Unhealthy</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 text-center">
          <div className="text-2xl font-bold text-yellow-600">{summary.stale || 0}</div>
          <div className="text-xs text-gray-500">Stale</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 text-center">
          <div className="text-2xl font-bold text-gray-400">{summary.inactive || 0}</div>
          <div className="text-xs text-gray-500">Inactive</div>
        </div>
      </div>

      {/* Sources table */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase">
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Tier</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Signals</th>
              <th className="px-4 py-3">Avg Score</th>
              <th className="px-4 py-3">Reliability</th>
              <th className="px-4 py-3">Last Signal</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data?.sources?.map((s, i) => (
              <tr key={i} className={!s.active ? 'opacity-50' : ''}>
                <td className="px-4 py-3 font-medium text-gray-900">{s.source_name}</td>
                <td className="px-4 py-3 text-gray-500">{s.type}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    s.tier === 1 ? 'bg-blue-100 text-blue-800' :
                    s.tier === 2 ? 'bg-gray-100 text-gray-700' : 'bg-gray-50 text-gray-500'
                  }`}>T{s.tier}</span>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[s.status]}`}>
                    <span style={{ color: s.status === 'healthy' ? '#16a34a' : s.status === 'unhealthy' ? '#dc2626' : s.status === 'stale' ? '#ca8a04' : '#9ca3af' }}>
                      {statusIcons[s.status]}
                    </span>
                    {s.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {s.scored_signals}/{s.total_signals}
                  {s.error_count > 0 && <span className="text-red-500 ml-1">({s.error_count} err)</span>}
                </td>
                <td className="px-4 py-3">{s.avg_score || '-'}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-16 bg-gray-200 rounded-full h-1.5">
                      <div className={`h-1.5 rounded-full ${
                        s.reliability >= 90 ? 'bg-green-500' :
                        s.reliability >= 70 ? 'bg-yellow-500' : 'bg-red-500'
                      }`} style={{ width: `${s.reliability}%` }} />
                    </div>
                    <span className="text-xs text-gray-500">{s.reliability}%</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-gray-400">
                  {s.last_signal_at ? new Date(s.last_signal_at).toLocaleDateString() : 'Never'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
