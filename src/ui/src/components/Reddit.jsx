import React, { useEffect, useState } from 'react'

export default function Reddit() {
  const [subs, setSubs] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [newSub, setNewSub] = useState({ name: '', category: '', notes: '' })
  const [editId, setEditId] = useState(null)
  const [editData, setEditData] = useState({})

  const load = () => {
    setLoading(true)
    fetch('/api/reddit/subreddits')
      .then(r => r.json())
      .then(d => setSubs(d.subreddits || []))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const addSub = async () => {
    if (!newSub.name.trim()) return
    const resp = await fetch('/api/reddit/subreddits', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newSub),
    })
    if (resp.ok) {
      setNewSub({ name: '', category: '', notes: '' })
      setShowAdd(false)
      load()
    } else {
      const err = await resp.json()
      alert(err.detail || 'Failed to add subreddit')
    }
  }

  const toggleActive = async (sub) => {
    await fetch(`/api/reddit/subreddits/${sub.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active: !sub.active }),
    })
    load()
  }

  const saveSub = async (id) => {
    await fetch(`/api/reddit/subreddits/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editData),
    })
    setEditId(null)
    load()
  }

  const deleteSub = async (id) => {
    if (!confirm('Remove this subreddit from monitoring?')) return
    await fetch(`/api/reddit/subreddits/${id}`, { method: 'DELETE' })
    load()
  }

  // Group by category
  const grouped = {}
  subs.forEach(s => {
    const cat = s.category || 'Uncategorized'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(s)
  })

  const activeCount = subs.filter(s => s.active).length

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-vpg-navy">Reddit Monitoring</h2>
          <p className="text-sm text-gray-500 mt-1">
            {activeCount} active / {subs.length} total subreddits
          </p>
        </div>
        <button onClick={() => setShowAdd(!showAdd)}
          className="bg-vpg-blue text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700">
          + Add Subreddit
        </button>
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="bg-white rounded-lg shadow-sm p-5 mb-6">
          <h3 className="text-sm font-semibold text-vpg-navy mb-3">Add New Subreddit</h3>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div>
              <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Subreddit Name</label>
              <div className="flex items-center gap-1">
                <span className="text-sm text-gray-400">r/</span>
                <input type="text" value={newSub.name}
                  onChange={e => setNewSub({ ...newSub, name: e.target.value })}
                  placeholder="subredditname"
                  className="flex-1 border rounded px-2 py-1.5 text-xs" />
              </div>
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Category</label>
              <input type="text" value={newSub.category}
                onChange={e => setNewSub({ ...newSub, category: e.target.value })}
                placeholder="e.g. Robotics & Automation"
                className="w-full border rounded px-2 py-1.5 text-xs" />
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Notes</label>
              <input type="text" value={newSub.notes}
                onChange={e => setNewSub({ ...newSub, notes: e.target.value })}
                placeholder="Optional notes"
                className="w-full border rounded px-2 py-1.5 text-xs" />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={addSub}
              className="bg-vpg-blue text-white px-4 py-1.5 rounded text-xs font-medium hover:bg-blue-700">
              Add
            </button>
            <button onClick={() => setShowAdd(false)}
              className="bg-gray-100 text-gray-600 px-4 py-1.5 rounded text-xs font-medium hover:bg-gray-200">
              Cancel
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading subreddits...</div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([category, catSubs]) => (
            <div key={category} className="bg-white rounded-lg shadow-sm overflow-hidden">
              <div className="px-5 py-3 bg-gray-50 border-b">
                <span className="font-semibold text-vpg-navy">{category}</span>
                <span className="text-xs text-gray-400 ml-2">{catSubs.length} subreddits</span>
              </div>
              <div className="divide-y">
                {catSubs.map(sub => (
                  <div key={sub.id} className={`px-5 py-3 flex items-center gap-4 ${!sub.active ? 'opacity-50' : ''}`}>
                    {editId === sub.id ? (
                      <>
                        <div className="flex-1 grid grid-cols-3 gap-2">
                          <input type="text" value={editData.category ?? sub.category}
                            onChange={e => setEditData({ ...editData, category: e.target.value })}
                            placeholder="Category"
                            className="border rounded px-2 py-1 text-xs" />
                          <input type="text" value={editData.notes ?? sub.notes}
                            onChange={e => setEditData({ ...editData, notes: e.target.value })}
                            placeholder="Notes"
                            className="border rounded px-2 py-1 text-xs" />
                        </div>
                        <div className="flex gap-1">
                          <button onClick={() => saveSub(sub.id)}
                            className="text-xs px-2 py-1 bg-green-50 text-green-700 rounded hover:bg-green-100">Save</button>
                          <button onClick={() => setEditId(null)}
                            className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded hover:bg-gray-200">Cancel</button>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-vpg-navy">r/{sub.name}</span>
                            <span className={`text-[9px] px-1.5 py-0.5 rounded font-semibold ${
                              sub.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                            }`}>
                              {sub.active ? 'ACTIVE' : 'DISABLED'}
                            </span>
                          </div>
                          {sub.notes && <p className="text-xs text-gray-400 mt-0.5">{sub.notes}</p>}
                        </div>
                        <div className="flex gap-1 flex-shrink-0">
                          <button onClick={() => toggleActive(sub)}
                            className={`text-xs px-2 py-1 rounded font-medium ${
                              sub.active
                                ? 'bg-yellow-50 text-yellow-700 hover:bg-yellow-100'
                                : 'bg-green-50 text-green-700 hover:bg-green-100'
                            }`}>
                            {sub.active ? 'Disable' : 'Enable'}
                          </button>
                          <button onClick={() => { setEditId(sub.id); setEditData({ category: sub.category, notes: sub.notes }) }}
                            className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100">
                            Edit
                          </button>
                          <button onClick={() => deleteSub(sub.id)}
                            className="text-xs px-2 py-1 bg-red-50 text-red-600 rounded hover:bg-red-100">
                            Remove
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
