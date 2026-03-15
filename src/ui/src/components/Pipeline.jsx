import React, { useEffect, useState, useRef } from 'react'

const SCAN_STAGES = ['collection', 'validation', 'scoring', 'trends']
const SEND_STAGES = ['composition', 'delivery']
const ALL_STAGES = [...SCAN_STAGES, ...SEND_STAGES]

const STAGE_LABELS = {
  collection: 'Collecting signals...',
  validation: 'Validating (3+ sources)...',
  scoring: 'AI scoring & analysis...',
  trends: 'Analyzing trends...',
  composition: 'Composing digest...',
  delivery: 'Delivering to recipients...',
}

export default function Pipeline() {
  const [status, setStatus] = useState(null)
  const [running, setRunning] = useState(false)
  const [paused, setPaused] = useState(false)
  const [lastRun, setLastRun] = useState(null)
  const [lastScan, setLastScan] = useState(null)
  const [activeMode, setActiveMode] = useState(null) // 'scan' | 'send' | 'full'
  const pollRef = useRef(null)

  // Scan form state
  const [scanDateRange, setScanDateRange] = useState({ start: '', end: '' })
  const [scanSources, setScanSources] = useState({ rss: true, reddit: true, trends: true })

  // Send form state
  const [sendDateRange, setSendDateRange] = useState({ start: '', end: '' })
  const [sendBuFilter, setSendBuFilter] = useState('')
  const [sendIndustryFilter, setSendIndustryFilter] = useState('')
  const [sendMinScore, setSendMinScore] = useState(5.0)
  const [sendPdfMode, setSendPdfMode] = useState(true)

  // Config data
  const [businessUnits, setBusinessUnits] = useState([])
  const [industries, setIndustries] = useState([])

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
          setActiveMode(null)
          fetchLastRun()
          fetchLastScan()
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

  const fetchLastScan = () => {
    fetch('/api/pipeline/scan-log?limit=1')
      .then(r => r.json())
      .then(d => setLastScan(d.scans?.[0] || null))
      .catch(() => {})
  }

  useEffect(() => {
    checkStatus()
    fetchLastRun()
    fetchLastScan()
    fetch('/api/business-units').then(r => r.json()).then(d => setBusinessUnits(d.business_units || [])).catch(() => {})
    fetch('/api/industries').then(r => r.json()).then(d => setIndustries(d.industries || [])).catch(() => {})
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const startPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(checkStatus, 3000)
  }

  const runScan = async () => {
    const sources = Object.entries(scanSources).filter(([, v]) => v).map(([k]) => k)
    try {
      const res = await fetch('/api/pipeline/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sources: sources.length < 3 ? sources : null,
          date_from: scanDateRange.start || null,
          date_to: scanDateRange.end || null,
        }),
      })
      if (res.ok) {
        setRunning(true)
        setPaused(false)
        setActiveMode('scan')
        startPolling()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to start scan')
      }
    } catch (e) {
      alert('Failed to start scan: ' + e.message)
    }
  }

  const runSend = async (previewOnly = false) => {
    try {
      const res = await fetch('/api/pipeline/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date_from: sendDateRange.start || null,
          date_to: sendDateRange.end || null,
          bu_filter: sendBuFilter || null,
          industry_filter: sendIndustryFilter || null,
          min_score: sendMinScore,
          pdf_mode: sendPdfMode,
          preview_only: previewOnly,
        }),
      })
      if (res.ok) {
        setRunning(true)
        setPaused(false)
        setActiveMode('send')
        startPolling()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to start send')
      }
    } catch (e) {
      alert('Failed to start: ' + e.message)
    }
  }

  const runFull = async (dryRun) => {
    try {
      const params = new URLSearchParams({ dry_run: dryRun, pdf_mode: sendPdfMode })
      const res = await fetch(`/api/pipeline/run?${params}`, { method: 'POST' })
      if (res.ok) {
        setRunning(true)
        setPaused(false)
        setActiveMode('full')
        startPolling()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to start pipeline')
      }
    } catch (e) {
      alert('Failed to start pipeline: ' + e.message)
    }
  }

  const handlePause = async () => {
    try { await fetch('/api/pipeline/pause', { method: 'POST' }); setPaused(true) }
    catch (e) { alert('Failed to pause: ' + e.message) }
  }

  const handleResume = async () => {
    try { await fetch('/api/pipeline/resume', { method: 'POST' }); setPaused(false) }
    catch (e) { alert('Failed to resume: ' + e.message) }
  }

  const handleCancel = async () => {
    if (!confirm('Cancel the running operation?')) return
    try { await fetch('/api/pipeline/cancel', { method: 'POST' }) }
    catch (e) { alert('Failed to cancel: ' + e.message) }
  }

  const currentStage = status?.current_stage || ''
  const stages = activeMode === 'scan' ? SCAN_STAGES : activeMode === 'send' ? SEND_STAGES : ALL_STAGES
  const currentStageIdx = stages.indexOf(currentStage)

  const toggleSource = (key) => setScanSources(prev => ({ ...prev, [key]: !prev[key] }))

  return (
    <div>
      <h2 className="text-2xl font-bold text-vpg-navy mb-6">Run Digest Pipeline</h2>

      {/* Last Run Indicator */}
      {lastRun && (
        <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
          <div className="flex items-center gap-4 flex-wrap">
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

      {/* Two-card layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* ── RUN SCAN CARD ── */}
        <div className="bg-white rounded-lg shadow-sm p-6 border-t-4 border-vpg-blue">
          <h3 className="text-lg font-semibold text-vpg-navy mb-1">Run Scan</h3>
          <p className="text-sm text-gray-500 mb-4">
            Collect and score new signals from all sources
          </p>

          {/* Date Range */}
          <div className="mb-4">
            <label className="text-xs font-semibold text-gray-600 block mb-1">Date Range</label>
            <div className="flex items-center gap-2">
              <input type="date" value={scanDateRange.start}
                onChange={e => setScanDateRange({ ...scanDateRange, start: e.target.value })}
                disabled={running}
                className="border rounded px-2 py-1.5 text-xs flex-1" />
              <span className="text-xs text-gray-400">to</span>
              <input type="date" value={scanDateRange.end}
                onChange={e => setScanDateRange({ ...scanDateRange, end: e.target.value })}
                disabled={running}
                className="border rounded px-2 py-1.5 text-xs flex-1" />
            </div>
            <span className="text-xs text-gray-400">(default: last 7 days)</span>
          </div>

          {/* Sources */}
          <div className="mb-4">
            <label className="text-xs font-semibold text-gray-600 block mb-1">Sources</label>
            <div className="flex gap-3">
              {[['rss', 'RSS/Web'], ['reddit', 'Reddit'], ['trends', 'Google Trends']].map(([key, label]) => (
                <label key={key} className="flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={scanSources[key]}
                    onChange={() => toggleSource(key)} disabled={running}
                    className="rounded text-vpg-blue" />
                  <span className="text-xs">{label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Incremental note */}
          <div className="bg-blue-50 rounded p-3 mb-4">
            <p className="text-xs text-blue-700">
              <span className="font-semibold">⚡ Incremental:</span> Only collects new signals.
              Existing signals are updated if new data found. No duplicates created.
            </p>
          </div>

          <button
            onClick={runScan}
            disabled={running}
            className="w-full bg-vpg-blue text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {running && activeMode === 'scan' ? 'Scanning...' : 'Run Scan Now'}
          </button>

          {/* Last Scan Info */}
          {lastScan && (
            <div className="mt-3 pt-3 border-t text-xs text-gray-500">
              <span className="font-medium">Last scan:</span>{' '}
              {lastScan.started_at ? new Date(lastScan.started_at).toLocaleString() : 'N/A'}
              {lastScan.signals_new != null && (
                <> | {lastScan.signals_new} new | {lastScan.signals_updated || 0} updated</>
              )}
            </div>
          )}
        </div>

        {/* ── SEND DIGEST EMAIL CARD ── */}
        <div className="bg-white rounded-lg shadow-sm p-6 border-t-4 border-vpg-accent">
          <h3 className="text-lg font-semibold text-vpg-navy mb-1">Send Digest Email</h3>
          <p className="text-sm text-gray-500 mb-4">
            Compose and send email digest from existing signals
          </p>

          {/* Signal Date Range */}
          <div className="mb-3">
            <label className="text-xs font-semibold text-gray-600 block mb-1">Signal Date Range</label>
            <div className="flex items-center gap-2">
              <input type="date" value={sendDateRange.start}
                onChange={e => setSendDateRange({ ...sendDateRange, start: e.target.value })}
                disabled={running}
                className="border rounded px-2 py-1.5 text-xs flex-1" />
              <span className="text-xs text-gray-400">to</span>
              <input type="date" value={sendDateRange.end}
                onChange={e => setSendDateRange({ ...sendDateRange, end: e.target.value })}
                disabled={running}
                className="border rounded px-2 py-1.5 text-xs flex-1" />
            </div>
          </div>

          {/* Filters */}
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="text-xs font-semibold text-gray-600 block mb-1">Business Unit</label>
              <select value={sendBuFilter}
                onChange={e => setSendBuFilter(e.target.value)}
                disabled={running}
                className="border rounded px-2 py-1.5 text-xs w-full">
                <option value="">All BUs</option>
                {businessUnits.map(bu => (
                  <option key={bu.id} value={bu.id}>{bu.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-600 block mb-1">Industry</label>
              <select value={sendIndustryFilter}
                onChange={e => setSendIndustryFilter(e.target.value)}
                disabled={running}
                className="border rounded px-2 py-1.5 text-xs w-full">
                <option value="">All Industries</option>
                {industries.map(ind => (
                  <option key={ind.id} value={ind.id}>{ind.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label className="text-xs font-semibold text-gray-600 block mb-1">Min Score</label>
              <input type="number" value={sendMinScore} step="0.5" min="0" max="10"
                onChange={e => setSendMinScore(parseFloat(e.target.value) || 0)}
                disabled={running}
                className="border rounded px-2 py-1.5 text-xs w-full" />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-600 block mb-1">Format</label>
              <select value={sendPdfMode ? 'pdf' : 'html'}
                onChange={e => setSendPdfMode(e.target.value === 'pdf')}
                disabled={running}
                className="border rounded px-2 py-1.5 text-xs w-full">
                <option value="pdf">PDF Attachment</option>
                <option value="html">HTML Email</option>
              </select>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => runSend(true)}
              disabled={running}
              className="flex-1 bg-white border-2 border-vpg-accent text-vpg-accent px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-orange-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Preview Email
            </button>
            <button
              onClick={() => runSend(false)}
              disabled={running}
              className="flex-1 bg-vpg-accent text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-orange-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {running && activeMode === 'send' ? 'Sending...' : 'Send Digest'}
            </button>
          </div>

          {/* Last Send Info */}
          {lastRun && lastRun.run_type === 'send' && (
            <div className="mt-3 pt-3 border-t text-xs text-gray-500">
              <span className="font-medium">Last sent:</span>{' '}
              {lastRun.started_at ? new Date(lastRun.started_at).toLocaleString() : 'N/A'}
              {lastRun.signals_scored != null && (
                <> | {lastRun.signals_scored} signals</>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Full pipeline (legacy) — collapsed section */}
      <details className="bg-white rounded-lg shadow-sm mb-6">
        <summary className="p-4 cursor-pointer text-sm font-semibold text-gray-500 hover:text-vpg-navy">
          ▶ Full Pipeline (Dry Run / Live) — runs all stages end-to-end
        </summary>
        <div className="px-4 pb-4">
          <div className="grid grid-cols-2 gap-4">
            <button onClick={() => runFull(true)} disabled={running}
              className="bg-vpg-blue text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
              {running && activeMode === 'full' ? 'Running...' : 'Start Dry Run'}
            </button>
            <button onClick={() => runFull(false)} disabled={running}
              className="bg-vpg-navy text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
              {running && activeMode === 'full' ? 'Running...' : 'Start Live Pipeline'}
            </button>
          </div>
        </div>
      </details>

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
              {stages.map((stage, idx) => (
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
              {stages.map(stage => (
                <span key={stage} className="text-center flex-1 truncate">
                  {stage.charAt(0).toUpperCase() + stage.slice(1)}
                </span>
              ))}
            </div>

            {/* Pause / Resume / Cancel */}
            <div className="flex gap-3">
              {!paused ? (
                <button onClick={handlePause}
                  className="bg-yellow-500 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-yellow-600 transition-colors">
                  Pause
                </button>
              ) : (
                <button onClick={handleResume}
                  className="bg-green-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-green-700 transition-colors">
                  Resume
                </button>
              )}
              <button onClick={handleCancel}
                className="bg-red-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-red-700 transition-colors">
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
            {/* Scan-specific results */}
            {status.last_result.signals_new !== undefined && (
              <p className="text-xs text-gray-600">
                Signals: {status.last_result.signals_new} new, {status.last_result.signals_updated || 0} updated
              </p>
            )}
            {status.last_result.signals_scored !== undefined && (
              <p className="text-xs text-gray-600">Signals scored: {status.last_result.signals_scored}</p>
            )}
            {status.last_result.recipients_sent !== undefined && (
              <p className="text-xs text-gray-600">
                Delivered to {status.last_result.recipients_sent}/{status.last_result.recipients_total} recipients
              </p>
            )}
            {status.last_result.pdf_generated && (
              <p className="text-xs text-green-600">PDF digest generated</p>
            )}
            {status.last_result.preview && (
              <p className="text-xs text-blue-600">Preview generated (no email sent)</p>
            )}
            {status.last_result.subject && (
              <p className="text-xs text-gray-500 mt-1">Subject: {status.last_result.subject}</p>
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
