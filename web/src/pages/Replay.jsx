import { useState, useEffect, useMemo } from 'react'
import { api, CAUSE_COLORS, fmtDuration, fmtCause } from '../api.js'
import { MapView } from '../components/MapView.jsx'
import { MetricCard, Spinner, SectionHeader } from '../components/UI.jsx'

const priorityBadge = p => {
  if (!p) return 'muted'
  return p.toLowerCase() === 'high' ? 'red' : p.toLowerCase() === 'medium' ? 'amber' : 'green'
}

export function Replay({ date }) {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading]     = useState(false)
  const [sliderVal, setSliderVal] = useState(100)
  const [sortKey, setSortKey]     = useState('start_datetime')

  useEffect(() => {
    if (!date) return
    setLoading(true)
    api.incidents(date)
      .then(r => { setIncidents(r.incidents); setSliderVal(r.incidents.length) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [date])

  const visible = useMemo(() => {
    const n = Math.max(1, sliderVal)
    return incidents.slice(0, n)
  }, [incidents, sliderVal])

  // Stats
  const high    = visible.filter(r => r.priority === 'High').length
  const unplann = visible.filter(r => r.event_type === 'unplanned').length
  const avgDur  = visible.length
    ? visible.reduce((s, r) => s + (r.duration_minutes || 0), 0) / visible.filter(r => r.duration_minutes).length
    : 0

  if (loading) return <Spinner text="Loading incidents…" />

  return (
    <div className="page-enter">
      <SectionHeader
        title="Live Replay — Bengaluru Traffic Incidents"
        sub={`Stepping through ${date} — ${incidents.length} events recorded`}
      />

      {/* Timeline slider */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="slider-wrap">
          <label>Timeline — showing {sliderVal} of {incidents.length} incidents</label>
          <input
            type="range" min={1} max={Math.max(incidents.length, 1)}
            value={sliderVal}
            onChange={e => setSliderVal(+e.target.value)}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--muted)', fontFamily: 'monospace' }}>
            <span>{incidents[0]?.start_datetime?.slice(11,16) || '00:00'}</span>
            <span>{incidents[sliderVal - 1]?.start_datetime?.slice(11,16) || '--:--'}</span>
            <span>{incidents[incidents.length - 1]?.start_datetime?.slice(11,16) || '23:59'}</span>
          </div>
        </div>
      </div>

      {/* Map */}
      <div className="chart-wrap" style={{ marginBottom: 16 }}>
        <MapView incidents={visible} height={480} />
      </div>

      {/* Stats row */}
      <div className="grid-4" style={{ marginBottom: 20 }}>
        <MetricCard value={visible.length} label="Incidents shown" />
        <MetricCard value={unplann} label="Unplanned" color="red" />
        <MetricCard value={high} label="High priority" color="red" />
        <MetricCard value={isNaN(avgDur) ? '—' : Math.round(avgDur)} label="Avg duration (min)" />
      </div>

      {/* Table */}
      <SectionHeader title="Events at this timestamp" />
      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Cause</th>
              <th>Priority</th>
              <th>Corridor</th>
              <th>Duration</th>
              <th>Address</th>
            </tr>
          </thead>
          <tbody>
            {[...visible].reverse().slice(0, 25).map((r, i) => (
              <tr key={r.id || i}>
                <td style={{ fontFamily: 'monospace', fontSize: 12 }}>
                  {r.start_datetime?.slice(11, 16) || '—'}
                </td>
                <td>
                  <span className="cause-dot" style={{ background: CAUSE_COLORS[r.event_cause] || '#6E6E69' }} />
                  {fmtCause(r.event_cause)}
                </td>
                <td>
                  <span className={`badge badge-${priorityBadge(r.priority)}`}>
                    {r.priority || '—'}
                  </span>
                </td>
                <td style={{ color: 'var(--muted)', fontSize: 12 }}>{r.corridor || '—'}</td>
                <td style={{ fontFamily: 'monospace' }}>{fmtDuration(r.duration_minutes)}</td>
                <td style={{ color: 'var(--muted)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {r.address?.slice(0, 50) || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
