import React, { useEffect, useState } from 'react'

const SIGNAL_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'competitive-threat', label: 'Competitive Threat' },
  { value: 'revenue-opportunity', label: 'Revenue Opportunity' },
  { value: 'market-shift', label: 'Market Shift' },
  { value: 'partnership-signal', label: 'Partnership Signal' },
  { value: 'customer-intelligence', label: 'Customer Intelligence' },
  { value: 'technology-trend', label: 'Technology Trend' },
  { value: 'trade-tariff', label: 'Trade & Tariff' },
]

const TYPE_ICONS = {
  'competitive-threat': { icon: '\u26A0', color: '#E53935' },
  'revenue-opportunity': { icon: '\uD83D\uDCB0', color: '#43A047' },
  'market-shift': { icon: '\uD83C\uDFAF', color: '#1E88E5' },
  'partnership-signal': { icon: '\uD83E\uDD1D', color: '#7B1FA2' },
  'customer-intelligence': { icon: '\uD83D\uDCCA', color: '#F57C00' },
  'technology-trend': { icon: '\uD83D\uDE80', color: '#0097A7' },
  'trade-tariff': { icon: '\uD83C\uDF0D', color: '#455A64' },
}

const VALIDATION_BADGES = {
  verified: { label: 'VERIFIED', color: 'bg-green-100 text-green-800' },
  likely: { label: 'LIKELY', color: 'bg-yellow-100 text-yellow-800' },
  unverified: { label: 'UNVERIFIED', color: 'bg-gray-100 text-gray-600' },
}

