"""
Phase 7: Streamlit Dashboard — Gridlock
Run: streamlit run app/dashboard.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import joblib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(
    page_title="GRIDLOCK PROJECT",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling (matching reference.html aesthetic) ──────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #FAFAF8; }

.gl-header {
    background: #111110;
    padding: 18px 32px;
    display: flex; align-items: center; gap: 12px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    margin: -1rem -1rem 2rem -1rem;
}
.gl-logo { font-size: 22px; font-weight: 900; color: #fff; letter-spacing: -0.02em; }
.gl-logo .o { color: #E5484D; }
.gl-logo .a { color: #F2A93B; }
.gl-logo .e { color: #0E9F6E; }
.gl-tag { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #0E9F6E;
          border: 1px solid #0E9F6E; padding: 3px 10px; border-radius: 3px; background: rgba(14,159,110,0.07); }
.gl-badge { display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 11px;
            padding: 3px 10px; border-radius: 3px; margin: 2px; }
.badge-planned   { background: rgba(14,159,110,0.12); color: #0E9F6E; border: 1px solid rgba(14,159,110,0.3); }
.badge-unplanned { background: rgba(229,72,77,0.12);  color: #E5484D; border: 1px solid rgba(229,72,77,0.3); }
.badge-high      { background: rgba(229,72,77,0.12);  color: #E5484D; border: 1px solid rgba(229,72,77,0.3); }
.badge-medium    { background: rgba(242,169,59,0.12); color: #F2A93B; border: 1px solid rgba(242,169,59,0.3); }
.badge-low       { background: rgba(14,159,110,0.12); color: #0E9F6E; border: 1px solid rgba(14,159,110,0.3); }

.metric-card { background: #fff; border: 1px solid rgba(17,17,17,0.1); border-radius: 8px;
               padding: 16px 20px; text-align: center; }
.metric-val  { font-size: 28px; font-weight: 700; color: #111110; }
.metric-lbl  { font-size: 11px; color: #6E6E69; font-family: 'JetBrains Mono', monospace;
               text-transform: uppercase; letter-spacing: 0.06em; margin-top: 4px; }

div[data-testid="stSidebarContent"] { background: #111110; }
div[data-testid="stSidebarContent"] * { color: #e8e8e6 !important; }
.stSelectbox label, .stSlider label { color: #e8e8e6 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="gl-header">
  <div class="gl-logo">GR<span class="o">●</span><span class="a">●</span><span class="e">●</span>DLOCK</div>
  <div class="gl-tag">[ predict → simulate → recommend ]</div>
</div>
""", unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading processed data...")
def load_data():
    feat_path = ROOT / "data" / "processed" / "features.parquet"
    if not feat_path.exists():
        return None
    df = pd.read_parquet(feat_path)
    if "start_datetime" in df.columns:
        df["start_datetime"] = pd.to_datetime(df["start_datetime"], utc=True, errors="coerce")
    return df

@st.cache_resource(show_spinner="Loading ML models...")
def load_models():
    out = {}
    dur_path = ROOT / "data" / "processed" / "model_duration.joblib"
    cap_path = ROOT / "data" / "processed" / "model_capacity.joblib"
    if dur_path.exists():
        out["duration"] = joblib.load(dur_path)
    if cap_path.exists():
        out["capacity"] = joblib.load(cap_path)
    return out

df = load_data()
models = load_models()

