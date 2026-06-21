import { useState, useEffect } from 'react'
import { api, CAUSE_COLORS, fmtDuration, fmtCause } from '../api.js'
import { CTMHeatmap } from '../components/CTMHeatmap.jsx'
import { MetricCard, Spinner, SectionHeader, Badge, Divider, EmptyState } from '../components/UI.jsx'

function pBadge(p) {
  if (!p) return 'muted'
  return p === 'High' ? 'red' : p === 'Medium' ? 'amber' : 'green'
}

export function Incident({ date }) {
  const [incidents, setIncidents] = useState([])
  const [selId, setSelId]         = useState(null)
  const [loading, setLoading]     = useState(false)
  const [simLoading, setSimLoading] = useState(false)
  const [prediction, setPrediction] = useState(null)
  const [simResult, setSimResult]   = useState(null)
  const [recResult, setRecResult]   = useState(null)
  const [error, setError]           = useState(null)

  // Load incidents for the selected day
  useEffect(() => {
    if (!date) return
    setLoading(true)
    setSimResult(null); setPrediction(null); setRecResult(null)
    api.incidents(date)
      .then(r => {
        setIncidents(r.incidents)
        setSelId(r.incidents[0]?.id ?? null)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [date])

  const row = incidents.find(r => r.id === selId) || incidents[0]

  // Run full pipeline when incident changes
  useEffect(() => {
    if (!row) return
    setSimLoading(true)
    setError(null)

    const predBody = {
      hour_of_day: row.hour_of_day ?? 8,
      day_of_week: row.day_of_week ?? 0,
      is_weekend:  row.is_weekend ?? 0,
      is_peak_hour: row.is_peak_hour ?? 0,
      month: row.month ?? 6,
      requires_road_closure_bin: row.requires_road_closure_bin ?? 0,
      priority_num: row.priority_num ?? 1,
      is_unplanned: row.is_unplanned ?? 1,
      location_cluster: row.location_cluster ?? 0,
      corridor_incident_7d: row.corridor_incident_7d ?? 0,
      corridor_incident_30d: row.corridor_incident_30d ?? 0,
      hist_avg_duration: row.hist_avg_duration ?? 60,
      event_cause_enc: row.event_cause_enc ?? 0,
      corridor_enc: row.corridor_enc ?? 0,
      zone_enc: row.zone_enc ?? 0,
      junction_enc: row.junction_enc ?? 0,
      veh_type_enc: row.veh_type_enc ?? 0,
    }

    api.predict(predBody)
      .then(pred => {
        setPrediction(pred)
        return api.simulate({
          corridor: row.corridor || 'Non-corridor',
          duration_min: pred.predicted_duration_min,
          capacity_loss: pred.predicted_capacity_loss,
          upstream_demand_frac: 0.70,
        })
      })
      .then(sim => {
        setSimResult(sim)
        return api.recommend({
          corridor: row.corridor || 'Non-corridor',
          predicted_duration_min: sim.incident_duration_min,
          predicted_capacity_loss: prediction?.predicted_capacity_loss ?? 0.35,
          max_queue_km: sim.max_queue_km,
          peak_queue_time_min: sim.peak_queue_time_min,
          clearance_time_min: sim.clearance_time_min,
          incident_cell: 12,
          requires_closure: String(row.requires_road_closure).toUpperCase() === 'TRUE',
          priority_high: row.priority === 'High',
        })
      })
      .then(setRecResult)
      .catch(e => setError(e.message))
      .finally(() => setSimLoading(false))
  }, [row?.id])

  if (loading) return <Spinner text="Loading incidents…" />

  return (
    <div className="page-enter">
      <SectionHeader title="Incident Detail — Full Pipeline" />

      {/* Incident selector */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center' }}>
        <label className="field-label" style={{ marginBottom: 0, whiteSpace: 'nowrap' }}>Select Incident</label>
        <select
          className="select-field"
          value={selId ?? ''}
          onChange={e => setSelId(e.target.value)}
        >
          {incidents.map(r => (
            <option key={r.id} value={r.id}>
              [{r.start_datetime?.slice(11,16)}] {fmtCause(r.event_cause)} — {r.corridor}
            </option>
          ))}
        </select>
      </div>

      {/* Incident card */}
      {row && (
        <div className="incident-meta" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <div className="incident-title">
                <span className="cause-dot" style={{ background: CAUSE_COLORS[row.event_cause] || '#6E6E69', width: 10, height: 10 }} />
                {fmtCause(row.event_cause)}
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                <Badge variant={pBadge(row.priority)}>{row.priority || '?'} Priority</Badge>
                <Badge variant={row.event_type === 'unplanned' ? 'red' : 'green'}>{row.event_type || 'unplanned'}</Badge>
                {row.requires_road_closure === 'true' && <Badge variant="red">Road Closed</Badge>}
              </div>
              <div className="incident-sub">{row.address?.slice(0, 80) || '—'}</div>
              <div className="incident-sub" style={{ fontFamily: 'monospace', marginTop: 4, fontSize: 11 }}>
                {row.corridor} · {row.zone} · {row.start_datetime?.slice(11,16)}
              </div>
            </div>
            {row.duration_minutes != null && (
              <MetricCard value={`${Math.round(row.duration_minutes)} min`} label="Actual Duration" />
            )}
          </div>
        </div>
      )}

      {/* ML Prediction */}
      {prediction && (
        <>
          <SectionHeader title="ML Prediction" sub="XGBoost model trained on 8,000+ historical incidents" />
          <div className="grid-2" style={{ marginBottom: 20 }}>
            <MetricCard
              value={`${Math.round(prediction.predicted_duration_min)} min`}
              label="Predicted Duration"
              color={prediction.predicted_duration_min > 120 ? 'red' : 'amber'}
            />
            <MetricCard
              value={`${Math.round(prediction.predicted_capacity_loss * 100)}%`}
              label="Capacity Loss"
              color={prediction.predicted_capacity_loss > 0.6 ? 'red' : 'amber'}
            />
          </div>
          <Divider />
        </>
      )}

      {/* CTM Simulation */}
      {simLoading && <Spinner text="Running Cell Transmission Model (LWR PDE)…" />}
      {error && (
        <div style={{ color: 'var(--red)', padding: '12px 16px', background: 'var(--red-bg)', border: '1px solid var(--red-bd)', borderRadius: 6, marginBottom: 16 }}>
          ⚠ {error}
        </div>
      )}

      {simResult && (
        <>
          <SectionHeader title="CTM Traffic Flow Simulation" sub="Godunov scheme — LWR kinematic wave PDE" />
          <div className="chart-wrap" style={{ marginBottom: 16 }}>
            <CTMHeatmap
              data={{ ...simResult, incident_duration_min: prediction?.predicted_duration_min }}
              title="Space-Time Density Diagram — Shockwave Propagation"
            />
          </div>

          <div className="grid-3" style={{ marginBottom: 20 }}>
            <MetricCard value={`${simResult.max_queue_km.toFixed(2)} km`} label="Max Queue" color="red" />
            <MetricCard value={`${Math.round(simResult.peak_queue_time_min)} min`} label="Peak Queue At" color="amber" />
            <MetricCard value={`${Math.round(simResult.clearance_time_min)} min`} label="Clearance Time" color="green" />
          </div>
          <Divider />
        </>
      )}

      {/* Recommendation */}
      {recResult && (
        <>
          <SectionHeader title="Resource Recommendation" />
          <div className="grid-3" style={{ marginBottom: 16 }}>
            <MetricCard value={recResult.officers_recommended} label="Officers" />
            <MetricCard value={recResult.barricades_recommended} label="Barricades" />
            <MetricCard value={recResult.diversion_routes.length} label="Diversion Routes" color="green" />
          </div>

          {recResult.diversion_routes.length > 0 && (
            <div>
              <div className="field-label" style={{ marginBottom: 8 }}>Diversion Routes (Dijkstra shortest-path)</div>
              {recResult.diversion_routes.map((route, i) => (
                <div key={i} className="route-code">
                  Route {i + 1}: {route.join(' → ')}{route.length >= 10 ? ' …' : ''}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {!simLoading && !simResult && !error && (
        <EmptyState icon="🔬" message="Select an incident to run the full pipeline" />
      )}
    </div>
  )
}
