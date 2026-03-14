import React, { useState, useEffect } from 'react'

export default function KeywordExpansion() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [applying, setApplying] = useState(false)
  const [lastApplied, setLastApplied] = useState(null)

  const fetchData = () => {
    setLoading(true)
    fetch('/api/keyword-expansion')
      .then(r => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }

  useEffect(fetchData, [])

  const handleApply = () => {
    setApplying(true)
    fetch('/api/keyword-expansion/apply', { method: 'POST' })
      .then(r => r.json())
      .then(result => {
        setLastApplied(result)
        fetchData()
      })
      .catch(() => {})
      .finally(() => setApplying(false))
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Analyzing feedback patterns...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Keyword Expansion</h2>
          <p className="text-sm text-gray-500 mt-1">Self-improving keyword activation based on feedback</p>
        </div>
        <button
          onClick={handleApply}
          disabled={applying}
          className="px-4 py-2 bg-vpg-blue text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {applying ? 'Applying...' : 'Apply Changes'}
        </button>
      </div>

      {lastApplied && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-800">
          Applied: {lastApplied.summary?.keywords_activated || 0} activated, {lastApplied.summary?.keywords_deactivated || 0} deactivated
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow-sm p-5">
          <div className="text-3xl font-bold text-green-600">{data?.summary?.keywords_activated || 0}</div>
          <div className="text-sm text-gray-500 mt-1">To Activate</div>
          <div className="text-xs text-gray-400">Keywords in positively-rated signals</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-5">
          <div className="text-3xl font-bold text-red-600">{data?.summary?.keywords_deactivated || 0}</div>
          <div className="text-sm text-gray-500 mt-1">To Deactivate</div>
          <div className="text-xs text-gray-400">Keywords in negatively-rated signals</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-5">
          <div className="text-3xl font-bold text-blue-600">{data?.summary?.new_suggestions || 0}</div>
          <div className="text-sm text-gray-500 mt-1">New Suggestions</div>
          <div className="text-xs text-gray-400">Extracted from positive feedback</div>
        </div>
      </div>

      {/* Activate list */}
      {data?.activated?.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Keywords to Activate</h3>
          <div className="space-y-2">
            {data.activated.map((k, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-green-50 rounded">
                <span className="font-medium text-gray-900">{k.keyword}</span>
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-green-700">{k.positive_rate}% positive</span>
                  <span className="text-gray-400">{k.feedback_count} feedback</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Deactivate list */}
      {data?.deactivated?.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Keywords to Deactivate</h3>
          <div className="space-y-2">
            {data.deactivated.map((k, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-red-50 rounded">
                <span className="font-medium text-gray-900">{k.keyword}</span>
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-red-700">{k.positive_rate}% positive</span>
                  <span className="text-gray-400">{k.feedback_count} feedback</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Suggestions */}
      {data?.suggestions?.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Suggested New Keywords</h3>
          <p className="text-sm text-gray-500 mb-3">Extracted from positively-rated signals. Add via Keywords page.</p>
          <div className="flex flex-wrap gap-2">
            {data.suggestions.map((s, i) => (
              <span key={i} className="px-3 py-1.5 bg-blue-50 text-blue-800 rounded-full text-sm">
                {s.keyword} <span className="text-blue-400">({s.occurrences}x)</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {!data?.activated?.length && !data?.deactivated?.length && !data?.suggestions?.length && (
        <div className="bg-white rounded-lg shadow-sm p-8 text-center text-gray-500">
          Not enough feedback data yet. Keyword expansion requires at least {5} feedback responses per keyword.
        </div>
      )}
    </div>
  )
}
