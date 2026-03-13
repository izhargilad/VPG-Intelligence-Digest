import React, { useState, useEffect } from 'react'

const API = '/api'

export default function MeetingPrep() {
  const [accounts, setAccounts] = useState([])
  const [brief, setBrief] = useState(null)
  const [loading, setLoading] = useState(true)
  const [briefLoading, setBriefLoading] = useState(false)

  useEffect(() => {
    fetch(`${API}/accounts`)
      .then(r => r.json())
      .then(d => { setAccounts(d.accounts || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const generateBrief = (key) => {
    setBriefLoading(true)
    setBrief(null)
    fetch(`${API}/accounts/${key}/meeting-brief`)
      .then(r => r.json())
      .then(d => { setBrief(d); setBriefLoading(false) })
      .catch(() => setBriefLoading(false))
  }

  if (loading) return <div className="p-6 text-gray-500">Loading accounts...</div>

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-vpg-navy">Meeting Prep Briefs</h2>
        <p className="text-sm text-gray-500">Auto-generated account intelligence for strategic target accounts</p>
      </div>

      {/* Account Cards */}
      <div className="grid grid-cols-2 gap-4">
        {accounts.map(acc => (
          <div key={acc.key} className="bg-white rounded-lg shadow-sm p-5 hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-bold text-vpg-navy">{acc.name}</h3>
                <p className="text-sm text-gray-500">{acc.industry}</p>
                <p className="text-xs text-gray-400 mt-1">{acc.relationship}</p>
                <div className="flex gap-1 mt-2 flex-wrap">
                  {(acc.relevant_bus || []).map(bu => (
                    <span key={bu} className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">{bu}</span>
                  ))}
                </div>
              </div>
              <button
                onClick={() => generateBrief(acc.key)}
                className="bg-vpg-accent text-white px-3 py-1.5 rounded text-sm font-medium whitespace-nowrap"
              >
                Generate Brief
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Brief Display */}
      {briefLoading && <div className="p-6 text-gray-500">Generating meeting brief...</div>}
      {brief && !brief.error && (
        <div className="bg-white rounded-lg shadow-sm border-2 border-vpg-blue">
          {/* Brief Header */}
          <div className="bg-vpg-navy text-white p-6 rounded-t-lg">
            <div className="text-xs uppercase tracking-wider opacity-70">Meeting Prep Brief</div>
            <h3 className="text-xl font-bold mt-1">{brief.account?.name}</h3>
            <div className="text-sm opacity-80">{brief.account?.industry} | {brief.account?.relationship}</div>
          </div>

          <div className="p-6 space-y-6">
            {/* Summary Stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-blue-50 rounded p-3 text-center">
                <div className="text-2xl font-bold text-vpg-blue">{brief.summary?.signals_found || 0}</div>
                <div className="text-xs text-gray-500">Account Signals</div>
              </div>
              <div className="bg-gray-50 rounded p-3 text-center">
                <div className="text-2xl font-bold text-gray-700">{brief.summary?.industry_signals || 0}</div>
                <div className="text-xs text-gray-500">Industry Signals</div>
              </div>
              <div className="bg-red-50 rounded p-3 text-center">
                <div className="text-2xl font-bold text-red-600">{brief.summary?.competitor_mentions || 0}</div>
                <div className="text-xs text-gray-500">Competitor Mentions</div>
              </div>
            </div>

            {/* VPG Solutions */}
            <div>
              <h4 className="font-semibold text-vpg-navy mb-3">VPG Solution Mapping</h4>
              <div className="grid gap-3">
                {(brief.vpg_solutions || []).map((sol, i) => (
                  <div key={i} className="border rounded p-3 bg-green-50 border-green-200">
                    <div className="font-medium text-green-800">{sol.bu_name}</div>
                    <div className="text-sm text-gray-700">{sol.product_fit}</div>
                    <div className="text-xs text-gray-500 mt-1">{(sol.key_products || []).join(', ')}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Talking Points */}
            <div>
              <h4 className="font-semibold text-vpg-navy mb-3">Talking Points</h4>
              <div className="space-y-3">
                {(brief.talking_points || []).map((tp, i) => (
                  <div key={i} className="border-l-4 border-vpg-accent pl-3 py-2">
                    <div className="text-xs font-semibold text-gray-500 uppercase">{tp.category}</div>
                    <div className="text-sm font-medium">{tp.point}</div>
                    {tp.detail && <div className="text-xs text-gray-500 mt-1">{tp.detail}</div>}
                    {tp.action && <div className="text-xs text-vpg-blue mt-1 font-medium">Action: {tp.action}</div>}
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Account Signals */}
            {(brief.recent_signals || []).length > 0 && (
              <div>
                <h4 className="font-semibold text-vpg-navy mb-3">Recent Account Intelligence</h4>
                <div className="space-y-2">
                  {brief.recent_signals.map((s, i) => (
                    <div key={i} className="flex items-start gap-3 text-sm border-b pb-2">
                      <span className="bg-vpg-blue text-white rounded px-2 py-0.5 text-xs font-bold mt-0.5">
                        {(s.score_composite || 0).toFixed(1)}
                      </span>
                      <div className="flex-1">
                        <div className="font-medium">{s.headline}</div>
                        <div className="text-xs text-gray-500 mt-0.5">{s.what_summary?.slice(0, 150)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Competitor Activity */}
            {(brief.competitor_activity || []).length > 0 && (
              <div>
                <h4 className="font-semibold text-vpg-navy mb-3">Competitor Activity in This Space</h4>
                {brief.competitor_activity.map((ca, i) => (
                  <div key={i} className="mb-3">
                    <div className="font-medium text-red-700 text-sm">{ca.competitor}</div>
                    {(ca.signals || []).map((s, j) => (
                      <div key={j} className="text-xs text-gray-600 ml-3 mt-1">
                        • {s.headline} ({new Date(s.collected_at).toLocaleDateString()})
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="border-t p-4 text-xs text-gray-400 text-center">
            Generated {new Date(brief.generated_at).toLocaleString()} | VPG Intelligence Digest
          </div>
        </div>
      )}
    </div>
  )
}
