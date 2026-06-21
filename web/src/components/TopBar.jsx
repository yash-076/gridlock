// Animated traffic-light signal bar (from reference.html)
export function Signal() {
  return (
    <div className="signal">
      <i className="red" />
      <i className="amber" />
      <i className="green" />
    </div>
  )
}

export function TopBar({ stats, onNavigate }) {
  return (
    <header className="topbar">
      <div 
        className="topbar-brand" 
        onClick={() => onNavigate && onNavigate('landing')} 
        style={{ cursor: 'pointer' }}
        title="Go to Landing Page"
      >
        <Signal />
        <div className="brand-logo">
          <span>GR</span>
          <span className="logo-dots">
            <i className="red" />
            <i className="amber" />
            <i className="green" />
          </span>
          <span>DLOCK</span>
        </div>
        <div className="topbar-tag">[ predict → simulate → recommend ]</div>
      </div>

      <div className="topbar-right">
        {stats && (
          <>
            <span className="topbar-stat">
              <strong>{stats.total_incidents?.toLocaleString()}</strong> incidents
            </span>
            <span className="topbar-stat" style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
            <span className="topbar-stat">
              avg <strong>{stats.avg_duration_min} min</strong>
            </span>
            <span className="topbar-stat" style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
            <span className="topbar-stat">
              <strong style={{ color: 'var(--red)' }}>{stats.high_priority_count}</strong> high-priority
            </span>
          </>
        )}
        <span className="pill" style={{ fontSize: '10px' }}>Bengaluru Traffic Police</span>
      </div>
    </header>
  )
}
