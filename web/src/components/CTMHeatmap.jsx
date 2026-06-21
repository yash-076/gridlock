import Plot from 'react-plotly.js'

const CTM_COLORSCALE = [
  [0.0, '#0E9F6E'],
  [0.4, '#F2A93B'],
  [0.7, '#E5484D'],
  [1.0, '#7B1FA2'],
]

export function CTMHeatmap({ data, title = 'Space-Time Density Diagram' }) {
  if (!data) return null
  const { density_matrix, time_axis_min, cell_positions_m, rho_jam = 140,
          incident_cell = 12, incident_duration_min } = data

  const posKm = cell_positions_m.map(p => +(p / 1000).toFixed(3))
  const incPosKm = +(incident_cell * 0.2).toFixed(2)

  const shapes = [
    {
      type: 'line', x0: incPosKm, x1: incPosKm,
      y0: 0, y1: Math.max(...time_axis_min),
      line: { color: 'rgba(255,255,255,0.7)', width: 1.5, dash: 'dash' },
    },
  ]
  if (incident_duration_min) {
    shapes.push({
      type: 'line', x0: posKm[0], x1: posKm[posKm.length - 1],
      y0: incident_duration_min, y1: incident_duration_min,
      line: { color: '#F2A93B', width: 1.5, dash: 'dot' },
    })
  }

  return (
    <Plot
      data={[{
        type: 'heatmap',
        z: density_matrix,
        x: posKm,
        y: time_axis_min,
        colorscale: CTM_COLORSCALE,
        zmin: 0,
        zmax: rho_jam,
        colorbar: {
          title: { text: 'Density<br>(veh/km)', font: { color: '#aaa', size: 11 } },
          tickfont: { color: '#aaa', size: 10 },
          thickness: 12,
          len: 0.8,
        },
        hovertemplate: 'Position: %{x:.2f} km<br>Time: %{y:.1f} min<br>Density: %{z:.1f} veh/km<extra></extra>',
      }]}
      layout={{
        title: { text: title, font: { color: '#e8e8e6', size: 13, family: 'Inter' } },
        xaxis: { title: { text: 'Position (km)', font: { color: '#888', size: 11 } }, color: '#888', gridcolor: '#222', tickfont: { color: '#888', size: 10 } },
        yaxis: { title: { text: 'Time (min from incident)', font: { color: '#888', size: 11 } }, color: '#888', gridcolor: '#222', tickfont: { color: '#888', size: 10 } },
        paper_bgcolor: '#111110',
        plot_bgcolor: '#111110',
        margin: { l: 60, r: 20, t: 40, b: 50 },
        shapes,
        annotations: [
          { x: incPosKm, y: 0, text: 'Incident ↑', font: { color: 'rgba(255,255,255,0.7)', size: 10 }, showarrow: false, xanchor: 'left' },
          ...(incident_duration_min ? [{
            x: posKm[posKm.length - 1], y: incident_duration_min,
            text: ' Capacity restored', font: { color: '#F2A93B', size: 10 },
            showarrow: false, xanchor: 'right',
          }] : []),
        ],
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%', height: 380 }}
    />
  )
}
