import React, { useState } from 'react';
import { Signal } from '../components/TopBar.jsx';

export function Landing({ onNavigate }) {
  const cards = [
    {
      id: 'replay',
      icon: '🗺️',
      title: 'Replay Mode',
      desc: 'Interactive timeline slider, historical incident database, and live density heatmaps of Bengaluru.',
      className: 'replay'
    },
    {
      id: 'incident',
      icon: '🔬',
      title: 'Incident Analysis',
      desc: 'XGBoost models for duration/capacity prediction, CTM shockwave simulation, and recommendation engine.',
      className: 'incident'
    },
    {
      id: 'calibration',
      icon: '📊',
      title: 'Calibration Insights',
      desc: 'Model accuracy reports, R² scatter plots, and SHAP feature importance analysis.',
      className: 'calibration'
    },
    {
      id: 'whatif',
      icon: '⚙️',
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

        {/* Dynamic Navigation Cards */}
        <div className="landing-cards">
          {cards.map(c => (
            <div
              key={c.id}
              className={`landing-card ${c.className}`}
              onClick={() => onNavigate(c.id)}
            >
              <div>
                <div className="landing-card-icon">{c.icon}</div>
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
