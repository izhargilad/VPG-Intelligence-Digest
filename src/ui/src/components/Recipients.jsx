import React, { useEffect, useState } from 'react'

export default function Recipients() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', email: '', role: '', notes: '' })
  const [saving, setSaving] = useState(false)

  const load = () => {
    fetch('/api/recipients')
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleAdd = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await fetch('/api/recipients', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      setForm({ name: '', email: '', role: '', notes: '' })
      setShowForm(false)
      load()
    } finally {
      setSaving(false)
    }
  }

  const toggleStatus = async (id, currentStatus) => {
    const newStatus = currentStatus === 'active' ? 'inactive' : 'active'
    await fetch(`/api/recipients/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus }),
    })
    load()
  }

  const handleDelete = async (id, name) => {
    if (!confirm(`Remove ${name} from recipients?`)) return
    await fetch(`/api/recipients/${id}`, { method: 'DELETE' })
    load()
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>

  const recipients = data?.recipients || []
  const settings = data?.delivery_settings || {}

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-vpg-navy">Recipients</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-vpg-blue text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          {showForm ? 'Cancel' : '+ Add Recipient'}
        </button>
      </div>

      {/* Add Form */}
      {showForm && (
        <form onSubmit={handleAdd} className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h3 className="text-lg font-semibold text-vpg-navy mb-4">Add New Recipient</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
              <input
                required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email *</label>
              <input
                required type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
              <input
                value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
                placeholder="e.g., VP Sales"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
              <input
                value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-vpg-blue focus:outline-none"
              />
            </div>
          </div>
          <button
            type="submit" disabled={saving}
            className="mt-4 bg-vpg-navy text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-gray-800 disabled:opacity-50"
          >
            {saving ? 'Adding...' : 'Add Recipient'}
          </button>
        </form>
      )}

      {/* Recipients List */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Name</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Email</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Role</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Status</th>
              <th className="text-right px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody>
            {recipients.map(r => (
              <tr key={r.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="px-4 py-3 text-sm font-medium text-gray-900">{r.name}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{r.email}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{r.role}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${
                    r.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {r.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => toggleStatus(r.id, r.status)}
                    className="text-xs text-vpg-blue hover:underline mr-3"
                  >
                    {r.status === 'active' ? 'Deactivate' : 'Activate'}
                  </button>
                  <button
                    onClick={() => handleDelete(r.id, r.name)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {recipients.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No recipients configured</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Delivery Settings */}
      <div className="bg-white rounded-lg shadow-sm p-6 mt-6">
        <h3 className="text-lg font-semibold text-vpg-navy mb-3">Delivery Schedule</h3>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Send Day:</span>
            <span className="ml-2 font-medium">{settings.send_day}</span>
          </div>
          <div>
            <span className="text-gray-500">Send Time:</span>
            <span className="ml-2 font-medium">{settings.send_time_et} ET</span>
          </div>
          <div>
            <span className="text-gray-500">Timezone:</span>
            <span className="ml-2 font-medium">{settings.timezone}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
