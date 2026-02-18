import React, { useEffect, useState } from 'react'

const TIER_LABELS = { 1: 'Tier 1 — Authority', 2: 'Tier 2 — Industry', 3: 'Tier 3 — Signal' }
const TIER_COLORS = { 1: 'bg-green-100 text-green-800', 2: 'bg-blue-100 text-blue-800', 3: 'bg-gray-100 text-gray-600' }

export default function Sources() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    fetch('/api/sources')
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const toggleActive = async (id, currentActive) => {
    await fetch(`/api/sources/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active: !currentActive }),
    })
    load()
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>

  const sources = data?.sources || []
  const grouped = { 1: [], 2: [], 3: [] }
  sources.forEach(s => {
    const tier = s.tier || 2
    if (!grouped[tier]) grouped[tier] = []
    grouped[tier].push(s)
  })

  return (
    <div>
      <h2 className="text-2xl font-bold text-vpg-navy mb-6">Data Sources</h2>

      {[1, 2, 3].map(tier => (
        grouped[tier]?.length > 0 && (
          <div key={tier} className="mb-8">
            <h3 className="text-lg font-semibold text-vpg-navy mb-3">
              <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold mr-2 ${TIER_COLORS[tier]}`}>
                {TIER_LABELS[tier]}
              </span>
              ({grouped[tier].length} sources)
            </h3>
            <div className="bg-white rounded-lg shadow-sm overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Name</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Type</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600 uppercase">URL</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Status</th>
                    <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Toggle</th>
                  </tr>
                </thead>
                <tbody>
                  {grouped[tier].map(s => (
                    <tr key={s.id} className="border-b last:border-0 hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{s.name}</td>
                      <td className="px-4 py-3">
                        <span className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
                          {s.type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 truncate max-w-xs">{s.url}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block w-2 h-2 rounded-full mr-1 ${s.active !== false ? 'bg-green-500' : 'bg-gray-300'}`}></span>
                        <span className="text-xs">{s.active !== false ? 'Active' : 'Disabled'}</span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => toggleActive(s.id, s.active !== false)}
                          className="text-xs text-vpg-blue hover:underline"
                        >
                          {s.active !== false ? 'Disable' : 'Enable'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )
      ))}
    </div>
  )
}
