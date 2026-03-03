import React, { useEffect, useState } from 'react'

export default function Keywords() {
  const [keywords, setKeywords] = useState([])
  const [industries, setIndustries] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [showBulk, setShowBulk] = useState(false)
  const [filterIndustry, setFilterIndustry] = useState('')
  const [form, setForm] = useState({ keyword: '', industry_id: '', bu_id: '' })
  const [bulkForm, setBulkForm] = useState({ keywords: '', industry_id: '' })
  const [saving, setSaving] = useState(false)

  const load = () => {
    const url = filterIndustry
      ? `/api/keywords?industry_id=${filterIndustry}`
      : '/api/keywords'

    Promise.all([
      fetch(url).then(r => r.json()),
      fetch('/api/industries').then(r => r.json()),
    ])
      .then(([kwData, indData]) => {
        setKeywords(kwData.keywords || [])
        setIndustries(indData.industries || [])
      })
      .finally(() => setLoading(false))
  }

  useEffect(load, [filterIndustry])

  const industryMap = {}
  industries.forEach(ind => { industryMap[ind.id] = ind.name })

  const handleAdd = async () => {
    if (!form.keyword.trim()) return
    setSaving(true)
    await fetch('/api/keywords', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        keyword: form.keyword.trim(),
        industry_id: form.industry_id || null,
        bu_id: form.bu_id || null,
        source: 'manual',
      }),
    })
    setSaving(false)
    setForm({ keyword: '', industry_id: form.industry_id, bu_id: '' })
    load()
  }

  const handleBulkImport = async () => {
    if (!bulkForm.keywords.trim()) return
    setSaving(true)
    const kws = bulkForm.keywords.split(/[,\n]/).map(s => s.trim()).filter(Boolean)
    await fetch('/api/keywords/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        keywords: kws,
        industry_id: bulkForm.industry_id || null,
        source: 'imported',
      }),
    })
    setSaving(false)
    setBulkForm({ keywords: '', industry_id: bulkForm.industry_id })
    setShowBulk(false)
    load()
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this keyword?')) return
    await fetch(`/api/keywords/${id}`, { method: 'DELETE' })
    load()
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>

  // Group keywords by industry for display
  const grouped = {}
  keywords.forEach(kw => {
    const key = kw.industry_id || '_unassigned'
    if (!grouped[key]) grouped[key] = []
    grouped[key].push(kw)
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-vpg-navy">Keywords</h2>
          <p className="text-sm text-gray-500 mt-1">{keywords.length} keywords total</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setShowBulk(!showBulk); setShowForm(false) }}
            className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-200"
          >
            {showBulk ? 'Cancel' : 'Bulk Import'}
          </button>
          <button
            onClick={() => { setShowForm(!showForm); setShowBulk(false) }}
            className="bg-vpg-blue text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            {showForm ? 'Cancel' : '+ Add Keyword'}
          </button>
        </div>
      </div>

      {/* Filter */}
      <div className="bg-white rounded-lg shadow-sm p-4 mb-4">
        <label className="text-xs font-semibold text-gray-600 mr-2">Filter by Industry:</label>
        <select
          value={filterIndustry}
          onChange={e => setFilterIndustry(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
        >
          <option value="">All Industries</option>
          {industries.map(ind => (
            <option key={ind.id} value={ind.id}>{ind.name}</option>
          ))}
        </select>
      </div>

      {/* Add Single Keyword */}
      {showForm && (
        <div className="bg-white rounded-lg shadow-sm p-6 mb-4">
          <h3 className="text-sm font-semibold text-vpg-navy mb-4 uppercase">Add Keyword</h3>
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Keyword</label>
              <input
                value={form.keyword}
                onChange={e => setForm({ ...form, keyword: e.target.value })}
                placeholder="e.g. humanoid robot"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                onKeyDown={e => e.key === 'Enter' && handleAdd()}
              />
            </div>
            <div className="w-48">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Industry</label>
              <select
                value={form.industry_id}
                onChange={e => setForm({ ...form, industry_id: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
              >
                <option value="">None</option>
                {industries.map(ind => (
                  <option key={ind.id} value={ind.id}>{ind.name}</option>
                ))}
              </select>
            </div>
            <button
              onClick={handleAdd}
              disabled={saving || !form.keyword.trim()}
              className="bg-vpg-navy text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-gray-800 disabled:opacity-50"
            >
              Add
            </button>
          </div>
        </div>
      )}

      {/* Bulk Import */}
      {showBulk && (
        <div className="bg-white rounded-lg shadow-sm p-6 mb-4">
          <h3 className="text-sm font-semibold text-vpg-navy mb-4 uppercase">Bulk Import Keywords</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Assign to Industry</label>
              <select
                value={bulkForm.industry_id}
                onChange={e => setBulkForm({ ...bulkForm, industry_id: e.target.value })}
                className="w-64 border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
              >
                <option value="">None (unassigned)</option>
                {industries.map(ind => (
                  <option key={ind.id} value={ind.id}>{ind.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                Keywords (one per line, or comma-separated)
              </label>
              <textarea
                value={bulkForm.keywords}
                onChange={e => setBulkForm({ ...bulkForm, keywords: e.target.value })}
                placeholder="humanoid robot&#10;cobot&#10;robotic gripper&#10;force sensing"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none font-mono"
                rows={6}
              />
            </div>
            <button
              onClick={handleBulkImport}
              disabled={saving || !bulkForm.keywords.trim()}
              className="bg-vpg-navy text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-gray-800 disabled:opacity-50"
            >
              {saving ? 'Importing...' : 'Import Keywords'}
            </button>
          </div>
        </div>
      )}

      {/* Keywords grouped by industry */}
      {Object.entries(grouped).map(([industryId, kws]) => (
        <div key={industryId} className="bg-white rounded-lg shadow-sm mb-4 overflow-hidden">
          <div className="px-6 py-3 bg-gray-50 border-b flex items-center justify-between">
            <h3 className="text-sm font-semibold text-vpg-navy">
              {industryId === '_unassigned' ? 'Unassigned' : (industryMap[industryId] || industryId)}
            </h3>
            <span className="text-xs text-gray-500">{kws.length} keywords</span>
          </div>
          <div className="px-6 py-4 flex flex-wrap gap-2">
            {kws.map(kw => (
              <span
                key={kw.id}
                className={`inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border ${
                  kw.active ? 'bg-blue-50 text-blue-800 border-blue-200' : 'bg-gray-100 text-gray-400 border-gray-200 line-through'
                }`}
              >
                {kw.keyword}
                {kw.hit_count > 0 && (
                  <span className="text-[10px] bg-blue-200 text-blue-800 px-1.5 py-0.5 rounded-full ml-1">
                    {kw.hit_count}
                  </span>
                )}
                <button
                  onClick={() => handleDelete(kw.id)}
                  className="text-gray-400 hover:text-red-500 ml-0.5"
                  title="Delete keyword"
                >
                  x
                </button>
              </span>
            ))}
          </div>
        </div>
      ))}

      {keywords.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          No keywords found. Add keywords manually or import them in bulk.
        </div>
      )}
    </div>
  )
}
