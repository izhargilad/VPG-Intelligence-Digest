import React, { useEffect, useState, useRef } from 'react'

const STAGE_LABELS = {
  collection: 'Collecting signals from sources...',
  validation: 'Validating signals (3+ sources)...',
  scoring: 'AI scoring & analysis...',
  trends: 'Analyzing trends...',
  composition: 'Composing digest...',
  delivery: 'Delivering to recipients...',
}

const STAGE_ORDER = ['collection', 'validation', 'scoring', 'trends', 'composition', 'delivery']

export default function Pipeline() {
  const [status, setStatus] = useState(null)
  const [running, setRunning] = useState(false)
  const [paused, setPaused] = useState(false)
  const [pdfMode, setPdfMode] = useState(true)
  const [lastRun, setLastRun] = useState(null)
  const [dateRange, setDateRange] = useState({ start: '', end: '' })
  const pollRef = useRef(null)

  const checkStatus = () => {
    fetch('/api/pipeline/status')
      .then(r => r.json())
      .then(data => {
        setStatus(data)
        setRunning(data.running)
        setPaused(data.paused || false)
        if (!data.running && pollRef.current) {
          clearInterval(pollRef.current)
          pollRef.current = null
          fetchLastRun()
        }
      })
      .catch(() => {})
  }

  const fetchLastRun = () => {
    fetch('/api/pipeline/last-run')
      .then(r => r.json())
      .then(d => setLastRun(d.last_run))
      .catch(() => {})
  }

  useEffect(() => {
    checkStatus()
    fetchLastRun()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const startPoll = () => {
    setRunning(true)
    setPaused(false)
    pollRef.current = setInterval(checkStatus, 3000)
  }

  const runPipeline = async (dryRun) => {
    try {
      const params = new URLSearchParams({ dry_run: dryRun, pdf_mode: pdfMode })
      if (dateRange.start) params.set('start_date', dateRange.start)
      if (dateRange.end) params.set('end_date', dateRange.end)
      const res = await fetch(`/api/pipeline/run?${params}`, { method: 'POST' })
      if (res.ok) {
        startPoll()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to start pipeline')
      }
    } catch (e) {
      alert('Failed to start pipeline: ' + e.message)
    }
  }

  const runCollectScore = async (dryRun) => {
    try {
      const params = new URLSearchParams({ dry_run: dryRun })
      const res = await fetch(`/api/pipeline/collect-score?${params}`, { method: 'POST' })
      if (res.ok) {
        startPoll()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to start collect & score')
      }
    } catch (e) {
      alert('Failed: ' + e.message)
    }
  }

  const runSendMail = async () => {
    try {
      const params = new URLSearchParams({ pdf_mode: pdfMode })
      const res = await fetch(`/api/pipeline/send-mail?${params}`, { method: 'POST' })
      if (res.ok) {
        startPoll()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to start send mail')
      }
    } catch (e) {
      alert('Failed: ' + e.message)
    }
  }

  const handlePause = async () => {
    try {
      await fetch('/api/pipeline/pause', { method: 'POST' })
      setPaused(true)
    } catch (e) {
      alert('Failed to pause: ' + e.message)
    }
  }

  const handleResume = async () => {
    try {
      await fetch('/api/pipeline/resume', { method: 'POST' })
      setPaused(false)
    } catch (e) {
      alert('Failed to resume: ' + e.message)
    }
  }

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel the running pipeline?')) return
    try {
      await fetch('/api/pipeline/cancel', { method: 'POST' })
    } catch (e) {
      alert('Failed to cancel: ' + e.message)
    }
  }

  const currentStage = status?.current_stage || ''
  const currentStageIdx = STAGE_ORDER.indexOf(currentStage)

  return (
    <div>
      <h2 className="text-2xl font-bold text-vpg-navy mb-6">Run Digest Pipeline</h2>

      {/* Last Run Indicator */}
      {lastRun && (
        <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${
                lastRun.status === 'completed' ? 'bg-green-500' :
                lastRun.status === 'failed' ? 'bg-red-500' : 'bg-yellow-500'
              }`} />
              <span className="text-sm font-semibold text-vpg-navy">Last Run</span>
            </div>
            <span className="text-sm text-gray-600">
              {lastRun.started_at ? new Date(lastRun.started_at).toLocaleString() : 'N/A'}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded font-semibold ${
              lastRun.status === 'completed' ? 'bg-green-100 text-green-700' :
              lastRun.status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'
            }`}>
              {lastRun.status?.toUpperCase()}
            </span>
            {lastRun.signals_collected != null && (
              <span className="text-xs text-gray-500">
                {lastRun.signals_collected} collected / {lastRun.signals_scored || 0} scored
              </span>
            )}
            <span className="text-xs text-gray-400">{lastRun.run_type}</span>
          </div>
        </div>
      )}

      {/* Date Range */}
      <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
        <div className="flex items-center gap-4">
          <span className="text-sm font-semibold text-vpg-navy">Collection Date Range:</span>
          <div className="flex items-center gap-2">
            <input type="date" value={dateRange.start}
              onChange={e => setDateRange({ ...dateRange, start: e.target.value })}
              disabled={running}
              className="border rounded px-2 py-1.5 text-xs" />
            <span className="text-xs text-gray-400">to</span>
            <input type="date" value={dateRange.end}
              onChange={e => setDateRange({ ...dateRange, end: e.target.value })}
              disabled={running}
              className="border rounded px-2 py-1.5 text-xs" />
          </div>
          <span className="text-xs text-gray-400">(leave empty for default 7-day window)</span>
        </div>
      </div>

      {/* Delivery Format Toggle */}
      <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
        <div className="flex items-center gap-4">
          <span className="text-sm font-semibold text-vpg-navy">Delivery Format:</span>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="deliveryFormat"
              checked={!pdfMode}
              onChange={() => setPdfMode(false)}
              disabled={running}
              className="text-vpg-blue"
            />
            <span className="text-sm">HTML Email</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="deliveryFormat"
              checked={pdfMode}
              onChange={() => setPdfMode(true)}
              disabled={running}
              className="text-vpg-blue"
            />
            <span className="text-sm">PDF Attachment</span>
            <span className="text-xs text-gray-500">(recommended)</span>
          </label>
        </div>
      </div>

      {/* === STEP 1: Collect & Score === */}
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Step 1 — Collect & Score Signals</h3>
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-vpg-blue">
            <h3 className="text-lg font-semibold text-vpg-navy mb-2">Dry Run (Seed Data)</h3>
            <p className="text-sm text-gray-600 mb-4">
              Collect, validate, and score signals using seed data.
              Good for testing. No emails sent.
            </p>
            <button
              onClick={() => runCollectScore(true)}
              disabled={running}
              className="bg-vpg-blue text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {running ? 'Running...' : 'Collect & Score (Dry Run)'}
            </button>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-vpg-navy">
            <h3 className="text-lg font-semibold text-vpg-navy mb-2">Live Collection</h3>
            <p className="text-sm text-gray-600 mb-4">
              Collect from live RSS feeds, scrape websites, validate against 3+ sources, and AI score.
            </p>
            <button
              onClick={() => runCollectScore(false)}
              disabled={running}
              className="bg-vpg-navy text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {running ? 'Running...' : 'Collect & Score (Live)'}
            </button>
          </div>
        </div>
      </div>

      {/* === STEP 2: Send Mail === */}
      <div className="mb-8">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3 mt-6">Step 2 — Compose & Send Digest</h3>
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-vpg-accent">
            <h3 className="text-lg font-semibold text-vpg-navy mb-2">Send Mail</h3>
            <p className="text-sm text-gray-600 mb-4">
              Compose the digest from scored signals and deliver to active recipients.
              Review signals in Intel Feed first.
            </p>
            <button
              onClick={runSendMail}
              disabled={running}
              className="bg-vpg-accent text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-orange-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {running ? 'Sending...' : 'Compose & Send Mail'}
            </button>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-green-500">
            <h3 className="text-lg font-semibold text-vpg-navy mb-2">Full Pipeline</h3>
            <p className="text-sm text-gray-600 mb-4">
              Run everything end-to-end in one shot: collect, validate, score, compose, and deliver.
            </p>
            <button
              onClick={() => runPipeline(false)}
              disabled={running}
              className="bg-green-600 text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {running ? 'Running...' : 'Run Full Pipeline'}
            </button>
          </div>
        </div>
      </div>

      {/* Status */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-vpg-navy mb-4">Pipeline Status</h3>

        {running && (
          <div className="mb-4">
            {/* Stage Progress */}
            <div className="flex items-center gap-3 p-4 bg-blue-50 rounded-lg mb-4">
              {!paused && (
                <svg className="animate-spin h-5 w-5 text-vpg-blue" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
              )}
              {paused && (
                <span className="text-lg font-bold text-yellow-600">||</span>
              )}
              <span className="text-sm font-medium text-vpg-blue">
                {paused ? 'Pipeline paused' : (STAGE_LABELS[currentStage] || 'Pipeline is running...')}
              </span>
            </div>

            {/* Stage Progress Bar */}
            <div className="flex gap-1 mb-4">
              {STAGE_ORDER.map((stage, idx) => (
                <div
                  key={stage}
                  className={`flex-1 h-2 rounded-full ${
                    idx < currentStageIdx ? 'bg-green-500' :
                    idx === currentStageIdx ? (paused ? 'bg-yellow-400' : 'bg-vpg-blue animate-pulse') :
                    'bg-gray-200'
                  }`}
                  title={stage.charAt(0).toUpperCase() + stage.slice(1)}
                />
              ))}
            </div>
            <div className="flex justify-between text-xs text-gray-500 mb-4">
              {STAGE_ORDER.map(stage => (
                <span key={stage} className="text-center flex-1 truncate">
                  {stage.charAt(0).toUpperCase() + stage.slice(1)}
                </span>
              ))}
            </div>

            {/* Pause / Resume / Cancel */}
            <div className="flex gap-3">
              {!paused ? (
                <button
                  onClick={handlePause}
                  className="bg-yellow-500 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-yellow-600 transition-colors"
                >
                  Pause
                </button>
              ) : (
                <button
                  onClick={handleResume}
                  className="bg-green-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
                >
                  Resume
                </button>
              )}
              <button
                onClick={handleCancel}
                className="bg-red-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-red-700 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {status?.last_result && (
          <div className={`p-4 rounded-lg ${
            status.last_result.status === 'completed' ? 'bg-green-50' :
            status.last_result.status === 'cancelled' ? 'bg-yellow-50' :
            'bg-red-50'
          }`}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-sm font-semibold ${
                status.last_result.status === 'completed' ? 'text-green-700' :
                status.last_result.status === 'cancelled' ? 'text-yellow-700' :
                'text-red-700'
              }`}>
                {status.last_result.status === 'completed' ? 'Completed' :
                 status.last_result.status === 'cancelled' ? 'Cancelled' :
                 'Failed'}
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
            {status.last_result.signals_in_digest !== undefined && (
              <p className="text-xs text-gray-600">Signals in digest: {status.last_result.signals_in_digest}</p>
            )}
            {status.last_result.recipients_sent !== undefined && (
              <p className="text-xs text-gray-600">Recipients delivered: {status.last_result.recipients_sent}</p>
            )}
            {status.last_result.pdf_generated && (
              <p className="text-xs text-green-600">PDF digest generated</p>
            )}
            {status.last_result.error && (
              <p className="text-xs text-red-600 mt-1">Error: {status.last_result.error}</p>
            )}
            {status.last_result.message && (
              <p className="text-xs text-gray-600 mt-1">{status.last_result.message}</p>
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
