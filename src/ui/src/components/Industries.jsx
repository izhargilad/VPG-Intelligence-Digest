import React, { useEffect, useState } from 'react'

const PRIORITY_LABELS = { 1: 'High', 2: 'Medium', 3: 'Low' }
const PRIORITY_COLORS = { 1: '#E53935', 2: '#FB8C00', 3: '#9E9E9E' }

export default function Industries() {
  const [industries, setIndustries] = useState([])
  const [busUnits, setBusUnits] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({
    id: '', name: '', category: '', description: '',
    relevant_bus: '', keywords: '', priority: 2,
  })
  const [saving, setSaving] = useState(false)

  const load = () => {
    Promise.all([
      fetch('/api/industries').then(r => r.json()),
      fetch('/api/business-units').then(r => r.json()),
    ])
      .then(([indData, buData]) => {
        setIndustries(indData.industries || [])
        setBusUnits(buData.business_units || [])
      })
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const buNameMap = {}
  busUnits.forEach(bu => { buNameMap[bu.id] = bu.short_name || bu.name })

  const resetForm = () => {
    setForm({ id: '', name: '', category: '', description: '', relevant_bus: '', keywords: '', priority: 2 })
    setEditing(null)
    setShowForm(false)
  }

  const startEdit = (ind) => {
    setEditing(ind.id)
    setForm({
      id: ind.id,
      name: ind.name,
      category: ind.category || '',
      description: ind.description || '',
      relevant_bus: (ind.relevant_bus || []).join(', '),
      keywords: (ind.keywords || []).join(', '),
      priority: ind.priority || 2,
    })
    setShowForm(false)
  }

  const handleSave = async () => {
    setSaving(true)
    const payload = {
      id: form.id.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, ''),
      name: form.name,
      category: form.category,
      description: form.description,
      relevant_bus: form.relevant_bus.split(',').map(s => s.trim()).filter(Boolean),
      keywords: form.keywords.split(',').map(s => s.trim()).filter(Boolean),
      priority: parseInt(form.priority) || 2,
      active: true,
    }

    if (editing) {
      await fetch(`/api/industries/${editing}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: payload.name,
          category: payload.category,
          description: payload.description,
          relevant_bus: payload.relevant_bus,
          priority: payload.priority,
        }),
      })
    } else {
      await fetch('/api/industries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    }
    setSaving(false)
    resetForm()
    load()
  }

  const handleDelete = async (id) => {
    if (!confirm(`Delete industry "${id}"? Keywords linked to it will be unlinked.`)) return
    await fetch(`/api/industries/${id}`, { method: 'DELETE' })
    load()
  }

  const handleToggle = async (ind) => {
    await fetch(`/api/industries/${ind.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active: !ind.active }),
    })
    load()
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-vpg-navy">Industries</h2>
          <p className="text-sm text-gray-500 mt-1">{industries.length} industries configured</p>
        </div>
        <button
          onClick={() => { resetForm(); setShowForm(!showForm) }}
          className="bg-vpg-blue text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          {showForm ? 'Cancel' : '+ Add Industry'}
        </button>
      </div>

      {/* Add / Edit Form */}
      {(showForm || editing) && (
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h3 className="text-sm font-semibold text-vpg-navy mb-4 uppercase">
            {editing ? 'Edit Industry' : 'New Industry'}
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Name</label>
              <input
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value, id: editing ? form.id : e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-') })}
                placeholder="e.g. Robotics & Automation"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                disabled={!!editing}
              />
              {!editing && <p className="text-xs text-gray-400 mt-1">ID: {form.id || '(auto-generated)'}</p>}
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Category</label>
              <input
                value={form.category}
                onChange={e => setForm({ ...form, category: e.target.value })}
                placeholder="e.g. Manufacturing & Industrial"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Description</label>
              <input
                value={form.description}
                onChange={e => setForm({ ...form, description: e.target.value })}
                placeholder="Brief description of this industry vertical"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Relevant BUs (comma-separated IDs)</label>
              <input
                value={form.relevant_bus}
                onChange={e => setForm({ ...form, relevant_bus: e.target.value })}
                placeholder="vpg-force-sensors, dts"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
              />
              <p className="text-xs text-gray-400 mt-1">
                Available: {busUnits.map(b => b.id).join(', ')}
              </p>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Priority</label>
              <select
                value={form.priority}
                onChange={e => setForm({ ...form, priority: parseInt(e.target.value) })}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
              >
                <option value={1}>High (Tier 1)</option>
                <option value={2}>Medium (Tier 2)</option>
                <option value={3}>Low (Tier 3)</option>
              </select>
            </div>
            {!editing && (
              <div className="col-span-2">
                <label className="block text-xs font-semibold text-gray-600 mb-1">Initial Keywords (comma-separated)</label>
                <textarea
                  value={form.keywords}
                  onChange={e => setForm({ ...form, keywords: e.target.value })}
                  placeholder="robot, cobot, humanoid robot, robotic gripper"
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                  rows={2}
                />
              </div>
            )}
          </div>
          <div className="flex gap-3 mt-4">
            <button
              onClick={handleSave}
              disabled={saving || !form.name}
              className="bg-vpg-navy text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-gray-800 disabled:opacity-50"
            >
              {saving ? 'Saving...' : editing ? 'Save Changes' : 'Create Industry'}
            </button>
            <button
              onClick={resetForm}
              className="text-gray-600 px-4 py-2 rounded-lg text-sm hover:bg-gray-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Industries List */}
      <div className="space-y-3">
        {industries.map(ind => (
          <div key={ind.id} className={`bg-white rounded-lg shadow-sm overflow-hidden ${!ind.active ? 'opacity-60' : ''}`}>
            <div className="flex items-center gap-4 px-6 py-4"
              style={{ borderLeftWidth: 4, borderLeftColor: PRIORITY_COLORS[ind.priority] || '#9E9E9E' }}>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-semibold text-vpg-navy">{ind.name}</h3>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                    {ind.category}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-full"
                    style={{ backgroundColor: PRIORITY_COLORS[ind.priority] + '20', color: PRIORITY_COLORS[ind.priority] }}>
                    {PRIORITY_LABELS[ind.priority]} priority
                  </span>
                  {!ind.active && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-600">Disabled</span>
                  )}
                </div>
                {ind.description && (
                  <p className="text-xs text-gray-500 mt-1">{ind.description}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleToggle(ind)}
                  className={`text-xs px-3 py-1 rounded ${ind.active ? 'bg-gray-100 text-gray-600 hover:bg-gray-200' : 'bg-green-50 text-green-700 hover:bg-green-100'}`}
                >
                  {ind.active ? 'Disable' : 'Enable'}
                </button>
                <button
                  onClick={() => editing === ind.id ? resetForm() : startEdit(ind)}
                  className="text-xs text-vpg-blue hover:underline"
                >
                  {editing === ind.id ? 'Cancel' : 'Edit'}
                </button>
                <button
                  onClick={() => handleDelete(ind.id)}
                  className="text-xs text-red-500 hover:underline"
                >
                  Delete
                </button>
              </div>
            </div>

            {editing === ind.id ? (
              <div className="p-6 bg-gray-50 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1">Name</label>
                    <input
                      value={form.name}
                      onChange={e => setForm({ ...form, name: e.target.value })}
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1">Category</label>
                    <input
                      value={form.category}
                      onChange={e => setForm({ ...form, category: e.target.value })}
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                    />
                  </div>
                  <div className="col-span-2">
                    <label className="block text-xs font-semibold text-gray-600 mb-1">Description</label>
                    <input
                      value={form.description}
                      onChange={e => setForm({ ...form, description: e.target.value })}
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1">Relevant BUs (comma-separated)</label>
                    <input
                      value={form.relevant_bus}
                      onChange={e => setForm({ ...form, relevant_bus: e.target.value })}
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1">Priority</label>
                    <select
                      value={form.priority}
                      onChange={e => setForm({ ...form, priority: parseInt(e.target.value) })}
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                    >
                      <option value={1}>High</option>
                      <option value={2}>Medium</option>
                      <option value={3}>Low</option>
                    </select>
                  </div>
                </div>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="bg-vpg-navy text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-gray-800 disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            ) : (
              <div className="px-6 py-3 flex flex-wrap gap-4 text-sm">
                <div>
                  <span className="text-xs font-semibold text-gray-500 uppercase">BUs: </span>
                  {(ind.relevant_bus || []).length > 0
                    ? ind.relevant_bus.map(buId => (
                        <span key={buId} className="inline-block text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded mr-1">
                          {buNameMap[buId] || buId}
                        </span>
                      ))
                    : <span className="text-gray-400 text-xs">None</span>
                  }
                </div>
                <div>
                  <span className="text-xs font-semibold text-gray-500 uppercase">Keywords: </span>
                  <span className="text-xs text-gray-500">{ind.keyword_count || ind.keywords?.length || 0} configured</span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {industries.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          No industries configured. Click "+ Add Industry" to create one.
        </div>
      )}
    </div>
  )
}
