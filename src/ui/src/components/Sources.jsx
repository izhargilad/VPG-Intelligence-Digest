import React, { useEffect, useState } from 'react'

const TIER_LABELS = { 1: 'Tier 1 — Authority', 2: 'Tier 2 — Industry', 3: 'Tier 3 — Signal' }
const TIER_COLORS = { 1: 'bg-green-100 text-green-800', 2: 'bg-blue-100 text-blue-800', 3: 'bg-gray-100 text-gray-600' }
const SOURCE_TYPES = ['rss', 'scrape', 'api']

export default function Sources() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    name: '',
    url: '',
    type: 'rss',
    tier: 2,
    keywords: '',
    relevant_bus: '',
    is_competitor: false,
  })

  const load = () => {
    fetch('/api/sources')
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const toggleActive = async (id, currentActive) => {
    await fetch(`/api/sources/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active: !currentActive }),
    })
    load()
  }

  const handleDelete = async (id, name) => {
    if (!confirm(`Remove source "${name}"?`)) return
    await fetch(`/api/sources/${id}`, { method: 'DELETE' })
    load()
  }

  const handleAdd = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload = {
        name: form.name,
        url: form.url,
        type: form.type,
        tier: parseInt(form.tier),
        keywords: form.keywords ? form.keywords.split(',').map(k => k.trim()).filter(Boolean) : [],
        relevant_bus: form.relevant_bus ? form.relevant_bus.split(',').map(k => k.trim()).filter(Boolean) : [],
        is_competitor: form.is_competitor,
      }
      const res = await fetch('/api/sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (res.ok) {
        setForm({ name: '', url: '', type: 'rss', tier: 2, keywords: '', relevant_bus: '', is_competitor: false })
        setShowForm(false)
        load()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to add source')
      }
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>

  const sources = data?.sources || []
  const grouped = { 1: [], 2: [], 3: [] }
  sources.forEach(s => {
    const tier = s.tier || 2
    if (!grouped[tier]) grouped[tier] = []
    grouped[tier].push(s)
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-vpg-navy">Data Sources</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-vpg-blue text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          {showForm ? 'Cancel' : '+ Add Source'}
        </button>
      </div>

      {/* Add Source Form */}
      {showForm && (
        <form onSubmit={handleAdd} className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h3 className="text-lg font-semibold text-vpg-navy mb-4">Add New Data Source</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
              <input
                required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                placeholder="e.g., Automation World"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">URL *</label>
              <input
                required value={form.url} onChange={e => setForm({ ...form, url: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                placeholder="https://example.com/feed/"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
              <select
                value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
              >
                {SOURCE_TYPES.map(t => (
                  <option key={t} value={t}>{t.toUpperCase()}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Tier</label>
              <select
                value={form.tier} onChange={e => setForm({ ...form, tier: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
              >
                <option value={1}>Tier 1 — Authority</option>
                <option value={2}>Tier 2 — Industry</option>
                <option value={3}>Tier 3 — Signal</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Keywords</label>
              <input
                value={form.keywords} onChange={e => setForm({ ...form, keywords: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                placeholder="Comma-separated: sensor, robot, test"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Relevant BUs</label>
              <input
                value={form.relevant_bus} onChange={e => setForm({ ...form, relevant_bus: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                placeholder="Comma-separated: vpg-force-sensors, dts"
              />
            </div>
          </div>
          <label className="flex items-center gap-2 mt-3 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_competitor}
              onChange={e => setForm({ ...form, is_competitor: e.target.checked })}
              className="rounded"
            />
            <span className="text-sm text-gray-700">Competitor source</span>
          </label>
          <button
            type="submit" disabled={saving}
            className="mt-4 bg-vpg-navy text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-gray-800 disabled:opacity-50"
          >
            {saving ? 'Adding...' : 'Add Source'}
          </button>
        </form>
      )}

      {[1, 2, 3].map(tier => (
        grouped[tier]?.length > 0 && (
          <div key={tier} className="mb-8">
            <h3 className="text-lg font-semibold text-vpg-navy mb-3">
              <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold mr-2 ${TIER_COLORS[tier]}`}>
                {TIER_LABELS[tier]}
              </span>
              ({grouped[tier].length} sources)
            </h3>
            <div className="bg-white rounded-lg shadow-sm overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Name</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Type</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600 uppercase">URL</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Status</th>
                    <th className="text-right px-4 py-2 text-xs font-semibold text-gray-600 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {grouped[tier].map(s => (
                    <tr key={s.id} className="border-b last:border-0 hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">
                        {s.name}
                        {s.is_competitor && (
                          <span className="ml-2 text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded">Competitor</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
                          {s.type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 truncate max-w-xs">{s.url}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block w-2 h-2 rounded-full mr-1 ${s.active !== false ? 'bg-green-500' : 'bg-gray-300'}`}></span>
                        <span className="text-xs">{s.active !== false ? 'Active' : 'Disabled'}</span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => toggleActive(s.id, s.active !== false)}
                          className="text-xs text-vpg-blue hover:underline mr-3"
                        >
                          {s.active !== false ? 'Disable' : 'Enable'}
                        </button>
                        <button
                          onClick={() => handleDelete(s.id, s.name)}
                          className="text-xs text-red-600 hover:underline"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )
      ))}
    </div>
  )
}
