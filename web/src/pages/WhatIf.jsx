import { useState } from 'react'
import { api, CORRIDORS } from '../api.js'
import { CTMHeatmap } from '../components/CTMHeatmap.jsx'
import { MetricCard, Spinner, SectionHeader, Divider, EmptyState } from '../components/UI.jsx'

const CAP_MAP = { Low: 0.12, Medium: 0.35, High: 0.55 }

export function WhatIf() {
  const [corridor,  setCorridor]  = useState('ORR East 1')
  const [duration,  setDuration]  = useState(60)
  const [demand,    setDemand]    = useState(70)
  const [closure,   setClosure]   = useState(false)
  const [priority,  setPriority]  = useState('Medium')

  const [loading,   setLoading]   = useState(false)
  const [result,    setResult]    = useState(null)
  const [error,     setError]     = useState(null)

  const capLoss = closure ? 0.92 : CAP_MAP[priority]

  async function run() {
    setLoading(true); setError(null); setResult(null)
    try {
      const r = await api.whatif({
        corridor, duration_min: duration,
        capacity_loss: capLoss,
        upstream_demand_frac: demand / 100,
        requires_closure: closure,
        priority_high: priority === 'High',
      })
      setResult(r)
    } catch(e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-enter">
      <SectionHeader
        title="What-If Simulator"
        sub="Adjust incident parameters and re-run the CTM live"
      />

      <div className="grid-2" style={{ marginBottom: 20, alignItems: 'start' }}>
        {/* Controls */}
        <div className="whatif-controls">
          <div>
            <span className="field-label">Corridor</span>
            <select className="select-field" value={corridor} onChange={e => setCorridor(e.target.value)}>
              {CORRIDORS.map(c => <option key={c}>{c}</option>)}
            </select>
          </div>

          <div className="slider-wrap">
            <label>Predicted Duration — <strong>{duration} min</strong></label>
            <input type="range" min={5} max={480} value={duration} onChange={e => setDuration(+e.target.value)} />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--muted)', fontFamily: 'monospace' }}>
              <span>5 min</span><span>480 min (8h)</span>
            </div>
          </div>

          <div className="slider-wrap">
            <label>Upstream Demand — <strong>{demand}% of capacity</strong></label>
            <input type="range" min={20} max={95} value={demand} onChange={e => setDemand(+e.target.value)} />
          </div>

          <div>
            <span className="field-label">Priority Level</span>
            <div style={{ display: 'flex', gap: 8 }}>
              {['Low', 'Medium', 'High'].map(p => (
                <button
                  key={p}
                  onClick={() => setPriority(p)}
                  className="btn"
                  style={{
                    flex: 1, justifyContent: 'center',
                    background: priority === p ? 'var(--ink)' : 'var(--surface)',
                    color: priority === p ? '#fff' : 'var(--ink)',
                    border: '1px solid var(--line)',
                    fontSize: 12,
                  }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div className="toggle-row">
            <div>
              <div className="toggle-label">Requires Road Closure</div>
              <div className="toggle-sub">Full closure → 92% capacity loss</div>
            </div>
            <label className="toggle-switch">
              <input type="checkbox" checked={closure} onChange={e => setClosure(e.target.checked)} />
              <span className="toggle-track" />
            </label>
          </div>

          <Divider />

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <span className="field-label">Capacity Loss</span>
              <div style={{ fontSize: 22, fontWeight: 700, color: capLoss > 0.6 ? 'var(--red)' : 'var(--amber)' }}>
                {Math.round(capLoss * 100)}%
              </div>
            </div>
            <button className="btn btn-primary" onClick={run} disabled={loading} style={{ padding: '10px 24px' }}>
              {loading ? '⟳ Solving…' : '▶ Run Simulation'}
            </button>
          </div>
        </div>

        {/* Live results */}
        <div>
          {loading && <Spinner text="Solving LWR PDE via CTM…" />}
          {error && (
            <div style={{ color: 'var(--red)', padding: '12px 16px', background: 'var(--red-bg)', border: '1px solid var(--red-bd)', borderRadius: 6 }}>
              ⚠ {error}
            </div>
          )}
          {!loading && !result && !error && (
            <EmptyState icon="⚙️" message="Press 'Run Simulation' to compute traffic impact" />
          )}

          {result && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="grid-3">
                <MetricCard value={`${result.max_queue_km.toFixed(2)} km`} label="Max Queue" color="red" />
                <MetricCard value={`${Math.round(result.peak_queue_time_min)} min`} label="Peak at" color="amber" />
                <MetricCard value={`${Math.round(result.clearance_time_min)} min`} label="Clearance" color="green" />
              </div>
              <div className="grid-2">
                <MetricCard value={result.officers_recommended} label="Officers" />
                <MetricCard value={result.barricades_recommended} label="Barricades" />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* CTM heatmap */}
      {result && (
        <>
          <div className="chart-wrap">
            <CTMHeatmap
              data={{ ...result, incident_duration_min: duration }}
              title={`Space-Time Diagram — ${corridor} — ${duration} min incident`}
            />
          </div>

          {result.diversion_routes?.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div className="field-label" style={{ marginBottom: 8 }}>Diversion Routes</div>
              {result.diversion_routes.map((route, i) => (
                <div key={i} className="route-code">
                  Route {i + 1}: {route.join(' → ')}{route.length >= 10 ? ' …' : ''}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
