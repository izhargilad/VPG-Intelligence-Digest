import React, { useEffect, useState } from 'react'

export default function BusinessUnits() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null)
  const [editForm, setEditForm] = useState({})

  const load = () => {
    fetch('/api/business-units')
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const startEdit = (bu) => {
    setEditing(bu.id)
    setEditForm({
      core_industries: bu.core_industries?.join(', ') || '',
      key_competitors: bu.key_competitors?.join(', ') || '',
      monitoring_keywords: bu.monitoring_keywords?.join(', ') || '',
    })
  }

  const saveEdit = async (buId) => {
    await fetch(`/api/business-units/${buId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        core_industries: editForm.core_industries.split(',').map(s => s.trim()).filter(Boolean),
        key_competitors: editForm.key_competitors.split(',').map(s => s.trim()).filter(Boolean),
        monitoring_keywords: editForm.monitoring_keywords.split(',').map(s => s.trim()).filter(Boolean),
      }),
    })
    setEditing(null)
    load()
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>

  const bus = data?.business_units || []

  return (
    <div>
      <h2 className="text-2xl font-bold text-vpg-navy mb-6">Business Units</h2>

      <div className="space-y-4">
        {bus.map(bu => (
          <div key={bu.id} className="bg-white rounded-lg shadow-sm overflow-hidden">
            <div className="flex items-center gap-4 px-6 py-4 border-b" style={{ borderLeftWidth: 4, borderLeftColor: bu.color || '#2E75B6' }}>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-vpg-navy">{bu.name}</h3>
                <p className="text-xs text-gray-500">{bu.description}</p>
              </div>
              <span className="inline-block w-6 h-6 rounded" style={{ backgroundColor: bu.color || '#2E75B6' }}></span>
              <button
                onClick={() => editing === bu.id ? setEditing(null) : startEdit(bu)}
                className="text-xs text-vpg-blue hover:underline"
              >
                {editing === bu.id ? 'Cancel' : 'Edit'}
              </button>
            </div>

            {editing === bu.id ? (
              <div className="p-6 bg-gray-50 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1 uppercase">Core Industries (comma-separated)</label>
                  <textarea
                    value={editForm.core_industries}
                    onChange={e => setEditForm({ ...editForm, core_industries: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                    rows={2}
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1 uppercase">Key Competitors (comma-separated)</label>
                  <textarea
                    value={editForm.key_competitors}
                    onChange={e => setEditForm({ ...editForm, key_competitors: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                    rows={2}
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1 uppercase">Monitoring Keywords (comma-separated)</label>
                  <textarea
                    value={editForm.monitoring_keywords}
                    onChange={e => setEditForm({ ...editForm, monitoring_keywords: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                    rows={3}
                  />
                </div>
                <button
                  onClick={() => saveEdit(bu.id)}
                  className="bg-vpg-navy text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-gray-800"
                >
                  Save Changes
                </button>
              </div>
            ) : (
              <div className="px-6 py-4 space-y-3">
                <div>
                  <span className="text-xs font-semibold text-gray-500 uppercase">Products: </span>
                  <span className="text-sm text-gray-700">{bu.key_products?.join(', ')}</span>
                </div>
                <div>
                  <span className="text-xs font-semibold text-gray-500 uppercase">Industries: </span>
                  <span className="text-sm text-gray-700">{bu.core_industries?.join(', ')}</span>
                </div>
                <div>
                  <span className="text-xs font-semibold text-gray-500 uppercase">Competitors: </span>
                  <span className="text-sm text-gray-700">{bu.key_competitors?.join(', ') || 'None specified'}</span>
                </div>
                <div>
                  <span className="text-xs font-semibold text-gray-500 uppercase">Keywords: </span>
                  <span className="text-xs text-gray-500">{bu.monitoring_keywords?.length || 0} configured</span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
