const NAV = [
  { id: 'landing',     icon: '🏠', label: 'Landing Page' },
  { id: 'replay',      icon: '🗺️',  label: 'Replay Mode' },
  { id: 'incident',    icon: '🔬', label: 'Incident Detail' },
  { id: 'calibration', icon: '📊', label: 'Calibration' },
  { id: 'whatif',      icon: '⚙️',  label: 'What-If' },
]

export function Sidebar({ page, onPage, dates, date, onDate, dayCount }) {
  return (
    <nav className="sidebar">
      <div className="sidebar-section">Navigation</div>

      {NAV.map(n => (
        <button
          key={n.id}
          className={`sidebar-item${page === n.id ? ' active' : ''}`}
          onClick={() => onPage(n.id)}
        >
          <span className="sidebar-icon">{n.icon}</span>
          {n.label}
        </button>
      ))}

      <div className="sidebar-divider" />
      <div className="sidebar-section">Select Day</div>

      <select
        className="sidebar-date-select"
        value={date}
        onChange={e => onDate(e.target.value)}
      >
        {dates.map(d => (
          <option key={d} value={d}>{d}</option>
        ))}
      </select>

      {dayCount != null && (
        <div className="sidebar-caption">{dayCount} incidents</div>
      )}
    </nav>
  )
}
