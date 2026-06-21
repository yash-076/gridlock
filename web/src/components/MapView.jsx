import Plot from 'react-plotly.js'
import { CAUSE_COLORS } from '../api.js'

export function MapView({ incidents = [], height = 500 }) {
  // Group by cause
  const groups = {}
  for (const inc of incidents) {
    const cause = inc.event_cause || 'others'
    if (!groups[cause]) groups[cause] = []
    groups[cause].push(inc)
  }

  const traces = Object.entries(groups).map(([cause, rows]) => {
    const lats = rows.map(r => r.latitude).filter(v => v != null)
    const lons = rows.map(r => r.longitude).filter(v => v != null)
    const texts = rows.map(r => {
      const dur = r.duration_minutes != null ? `${Math.round(r.duration_minutes)} min` : 'Active'
      const time = r.start_datetime ? r.start_datetime.slice(11, 16) : ''
      return `<b>${(cause).replace(/_/g, ' ')}</b><br>${r.address || ''}<br>Priority: ${r.priority || '?'}<br>Time: ${time}<br>Duration: ${dur}`
    })
    return {
      type: 'scattermap',
      lat: lats,
      lon: lons,
      mode: 'markers',
      marker: {
        size: 9,
        color: CAUSE_COLORS[cause] || '#6E6E69',
        opacity: 0.85,
      },
      name: cause.replace(/_/g, ' '),
      text: texts,
      hovertemplate: '%{text}<extra></extra>',
    }
  })

  return (
    <Plot
      data={traces}
      layout={{
        map: { style: 'carto-darkmatter', center: { lat: 12.97, lon: 77.59 }, zoom: 10.5 },
        margin: { l: 0, r: 0, t: 0, b: 0 },
        legend: {
          bgcolor: 'rgba(17,17,17,0.75)',
          font: { color: 'white', size: 10, family: 'JetBrains Mono' },
          itemsizing: 'constant',
        },
        paper_bgcolor: '#0f1117',
        plot_bgcolor: '#0f1117',
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%', height }}
    />
  )
}
