import React, { useState, useEffect } from 'react'

const API = '/api'

export default function Events() {
  const [data, setData] = useState(null)
  const [intelPack, setIntelPack] = useState(null)
  const [loading, setLoading] = useState(true)
  const [packLoading, setPackLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ id: '', name: '', start_date: '', end_date: '', location: '', description: '', relevant_bus: '', key_topics: '', competitors_attending: '', vpg_presence: '', prep_weeks_before: 4 })

  const load = () => {
    fetch(`${API}/events`).then(r => r.json()).then(d => { setData(d); setLoading(false) }).catch(() => setLoading(false))
  }

  useEffect(load, [])

  const generatePack = (eventId) => {
    setPackLoading(true)
    setIntelPack(null)
    fetch(`${API}/events/${eventId}/intel-pack`)
      .then(r => r.json())
      .then(d => { setIntelPack(d); setPackLoading(false) })
      .catch(() => setPackLoading(false))
  }

  const addEvent = () => {
    const payload = {
      ...form,
      relevant_bus: form.relevant_bus.split(',').map(s => s.trim()).filter(Boolean),
      key_topics: form.key_topics.split(',').map(s => s.trim()).filter(Boolean),
      competitors_attending: form.competitors_attending.split(',').map(s => s.trim()).filter(Boolean),
      prep_weeks_before: parseInt(form.prep_weeks_before) || 4,
    }
    fetch(`${API}/events`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      .then(() => { setShowForm(false); load() })
  }

  const deleteEvent = (id) => {
    if (!confirm(`Delete event ${id}?`)) return
    fetch(`${API}/events/${id}`, { method: 'DELETE' }).then(load)
  }

  if (loading) return <div className="p-6 text-gray-500">Loading events...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-vpg-navy">Events & Intel Packs</h2>
        <button onClick={() => setShowForm(!showForm)} className="bg-vpg-blue text-white px-4 py-2 rounded text-sm font-medium">
          + Add Event
        </button>
      </div>

      {/* Upcoming Events Alert */}
      {(data?.upcoming || []).filter(e => e.needs_prep).length > 0 && (
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-4">
          <div className="font-semibold text-amber-800">Events Needing Prep</div>
          {data.upcoming.filter(e => e.needs_prep).map(e => (
            <div key={e.id} className="text-sm text-amber-700 mt-1">
              <strong>{e.name}</strong> — {e.days_until} days away ({e.start_date})
              <button onClick={() => generatePack(e.id)} className="ml-2 text-vpg-blue underline text-xs">
                Generate Intel Pack
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add Event Form */}
      {showForm && (
        <div className="bg-white rounded-lg shadow-sm p-6 space-y-4">
          <h3 className="font-semibold text-vpg-navy">New Event</h3>
          <div className="grid grid-cols-2 gap-4">
            <input placeholder="Event ID (slug)" value={form.id} onChange={e => setForm({...form, id: e.target.value})} className="border rounded px-3 py-2 text-sm" />
            <input placeholder="Event Name" value={form.name} onChange={e => setForm({...form, name: e.target.value})} className="border rounded px-3 py-2 text-sm" />
            <input type="date" placeholder="Start Date" value={form.start_date} onChange={e => setForm({...form, start_date: e.target.value})} className="border rounded px-3 py-2 text-sm" />
            <input type="date" placeholder="End Date" value={form.end_date} onChange={e => setForm({...form, end_date: e.target.value})} className="border rounded px-3 py-2 text-sm" />
            <input placeholder="Location" value={form.location} onChange={e => setForm({...form, location: e.target.value})} className="border rounded px-3 py-2 text-sm" />
            <input placeholder="VPG Presence (e.g. Exhibitor)" value={form.vpg_presence} onChange={e => setForm({...form, vpg_presence: e.target.value})} className="border rounded px-3 py-2 text-sm" />
            <input placeholder="Relevant BUs (comma-separated IDs)" value={form.relevant_bus} onChange={e => setForm({...form, relevant_bus: e.target.value})} className="border rounded px-3 py-2 text-sm col-span-2" />
            <input placeholder="Key Topics (comma-separated)" value={form.key_topics} onChange={e => setForm({...form, key_topics: e.target.value})} className="border rounded px-3 py-2 text-sm col-span-2" />
            <input placeholder="Competitors Attending (comma-separated)" value={form.competitors_attending} onChange={e => setForm({...form, competitors_attending: e.target.value})} className="border rounded px-3 py-2 text-sm col-span-2" />
          </div>
          <div className="flex gap-2">
            <button onClick={addEvent} className="bg-vpg-blue text-white px-4 py-2 rounded text-sm">Save</button>
            <button onClick={() => setShowForm(false)} className="bg-gray-200 text-gray-700 px-4 py-2 rounded text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Events List */}
      <div className="grid gap-4">
        {(data?.events || []).map(event => (
          <div key={event.id} className="bg-white rounded-lg shadow-sm p-5">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-bold text-vpg-navy text-lg">{event.name}</h3>
                <p className="text-sm text-gray-500">{event.description}</p>
                <div className="flex gap-4 mt-2 text-sm text-gray-600">
                  <span>{event.start_date} — {event.end_date}</span>
                  <span>{event.location}</span>
                  {event.vpg_presence && <span className="text-vpg-blue font-medium">{event.vpg_presence}</span>}
                </div>
                <div className="flex gap-2 mt-2 flex-wrap">
                  {(event.relevant_bus || []).map(bu => (
                    <span key={bu} className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">{bu}</span>
                  ))}
                  {(event.key_topics || []).map(t => (
                    <span key={t} className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">{t}</span>
                  ))}
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={() => generatePack(event.id)} className="bg-vpg-accent text-white px-3 py-1.5 rounded text-sm font-medium">
                  Intel Pack
                </button>
                <button onClick={() => deleteEvent(event.id)} className="text-red-500 text-sm hover:underline">
                  Delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Intel Pack Display */}
      {packLoading && <div className="p-6 text-gray-500">Generating intelligence pack...</div>}
      {intelPack && !intelPack.error && (
        <div className="bg-white rounded-lg shadow-sm p-6 space-y-6 border-2 border-vpg-blue">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-bold text-vpg-navy">Intel Pack: {intelPack.event?.name}</h3>
            <span className="text-xs text-gray-400">{intelPack.generated_at}</span>
          </div>

          {/* Summary */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-blue-50 rounded p-3 text-center">
              <div className="text-2xl font-bold text-vpg-blue">{intelPack.summary?.signals_found || 0}</div>
              <div className="text-xs text-gray-500">Relevant Signals</div>
            </div>
            <div className="bg-amber-50 rounded p-3 text-center">
              <div className="text-2xl font-bold text-amber-600">{intelPack.summary?.competitors_tracked || 0}</div>
              <div className="text-xs text-gray-500">Competitors Tracked</div>
            </div>
            <div className="bg-green-50 rounded p-3 text-center">
              <div className="text-2xl font-bold text-green-600">{intelPack.summary?.meeting_targets || 0}</div>
              <div className="text-xs text-gray-500">Meeting Targets</div>
            </div>
          </div>

          {/* Talking Points */}
          <div>
            <h4 className="font-semibold text-vpg-navy mb-3">Talking Points</h4>
            <div className="space-y-2">
              {(intelPack.talking_points || []).map((tp, i) => (
                <div key={i} className={`border-l-4 pl-3 py-2 ${tp.priority === 'high' ? 'border-red-400' : tp.priority === 'medium' ? 'border-amber-400' : 'border-gray-300'}`}>
                  <div className="text-xs font-semibold text-gray-500 uppercase">{tp.category}</div>
                  <div className="text-sm">{tp.point}</div>
                  {tp.action && <div className="text-xs text-vpg-blue mt-1">Action: {tp.action}</div>}
                </div>
              ))}
            </div>
          </div>

          {/* Competitor Intel */}
          {(intelPack.competitor_intel || []).length > 0 && (
            <div>
              <h4 className="font-semibold text-vpg-navy mb-3">Competitor Intelligence</h4>
              {intelPack.competitor_intel.map((ci, i) => (
                <div key={i} className="mb-3 bg-red-50 rounded p-3">
                  <div className="font-medium text-red-800">{ci.competitor} ({ci.signal_count} signals, avg {ci.avg_score})</div>
                  {ci.recent_signals.slice(0, 2).map((s, j) => (
                    <div key={j} className="text-sm text-gray-600 mt-1">• {s.headline}</div>
                  ))}
                </div>
              ))}
            </div>
          )}

          {/* Relevant Signals */}
          {(intelPack.relevant_signals || []).length > 0 && (
            <div>
              <h4 className="font-semibold text-vpg-navy mb-3">Top Signals</h4>
              <div className="space-y-2">
                {intelPack.relevant_signals.slice(0, 8).map((s, i) => (
                  <div key={i} className="flex items-center gap-3 text-sm border-b pb-2">
                    <span className="bg-vpg-blue text-white rounded px-2 py-0.5 text-xs font-bold">{(s.score_composite || 0).toFixed(1)}</span>
                    <span className="flex-1 truncate">{s.headline}</span>
                    <span className="text-xs text-gray-400 capitalize">{(s.signal_type || '').replace(/-/g, ' ')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
