import React, { useState, useEffect } from 'react'

export default function CustomerTriggers() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/customer-triggers')
      .then(r => r.json())
      .then(setData)
      .catch(() => setData({ triggers: [], total_triggers: 0 }))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Loading customer triggers...</div>

  const triggerTypeColors = {
    'facility-expansion': 'bg-green-100 text-green-800',
    'product-launch': 'bg-blue-100 text-blue-800',
    'hiring-surge': 'bg-purple-100 text-purple-800',
    'capex-increase': 'bg-yellow-100 text-yellow-800',
    'acquisition': 'bg-red-100 text-red-800',
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Customer Expansion Triggers</h2>
          <p className="text-sm text-gray-500 mt-1">
            Auto-detected expansion signals from known VPG customers
          </p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-vpg-blue">{data?.total_triggers || 0}</div>
          <div className="text-xs text-gray-500">Active Triggers</div>
        </div>
      </div>

      {(!data?.triggers?.length) ? (
        <div className="bg-white rounded-lg shadow-sm p-8 text-center text-gray-500">
          No customer expansion triggers detected in recent signals.
          <br />
          <span className="text-sm">Triggers are detected from scored signals mentioning known customers.</span>
        </div>
      ) : (
        data.triggers.map((customer, idx) => (
          <div key={idx} className="bg-white rounded-lg shadow-sm overflow-hidden">
            <div className="bg-vpg-navy text-white px-6 py-4 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold">{customer.customer}</h3>
                <p className="text-sm text-blue-300">
                  {customer.triggers.length} trigger{customer.triggers.length !== 1 ? 's' : ''} detected
                </p>
              </div>
              <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                customer.upsell_brief?.priority === 'high' ? 'bg-red-500 text-white' : 'bg-yellow-500 text-white'
              }`}>
                {customer.upsell_brief?.priority?.toUpperCase()} PRIORITY
              </span>
            </div>

            <div className="p-6 space-y-4">
              {/* Triggers */}
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Detected Triggers</h4>
                <div className="space-y-2">
                  {customer.triggers.map((t, i) => (
                    <div key={i} className="flex items-start gap-3 p-3 bg-gray-50 rounded">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${triggerTypeColors[t.trigger_type] || 'bg-gray-100 text-gray-700'}`}>
                        {t.trigger_type}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">{t.headline}</p>
                        <p className="text-xs text-gray-500 mt-0.5">Score: {t.score} | {t.date}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Products & Actions */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Recommended Products</h4>
                  <ul className="text-sm text-gray-600 space-y-1">
                    {customer.recommended_products?.map((p, i) => (
                      <li key={i} className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 bg-vpg-blue rounded-full" />
                        {p}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Recommended Actions</h4>
                  <ul className="text-sm text-gray-600 space-y-1">
                    {customer.upsell_brief?.recommended_actions?.map((a, i) => (
                      <li key={i} className="text-sm">{a}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
