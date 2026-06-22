/* ═══════════════════════════════════════════════════════════════
   GRIDLOCK DASHBOARD — JavaScript (vanilla)
   ═══════════════════════════════════════════════════════════════ */

const CAUSE_COLORS = {
  vehicle_breakdown: '#E5484D', accident: '#C62828',
  water_logging: '#1565C0',     tree_fall: '#2E7D32',
  pot_holes: '#F57F17',         construction: '#6A1B9A',
  others: '#6E6E69',            tyre_puncture: '#BF360C',
  vip_movement: '#0277BD',      signal_failure: '#FF8F00',
  event_political: '#AD1457',   congestion: '#455A64',
  public_event: '#7B1FA2',      road_conditions: '#795548',
  procession: '#AD1457',        debris: '#9E9E9E',
  protest: '#D50000',
};

function causeColor(c) { return CAUSE_COLORS[c] || '#6E6E69'; }
function badgeClass(p) {
  if (p === 'High') return 'badge-high';
  if (p === 'Medium') return 'badge-medium';
  return 'badge-low';
}

// ── State ────────────────────────────────────────────────────
let allIncidents = [];
let map;
let markers = [];

// ── Tab switching ────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.add('hidden'));
    btn.classList.add('active');
    document.getElementById('panel-' + btn.dataset.tab).classList.remove('hidden');
    if (btn.dataset.tab === 'replay' && map) map.invalidateSize();
    if (btn.dataset.tab === 'calibration') loadCalibration();
  });
});

// ── Init ─────────────────────────────────────────────────────
async function init() {
  // Init Leaflet map
  map = L.map('map', { zoomControl: true }).setView([12.97, 77.59], 11);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© CartoDB', maxZoom: 18,
  }).addTo(map);

  // Load dates
  const res = await fetch('/api/dates');
  const data = await res.json();
  const dateSelect = document.getElementById('date-select');
  const detailDate = document.getElementById('detail-date');

  data.dates.forEach(d => {
    dateSelect.add(new Option(d, d));
    detailDate.add(new Option(d, d));
  });

  // Default to a date with decent data (pick mid-range)
  const midIdx = Math.floor(data.dates.length * 0.7);
  dateSelect.selectedIndex = midIdx;
  detailDate.selectedIndex = midIdx;

  // Load initial date
  await loadDate(data.dates[midIdx]);

  // Event listeners
  dateSelect.addEventListener('change', () => loadDate(dateSelect.value));
  document.getElementById('timeline-slider').addEventListener('input', updateTimeline);
  detailDate.addEventListener('change', () => loadDetailIncidents(detailDate.value));
  document.getElementById('btn-run-sim').addEventListener('click', runSimulation);
  document.getElementById('btn-whatif').addEventListener('click', runWhatIf);

  // Range display updates
  ['wi-dur', 'wi-cap', 'wi-demand'].forEach(id => {
    const el = document.getElementById(id);
    const valEl = document.getElementById(id + '-val');
    el.addEventListener('input', () => {
      valEl.textContent = id === 'wi-dur' ? el.value : el.value + '%';
    });
  });

  await loadDetailIncidents(data.dates[midIdx]);
}

// ── Replay: load incidents for a date ────────────────────────
async function loadDate(date) {
  const res = await fetch(`/api/incidents?date=${date}`);
  const data = await res.json();
  allIncidents = data.incidents;

  const slider = document.getElementById('timeline-slider');
  slider.max = Math.max(allIncidents.length - 1, 0);
  slider.value = slider.max;

  updateTimeline();
}

