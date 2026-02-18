import React, { useState } from 'react'
import Dashboard from './components/Dashboard'
import Recipients from './components/Recipients'
import Sources from './components/Sources'
import BusinessUnits from './components/BusinessUnits'
import Pipeline from './components/Pipeline'
import Digests from './components/Digests'
import Trends from './components/Trends'

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: '📊' },
  { id: 'pipeline', label: 'Run Digest', icon: '▶' },
  { id: 'recipients', label: 'Recipients', icon: '📧' },
  { id: 'sources', label: 'Sources', icon: '🔗' },
  { id: 'business-units', label: 'Business Units', icon: '🏢' },
  { id: 'trends', label: 'Trends', icon: '📈' },
  { id: 'digests', label: 'Digest History', icon: '📰' },
]

export default function App() {
  const [activePage, setActivePage] = useState('dashboard')

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard': return <Dashboard />
      case 'pipeline': return <Pipeline />
      case 'recipients': return <Recipients />
      case 'sources': return <Sources />
      case 'business-units': return <BusinessUnits />
      case 'trends': return <Trends />
      case 'digests': return <Digests />
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
            v1.0
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6 flex gap-6">
        {/* Sidebar */}
        <nav className="w-56 flex-shrink-0">
          <div className="bg-white rounded-lg shadow-sm overflow-hidden">
            {NAV_ITEMS.map(item => (
              <button
                key={item.id}
                onClick={() => setActivePage(item.id)}
                className={`w-full text-left px-4 py-3 text-sm font-medium flex items-center gap-3 transition-colors
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
        </nav>

        {/* Main Content */}
        <main className="flex-1 min-w-0">
          {renderPage()}
        </main>
      </div>
    </div>
  )
}
