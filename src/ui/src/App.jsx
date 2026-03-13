import React, { useState } from 'react'
import Dashboard from './components/Dashboard'
import Executive from './components/Executive'
import Feed from './components/Feed'
import Recipients from './components/Recipients'
import Sources from './components/Sources'
import BusinessUnits from './components/BusinessUnits'
import Industries from './components/Industries'
import Keywords from './components/Keywords'
import Pipeline from './components/Pipeline'
import Digests from './components/Digests'
import Trends from './components/Trends'
import Scoring from './components/Scoring'
import Recommendations from './components/Recommendations'
import Reddit from './components/Reddit'
import Events from './components/Events'
import Feedback from './components/Feedback'
import IndiaMonitor from './components/IndiaMonitor'
import MonthlyReport from './components/MonthlyReport'
import MeetingPrep from './components/MeetingPrep'

const NAV_SECTIONS = [
  {
    label: 'Intelligence',
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: '📊' },
      { id: 'executive', label: 'Executive View', icon: '👔' },
      { id: 'feed', label: 'Intel Feed', icon: '📡' },
      { id: 'recommendations', label: 'Recommendations', icon: '💡' },
      { id: 'trends', label: 'Trends', icon: '📈' },
    ],
  },
  {
    label: 'Phase 3',
    items: [
      { id: 'events', label: 'Events & Intel Packs', icon: '🎪' },
      { id: 'india', label: 'India Monitor', icon: '🇮🇳' },
      { id: 'meeting-prep', label: 'Meeting Prep', icon: '🤝' },
      { id: 'monthly-report', label: 'Monthly Report', icon: '📋' },
      { id: 'feedback', label: 'Feedback & Scoring', icon: '👍' },
    ],
  },
  {
    label: 'Operations',
    items: [
      { id: 'pipeline', label: 'Run Digest', icon: '▶' },
      { id: 'recipients', label: 'Recipients', icon: '📧' },
      { id: 'sources', label: 'Sources', icon: '🔗' },
      { id: 'digests', label: 'Digest History', icon: '📰' },
    ],
  },
  {
    label: 'Configuration',
    items: [
      { id: 'business-units', label: 'Business Units', icon: '🏢' },
      { id: 'industries', label: 'Industries', icon: '🏭' },
      { id: 'keywords', label: 'Keywords', icon: '🔑' },
      { id: 'reddit', label: 'Reddit', icon: '🔴' },
      { id: 'scoring', label: 'Scoring', icon: '🎚' },
    ],
  },
]

export default function App() {
  const [activePage, setActivePage] = useState('dashboard')

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard': return <Dashboard />
      case 'executive': return <Executive />
      case 'feed': return <Feed />
      case 'recommendations': return <Recommendations />
      case 'pipeline': return <Pipeline />
      case 'recipients': return <Recipients />
      case 'sources': return <Sources />
      case 'business-units': return <BusinessUnits />
      case 'industries': return <Industries />
      case 'keywords': return <Keywords />
      case 'reddit': return <Reddit />
      case 'scoring': return <Scoring />
      case 'trends': return <Trends />
      case 'digests': return <Digests />
      case 'events': return <Events />
      case 'feedback': return <Feedback />
      case 'india': return <IndiaMonitor />
      case 'monthly-report': return <MonthlyReport />
      case 'meeting-prep': return <MeetingPrep />
      default: return <Dashboard />
    }
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-vpg-navy text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-wide">VPG Intelligence Digest</h1>
            <p className="text-sm text-blue-300">Management Console</p>
          </div>
          <div className="text-xs text-blue-400">
            v3.0
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6 flex gap-6">
        {/* Sidebar */}
        <nav className="w-56 flex-shrink-0">
          <div className="bg-white rounded-lg shadow-sm overflow-hidden">
            {NAV_SECTIONS.map(section => (
              <div key={section.label}>
                <div className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider bg-gray-50 border-t first:border-t-0">
                  {section.label}
                </div>
                {section.items.map(item => (
                  <button
                    key={item.id}
                    onClick={() => setActivePage(item.id)}
                    className={`w-full text-left px-4 py-2.5 text-sm font-medium flex items-center gap-3 transition-colors
                      ${activePage === item.id
                        ? 'bg-vpg-blue text-white'
                        : 'text-gray-700 hover:bg-gray-50'
                      }`}
                  >
                    <span>{item.icon}</span>
                    {item.label}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </nav>

        {/* Main Content */}
        <main className="flex-1 min-w-0">
          {renderPage()}
        </main>
      </div>
    </div>
  )
}