CAUSE_COLORS = {
    "vehicle_breakdown": "#E5484D", "accident": "#C62828",
    "water_logging": "#1565C0",    "tree_fall": "#2E7D32",
    "pot_holes": "#F57F17",        "construction": "#6A1B9A",
    "others": "#6E6E69",           "tyre_puncture": "#BF360C",
    "vip_movement": "#0277BD",     "signal_failure": "#FF8F00",
    "event_political": "#AD1457",
}

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Controls")
    tab_choice = st.radio("View", ["Replay Mode", "Incident Detail", "Calibration", "What-If"])
    st.markdown("---")

    if df is not None:
        available_dates = sorted(df["start_datetime"].dt.date.dropna().unique())
        sel_date = st.selectbox("Select Day", available_dates,
                                 index=min(len(available_dates)-1, len(available_dates)//2))
        day_df = df[df["start_datetime"].dt.date == sel_date].copy()
        day_df = day_df.sort_values("start_datetime")
        st.caption(f"{len(day_df)} incidents on {sel_date}")
    else:
        st.warning("Run the pipeline first:\n```\npython src/clean.py\npython src/features.py\npython src/forecast_model.py\n```")
        st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: REPLAY MODE
# ─────────────────────────────────────────────────────────────────────────────
if tab_choice == "Replay Mode":
    st.markdown("## Live Replay — Bengaluru Traffic Incidents")
    st.caption(f"Stepping through **{sel_date}** — {len(day_df)} events recorded")

    max_idx = max(len(day_df) - 1, 1)
    slider_val = st.slider("Timeline (drag to step through the day)",
                           0, max_idx, max_idx,
                           format="Incident %d")

    visible = day_df.iloc[:slider_val + 1].copy()
    visible["color"] = visible["event_cause"].map(CAUSE_COLORS).fillna("#6E6E69")
    visible["time_str"] = visible["start_datetime"].dt.strftime("%H:%M")
    visible["lat"] = pd.to_numeric(visible["latitude"], errors="coerce")
    visible["lon"] = pd.to_numeric(visible["longitude"], errors="coerce")
    visible = visible.dropna(subset=["lat", "lon"])

    # Plotly map
    fig_map = go.Figure()
    for cause, grp in visible.groupby("event_cause", dropna=False):
        color = CAUSE_COLORS.get(str(cause), "#6E6E69")
        hover = grp.apply(
            lambda r: f"<b>{r.get('event_cause','?')}</b><br>"
                      f"{r.get('address','')[:60]}<br>"
                      f"Priority: {r.get('priority','?')}<br>"
                      f"Time: {r.get('time_str','?')}<br>"
                      f"Duration: {r['duration_minutes']:.0f} min" if pd.notna(r.get("duration_minutes")) else "Active",
            axis=1,
        )
        fig_map.add_trace(go.Scattermapbox(
            lat=grp["lat"], lon=grp["lon"],
            mode="markers",
            marker=dict(size=10, color=color, opacity=0.85),
            name=str(cause),
            text=hover,
            hovertemplate="%{text}<extra></extra>",
            customdata=grp.index.tolist(),
        ))

    fig_map.update_layout(
        mapbox=dict(style="carto-darkmatter", center=dict(lat=12.97, lon=77.59), zoom=10.5),
        margin=dict(l=0, r=0, t=0, b=0), height=520,
        legend=dict(bgcolor="rgba(17,17,17,0.7)", font=dict(color="white", size=10)),
        paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
    )
    st.plotly_chart(fig_map, use_container_width=True)

    # Stats row
    c1, c2, c3, c4 = st.columns(4)
    unplanned = visible[visible["event_type"] == "unplanned"] if "event_type" in visible else visible
    high_pri  = visible[visible["priority"] == "High"] if "priority" in visible else visible
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-val">{len(visible)}</div><div class="metric-lbl">Incidents shown</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-val">{len(unplanned)}</div><div class="metric-lbl">Unplanned</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-val">{len(high_pri)}</div><div class="metric-lbl">High Priority</div></div>', unsafe_allow_html=True)
    with c4:
        avg_dur = visible["duration_minutes"].dropna().mean()
        st.markdown(f'<div class="metric-card"><div class="metric-val">{avg_dur:.0f}</div><div class="metric-lbl">Avg Duration (min)</div></div>', unsafe_allow_html=True)

    # Incident table
    st.markdown("### Events at this timestamp")
    show_cols = [c for c in ["id","time_str","event_cause","priority","corridor","duration_minutes","address"] if c in visible.columns]
    st.dataframe(visible[show_cols].tail(20), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: INCIDENT DETAIL
# ─────────────────────────────────────────────────────────────────────────────
elif tab_choice == "Incident Detail":
    st.markdown("## Incident Detail — Full Pipeline")

    from ctm_simulation import simulate_incident, get_road_type
    from recommend import recommend, format_recommendation

    # Select incident
    incident_options = day_df["id"].tolist() if "id" in day_df.columns else list(range(len(day_df)))
    sel_id = st.selectbox("Select Incident ID", incident_options)

    row = day_df[day_df["id"] == sel_id].iloc[0] if "id" in day_df.columns else day_df.iloc[sel_id]

    # Incident metadata
    c1, c2 = st.columns([1, 2])
    with c1:
        priority_val = str(row.get("priority", "Medium"))
        cause_val    = str(row.get("event_cause", "others"))
        ptype        = str(row.get("event_type", "unplanned"))
        st.markdown(f"""
        <div class="metric-card" style="text-align:left;margin-bottom:12px">
          <b style="font-size:15px">{cause_val.replace('_',' ').title()}</b><br>
          <span class="gl-badge badge-{priority_val.lower()}">{priority_val} Priority</span>
          <span class="gl-badge badge-{ptype}">{ptype}</span><br><br>
          <span style="font-size:12px;color:#6E6E69">{str(row.get('address',''))[:80]}</span><br>
          <span style="font-family:monospace;font-size:11px;color:#6E6E69">
            {str(row.get('corridor',''))} · {str(row.get('zone',''))}
          </span>
        </div>
        """, unsafe_allow_html=True)

        actual_dur = row.get("duration_minutes", None)
        if pd.notna(actual_dur):
            st.metric("Actual Duration", f"{actual_dur:.0f} min")

    # ML Prediction
    with c2:
        st.markdown("#### ML Prediction")
        feat_cols = models.get("duration", {}).get("features", []) if models else []

        if models and feat_cols:
            X_row = pd.DataFrame([{f: row.get(f, -1) for f in feat_cols}]).fillna(-1)
            log_dur = models["duration"]["model"].predict(X_row)[0]
            pred_dur = float(np.expm1(log_dur))

            cap_feats = models.get("capacity", {}).get("features", [])
            X_cap = pd.DataFrame([{f: row.get(f, -1) for f in cap_feats}]).fillna(-1)
            pred_cap = float(np.clip(models["capacity"]["model"].predict(X_cap)[0], 0.05, 0.95))
        else:
            pred_dur = float(actual_dur) if pd.notna(actual_dur) else 60.0
            pred_cap = 0.55

        mc1, mc2 = st.columns(2)
        mc1.metric("Predicted Duration", f"{pred_dur:.0f} min",
                   delta=f"{pred_dur - actual_dur:.0f} min vs actual" if pd.notna(actual_dur) else None)
        mc2.metric("Capacity Loss", f"{pred_cap*100:.0f}%")

    st.markdown("---")

    # Run CTM simulation
    st.markdown("#### CTM Traffic Flow Simulation")
    corridor  = str(row.get("corridor", "Non-corridor"))
    requires_closure = str(row.get("requires_road_closure", "")).upper() == "TRUE"

    with st.spinner("Running Cell Transmission Model (LWR PDE)..."):
        result = simulate_incident(
            corridor=corridor,
            duration_min=pred_dur,
            capacity_loss=pred_cap,
            incident_cell=12,
            upstream_demand_frac=0.70,
        )

    # Space-time diagram
    density = result.density_matrix
    times   = result.time_axis_min
    positions_m = result.cell_positions_m

    road_type = get_road_type(corridor)
    rho_jam_map = {"ring_road": 120, "arterial": 140, "local": 160}
    rho_jam = rho_jam_map.get(road_type, 140)

    fig_ctm = go.Figure(data=go.Heatmap(
        z=density,
        x=positions_m / 1000,
        y=times,
        colorscale=[
            [0.0,  "#0E9F6E"],
            [0.4,  "#F2A93B"],
            [0.7,  "#E5484D"],
            [1.0,  "#7B1FA2"],
        ],
        zmin=0, zmax=rho_jam,
        colorbar=dict(title=dict(text="Density<br>(veh/km)", font=dict(color="white")), tickfont=dict(color="white")),
    ))
    # Mark incident position and duration
    inc_pos_km = result.config.incident_cell * 0.2
    fig_ctm.add_vline(x=inc_pos_km, line_color="#fff", line_dash="dash", line_width=1.5,
                      annotation_text="Incident", annotation_font_color="white")
    fig_ctm.add_hline(y=pred_dur, line_color="#F2A93B", line_dash="dot", line_width=1.5,
                      annotation_text="Capacity restored", annotation_font_color="#F2A93B",
                      annotation_position="top right")

    fig_ctm.update_layout(
        title=dict(text="Space-Time Density Diagram — Shockwave Propagation", font=dict(color="white", size=14)),
        xaxis=dict(title="Position (km)", color="white", gridcolor="#333"),
        yaxis=dict(title="Time (min from incident)", color="white", gridcolor="#333"),
        paper_bgcolor="#111110", plot_bgcolor="#111110",
        height=400, margin=dict(l=60, r=20, t=50, b=50),
    )
    st.plotly_chart(fig_ctm, use_container_width=True)

    # CTM metrics
    cm1, cm2, cm3 = st.columns(3)
    cm1.metric("Max Queue", f"{result.max_queue_km:.2f} km")
    cm2.metric("Peak Queue At", f"{result.peak_queue_time_min:.0f} min")
    cm3.metric("Clearance Time", f"{result.clearance_time_min:.0f} min")

    st.markdown("---")
    st.markdown("#### Resource Recommendation")

    rec = recommend(
        corridor=corridor,
        predicted_duration_min=pred_dur,
        predicted_capacity_loss=pred_cap,
        max_queue_km=result.max_queue_km,
        peak_queue_time_min=result.peak_queue_time_min,
        clearance_time_min=result.clearance_time_min,
        incident_cell=12,
        requires_closure=requires_closure,
        priority_high=(priority_val == "High"),
    )

    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        st.markdown(f'<div class="metric-card"><div class="metric-val"> {rec.officers_recommended}</div><div class="metric-lbl">Officers</div></div>', unsafe_allow_html=True)
    with rc2:
        st.markdown(f'<div class="metric-card"><div class="metric-val"> {rec.barricades_recommended}</div><div class="metric-lbl">Barricades</div></div>', unsafe_allow_html=True)
    with rc3:
        routes_count = len(rec.diversion_routes)
        st.markdown(f'<div class="metric-card"><div class="metric-val"> {routes_count}</div><div class="metric-lbl">Diversion Routes</div></div>', unsafe_allow_html=True)

    if rec.diversion_routes:
        st.markdown("**Diversion Routes (Dijkstra shortest-path):**")
        for i, route in enumerate(rec.diversion_routes, 1):
            st.code(f"Route {i}: " + " → ".join(str(n) for n in route[:8]) + ("..." if len(route) > 8 else ""), language=None)

    with st.expander("Full Recommendation Text"):
        from recommend import format_recommendation
        st.code(format_recommendation(rec))

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: CALIBRATION
# ─────────────────────────────────────────────────────────────────────────────
elif tab_choice == "Calibration":
    st.markdown("## Model Calibration — Simulation vs Reality")
    st.caption("Proof the simulation is grounded in 8,000 real historical incidents")

    cal_plot = ROOT / "reports" / "calibration_plot.png"
    shap_plot = ROOT / "reports" / "shap_summary.png"

    if cal_plot.exists():
        st.image(str(cal_plot), caption="Simulated clearance time vs actual incident duration (grouped by event cause)", use_column_width=True)
    else:
        st.info("Run `python src/calibrate.py` to generate this plot.")

    if shap_plot.exists():
        st.markdown("### SHAP Feature Importance — Duration Model")
        st.image(str(shap_plot), caption="SHAP summary: which features drive the duration prediction", use_column_width=True)
    else:
        st.info("Run `python src/forecast_model.py` to generate the SHAP plot.")

    st.markdown("### Data Quality Report")
    dq_path = ROOT / "reports" / "data_quality.md"
    if dq_path.exists():
        st.markdown(dq_path.read_text())
    else:
        st.info("Run `python src/clean.py` to generate this report.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: WHAT-IF
# ─────────────────────────────────────────────────────────────────────────────
elif tab_choice == "What-If":
    st.markdown("## What-If Simulator")
    st.caption("Adjust incident parameters and re-run the CTM live")

    from ctm_simulation import simulate_incident, get_road_type, ROAD_PARAMS
    from recommend import recommend

    wc1, wc2 = st.columns(2)
    with wc1:
        wi_corridor  = st.selectbox("Corridor", ["ORR East 1", "ORR East 2", "Hosur Road",
                                                   "Bannerghatta Road", "Tumkur Road",
                                                   "Mysore Road", "Magadi Road", "Non-corridor"])
        wi_duration  = st.slider("Predicted Duration (min)", 5, 480, 60)
        wi_demand    = st.slider("Upstream Demand (% of capacity)", 30, 95, 70)
    with wc2:
        wi_closure   = st.toggle("Requires Road Closure", False)
        wi_priority  = st.select_slider("Priority", ["Low", "Medium", "High"], "Medium")

        cap_loss_map = {"Low": 0.12, "Medium": 0.35, "High": 0.55}
        wi_cap_loss  = cap_loss_map[wi_priority]
        if wi_closure:
            wi_cap_loss = 0.92
        st.metric("Capacity Loss", f"{wi_cap_loss*100:.0f}%")

    if st.button("▶ Run Simulation", type="primary"):
        with st.spinner("Solving LWR PDE via CTM..."):
            result = simulate_incident(
                corridor=wi_corridor,
                duration_min=wi_duration,
                capacity_loss=wi_cap_loss,
                incident_cell=12,
                upstream_demand_frac=wi_demand / 100,
            )

        road_type = get_road_type(wi_corridor)
        rho_jam_map = {"ring_road": 120, "arterial": 140, "local": 160}
        rho_jam = rho_jam_map.get(road_type, 140)

        fig_wi = go.Figure(data=go.Heatmap(
            z=result.density_matrix,
            x=result.cell_positions_m / 1000,
            y=result.time_axis_min,
            colorscale=[[0.0,"#0E9F6E"],[0.4,"#F2A93B"],[0.7,"#E5484D"],[1.0,"#7B1FA2"]],
            zmin=0, zmax=rho_jam,
            colorbar=dict(title=dict(text="veh/km", font=dict(color="white")), tickfont=dict(color="white")),
        ))
        inc_pos = result.config.incident_cell * 0.2
        fig_wi.add_vline(x=inc_pos, line_color="white", line_dash="dash", line_width=2,
                         annotation_text="Incident", annotation_font_color="white")
        fig_wi.add_hline(y=wi_duration, line_color="#F2A93B", line_dash="dot", line_width=1.5,
                         annotation_text="Capacity restored", annotation_font_color="#F2A93B",
                         annotation_position="top right")
        fig_wi.update_layout(
            title=dict(text=f"Space-Time Diagram — {wi_corridor} — {wi_duration} min incident", font=dict(color="white", size=13)),
            xaxis=dict(title="Position (km)", color="white", gridcolor="#333"),
            yaxis=dict(title="Time (min)", color="white", gridcolor="#333"),
            paper_bgcolor="#111110", plot_bgcolor="#111110",
            height=420, margin=dict(l=60, r=20, t=50, b=50),
        )
        st.plotly_chart(fig_wi, use_container_width=True)

        s1, s2, s3 = st.columns(3)
        s1.metric("Max Queue", f"{result.max_queue_km:.2f} km")
        s2.metric("Peak at", f"{result.peak_queue_time_min:.0f} min")
        s3.metric("Clearance", f"{result.clearance_time_min:.0f} min")

        rec = recommend(
            corridor=wi_corridor,
            predicted_duration_min=wi_duration,
            predicted_capacity_loss=wi_cap_loss,
            max_queue_km=result.max_queue_km,
            peak_queue_time_min=result.peak_queue_time_min,
            clearance_time_min=result.clearance_time_min,
            incident_cell=12,
            requires_closure=wi_closure,
            priority_high=(wi_priority == "High"),
        )
        st.markdown("**Resource Plan:**")
        r1, r2 = st.columns(2)
        r1.metric("Officers", rec.officers_recommended)
        r2.metric("Barricades", rec.barricades_recommended)
