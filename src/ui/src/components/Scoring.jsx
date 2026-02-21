import React, { useEffect, useState } from 'react'

const DIM_INFO = {
  revenue_impact: { label: 'Revenue Impact', color: 'bg-green-500' },
  time_sensitivity: { label: 'Time Sensitivity', color: 'bg-yellow-500' },
  strategic_alignment: { label: 'Strategic Alignment', color: 'bg-blue-500' },
  competitive_pressure: { label: 'Competitive Pressure', color: 'bg-red-500' },
}

export default function Scoring() {
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  // Local editable state
  const [thresholds, setThresholds] = useState({})
  const [weights, setWeights] = useState({})

  useEffect(() => {
    fetch('/api/scoring')
      .then(r => r.json())
      .then(data => {
        setConfig(data)
        setThresholds({ ...data.thresholds })
        const w = {}
        for (const [key, dim] of Object.entries(data.scoring_dimensions || {})) {
          w[key] = dim.weight
        }
        setWeights(w)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const handleSave = () => {
    setSaving(true)
    setSaved(false)
    setError(null)

    const updated = { ...config }
    updated.thresholds = { ...thresholds }
    for (const [key, weight] of Object.entries(weights)) {
      if (updated.scoring_dimensions[key]) {
        updated.scoring_dimensions[key].weight = weight
      }
    }

    fetch('/api/scoring', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updated),
    })
      .then(r => {
        if (!r.ok) throw new Error('Failed to save scoring configuration')
        return r.json()
      })
      .then(data => {
        setConfig(data)
        setSaved(true)
        setTimeout(() => setSaved(false), 3000)
      })
      .catch(e => setError(e.message))
      .finally(() => setSaving(false))
  }

  const updateThreshold = (key, value) => {
    setThresholds(prev => ({ ...prev, [key]: parseFloat(value) || 0 }))
  }

  const updateWeight = (key, value) => {
    setWeights(prev => ({ ...prev, [key]: parseFloat(value) || 0 }))
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading scoring configuration...</div>

  const totalWeight = Object.values(weights).reduce((sum, w) => sum + w, 0)
  const weightBalanced = Math.abs(totalWeight - 1.0) < 0.01

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-vpg-navy">Scoring Configuration</h2>
          <p className="text-sm text-gray-500 mt-1">
            Adjust thresholds and dimension weights to control which signals appear in the digest.
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-5 py-2.5 bg-vpg-blue text-white rounded-lg font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      {saved && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm font-medium">
          Scoring configuration saved successfully.
        </div>
      )}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          Error: {error}
        </div>
      )}

      {/* Thresholds */}
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 className="text-lg font-semibold text-vpg-navy mb-1">Signal Thresholds</h3>
        <p className="text-xs text-gray-500 mb-5">
          Signals are scored 1-10. Adjust these thresholds to control which signals are included, highlighted, or featured.
        </p>

        <div className="grid grid-cols-2 gap-6">
          <ThresholdSlider
            label="Include in Digest"
            description="Minimum composite score to include a signal in the weekly digest"
            value={thresholds.include_in_digest}
            onChange={v => updateThreshold('include_in_digest', v)}
            color="bg-vpg-blue"
          />
          <ThresholdSlider
            label="Highlight Signal"
            description="Score above which a signal gets highlighted with special styling"
            value={thresholds.highlight_signal}
            onChange={v => updateThreshold('highlight_signal', v)}
            color="bg-orange-500"
          />
          <ThresholdSlider
            label="Signal of the Week"
            description="Minimum score for the top signal featured in the subject line"
            value={thresholds.signal_of_week_minimum}
            onChange={v => updateThreshold('signal_of_week_minimum', v)}
            color="bg-red-500"
          />
          <ThresholdSlider
            label="Unverified Minimum"
            description="Minimum score to include a signal with fewer than 3 sources"
            value={thresholds.unverified_minimum}
            onChange={v => updateThreshold('unverified_minimum', v)}
            color="bg-yellow-500"
          />
        </div>
      </div>

      {/* Dimension Weights */}
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-lg font-semibold text-vpg-navy">Dimension Weights</h3>
          <span className={`text-xs font-bold px-2 py-1 rounded ${weightBalanced ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
            Total: {(totalWeight * 100).toFixed(0)}% {weightBalanced ? '' : '(should be 100%)'}
          </span>
        </div>
        <p className="text-xs text-gray-500 mb-5">
          Each signal is scored across four dimensions. Weights determine how much each dimension contributes to the composite score.
        </p>

        <div className="space-y-5">
          {Object.entries(DIM_INFO).map(([key, info]) => (
            <div key={key}>
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${info.color}`} />
                  <span className="text-sm font-medium text-gray-700">{info.label}</span>
                </div>
                <span className="text-sm font-bold text-vpg-navy">{((weights[key] || 0) * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="0.5"
                step="0.05"
                value={weights[key] || 0}
                onChange={e => updateWeight(key, e.target.value)}
                className="w-full h-2 rounded-lg appearance-none cursor-pointer accent-vpg-blue"
              />
              <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
                <span>0%</span>
                <span>50%</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Signal Types Reference */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-vpg-navy mb-4">Signal Types Reference</h3>
        <div className="grid grid-cols-2 gap-3">
          {(config?.signal_types || []).map(st => (
            <div key={st.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <span
                className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
                style={{ backgroundColor: st.color }}
              >
                {st.emoji}
              </span>
              <div>
                <div className="text-sm font-medium text-gray-800">{st.label}</div>
                <div className="text-xs text-gray-500">{st.action_template}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ThresholdSlider({ label, description, value, onChange, color }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min="0"
            max="10"
            step="0.5"
            value={value ?? 0}
            onChange={e => onChange(e.target.value)}
            className="w-16 text-right text-sm font-bold text-vpg-navy border border-gray-300 rounded px-2 py-1"
          />
          <span className="text-xs text-gray-400">/ 10</span>
        </div>
      </div>
      <input
        type="range"
        min="0"
        max="10"
        step="0.5"
        value={value ?? 0}
        onChange={e => onChange(e.target.value)}
        className="w-full h-2 rounded-lg appearance-none cursor-pointer accent-vpg-blue"
      />
      <p className="text-[11px] text-gray-400 mt-1">{description}</p>
    </div>
  )
}
