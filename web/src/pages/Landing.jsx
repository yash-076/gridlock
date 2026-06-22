import React, { useState } from 'react';
import { Signal } from '../components/TopBar.jsx';

const CARD_ICONS = {
  replay: (
    <svg viewBox="0 0 24 24" width="28" height="28" stroke="currentColor" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: '12px' }}>
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" />
      <line x1="16" y1="6" x2="16" y2="22" />
    </svg>
  ),
  incident: (
    <svg viewBox="0 0 24 24" width="28" height="28" stroke="currentColor" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: '12px' }}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  ),
  calibration: (
    <svg viewBox="0 0 24 24" width="28" height="28" stroke="currentColor" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: '12px' }}>
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  ),
  whatif: (
    <svg viewBox="0 0 24 24" width="28" height="28" stroke="currentColor" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: '12px' }}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
};

export function Landing({ onNavigate }) {
  const cards = [
    {
      id: 'replay',
      title: 'Replay Mode',
      desc: 'Interactive timeline slider, historical incident database, and live density heatmaps of Bengaluru.',
      className: 'replay'
    },
    {
      id: 'incident',
      title: 'Incident Analysis',
      desc: 'AI models for duration/capacity prediction, CTM shockwave simulation, and recommendation engine.',
      className: 'incident'
    },
    {
      id: 'calibration',
      title: 'Calibration Insights',
      desc: 'Model accuracy reports, R² scatter plots, and SHAP feature importance analysis.',
      className: 'calibration'
    },
    {
      id: 'whatif',
      title: 'What-If Simulator',
      desc: 'Custom parameter injection: adjust demand, toggle corridor closures, and re-run flow simulations live.',
      className: 'whatif'
    }
  ];

  // Routes for the Interactive Bengaluru commute delay estimator
  const routes = [
    { 
      name: "Silk Board Junction ➔ Outer Ring Road (ORR)", 
      baseline: 25, 
      delayFactor: 1.9, 
      hotspot: "HSR Layout Exit & Bellandur flyover", 
      action: "Deploy 2 traffic wardens at HSR exit; hold lane merger at Silk Board loop." 
    },
    { 
      name: "Tin Factory ➔ KR Puram Junction", 
      baseline: 20, 
      delayFactor: 2.3, 
      hotspot: "Benniganahalli flyover bottlenecks", 
      action: "Activate alternate loop diversion; restrict commercial vehicles to service lanes." 
    },
    { 
      name: "Indiranagar 100ft Rd ➔ Whitefield (via ITPL)", 
      baseline: 35, 
      delayFactor: 1.6, 
      hotspot: "Kundalahalli Underpass & Graphite India Junction", 
      action: "Enforce one-way flow cycles at ITPL junction; hold corridor access ramps." 
    },
    { 
      name: "Koramangala 80ft Rd ➔ Electronic City (Elevated Toll)", 
      baseline: 15, 
      delayFactor: 1.3, 
      hotspot: "Silk Board Toll Plaza lane queues", 
      action: "Open express lane toll barriers; divert excess demand to Hosur Road service lane." 
    }
  ];

  const [routeIndex, setRouteIndex] = useState(0);
  const [demandLevel, setDemandLevel] = useState("Peak Hour"); // Peak Hour, Normal, Off-Peak

  const currentRoute = routes[routeIndex];
  let multiplier = 1.0;
  if (demandLevel === "Peak Hour") multiplier = currentRoute.delayFactor;
  else if (demandLevel === "Normal") multiplier = (currentRoute.delayFactor + 1.0) / 2.0;
  else multiplier = 0.8;

  const predictedTime = Math.round(currentRoute.baseline * multiplier);
  const excessDelay = Math.max(0, predictedTime - currentRoute.baseline);

  return (
    <div className="landing-shell page-enter">
      {/* Landing topbar */}
      <header className="landing-topbar">
        <button className="landing-brand" onClick={() => onNavigate('landing')}>
          <Signal />
          <div className="landing-brand-text">
            FLIPKART<span>GRIDLOCK HACKATHON</span>
          </div>
        </button>
        
        <div className="landing-nav">
          {cards.map(c => (
            <button
              key={c.id}
              className="landing-nav-item"
              onClick={() => onNavigate(c.id)}
            >
              {c.title}
            </button>
          ))}
          <span className="pill" style={{ marginLeft: '12px' }}>[ solve . traffic ]</span>
        </div>
      </header>

      {/* Main landing content */}
      <main className="landing-main">
        <h1 className="landing-hero">
          <span>GR</span>
          <span className="dots">
            <i className="red"></i>
            <i className="amber"></i>
            <i className="green"></i>
          </span>
          <span>DLOCK</span>
        </h1>
        <p className="landing-subtitle">Event-driven congestion forecasting &amp; response simulation</p>
        <div className="landing-tag">
          [ impact prediction &middot; flow simulation &middot; resource planning ]
        </div>

        {/* Live Bengaluru Commute Stats Ticker */}
        <section className="landing-metrics-section">
          <div className="landing-section-title">Live Commute Index (Bengaluru Central)</div>
          <div className="landing-metrics-grid">
            <div className="landing-metric-card">
              <div className="label">🚨 Active Hotspots</div>
              <div className="value color-red">12 Junctions</div>
              <div className="sub">Silk Board & Tin Factory critical</div>
            </div>
            <div className="landing-metric-card">
              <div className="label">🐢 Commute Speed</div>
              <div className="value color-amber">14.6 km/h</div>
              <div className="sub">Peak flow velocity index</div>
            </div>
            <div className="landing-metric-card">
              <div className="label">⏱️ Peak Hour Delay</div>
              <div className="value color-red">+42 Mins</div>
              <div className="sub">Relative to free-flow baseline</div>
            </div>
            <div className="landing-metric-card">
              <div className="label">👮 Response Units</div>
              <div className="value color-green">48 Active</div>
              <div className="sub">Wardens & diversions deployed</div>
            </div>
          </div>
        </section>

        {/* Interactive Estimator Widget */}
        <section className="landing-estimator-section">
          <div className="landing-section-title">Interactive Commute Delay Estimator</div>
          <div className="landing-estimator-card">
            <div className="landing-estimator-controls">
              <div className="control-group">
                <label className="estimator-label">Select Corridor Route</label>
                <select 
                  className="select-field" 
                  value={routeIndex}
                  onChange={(e) => setRouteIndex(Number(e.target.value))}
                >
                  {routes.map((r, i) => (
                    <option key={i} value={i}>{r.name}</option>
                  ))}
                </select>
              </div>

              <div className="control-group">
                <label className="estimator-label">Demand Density Mode</label>
                <div className="estimator-toggle-group">
                  {["Off-Peak", "Normal", "Peak Hour"].map(mode => (
                    <button
                      key={mode}
                      className={`estimator-toggle-btn ${demandLevel === mode ? 'active' : ''}`}
                      onClick={() => setDemandLevel(mode)}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="landing-estimator-results">
              <div className="result-metric">
                <span className="result-label">Baseline (Free Flow)</span>
                <span className="result-value mono">{currentRoute.baseline} mins</span>
              </div>
              <div className="result-divider">➔</div>
              <div className="result-metric">
                <span className="result-label">Predicted Travel Time</span>
                <span className={`result-value mono ${excessDelay > 15 ? 'color-red' : excessDelay > 5 ? 'color-amber' : 'color-green'}`}>
                  {predictedTime} mins
                </span>
              </div>
              <div className="result-metric text-left" style={{ gridColumn: 'span 3', marginTop: '16px' }}>
                <span className="result-label">Forecasted Bottleneck Zone</span>
                <span className="result-text text-bold">{currentRoute.hotspot}</span>
              </div>
              <div className="result-metric text-left" style={{ gridColumn: 'span 3', marginTop: '10px' }}>
                <span className="result-label">Recommended Response Plan</span>
                <span className="result-text tag-action">{currentRoute.action}</span>
              </div>
            </div>
          </div>
        </section>

        {/* Traffic Physics & Methodology */}
        <section className="landing-model-section">
          <div className="landing-section-title">Traffic Physics &amp; Methodology</div>
          <div className="landing-model-card">
            <div className="landing-model-math-container">
              <div className="landing-model-math">
                <div className="math-fraction-expr">
                  <span className="fraction">
                    <span className="numerator">∂ρ</span>
                    <span className="denominator">∂t</span>
                  </span>
                  <span className="math-operator">+</span>
                  <span className="fraction">
                    <span className="numerator">∂q</span>
                    <span className="denominator">∂x</span>
                  </span>
                  <span className="math-operator">=</span>
                  <span className="math-number">0</span>
                </div>
              </div>
              <span className="landing-model-math-label">LWR Conservation Law PDE</span>
            </div>
            
            <div className="landing-model-desc-container">
              <p className="landing-model-desc">
                We use a <strong>Cell Transmission Model (CTM)</strong>, the standard discrete-time approximation of the Lighthill–Whitham–Richards (LWR) kinematic wave PDE (shown on the left).
              </p>
              <p className="landing-model-desc-sub">
                Our model implements this with a triangular fundamental diagram and Godunov flux, enabling realistic shockwave propagation and flow constraint modeling across the highway network.
              </p>
              <div className="landing-model-chips">
                <span className="landing-model-chip">Cell Transmission Model</span>
                <span className="landing-model-chip">Triangular Fundamental Diagram</span>
                <span className="landing-model-chip">Godunov Numerical Flux</span>
              </div>
            </div>
          </div>
        </section>

        {/* Dynamic Navigation Cards */}
        <div className="landing-cards">
          {cards.map(c => (
            <div
              key={c.id}
              className={`landing-card ${c.className}`}
              onClick={() => onNavigate(c.id)}
            >
              <div>
                <div className="landing-card-icon">{CARD_ICONS[c.id]}</div>
                <div className="landing-card-title">
                  {c.title}
                  <span className="landing-card-arrow">➔</span>
                </div>
                <div className="landing-card-desc">{c.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </main>

      {/* Footer */}
      <footer className="landing-footer">
        <span>predict</span>
        <span className="arrow">&rarr;</span>
        <span>simulate</span>
        <span className="arrow">&rarr;</span>
        <span>recommend</span>
      </footer>
    </div>
  );
}