function updateTimeline() {
  const count = parseInt(document.getElementById('timeline-slider').value) + 1;
  const visible = allIncidents.slice(0, count);

  document.getElementById('incident-counter').textContent =
    `${count} / ${allIncidents.length} incidents`;

  // Stats
  const unplanned = visible.filter(i => i.event_type === 'unplanned').length;
  const high = visible.filter(i => i.priority === 'High').length;
  const durs = visible.filter(i => i.duration_minutes).map(i => i.duration_minutes);
  const avgDur = durs.length ? (durs.reduce((a,b) => a+b, 0) / durs.length).toFixed(0) : '—';

  document.getElementById('stat-total').textContent = visible.length;
  document.getElementById('stat-unplanned').textContent = unplanned;
  document.getElementById('stat-high').textContent = high;
  document.getElementById('stat-avg-dur').textContent = avgDur;

  // Map markers
  markers.forEach(m => map.removeLayer(m));
  markers = [];
  visible.forEach(inc => {
    if (!inc.lat || !inc.lon) return;
    const m = L.circleMarker([inc.lat, inc.lon], {
      radius: 7, fillColor: causeColor(inc.event_cause),
      fillOpacity: 0.85, stroke: true, color: '#fff', weight: 1.5,
    }).addTo(map);
    m.bindPopup(`
      <b>${inc.event_cause.replace(/_/g, ' ')}</b><br>
      ${inc.address}<br>
      <span style="color:${causeColor(inc.event_cause)}">●</span> ${inc.priority} priority · ${inc.time}<br>
      Duration: ${inc.duration_minutes ? inc.duration_minutes + ' min' : 'Active'}
    `);
    markers.push(m);
  });

  // Table
  const tbody = document.getElementById('incident-tbody');
  tbody.innerHTML = '';
  visible.slice(-30).reverse().forEach(inc => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${inc.time}</td>
      <td><span class="cause-dot" style="background:${causeColor(inc.event_cause)}"></span>${inc.event_cause.replace(/_/g, ' ')}</td>
      <td><span class="badge ${badgeClass(inc.priority)}">${inc.priority}</span></td>
      <td>${inc.corridor}</td>
      <td>${inc.duration_minutes ? inc.duration_minutes + ' min' : '<em>active</em>'}</td>
      <td><button class="btn-sm" onclick="selectIncident('${inc.id}','${document.getElementById('date-select').value}')">Analyze</button></td>
    `;
    tbody.appendChild(tr);
  });
}

// ── Incident Detail ──────────────────────────────────────────
async function loadDetailIncidents(date) {
  const res = await fetch(`/api/incidents?date=${date}`);
  const data = await res.json();
  const sel = document.getElementById('detail-incident');
  sel.innerHTML = '';
  data.incidents.forEach(inc => {
    sel.add(new Option(`${inc.id} — ${inc.event_cause} (${inc.priority})`, inc.id));
  });
}

window.selectIncident = function(id, date) {
  // Switch to detail tab
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.add('hidden'));
  document.querySelector('[data-tab="detail"]').classList.add('active');
  document.getElementById('panel-detail').classList.remove('hidden');

  document.getElementById('detail-date').value = date;
  loadDetailIncidents(date).then(() => {
    document.getElementById('detail-incident').value = id;
    runSimulation();
  });
};

async function runSimulation() {
  const date = document.getElementById('detail-date').value;
  const incId = document.getElementById('detail-incident').value;
  if (!incId) return;

  document.getElementById('detail-results').classList.add('hidden');
  document.getElementById('detail-loading').classList.remove('hidden');

  try {
    const res = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ incident_id: incId, date }),
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    renderDetail(data);
  } catch (e) {
    alert('Simulation error: ' + e.message);
  } finally {
    document.getElementById('detail-loading').classList.add('hidden');
  }
}

function renderDetail(data) {
  const inc = data.incident;
  const pred = data.prediction;
  const sim = data.simulation;
  const rec = data.recommendation;

  // Metadata card
  document.getElementById('detail-meta').innerHTML = `
    <h3>Incident Metadata</h3>
    <div class="meta-row"><span class="meta-key">ID</span><span class="meta-val">${inc.id}</span></div>
    <div class="meta-row"><span class="meta-key">Cause</span><span class="meta-val"><span class="cause-dot" style="background:${causeColor(inc.event_cause)}"></span>${inc.event_cause.replace(/_/g,' ')}</span></div>
    <div class="meta-row"><span class="meta-key">Priority</span><span class="meta-val"><span class="badge ${badgeClass(inc.priority)}">${inc.priority}</span></span></div>
    <div class="meta-row"><span class="meta-key">Corridor</span><span class="meta-val">${inc.corridor} <small>(${inc.road_type.replace('_',' ')})</small></span></div>
    <div class="meta-row"><span class="meta-key">Address</span><span class="meta-val" style="font-size:11px">${inc.address}</span></div>
    <div class="meta-row"><span class="meta-key">Closure</span><span class="meta-val">${inc.requires_closure ? '🔴 Yes' : '🟢 No'}</span></div>
    ${inc.actual_duration ? `<div class="meta-row"><span class="meta-key">Actual dur.</span><span class="meta-val">${inc.actual_duration} min</span></div>` : ''}
  `;

  // Prediction card
  const delta = inc.actual_duration ? `(Δ ${(pred.predicted_duration_min - inc.actual_duration).toFixed(0)} min vs actual)` : '';
  document.getElementById('detail-prediction').innerHTML = `
    <h3>ML Prediction (AI Model)</h3>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:8px">
      <div class="stat-card"><div class="stat-val">${pred.predicted_duration_min.toFixed(0)}</div><div class="stat-lbl">Duration (min) ${delta}</div></div>
      <div class="stat-card"><div class="stat-val">${(pred.predicted_capacity_loss * 100).toFixed(0)}%</div><div class="stat-lbl">Capacity Loss</div></div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:12px">
      <div class="stat-card"><div class="stat-val">${sim.max_queue_km}</div><div class="stat-lbl">Max Queue (km)</div></div>
      <div class="stat-card"><div class="stat-val">${sim.peak_queue_time_min.toFixed(0)}</div><div class="stat-lbl">Peak at (min)</div></div>
      <div class="stat-card"><div class="stat-val">${sim.clearance_time_min.toFixed(0)}</div><div class="stat-lbl">Clearance (min)</div></div>
    </div>
  `;

  // CTM heatmap
  drawHeatmap('ctm-canvas', sim);

  // Legend
  document.getElementById('ctm-legend').innerHTML = `
    <span><span class="leg-swatch" style="background:#0E9F6E"></span>Free flow</span>
    <span><span class="leg-swatch" style="background:#F2A93B"></span>Congested</span>
    <span><span class="leg-swatch" style="background:#E5484D"></span>Near-jam</span>
    <span><span class="leg-swatch" style="background:#7B1FA2"></span>Full jam</span>
    <span style="margin-left:auto">Incident cell: ${sim.incident_cell_km.toFixed(1)} km  |  ρ_jam = ${sim.rho_jam} veh/km</span>
  `;

  // Recommendation
  document.getElementById('detail-rec').innerHTML = `
    <div class="stat-card"><div class="stat-val"> ${rec.officers}</div><div class="stat-lbl">Officers Required</div></div>
    <div class="stat-card"><div class="stat-val"> ${rec.barricades}</div><div class="stat-lbl">Barricades Required</div></div>
    <div class="stat-card">
      <div class="stat-val"> ${rec.diversion_routes.length}</div>
      <div class="stat-lbl">Diversion Routes</div>
      ${rec.diversion_routes.map((r,i) => `<div style="font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:6px">Route ${i+1}: ${r.join(' → ')}</div>`).join('')}
    </div>
  `;

  document.getElementById('detail-results').classList.remove('hidden');
}

// ── CTM Heatmap renderer (canvas) ────────────────────────────
function drawHeatmap(canvasId, sim) {
  const canvas = document.getElementById(canvasId);
  const ctx = canvas.getContext('2d');
  const density = sim.density;
  const times = sim.times;
  const positions = sim.positions_km;
  const rhoJam = sim.rho_jam;

  const T = density.length;
  const N = density[0] ? density[0].length : 0;
  if (T === 0 || N === 0) return;

  // Set canvas resolution
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth;
  const H = 380;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  canvas.style.height = H + 'px';
  ctx.scale(dpr, dpr);

  // Margins for axes
  const ml = 50, mr = 60, mt = 20, mb = 36;
  const pw = W - ml - mr;
  const ph = H - mt - mb;

  // Background
  ctx.fillStyle = '#111110';
  ctx.fillRect(0, 0, W, H);

  // Draw heatmap cells
  const cellW = pw / N;
  const cellH = ph / T;
  for (let t = 0; t < T; t++) {
    for (let x = 0; x < N; x++) {
      const rho = density[t][x];
      const ratio = Math.min(rho / rhoJam, 1.0);
      ctx.fillStyle = densityColor(ratio);
      ctx.fillRect(ml + x * cellW, mt + t * cellH, Math.ceil(cellW) + 1, Math.ceil(cellH) + 1);
    }
  }

  // Incident position line
  const incIdx = Math.round(sim.incident_cell_km / (positions[positions.length-1] || 5) * N);
  const incX = ml + incIdx * cellW;
  ctx.setLineDash([6, 4]);
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(incX, mt); ctx.lineTo(incX, mt + ph); ctx.stroke();
  ctx.setLineDash([]);

  // Capacity restored line
  const durMin = sim.times[sim.times.length - 1] * 0.5; // approx
  // find index closest to incident duration
  // Use clearance annotations instead
  const restoreIdx = times.findIndex(t => t >= (sim.clearance_time_min * 0.7));
  if (restoreIdx > 0) {
    const ry = mt + (restoreIdx / T) * ph;
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = '#F2A93B';
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(ml, ry); ctx.lineTo(ml + pw, ry); ctx.stroke();
    ctx.setLineDash([]);
  }

  // Axes
  ctx.fillStyle = '#888';
  ctx.font = '10px ui-monospace, monospace';
  ctx.textAlign = 'center';

  // X axis (position)
  for (let i = 0; i <= 4; i++) {
    const xPos = ml + (i / 4) * pw;
    const km = (positions[Math.round((i / 4) * (N - 1))] || 0).toFixed(1);
    ctx.fillText(km + ' km', xPos, H - mb + 16);
  }

  // Y axis (time)
  ctx.textAlign = 'right';
  const maxT = times[T - 1] || 1;
  for (let i = 0; i <= 5; i++) {
    const yPos = mt + (i / 5) * ph;
    const tVal = (maxT * i / 5).toFixed(0);
    ctx.fillText(tVal + ' min', ml - 6, yPos + 4);
  }

  // Axis labels
  ctx.fillStyle = '#6E6E69';
  ctx.font = '11px ui-monospace, monospace';
  ctx.textAlign = 'center';
  ctx.fillText('Position along corridor', ml + pw / 2, H - 4);

  ctx.save();
  ctx.translate(12, mt + ph / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('Time from incident', 0, 0);
  ctx.restore();

  // Colorbar
  const cbW = 14, cbH = ph;
  const cbX = W - mr + 14;
  for (let j = 0; j < cbH; j++) {
    const ratio = j / cbH;
    ctx.fillStyle = densityColor(ratio);
    ctx.fillRect(cbX, mt + j, cbW, 2);
  }
  ctx.fillStyle = '#888';
  ctx.font = '9px ui-monospace, monospace';
  ctx.textAlign = 'left';
  ctx.fillText('0', cbX + cbW + 4, mt + 8);
  ctx.fillText((rhoJam / 2).toFixed(0), cbX + cbW + 4, mt + cbH / 2 + 4);
  ctx.fillText(rhoJam.toString(), cbX + cbW + 4, mt + cbH);
  ctx.fillText('veh/km', cbX + cbW + 4, mt + cbH + 14);
}

function densityColor(ratio) {
  // 0=green, 0.4=amber, 0.7=red, 1.0=purple
  if (ratio <= 0.0) return '#0E9F6E';
  if (ratio <= 0.4) {
    const t = ratio / 0.4;
    return lerpColor('#0E9F6E', '#F2A93B', t);
  }
  if (ratio <= 0.7) {
    const t = (ratio - 0.4) / 0.3;
    return lerpColor('#F2A93B', '#E5484D', t);
  }
  const t = (ratio - 0.7) / 0.3;
  return lerpColor('#E5484D', '#7B1FA2', t);
}

function lerpColor(a, b, t) {
  const ar = parseInt(a.slice(1, 3), 16), ag = parseInt(a.slice(3, 5), 16), ab = parseInt(a.slice(5, 7), 16);
  const br = parseInt(b.slice(1, 3), 16), bg = parseInt(b.slice(3, 5), 16), bb = parseInt(b.slice(5, 7), 16);
  const r = Math.round(ar + (br - ar) * t).toString(16).padStart(2, '0');
  const g = Math.round(ag + (bg - ag) * t).toString(16).padStart(2, '0');
  const bl = Math.round(ab + (bb - ab) * t).toString(16).padStart(2, '0');
  return '#' + r + g + bl;
}

// ── Calibration tab ──────────────────────────────────────────
async function loadCalibration() {
  const container = document.getElementById('calibration-content');
  if (container.dataset.loaded) return;

  const res = await fetch('/api/calibration');
  const data = await res.json();

  let html = '';
  if (data.calibration_plot) {
    html += `<h3>Simulated vs Actual Duration</h3>
             <img src="${data.calibration_plot}" alt="Calibration scatter plot">`;
  }
  if (data.shap_plot) {
    html += `<h3>SHAP Feature Importance — Duration Model</h3>
             <img src="${data.shap_plot}" alt="SHAP summary">`;
  }
  if (data.data_quality_md) {
    html += `<h3>Data Quality Report</h3>
             <div class="card" style="font-family:var(--mono);font-size:11px;white-space:pre-wrap;line-height:1.6">${escapeHtml(data.data_quality_md)}</div>`;
  }
  container.innerHTML = html || '<p>Run the pipeline first to generate reports.</p>';
  container.dataset.loaded = 'true';
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── What-If tab ──────────────────────────────────────────────
async function runWhatIf() {
  const corridor = document.getElementById('wi-corridor').value;
  const duration = parseInt(document.getElementById('wi-dur').value);
  const capLoss = parseInt(document.getElementById('wi-cap').value) / 100;
  const demand = parseInt(document.getElementById('wi-demand').value);

  document.getElementById('whatif-results').classList.add('hidden');
  document.getElementById('whatif-loading').classList.remove('hidden');

  try {
    const res = await fetch('/api/whatif', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        corridor, duration_min: duration,
        capacity_loss: capLoss, upstream_demand_pct: demand,
      }),
    });
    const data = await res.json();

    drawHeatmap('wi-canvas', data.simulation);

    document.getElementById('wi-rec').innerHTML = `
      <div class="stat-card"><div class="stat-val">${data.simulation.max_queue_km} km</div><div class="stat-lbl">Max Queue</div></div>
      <div class="stat-card"><div class="stat-val">${data.simulation.clearance_time_min.toFixed(0)} min</div><div class="stat-lbl">Clearance Time</div></div>
      <div class="stat-card">
        <div class="stat-val"> ${data.recommendation.officers} ·  ${data.recommendation.barricades}</div>
        <div class="stat-lbl">Officers · Barricades</div>
      </div>
    `;
    document.getElementById('whatif-results').classList.remove('hidden');
  } catch (e) {
    alert('Error: ' + e.message);
  } finally {
    document.getElementById('whatif-loading').classList.add('hidden');
  }
}

// ── Boot ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
