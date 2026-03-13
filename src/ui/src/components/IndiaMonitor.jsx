import React, { useState, useEffect } from 'react'

const API = '/api'

export default function IndiaMonitor() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API}/india/monitor`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6 text-gray-500">Loading India monitor data...</div>
  if (!data) return <div className="p-6 text-gray-500">Could not load India monitor data.</div>

  const { summary, india_signals, china_risk_signals, reshoring_signals, competitor_vulnerabilities, talking_points } = data

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-vpg-navy">India Production Advantage Monitor</h2>
          <p className="text-sm text-gray-500">Track trade signals, China risks & VPG India competitive positioning</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-green-500">
          <div className="text-2xl font-bold text-green-700">{summary?.total_relevant_signals || 0}</div>
          <div className="text-sm text-gray-500">Total Signals</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-orange-500">
          <div className="text-2xl font-bold text-orange-700">{summary?.india_specific || 0}</div>
          <div className="text-sm text-gray-500">India-Specific</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-red-500">
          <div className="text-2xl font-bold text-red-700">{summary?.china_risk || 0}</div>
          <div className="text-sm text-gray-500">China Risk</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-blue-500">
          <div className="text-2xl font-bold text-blue-700">{summary?.reshoring || 0}</div>
          <div className="text-sm text-gray-500">Reshoring</div>
        </div>
      </div>

      {/* Competitor Vulnerabilities */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="font-semibold text-vpg-navy mb-4">Competitor China Dependency Assessment</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-3 py-2 font-medium text-gray-600">Competitor</th>
                <th className="text-left px-3 py-2 font-medium text-gray-600">China Exposure</th>
                <th className="text-center px-3 py-2 font-medium text-gray-600">Risk Level</th>
                <th className="text-center px-3 py-2 font-medium text-gray-600">Recent Signals</th>
                <th className="text-left px-3 py-2 font-medium text-gray-600">VPG Advantage</th>
              </tr>
            </thead>
            <tbody>
              {(competitor_vulnerabilities || []).map((cv, i) => (
                <tr key={i} className="border-t">
                  <td className="px-3 py-2 font-medium">{cv.competitor}</td>
                  <td className="px-3 py-2 text-gray-600">{cv.china_exposure}</td>
                  <td className="px-3 py-2 text-center">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      cv.vulnerability_level === 'high' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                    }`}>{cv.vulnerability_level}</span>
                  </td>
                  <td className="px-3 py-2 text-center">{cv.recent_signal_count}</td>
                  <td className="px-3 py-2 text-xs text-gray-600">{cv.vpg_advantage}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Sales Talking Points */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="font-semibold text-vpg-navy mb-4">Sales Enablement Talking Points</h3>
        <div className="grid gap-4 md:grid-cols-2">
          {(talking_points || []).map((tp, i) => (
            <div key={i} className="border rounded-lg p-4 bg-green-50 border-green-200">
              <div className="font-semibold text-green-800 mb-1">{tp.title}</div>
              <p className="text-sm text-gray-700">{tp.point}</p>
              <div className="text-xs text-green-600 mt-2 italic">Use when: {tp.use_when}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Signal Lists */}
      {[
        { title: 'China Risk Signals', signals: china_risk_signals, color: 'red' },
        { title: 'Reshoring / Nearshoring Signals', signals: reshoring_signals, color: 'blue' },
        { title: 'India-Specific Signals', signals: india_signals, color: 'green' },
      ].map(({ title, signals, color }) => (signals || []).length > 0 && (
        <div key={title} className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="font-semibold text-vpg-navy mb-3">{title}</h3>
          <div className="space-y-2">
            {signals.slice(0, 8).map((s, i) => (
              <div key={i} className="flex items-center gap-3 text-sm border-b pb-2">
                <span className={`bg-${color}-500 text-white rounded px-2 py-0.5 text-xs font-bold`}>
                  {(s.score_composite || 0).toFixed(1)}
                </span>
                <span className="flex-1 truncate">{s.headline}</span>
                {s.url && <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-vpg-blue text-xs hover:underline">Source</a>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
