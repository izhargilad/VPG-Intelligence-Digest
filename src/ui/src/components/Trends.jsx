import React, { useEffect, useState } from 'react'

const MOMENTUM_STYLES = {
  spike: { bg: 'bg-red-100', text: 'text-red-800', label: 'SPIKE' },
  rising: { bg: 'bg-orange-100', text: 'text-orange-800', label: 'RISING' },
  new: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'NEW' },
  stable: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'STABLE' },
  declining: { bg: 'bg-green-100', text: 'text-green-700', label: 'DECLINING' },
}

const TYPE_LABELS = {
  bu_signal_type: 'BU Signal',
  signal_type: 'Signal Type',
  business_unit: 'Business Unit',
  competitor: 'Competitor',
  industry: 'Industry',
  keyword: 'Keyword',
}

export default function Trends() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    fetch('/api/trends?limit=50')
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>

  const trends = data?.trends || []
  const filtered = filter === 'all' ? trends : trends.filter(t => t.type === filter)

  const types = [...new Set(trends.map(t => t.type))]

  return (
    <div>
      <h2 className="text-2xl font-bold text-vpg-navy mb-6">Trend Tracking</h2>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow-sm p-4">
          <div className="text-xs font-semibold text-red-600 uppercase mb-1">Spikes</div>
          <div className="text-2xl font-bold">{data?.rising?.filter(t => t.momentum === 'spike').length || 0}</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4">
          <div className="text-xs font-semibold text-orange-600 uppercase mb-1">Rising</div>
          <div className="text-2xl font-bold">{data?.rising?.filter(t => t.momentum === 'rising').length || 0}</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4">
          <div className="text-xs font-semibold text-blue-600 uppercase mb-1">New Trends</div>
          <div className="text-2xl font-bold">{data?.new?.length || 0}</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4">
          <div className="text-xs font-semibold text-green-600 uppercase mb-1">Declining</div>
          <div className="text-2xl font-bold">{data?.declining?.length || 0}</div>
        </div>
      </div>

      {/* Filter */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setFilter('all')}
          className={`px-3 py-1 rounded-full text-xs font-medium ${
            filter === 'all' ? 'bg-vpg-navy text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          All ({trends.length})
        </button>
        {types.map(type => (
          <button
            key={type}
            onClick={() => setFilter(type)}
            className={`px-3 py-1 rounded-full text-xs font-medium ${
              filter === type ? 'bg-vpg-navy text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            {TYPE_LABELS[type] || type} ({trends.filter(t => t.type === type).length})
          </button>
        ))}
      </div>

      {/* Trends Table */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Trend</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Type</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Momentum</th>
              <th className="text-right px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Signals</th>
              <th className="text-right px-4 py-3 text-xs font-semibold text-gray-600 uppercase">WoW Change</th>
              <th className="text-right px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Avg Score</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(t => {
              const style = MOMENTUM_STYLES[t.momentum] || MOMENTUM_STYLES.stable
              return (
                <tr key={t.key} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{t.label}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                      {TYPE_LABELS[t.type] || t.type}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${style.bg} ${style.text}`}>
                      {style.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-medium">{t.count}</td>
                  <td className="px-4 py-3 text-sm text-right">
                    {t.change_pct > 0 && <span className="text-red-600">+{t.change_pct}%</span>}
                    {t.change_pct < 0 && <span className="text-green-600">{t.change_pct}%</span>}
                    {t.change_pct === 0 && <span className="text-gray-400">-</span>}
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-medium">{t.avg_score?.toFixed(1)}</td>
                </tr>
              )
            })}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  No trends detected yet. Run the pipeline to start tracking.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
