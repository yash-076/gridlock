// API base URL — FastAPI backend
const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'API error')
  }
  return res.json()
}

export const api = {
  health:    ()       => apiFetch('/api/health'),
  dates:     ()       => apiFetch('/api/dates'),
  incidents: (date)   => apiFetch(`/api/incidents?date=${date}`),
  predict:   (body)   => apiFetch('/api/predict',   { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  simulate:  (body)   => apiFetch('/api/simulate',  { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  recommend: (body)   => apiFetch('/api/recommend', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  whatif:    (body)   => apiFetch('/api/whatif',    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  calibration:()      => apiFetch('/api/calibration'),
  stats:     ()       => apiFetch('/api/stats'),
}

// ── Event cause colour palette (matches dashboard.py) ────────────────────────
export const CAUSE_COLORS = {
  vehicle_breakdown: '#E5484D',
  accident:          '#C62828',
  water_logging:     '#1565C0',
  tree_fall:         '#2E7D32',
  pot_holes:         '#F57F17',
  construction:      '#6A1B9A',
  others:            '#6E6E69',
  tyre_puncture:     '#BF360C',
  vip_movement:      '#0277BD',
  signal_failure:    '#FF8F00',
  event_political:   '#AD1457',
  congestion:        '#F2A93B',
  procession:        '#5E35B1',
  debris:            '#4E342E',
  protest:           '#D81B60',
}

export const CORRIDORS = [
  'ORR East 1', 'ORR East 2', 'ORR West 1', 'ORR West 2',
  'Hosur Road', 'Bannerghatta Road', 'Tumkur Road',
  'Mysore Road', 'Magadi Road', 'Bellary Road 1', 'Bellary Road 2',
  'Non-corridor',
]

export function fmtDuration(min) {
  if (min == null) return '—'
  if (min < 60) return `${Math.round(min)} min`
  return `${Math.floor(min / 60)}h ${Math.round(min % 60)}m`
}

export function fmtCause(cause) {
  return (cause || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}
