export function MetricCard({ value, label, color }) {
  return (
    <div className="metric-card">
      <div className={`metric-val${color ? ` ${color}` : ''}`}>{value ?? '—'}</div>
      <div className="metric-lbl">{label}</div>
    </div>
  )
}

export function Spinner({ text = 'Loading…' }) {
  return (
    <div className="spinner-wrap">
      <div className="spinner" />
      <span>{text}</span>
    </div>
  )
}

export function EmptyState({ icon = '📭', message = 'No data available' }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">{icon}</div>
      <div>{message}</div>
    </div>
  )
}

export function Badge({ children, variant = 'muted' }) {
  return <span className={`badge badge-${variant}`}>{children}</span>
}

export function Divider() {
  return <div className="divider" />
}

export function SectionHeader({ title, sub }) {
  return (
    <div className="section-header">
      <h2>{title}</h2>
      {sub && <p>{sub}</p>}
    </div>
  )
}
