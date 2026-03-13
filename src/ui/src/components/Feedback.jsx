import React, { useState, useEffect } from 'react'

const API = '/api'

export default function Feedback() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API}/feedback/summary`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6 text-gray-500">Loading feedback data...</div>
  if (!data) return <div className="p-6 text-gray-500">Could not load feedback data.</div>

  const { feedback, adjustments } = data
  const hasData = feedback?.total_feedback > 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-vpg-navy">Feedback & Scoring Refinement</h2>
        <span className="text-sm text-gray-500">
          {adjustments?.summary?.adjustments_active ? 'Adjustments Active' : 'Collecting feedback...'}
        </span>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow-sm p-4">
          <div className="text-2xl font-bold text-vpg-navy">{feedback?.total_feedback || 0}</div>
          <div className="text-sm text-gray-500">Total Feedback</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4">
          <div className="text-2xl font-bold text-green-600">{feedback?.positive || 0}</div>
          <div className="text-sm text-gray-500">Positive</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4">
          <div className="text-2xl font-bold text-red-600">{feedback?.negative || 0}</div>
          <div className="text-sm text-gray-500">Negative</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4">
          <div className="text-2xl font-bold text-vpg-blue">{feedback?.positive_rate || 0}%</div>
          <div className="text-sm text-gray-500">Positive Rate</div>
        </div>
      </div>

      {!hasData && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
          <div className="text-lg font-medium text-blue-800">No feedback collected yet</div>
          <p className="text-sm text-blue-600 mt-1">
            Feedback will appear here as recipients rate signals using thumbs-up/down in their digest emails.
            After {5} ratings, scoring adjustments will activate automatically.
          </p>
        </div>
      )}

      {hasData && (
        <>
          {/* Signal Type Breakdown */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h3 className="font-semibold text-vpg-navy mb-4">Feedback by Signal Type</h3>
            <div className="space-y-3">
              {Object.entries(feedback?.type_breakdown || {}).map(([type, stats]) => {
                const total = (stats.up || 0) + (stats.down || 0)
                const rate = total > 0 ? ((stats.up || 0) / total * 100) : 0
                return (
                  <div key={type} className="flex items-center gap-4">
                    <div className="w-40 text-sm font-medium text-gray-700 capitalize">
                      {type.replace(/-/g, ' ')}
                    </div>
                    <div className="flex-1 bg-gray-100 rounded-full h-6 relative overflow-hidden">
                      <div
                        className="bg-green-500 h-full rounded-full transition-all"
                        style={{ width: `${rate}%` }}
                      />
                      <span className="absolute inset-0 flex items-center justify-center text-xs font-medium">
                        {stats.up || 0} up / {stats.down || 0} down ({rate.toFixed(0)}%)
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Scoring Adjustments */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h3 className="font-semibold text-vpg-navy mb-4">Active Scoring Adjustments</h3>
            {!adjustments?.summary?.adjustments_active ? (
              <p className="text-sm text-gray-500">
                Need {5 - (feedback?.total_feedback || 0)} more feedback responses to activate adjustments.
              </p>
            ) : (
              <div className="space-y-3">
                {Object.entries(adjustments?.signal_type_adjustments || {}).map(([type, adj]) => (
                  <div key={type} className="flex items-center justify-between border-b pb-2">
                    <span className="text-sm font-medium capitalize">{type.replace(/-/g, ' ')}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-gray-500">{adj.positive_rate}% positive</span>
                      <span className={`text-sm font-medium px-2 py-1 rounded ${
                        adj.adjustment > 0 ? 'bg-green-100 text-green-700' :
                        adj.adjustment < 0 ? 'bg-red-100 text-red-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {adj.adjustment > 0 ? '+' : ''}{(adj.adjustment * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Feedback */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h3 className="font-semibold text-vpg-navy mb-4">Recent Feedback</h3>
            <div className="space-y-2">
              {(feedback?.recent_feedback || []).map((fb, i) => (
                <div key={i} className="flex items-center gap-3 text-sm border-b pb-2">
                  <span className={`text-lg ${fb.rating === 'up' ? 'text-green-500' : 'text-red-500'}`}>
                    {fb.rating === 'up' ? '👍' : '👎'}
                  </span>
                  <span className="flex-1 truncate">{fb.headline}</span>
                  <span className="text-gray-400 text-xs">{new Date(fb.created_at).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