export default function Feed() {
  const [signals, setSignals] = useState([])
  const [busUnits, setBusUnits] = useState([])
  const [industries, setIndustries] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(null)
  const [exportError, setExportError] = useState(null)
  const [filters, setFilters] = useState({
    signal_type: '', bu_id: '', industry_id: '',
    min_score: 0, start_date: '', end_date: '',
  })

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (filters.signal_type) params.set('signal_type', filters.signal_type)
    if (filters.bu_id) params.set('bu_id', filters.bu_id)
    if (filters.industry_id) params.set('industry_id', filters.industry_id)
    if (filters.min_score > 0) params.set('min_score', filters.min_score)
    if (filters.start_date) params.set('start_date', filters.start_date)
    if (filters.end_date) params.set('end_date', filters.end_date)
    params.set('limit', '100')

    fetch(`/api/feed?${params}`)
      .then(r => r.json())
      .then(d => setSignals(d.signals || []))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    Promise.all([
      fetch('/api/business-units').then(r => r.json()),
      fetch('/api/industries').then(r => r.json()),
    ]).then(([buData, indData]) => {
      setBusUnits(buData.business_units || [])
      setIndustries(indData.industries || [])
    })
  }, [])

  useEffect(load, [filters])

  const buNameMap = {}
  busUnits.forEach(bu => { buNameMap[bu.id] = bu.short_name || bu.name })

  const handleExport = async (format) => {
    setExportError(null)
    try {
      const params = new URLSearchParams()
      if (filters.start_date) params.set('start_date', filters.start_date)
      if (filters.end_date) params.set('end_date', filters.end_date)
      if (filters.bu_id) params.set('bu_id', filters.bu_id)
      if (filters.signal_type) params.set('signal_type', filters.signal_type)
      if (filters.industry_id) params.set('industry_id', filters.industry_id)
      if (filters.min_score > 0) params.set('min_score', filters.min_score)
      const resp = await fetch(`/api/export/${format}?${params}`)
      if (!resp.ok) {
        const err = await resp.json()
        setExportError(err.detail || `Export failed (${resp.status})`)
        return
      }
      const blob = await resp.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = resp.headers.get('content-disposition')?.split('filename=')[1] || `export.${format}`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (e) {
      setExportError(`Export failed: ${e.message}`)
    }
  }

  const dismissSignal = async (signalId) => {
    await fetch(`/api/signals/${signalId}/dismiss`, { method: 'POST' })
    setSignals(prev => prev.filter(s => s.id !== signalId))
  }

  const handleSignal = async (signalId) => {
    await fetch(`/api/signals/${signalId}/handle`, { method: 'POST' })
    setSignals(prev => prev.map(s => s.id === signalId ? { ...s, handled: 1 } : s))
  }

  const unhandleSignal = async (signalId) => {
    await fetch(`/api/signals/${signalId}/unhandle`, { method: 'POST' })
    setSignals(prev => prev.map(s => s.id === signalId ? { ...s, handled: 0 } : s))
  }

  const [feedbackGiven, setFeedbackGiven] = useState({})

  const submitFeedback = async (signalId, rating) => {
    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signal_id: signalId, rating, recipient_email: 'ui-user' })
      })
      setFeedbackGiven(prev => ({ ...prev, [signalId]: rating }))
    } catch (e) {
      console.error('Feedback failed:', e)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-vpg-navy">Intelligence Feed</h2>
          <p className="text-sm text-gray-500 mt-1">{signals.length} signals</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleExport('excel')}
            className="bg-green-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-green-700"
          >
            Export Excel
          </button>
          <button
            onClick={() => handleExport('pptx')}
            className="bg-vpg-accent text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-orange-600"
          >
            Export PPTX
          </button>
        </div>
      </div>

      {exportError && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm flex justify-between items-center">
          <span>{exportError}</span>
          <button onClick={() => setExportError(null)} className="text-red-400 hover:text-red-600">&times;</button>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm p-4 mb-4">
        <div className="grid grid-cols-3 lg:grid-cols-6 gap-3">
          <div>
            <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Signal Type</label>
            <select
              value={filters.signal_type}
              onChange={e => setFilters({ ...filters, signal_type: e.target.value })}
              className="w-full border rounded px-2 py-1.5 text-xs"
            >
              {SIGNAL_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Business Unit</label>
            <select
              value={filters.bu_id}
              onChange={e => setFilters({ ...filters, bu_id: e.target.value })}
              className="w-full border rounded px-2 py-1.5 text-xs"
            >
              <option value="">All BUs</option>
              {busUnits.map(bu => <option key={bu.id} value={bu.id}>{bu.short_name || bu.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Industry</label>
            <select
              value={filters.industry_id}
              onChange={e => setFilters({ ...filters, industry_id: e.target.value })}
              className="w-full border rounded px-2 py-1.5 text-xs"
            >
              <option value="">All Industries</option>
              {industries.map(ind => <option key={ind.id} value={ind.id}>{ind.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Min Score</label>
            <input
              type="number" min="0" max="10" step="0.5"
              value={filters.min_score}
              onChange={e => setFilters({ ...filters, min_score: parseFloat(e.target.value) || 0 })}
              className="w-full border rounded px-2 py-1.5 text-xs"
            />
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">From</label>
            <input
              type="date"
              value={filters.start_date}
              onChange={e => setFilters({ ...filters, start_date: e.target.value })}
              className="w-full border rounded px-2 py-1.5 text-xs"
            />
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">To</label>
            <input
              type="date"
              value={filters.end_date}
              onChange={e => setFilters({ ...filters, end_date: e.target.value })}
              className="w-full border rounded px-2 py-1.5 text-xs"
            />
          </div>
        </div>
      </div>

      {/* Signal Cards */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading signals...</div>
      ) : signals.length === 0 ? (
        <div className="text-center py-12 text-gray-400">No signals match the current filters.</div>
      ) : (
        <div className="space-y-3">
          {signals.map(signal => {
            const typeConfig = TYPE_ICONS[signal.signal_type] || { icon: '\u2139', color: '#666' }
            const valBadge = VALIDATION_BADGES[signal.validation_level] || VALIDATION_BADGES.unverified
            const isExpanded = expanded === signal.id

            return (
              <div key={signal.id} className={`bg-white rounded-lg shadow-sm overflow-hidden ${signal.handled ? 'opacity-70' : ''}`}>
                <div
                  className="flex items-center gap-3 px-5 py-3 cursor-pointer hover:bg-gray-50"
                  onClick={() => setExpanded(isExpanded ? null : signal.id)}
                  style={{ borderLeftWidth: 4, borderLeftColor: typeConfig.color }}
                >
                  <span className="text-lg">{typeConfig.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-vpg-navy truncate">
                        {signal.headline || signal.title}
                      </span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded font-semibold ${valBadge.color}`}>
                        {valBadge.label}
                      </span>
                      {signal.handled ? (
                        <span className="text-[9px] px-1.5 py-0.5 rounded font-semibold bg-green-100 text-green-700">HANDLED</span>
                      ) : null}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      {signal.bus.map(buId => (
                        <span key={buId} className="text-[10px] bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">
                          {buNameMap[buId] || buId}
                        </span>
                      ))}
                      <span className="text-[10px] text-gray-400">{signal.source_name}</span>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className={`text-lg font-bold ${
                      signal.score_composite >= 8 ? 'text-green-600' :
                      signal.score_composite >= 6 ? 'text-vpg-blue' : 'text-gray-500'
                    }`}>
                      {(signal.score_composite || 0).toFixed(1)}
                    </div>
                    <div className="text-[10px] text-gray-400">
                      {signal.published_at ? new Date(signal.published_at).toLocaleDateString() : ''}
                    </div>
                  </div>
                  <span className="text-gray-400 text-xs">{isExpanded ? '\u25B2' : '\u25BC'}</span>
                </div>

                {isExpanded && (
                  <div className="px-5 py-4 bg-gray-50 border-t space-y-3">
                    {signal.what_summary && (
                      <div>
                        <span className="text-xs font-semibold text-vpg-blue uppercase">WHAT: </span>
                        <span className="text-sm text-gray-700">{signal.what_summary}</span>
                      </div>
                    )}
                    {signal.why_it_matters && (
                      <div>
                        <span className="text-xs font-semibold text-vpg-blue uppercase">WHY IT MATTERS: </span>
                        <span className="text-sm text-gray-700">{signal.why_it_matters}</span>
                      </div>
                    )}
                    {signal.quick_win && (
                      <div>
                        <span className="text-xs font-semibold text-vpg-accent uppercase">QUICK WIN: </span>
                        <span className="text-sm text-gray-700">{signal.quick_win}</span>
                      </div>
                    )}
                    <div className="flex gap-6 text-xs text-gray-500">
                      {signal.suggested_owner && <span><b>Owner:</b> {signal.suggested_owner}</span>}
                      {signal.estimated_impact && <span><b>Est. Impact:</b> {signal.estimated_impact}</span>}
                    </div>
                    <div className="flex gap-3 text-xs">
                      <span className="text-gray-400">Revenue: {(signal.score_revenue_impact || 0).toFixed(1)}</span>
                      <span className="text-gray-400">Time: {(signal.score_time_sensitivity || 0).toFixed(1)}</span>
                      <span className="text-gray-400">Strategic: {(signal.score_strategic_alignment || 0).toFixed(1)}</span>
                      <span className="text-gray-400">Competitive: {(signal.score_competitive_pressure || 0).toFixed(1)}</span>
                    </div>

                    {/* Source Links */}
                    <div className="flex flex-wrap gap-2">
                      {signal.url && (
                        <a href={signal.url} target="_blank" rel="noopener noreferrer"
                          className="text-xs text-vpg-blue hover:underline">
                          Primary Source &rarr;
                        </a>
                      )}
                      {(signal.source_links || []).map((link, i) => (
                        <a key={i} href={link.url} target="_blank" rel="noopener noreferrer"
                          className="text-xs text-gray-500 hover:text-vpg-blue hover:underline">
                          {link.source || `Source ${i + 1}`} &rarr;
                        </a>
                      ))}
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-2 pt-2 border-t border-gray-200">
                      <button
                        onClick={(e) => { e.stopPropagation(); dismissSignal(signal.id) }}
                        className="text-xs px-3 py-1.5 rounded bg-red-50 text-red-600 hover:bg-red-100 font-medium"
                      >
                        Dismiss (Not Relevant)
                      </button>
                      {signal.handled ? (
                        <button
                          onClick={(e) => { e.stopPropagation(); unhandleSignal(signal.id) }}
                          className="text-xs px-3 py-1.5 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 font-medium"
                        >
                          Unmark Handled
                        </button>
                      ) : (
                        <button
                          onClick={(e) => { e.stopPropagation(); handleSignal(signal.id) }}
                          className="text-xs px-3 py-1.5 rounded bg-green-50 text-green-700 hover:bg-green-100 font-medium"
                        >
                          Mark as Handled
                        </button>
                      )}

                      {/* Feedback — thumbs up / down */}
                      <div className="ml-auto flex items-center gap-1">
                        {feedbackGiven[signal.id] ? (
                          <span className="text-xs text-gray-500 italic">
                            {feedbackGiven[signal.id] === 'up' ? '👍' : '👎'} Thanks!
                          </span>
                        ) : (
                          <>
                            <span className="text-xs text-gray-400 mr-1">Rate:</span>
                            <button
                              onClick={(e) => { e.stopPropagation(); submitFeedback(signal.id, 'up') }}
                              className="text-lg hover:scale-125 transition-transform"
                              title="Useful signal"
                            >👍</button>
                            <button
                              onClick={(e) => { e.stopPropagation(); submitFeedback(signal.id, 'down') }}
                              className="text-lg hover:scale-125 transition-transform"
                              title="Not useful"
                            >👎</button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
