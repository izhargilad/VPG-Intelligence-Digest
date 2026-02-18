import React, { useEffect, useState, useRef } from 'react'

export default function Pipeline() {
  const [status, setStatus] = useState(null)
  const [running, setRunning] = useState(false)
  const pollRef = useRef(null)

  const checkStatus = () => {
    fetch('/api/pipeline/status')
      .then(r => r.json())
      .then(data => {
        setStatus(data)
        setRunning(data.running)
        if (!data.running && pollRef.current) {
          clearInterval(pollRef.current)
          pollRef.current = null
        }
      })
      .catch(() => {})
  }

  useEffect(() => {
    checkStatus()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const runPipeline = async (dryRun) => {
    try {
      const res = await fetch(`/api/pipeline/run?dry_run=${dryRun}`, { method: 'POST' })
      if (res.ok) {
        setRunning(true)
        pollRef.current = setInterval(checkStatus, 3000)
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to start pipeline')
      }
    } catch (e) {
      alert('Failed to start pipeline: ' + e.message)
    }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-vpg-navy mb-6">Run Digest Pipeline</h2>

      <div className="grid grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-lg font-semibold text-vpg-navy mb-2">Dry Run</h3>
          <p className="text-sm text-gray-600 mb-4">
            Run the pipeline with seed data. No live source collection.
            Good for testing the full flow end-to-end.
          </p>
          <button
            onClick={() => runPipeline(true)}
            disabled={running}
            className="bg-vpg-blue text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {running ? 'Running...' : 'Start Dry Run'}
          </button>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-lg font-semibold text-vpg-navy mb-2">Live Pipeline</h3>
          <p className="text-sm text-gray-600 mb-4">
            Run the full 6-stage pipeline: collect from live sources,
            validate, score with AI, compose, and deliver.
          </p>
          <button
            onClick={() => runPipeline(false)}
            disabled={running}
            className="bg-vpg-navy text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {running ? 'Running...' : 'Start Live Pipeline'}
          </button>
        </div>
      </div>

      {/* Status */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-vpg-navy mb-4">Pipeline Status</h3>

        {running && (
          <div className="flex items-center gap-3 p-4 bg-blue-50 rounded-lg mb-4">
            <svg className="animate-spin h-5 w-5 text-vpg-blue" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            <span className="text-sm font-medium text-vpg-blue">Pipeline is running...</span>
          </div>
        )}

        {status?.last_result && (
          <div className={`p-4 rounded-lg ${
            status.last_result.status === 'completed' ? 'bg-green-50' : 'bg-red-50'
          }`}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-sm font-semibold ${
                status.last_result.status === 'completed' ? 'text-green-700' : 'text-red-700'
              }`}>
                {status.last_result.status === 'completed' ? 'Completed' : 'Failed'}
              </span>
              {status.last_run && (
                <span className="text-xs text-gray-500">
                  at {new Date(status.last_run).toLocaleString()}
                </span>
              )}
            </div>
            {status.last_result.mode && (
              <p className="text-xs text-gray-600">Mode: {status.last_result.mode}</p>
            )}
            {status.last_result.signals_scored !== undefined && (
              <p className="text-xs text-gray-600">Signals scored: {status.last_result.signals_scored}</p>
            )}
            {status.last_result.error && (
              <p className="text-xs text-red-600 mt-1">Error: {status.last_result.error}</p>
            )}
          </div>
        )}

        {!status?.last_result && !running && (
          <p className="text-sm text-gray-400">No recent pipeline runs</p>
        )}
      </div>
    </div>
  )
}
