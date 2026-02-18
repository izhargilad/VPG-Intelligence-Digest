import React, { useEffect, useState } from 'react'

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/dashboard')
      .then(r => r.json())
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>

  if (!stats) return (
    <div className="bg-white rounded-lg shadow-sm p-8 text-center text-gray-500">
      Unable to load dashboard. Make sure the API server is running.
    </div>
  )

  const cards = [
    { label: 'Total Signals', value: stats.signals_total, color: 'bg-vpg-blue' },
    { label: 'Scored Signals', value: stats.signals_scored, color: 'bg-green-600' },
    { label: 'Pipeline Runs', value: stats.pipeline_runs, color: 'bg-purple-600' },
    { label: 'Active Recipients', value: stats.active_recipients, color: 'bg-vpg-accent' },
    { label: 'Digests Generated', value: stats.digests_generated, color: 'bg-vpg-navy' },
  ]

  return (
    <div>
      <h2 className="text-2xl font-bold text-vpg-navy mb-6">Dashboard</h2>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
        {cards.map(card => (
          <div key={card.label} className="bg-white rounded-lg shadow-sm p-5">
            <div className={`inline-block px-2 py-1 rounded text-white text-xs font-semibold ${card.color} mb-2`}>
              {card.label}
            </div>
            <div className="text-3xl font-bold text-gray-800">{card.value}</div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-vpg-navy mb-3">Last Pipeline Run</h3>
        {stats.last_run.time ? (
          <div className="text-sm text-gray-600">
            <p><span className="font-medium">Time:</span> {new Date(stats.last_run.time).toLocaleString()}</p>
            <p><span className="font-medium">Status:</span>{' '}
              <span className={stats.last_run.status === 'completed' ? 'text-green-600 font-semibold' : 'text-red-600 font-semibold'}>
                {stats.last_run.status}
              </span>
            </p>
          </div>
        ) : (
          <p className="text-sm text-gray-400">No pipeline runs yet</p>
        )}
        {stats.pipeline_running && (
          <div className="mt-3 flex items-center gap-2 text-vpg-blue">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            <span className="text-sm font-medium">Pipeline is currently running...</span>
          </div>
        )}
      </div>
    </div>
  )
}
