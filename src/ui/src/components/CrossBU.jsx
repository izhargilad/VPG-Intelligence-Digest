import React, { useState, useEffect } from 'react'

export default function CrossBU() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/cross-bu')
      .then(r => r.json())
      .then(setData)
      .catch(() => setData({ opportunities: [], total: 0 }))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Analyzing cross-BU opportunities...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Cross-BU Opportunities</h2>
          <p className="text-sm text-gray-500 mt-1">Signals spanning multiple business units with combined solution value</p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-vpg-blue">{data?.total || 0}</div>
          <div className="text-xs text-gray-500">Cross-BU Signals</div>
        </div>
      </div>

      {!data?.opportunities?.length ? (
        <div className="bg-white rounded-lg shadow-sm p-8 text-center text-gray-500">
          No cross-BU opportunities detected yet. Run the pipeline to identify signals that span multiple business units.
        </div>
      ) : (
        data.opportunities.map((opp, idx) => (
          <div key={idx} className="bg-white rounded-lg shadow-sm overflow-hidden">
            <div className="p-6">
              <div className="flex items-start justify-between mb-3">
                <h3 className="text-lg font-semibold text-gray-900">{opp.headline}</h3>
                <span className="px-2 py-1 bg-vpg-blue text-white rounded text-xs font-medium">{opp.score}</span>
              </div>

              <div className="flex flex-wrap gap-2 mb-4">
                {opp.affected_bus?.map((bu, i) => (
                  <span key={i} className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium">
                    {bu.name}
                  </span>
                ))}
              </div>

              {opp.did_you_know && (
                <div className="bg-orange-50 border-l-4 border-vpg-accent p-4 rounded-r">
                  <p className="text-sm font-semibold text-vpg-accent mb-1">Did You Know?</p>
                  <p className="text-sm font-medium text-gray-900">{opp.did_you_know.title}</p>
                  <p className="text-sm text-gray-600 mt-1">{opp.did_you_know.value_proposition}</p>
                </div>
              )}

              {opp.summary && (
                <p className="text-sm text-gray-600 mt-3">{opp.summary}</p>
              )}

              {opp.quick_win && (
                <div className="mt-3 flex items-start gap-2">
                  <span className="text-xs font-semibold text-gray-500 uppercase mt-0.5">Quick Win:</span>
                  <span className="text-sm text-gray-700">{opp.quick_win}</span>
                </div>
              )}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
