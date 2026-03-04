import React, { useEffect, useState } from 'react'

const SIGNAL_TYPE_LABELS = {
  'competitive-threat': { label: 'Competitive Threat', icon: '\u26A0', color: '#E53935' },
  'revenue-opportunity': { label: 'Revenue Opportunity', icon: '\uD83D\uDCB0', color: '#43A047' },
  'market-shift': { label: 'Market Shift', icon: '\uD83C\uDFAF', color: '#1E88E5' },
  'partnership-signal': { label: 'Partnership', icon: '\uD83E\uDD1D', color: '#7B1FA2' },
  'customer-intelligence': { label: 'Customer Intel', icon: '\uD83D\uDCCA', color: '#F57C00' },
  'technology-trend': { label: 'Tech Trend', icon: '\uD83D\uDE80', color: '#0097A7' },
  'trade-tariff': { label: 'Trade/Tariff', icon: '\uD83C\uDF0D', color: '#455A64' },
}

export default function Executive() {
  const [data, setData] = useState(null)
  const [trends, setTrends] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetch('/api/executive/bu-summary').then(r => r.json()),
      fetch('/api/trends?limit=10').then(r => r.json()),
    ])
      .then(([buData, trendData]) => {
        setData(buData)
        setTrends(trendData)
      })
      .finally(() => setLoading(false))
  }, [])

  const handleExport = (format) => {
    window.open(`/api/export/${format}`, '_blank')
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading executive dashboard...</div>

  if (!data) return (
    <div className="bg-white rounded-lg shadow-sm p-8 text-center text-gray-500">
      No data available. Run the pipeline first to generate intelligence.
    </div>
  )

  const summaries = data.bu_summaries || []
  const risingTrends = (trends?.rising || []).slice(0, 5)

  // Score distribution for summary bar
  const maxSignals = Math.max(...summaries.map(s => s.signal_count), 1)

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-vpg-navy">Executive Dashboard</h2>
          <p className="text-sm text-gray-500 mt-1">
            {data.total_signals} signals across {data.bus_with_signals} business units
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleExport('excel')}
            className="bg-green-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-green-700"
          >
            Export Excel
          </button>
          <button
            onClick={() => handleExport('pptx')}
            className="bg-vpg-accent text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-orange-600"
          >
            Export PPTX
          </button>
        </div>
      </div>

      {/* Top-level stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow-sm p-5 border-l-4 border-vpg-navy">
          <div className="text-3xl font-bold text-vpg-navy">{data.total_signals}</div>
          <div className="text-xs text-gray-500 uppercase tracking-wide mt-1">Total Scored Signals</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-5 border-l-4 border-vpg-blue">
          <div className="text-3xl font-bold text-vpg-blue">{data.overall_avg_score}</div>
          <div className="text-xs text-gray-500 uppercase tracking-wide mt-1">Average Score</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-5 border-l-4 border-vpg-accent">
          <div className="text-3xl font-bold text-vpg-accent">{data.bus_with_signals}/9</div>
          <div className="text-xs text-gray-500 uppercase tracking-wide mt-1">BUs with Active Signals</div>
        </div>
      </div>

      {/* BU Signal Breakdown */}
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 className="text-lg font-semibold text-vpg-navy mb-4">Business Unit Signal Breakdown</h3>
        <div className="space-y-4">
          {summaries.map(bu => (
            <div key={bu.bu_id} className="flex items-center gap-4">
              <div className="w-36 flex-shrink-0">
                <div className="text-sm font-medium text-vpg-navy">{bu.bu_short}</div>
                <div className="text-[10px] text-gray-400">{bu.signal_count} signals</div>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${(bu.signal_count / maxSignals) * 100}%`,
                        backgroundColor: bu.color || '#2E75B6',
                      }}
                    />
                  </div>
                  <span className={`text-sm font-bold w-10 text-right ${
                    bu.avg_score >= 8 ? 'text-green-600' :
                    bu.avg_score >= 6 ? 'text-vpg-blue' : 'text-gray-500'
                  }`}>
                    {bu.avg_score}
                  </span>
                </div>
              </div>
              <div className="w-48 flex gap-1 flex-shrink-0">
                {bu.top_types.map((t, i) => {
                  const config = SIGNAL_TYPE_LABELS[t.type] || { label: t.type, color: '#666' }
                  return (
                    <span key={i} className="text-[9px] px-1.5 py-0.5 rounded-full text-white"
                      style={{ backgroundColor: config.color }}
                      title={`${config.label}: ${t.count}`}
                    >
                      {config.icon} {t.count}
                    </span>
                  )
                })}
              </div>
            </div>
          ))}
          {summaries.length === 0 && (
            <div className="text-center py-6 text-gray-400 text-sm">
              No signal data available. Run the pipeline to collect and score signals.
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Top Signals */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-lg font-semibold text-vpg-navy mb-4">Top Signals by BU</h3>
          <div className="space-y-3">
            {summaries.filter(bu => bu.top_signal).map(bu => (
              <div key={bu.bu_id} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                <div className="w-3 h-3 rounded-full mt-1 flex-shrink-0"
                  style={{ backgroundColor: bu.color || '#2E75B6' }} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-gray-500 uppercase">{bu.bu_short}</div>
                  <div className="text-sm text-vpg-navy mt-0.5 truncate">
                    {bu.top_signal.headline}
                  </div>
                </div>
                <div className={`text-sm font-bold flex-shrink-0 ${
                  bu.top_signal.score >= 8 ? 'text-green-600' :
                  bu.top_signal.score >= 6 ? 'text-vpg-blue' : 'text-gray-500'
                }`}>
                  {bu.top_signal.score}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Rising Trends */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-lg font-semibold text-vpg-navy mb-4">Rising Trends</h3>
          {risingTrends.length > 0 ? (
            <div className="space-y-3">
              {risingTrends.map(trend => (
                <div key={trend.key} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold mr-2 ${
                      trend.momentum === 'spike' ? 'bg-red-600 text-white' : 'bg-orange-500 text-white'
                    }`}>
                      {trend.momentum.toUpperCase()}
                    </span>
                    <span className="text-sm font-medium text-vpg-navy">{trend.label}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold text-vpg-navy">{trend.count}</div>
                    <div className="text-[10px] text-green-600">
                      {trend.change_pct > 0 ? '+' : ''}{trend.change_pct}%
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6 text-gray-400 text-sm">
              No rising trends detected yet.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
