import { useState, useEffect } from 'react'
import { api } from './api.js'
import { TopBar }     from './components/TopBar.jsx'
import { Sidebar }    from './components/Sidebar.jsx'
import { Landing }    from './pages/Landing.jsx'
import { Replay }     from './pages/Replay.jsx'
import { Incident }   from './pages/Incident.jsx'
import { Calibration }from './pages/Calibration.jsx'
import { WhatIf }     from './pages/WhatIf.jsx'

export default function App() {
  const [page,    setPage]    = useState('landing')
  const [dates,   setDates]   = useState([])
  const [date,    setDate]    = useState(null)
  const [stats,   setStats]   = useState(null)
  const [dayCount,setDayCount]= useState(null)

  // Load dates + global stats on mount
  useEffect(() => {
    api.dates()
      .then(r => {
        const ds = r.dates
        setDates(ds)
        // Default to middle day for richer data
        const mid = ds[Math.floor(ds.length / 2)] || ds[0]
        setDate(mid)
      })
      .catch(console.error)

    api.stats().then(setStats).catch(console.error)
  }, [])

  // Keep dayCount in sync when date changes
  useEffect(() => {
    if (!date) return
    api.incidents(date)
      .then(r => setDayCount(r.count))
      .catch(() => setDayCount(null))
  }, [date])

  if (page === 'landing') {
    return <Landing onNavigate={setPage} />
  }

  const pages = { replay: Replay, incident: Incident, calibration: Calibration, whatif: WhatIf }
  const PageComponent = pages[page] || Replay

  return (
    <div className="app-shell page-enter">
      <TopBar stats={stats} onNavigate={setPage} />
      <div className="app-body">
        <Sidebar
          page={page} onPage={setPage}
          dates={dates} date={date || ''} onDate={setDate}
          dayCount={dayCount}
        />
        <main className="main-content">
          <PageComponent date={date} />
        </main>
      </div>
    </div>
  )
}
