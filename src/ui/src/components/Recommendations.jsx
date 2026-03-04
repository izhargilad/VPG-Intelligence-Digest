import React, { useState, useEffect } from 'react'

const API = '/api'

const PRIORITY_STYLES = {
  1: { bg: 'bg-red-50 border-red-300', badge: 'bg-red-600 text-white', label: 'Critical' },
  2: { bg: 'bg-amber-50 border-amber-300', badge: 'bg-amber-500 text-white', label: 'High' },
  3: { bg: 'bg-blue-50 border-blue-300', badge: 'bg-blue-500 text-white', label: 'Medium' },
}

const TYPE_LABELS = {
  'cross-bu': 'Cross-BU',
  'high-impact': 'Priority Action',
  'coverage-gap': 'Coverage Gap',
  'trend-alert': 'Trend Alert',
  'keyword-action': 'Keyword Action',
}

export default function Recommendations() {
  const [data, setData] = useState(null)
  const [patterns, setPatterns] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('recommendations')

  useEffect(() => {
    Promise.all([
      fetch(`${API}/recommendations`).then(r => r.json()).catch(() => null),
      fetch(`${API}/patterns`).then(r => r.json()).catch(() => null),
    ]).then(([recs, pats]) => {
      setData(recs)
      setPatterns(pats)
      setLoading(false)
    })
  }, [])

  if (loading) return <div className="p-6 text-gray-500">Loading recommendations...</div>

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-1">AI Recommendations & Pattern Detection</h2>
        <p className="text-sm text-gray-500">
          Strategic recommendations generated from signal patterns, trends, and coverage analysis
        </p>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-2">
        {['recommendations', 'patterns'].map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab ? 'bg-vpg-navy text-white' : 'bg-white text-gray-700 hover:bg-gray-50'
            }`}>
            {tab === 'recommendations' ? `Recommendations (${data?.recommendations?.length || 0})` : `Patterns (${patterns?.total_patterns || 0})`}
          </button>
        ))}
      </div>

      {activeTab === 'recommendations' && data && (
        <div className="space-y-4">
          {/* Summary */}
          {data.summary && (
            <div className="grid grid-cols-4 gap-3">
              {Object.entries(data.summary.by_type || {}).map(([type, count]) => (
                <div key={type} className="bg-white rounded-lg shadow-sm p-3 text-center">
                  <div className="text-lg font-bold text-gray-900">{count}</div>
                  <div className="text-xs text-gray-500">{TYPE_LABELS[type] || type}</div>
                </div>
              ))}
            </div>
          )}

          {/* Recommendation cards */}
          {(data.recommendations || []).map((rec, i) => {
            const ps = PRIORITY_STYLES[rec.priority] || PRIORITY_STYLES[3]
            return (
              <div key={i} className={`rounded-lg border-l-4 shadow-sm p-5 ${ps.bg}`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${ps.badge}`}>{ps.label}</span>
                      <span className="text-xs font-medium text-gray-500 bg-gray-200 px-2 py-0.5 rounded">
                        {TYPE_LABELS[rec.type] || rec.type}
                      </span>
                    </div>
                    <h3 className="font-semibold text-gray-900 mb-1">{rec.title}</h3>
                    <p className="text-sm text-gray-600 mb-3">{rec.description}</p>
                    <div className="bg-white/60 rounded p-3 border border-gray-200">
                      <span className="text-xs font-bold text-gray-500 uppercase">Recommended Action:</span>
                      <p className="text-sm text-gray-800 mt-1">{rec.action}</p>
                      {rec.owner && <p className="text-xs text-gray-500 mt-1">Owner: {rec.owner}</p>}
                    </div>
                  </div>
                  {rec.score > 0 && (
                    <div className="text-right flex-shrink-0">
                      <div className="text-2xl font-bold text-gray-800">{rec.score.toFixed(1)}</div>
                      <div className="text-xs text-gray-500">Score</div>
                    </div>
                  )}
                </div>
              </div>
            )
          })}

          {(!data.recommendations || data.recommendations.length === 0) && (
            <div className="bg-white rounded-lg shadow-sm p-8 text-center text-gray-500">
              No recommendations available yet. Run the pipeline to generate signal data.
            </div>
          )}
        </div>
      )}

      {activeTab === 'patterns' && patterns && (
        <div className="space-y-6">
          {/* Competitor patterns */}
          {patterns.competitor_patterns?.length > 0 && (
            <PatternSection title="Competitor Activity" items={patterns.competitor_patterns}
              renderItem={(p) => (
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-semibold text-gray-900">{p.competitor}</span>
                    <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
                      p.severity === 'high' ? 'bg-red-100 text-red-700' :
                      p.severity === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600'
                    }`}>{p.severity}</span>
                  </div>
                  <div className="text-right text-sm">
                    <div className="text-gray-900 font-medium">{p.signal_count} signals</div>
                    <div className="text-gray-500 text-xs">Avg score: {p.avg_score}</div>
                  </div>
                </div>
              )} />
          )}

          {/* Topic persistence */}
          {patterns.topic_persistence?.length > 0 && (
            <PatternSection title="Persistent Topics" items={patterns.topic_persistence}
              renderItem={(p) => (
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-semibold text-gray-900">{p.topic}</span>
                    <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
                      p.momentum === 'rising' ? 'bg-green-100 text-green-700' :
                      p.momentum === 'spike' ? 'bg-red-100 text-red-700' :
                      p.momentum === 'declining' ? 'bg-gray-100 text-gray-500' : 'bg-blue-100 text-blue-700'
                    }`}>{p.momentum}</span>
                    <span className="ml-1 text-xs text-gray-400">{p.persistence}</span>
                  </div>
                  <div className="text-right text-sm">
                    <div className="text-gray-900">{p.signal_count} signals / {p.weeks_active}w</div>
                    <div className="text-gray-500 text-xs">{p.wow_change > 0 ? '+' : ''}{p.wow_change}% WoW</div>
                  </div>
                </div>
              )} />
          )}

          {/* Score escalation */}
          {patterns.score_escalation?.length > 0 && (
            <PatternSection title="Score Escalation" items={patterns.score_escalation}
              renderItem={(p) => (
                <div>
                  <p className="text-sm text-gray-700">{p.summary}</p>
                  <div className="flex gap-4 mt-1 text-xs text-gray-500">
                    <span>Recent: {p.recent_count} signals</span>
                    <span>Historical: {p.historical_count} signals</span>
                  </div>
                </div>
              )} />
          )}

          {/* BU concentration */}
          {patterns.bu_concentration?.length > 0 && (
            <PatternSection title="BU Signal Distribution" items={patterns.bu_concentration}
              renderItem={(p) => (
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-semibold text-gray-900">{p.bu_name}</span>
                    <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
                      p.concentration === 'over-concentrated' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'
                    }`}>{p.concentration}</span>
                  </div>
                  <div className="text-sm text-gray-600">{p.signal_count} signals ({p.ratio}x avg)</div>
                </div>
              )} />
          )}

          {/* Source patterns */}
          {patterns.source_patterns?.length > 0 && (
            <PatternSection title="Source Performance" items={patterns.source_patterns}
              renderItem={(p) => (
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-semibold text-gray-900">{p.source_name}</span>
                    <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
                      p.performance === 'high-performer' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>{p.performance.replace('-', ' ')}</span>
                  </div>
                  <div className="text-sm text-gray-600">
                    {p.high_quality_rate}% quality | {p.signal_count} signals
                  </div>
                </div>
              )} />
          )}

          {patterns.total_patterns === 0 && (
            <div className="bg-white rounded-lg shadow-sm p-8 text-center text-gray-500">
              No patterns detected yet. More signal data is needed for pattern analysis.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function PatternSection({ title, items, renderItem }) {
  return (
    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
      <div className="px-5 py-3 bg-gray-50 border-b font-semibold text-gray-800">{title}</div>
      <div className="divide-y">
        {items.map((item, i) => (
          <div key={i} className="px-5 py-3">{renderItem(item)}</div>
        ))}
      </div>
    </div>
  )
}
