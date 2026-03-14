import React, { useState, useEffect } from 'react'

export default function BattleCards() {
  const [cards, setCards] = useState({})
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/battle-cards')
      .then(r => r.json())
      .then(d => {
        setCards(d.battle_cards || {})
        const keys = Object.keys(d.battle_cards || {})
        if (keys.length) setSelected(keys[0])
      })
      .catch(() => setCards({}))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Loading battle cards...</div>

  const card = selected ? cards[selected] : null

  const activityColors = {
    high: 'bg-red-100 text-red-800',
    medium: 'bg-yellow-100 text-yellow-800',
    low: 'bg-green-100 text-green-800',
    none: 'bg-gray-100 text-gray-600',
  }

  const priorityColors = {
    urgent: 'bg-red-100 text-red-800 border-red-200',
    proactive: 'bg-blue-100 text-blue-800 border-blue-200',
    opportunistic: 'bg-green-100 text-green-800 border-green-200',
    standard: 'bg-gray-100 text-gray-700 border-gray-200',
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Competitive Battle Cards</h2>
        <p className="text-sm text-gray-500 mt-1">Auto-updated positioning guides with counter-messaging</p>
      </div>

      {/* Competitor tabs */}
      <div className="flex gap-2 flex-wrap">
        {Object.entries(cards).map(([key, c]) => (
          <button
            key={key}
            onClick={() => setSelected(key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              selected === key
                ? 'bg-vpg-navy text-white'
                : 'bg-white text-gray-700 hover:bg-gray-50 shadow-sm'
            }`}
          >
            {c.competitor}
            <span className={`ml-2 px-1.5 py-0.5 rounded text-xs ${
              activityColors[c.signal_patterns?.activity_level || 'none']
            }`}>
              {c.summary?.total_signals || 0}
            </span>
          </button>
        ))}
      </div>

      {card && (
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          {/* Header */}
          <div className="bg-vpg-navy text-white px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold">{card.competitor}</h3>
                <p className="text-sm text-blue-300">
                  {card.profile?.segments?.join(' | ')}
                </p>
              </div>
              <div className="text-right">
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                  activityColors[card.signal_patterns?.activity_level || 'none']
                }`}>
                  {card.signal_patterns?.activity_level?.toUpperCase()} ACTIVITY
                </span>
                <p className="text-xs text-blue-300 mt-1">
                  Trend: {card.signal_patterns?.trend || 'N/A'}
                </p>
              </div>
            </div>
          </div>

          <div className="p-6 space-y-6">
            {/* Strengths / Weaknesses / VPG Advantages */}
            <div className="grid grid-cols-3 gap-4">
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Their Strengths</h4>
                <ul className="text-sm text-gray-600 space-y-1">
                  {card.profile?.strengths?.map((s, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-red-400 mt-0.5">-</span> {s}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Their Weaknesses</h4>
                <ul className="text-sm text-gray-600 space-y-1">
                  {card.profile?.weaknesses?.map((w, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-green-500 mt-0.5">+</span> {w}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-vpg-blue mb-2">VPG Advantages</h4>
                <ul className="text-sm text-gray-600 space-y-1">
                  {card.vpg_advantages?.map((a, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-vpg-accent font-bold mt-0.5">*</span> {a}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Counter Messaging */}
            {card.counter_messaging?.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-3">Counter-Messaging Playbook</h4>
                <div className="space-y-2">
                  {card.counter_messaging.map((msg, i) => (
                    <div key={i} className={`p-3 rounded border ${priorityColors[msg.priority] || priorityColors.standard}`}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-semibold uppercase">{msg.priority}</span>
                        <span className="text-sm font-medium">{msg.scenario}</span>
                      </div>
                      <p className="text-sm text-gray-700">{msg.message}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recent Intelligence */}
            {card.recent_intelligence?.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Recent Intelligence</h4>
                <div className="space-y-2">
                  {card.recent_intelligence.map((sig, i) => (
                    <div key={i} className="flex items-center gap-3 p-2 bg-gray-50 rounded text-sm">
                      <span className="px-2 py-0.5 bg-gray-200 rounded text-xs">{sig.signal_type}</span>
                      <span className="flex-1 truncate">{sig.headline}</span>
                      <span className="text-gray-400 text-xs">{sig.date}</span>
                      <span className="font-medium">{sig.score}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Affected BUs */}
            <div className="flex items-center gap-2 pt-2 border-t">
              <span className="text-xs font-semibold text-gray-500">AFFECTED BUs:</span>
              {card.affected_bus?.map((bu, i) => (
                <span key={i} className="px-2 py-0.5 bg-vpg-navy/10 text-vpg-navy rounded text-xs font-medium">
                  {bu}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
