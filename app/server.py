"""
FastAPI backend — serves the GRIDLOCK web dashboard.
Endpoints:
  GET  /                         → landing page (reference.html style)
  GET  /dashboard                → main dashboard SPA
  GET  /api/dates                → available dates
  GET  /api/incidents?date=...   → incidents for a given date
  POST /api/simulate             → run CTM + ML + recommendation for one incident
  POST /api/whatif               → run CTM with custom params
  GET  /api/calibration          → calibration stats
  GET  /reports/<file>           → static report images
"""

import sys, os, json, base64
from pathlib import Path

# Add src/ to path so we can import simulation modules
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd
import joblib
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="GRIDLOCK", docs_url="/docs")

# Mount static files
app.mount("/static", StaticFiles(directory=str(ROOT / "app" / "static")), name="static")

# ── Data loading ──────────────────────────────────────────────────────────────
FEAT_PATH = ROOT / "data" / "processed" / "features.parquet"
DUR_MODEL = ROOT / "data" / "processed" / "model_duration.joblib"
CAP_MODEL = ROOT / "data" / "processed" / "model_capacity.joblib"

_df_cache = None
_models_cache = None

def get_df() -> pd.DataFrame:
    global _df_cache
    if _df_cache is None:
        _df_cache = pd.read_parquet(FEAT_PATH)
        if "start_datetime" in _df_cache.columns:
            _df_cache["start_datetime"] = pd.to_datetime(
                _df_cache["start_datetime"], utc=True, errors="coerce"
            )
    return _df_cache

def get_models():
    global _models_cache
    if _models_cache is None:
        _models_cache = {}
        if DUR_MODEL.exists():
            _models_cache["duration"] = joblib.load(DUR_MODEL)
        if CAP_MODEL.exists():
            _models_cache["capacity"] = joblib.load(CAP_MODEL)
    return _models_cache

# ── Pages ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def landing():
    return (ROOT / "app" / "static" / "index.html").read_text()

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    return (ROOT / "app" / "static" / "dashboard.html").read_text()

# ── Report images ─────────────────────────────────────────────────────────────
@app.get("/reports/{filename}")
def serve_report(filename: str):
    path = ROOT / "reports" / filename
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "not found"}, 404)

# ── API: dates ────────────────────────────────────────────────────────────────
@app.get("/api/dates")
def api_dates():
    df = get_df()
    dates = sorted(df["start_datetime"].dt.date.dropna().unique())
    return {"dates": [str(d) for d in dates]}

# ── API: incidents for a date ─────────────────────────────────────────────────
@app.get("/api/incidents")
def api_incidents(date: str = Query(...)):
    df = get_df()
    target = pd.to_datetime(date).date()
    day = df[df["start_datetime"].dt.date == target].copy()
    day = day.sort_values("start_datetime")

    records = []
    for _, r in day.iterrows():
        records.append({
            "id": str(r.get("id", "")),
            "event_type": str(r.get("event_type", "")),
            "event_cause": str(r.get("event_cause", "")),
            "priority": str(r.get("priority", "")),
            "corridor": str(r.get("corridor", "")),
            "zone": str(r.get("zone", "")),
            "junction": str(r.get("junction", "")),
            "address": str(r.get("address", ""))[:100],
            "lat": float(r["latitude"]) if pd.notna(r.get("latitude")) else None,
            "lon": float(r["longitude"]) if pd.notna(r.get("longitude")) else None,
            "time": r["start_datetime"].strftime("%H:%M") if pd.notna(r.get("start_datetime")) else "",
            "duration_minutes": round(float(r["duration_minutes"]), 1) if pd.notna(r.get("duration_minutes")) else None,
            "requires_road_closure": str(r.get("requires_road_closure", "")).upper() == "TRUE" or bool(r.get("requires_road_closure_bin", 0)),
            "status": str(r.get("status", "")),
            "is_active": bool(r.get("is_active", False)),
        })
    return {"date": date, "count": len(records), "incidents": records}

# ── API: simulate ─────────────────────────────────────────────────────────────
class SimRequest(BaseModel):
    incident_id: str
    date: str

@app.post("/api/simulate")
def api_simulate(req: SimRequest):
    from ctm_simulation import simulate_incident, get_road_type, ROAD_PARAMS
    from recommend import recommend

    df = get_df()
    models = get_models()

    row = df[df["id"] == req.incident_id]
    if len(row) == 0:
        return JSONResponse({"error": "incident not found"}, 404)
    row = row.iloc[0]

    # ML prediction
    feat_cols = models.get("duration", {}).get("features", [])
    if feat_cols:
        X = pd.DataFrame([{f: row.get(f, -1) for f in feat_cols}]).fillna(-1)
        pred_dur = float(np.expm1(models["duration"]["model"].predict(X)[0]))
        cap_feats = models.get("capacity", {}).get("features", [])
        X_cap = pd.DataFrame([{f: row.get(f, -1) for f in cap_feats}]).fillna(-1)
        pred_cap = float(np.clip(models["capacity"]["model"].predict(X_cap)[0], 0.05, 0.95))
    else:
        pred_dur = float(row["duration_minutes"]) if pd.notna(row.get("duration_minutes")) else 60.0
        pred_cap = 0.55

    corridor = str(row.get("corridor", "Non-corridor"))
    road_type = get_road_type(corridor)
    requires_closure = str(row.get("requires_road_closure", "")).upper() == "TRUE" or bool(row.get("requires_road_closure_bin", 0))
    priority_val = str(row.get("priority", "Medium"))

    # Run CTM
    result = simulate_incident(
        corridor=corridor,
        duration_min=max(pred_dur, 5),
        capacity_loss=pred_cap,
        incident_cell=12,
        upstream_demand_frac=0.70,
    )

    # Recommendation
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

    # Build density matrix for heatmap (downsample for JSON)
    density = result.density_matrix
    times = result.time_axis_min
    step = max(1, len(times) // 120)  # max ~120 time rows
    density_ds = density[::step].tolist()
    times_ds = times[::step].tolist()
    positions_km = (result.cell_positions_m / 1000).tolist()

    rho_jam_map = {"ring_road": 120, "arterial": 140, "local": 160}
    rho_jam = rho_jam_map.get(road_type, 140)

    return {
        "incident": {
            "id": str(row.get("id", "")),
            "event_cause": str(row.get("event_cause", "")),
            "priority": priority_val,
            "corridor": corridor,
            "road_type": road_type,
            "address": str(row.get("address", ""))[:100],
            "actual_duration": round(float(row["duration_minutes"]), 1) if pd.notna(row.get("duration_minutes")) else None,
            "requires_closure": requires_closure,
        },
        "prediction": {
            "predicted_duration_min": round(pred_dur, 1),
            "predicted_capacity_loss": round(pred_cap, 3),
        },
        "simulation": {
            "density": density_ds,
            "times": times_ds,
            "positions_km": positions_km,
            "rho_jam": rho_jam,
            "incident_cell_km": 12 * 0.2,
            "max_queue_km": round(result.max_queue_km, 2),
            "peak_queue_time_min": round(result.peak_queue_time_min, 1),
            "clearance_time_min": round(result.clearance_time_min, 1),
        },
        "recommendation": {
            "officers": rec.officers_recommended,
            "barricades": rec.barricades_recommended,
            "diversion_routes": [
                [str(n) for n in route[:8]] for route in rec.diversion_routes
            ],
        },
    }

# ── API: what-if ──────────────────────────────────────────────────────────────
class WhatIfRequest(BaseModel):
    corridor: str = "ORR East 1"
    duration_min: float = 60
    capacity_loss: float = 0.55
    upstream_demand_pct: float = 70

@app.post("/api/whatif")
def api_whatif(req: WhatIfRequest):
    from ctm_simulation import simulate_incident, get_road_type, ROAD_PARAMS
    from recommend import recommend

    road_type = get_road_type(req.corridor)
    result = simulate_incident(
        corridor=req.corridor,
        duration_min=max(req.duration_min, 5),
        capacity_loss=np.clip(req.capacity_loss, 0.05, 0.95),
        incident_cell=12,
        upstream_demand_frac=req.upstream_demand_pct / 100,
    )

    rec = recommend(
        corridor=req.corridor,
        predicted_duration_min=req.duration_min,
        predicted_capacity_loss=req.capacity_loss,
        max_queue_km=result.max_queue_km,
        peak_queue_time_min=result.peak_queue_time_min,
        clearance_time_min=result.clearance_time_min,
        incident_cell=12,
        requires_closure=(req.capacity_loss > 0.85),
        priority_high=(req.capacity_loss > 0.45),
    )

    density = result.density_matrix
    times = result.time_axis_min
    step = max(1, len(times) // 120)
    rho_jam_map = {"ring_road": 120, "arterial": 140, "local": 160}

    return {
        "simulation": {
            "density": density[::step].tolist(),
            "times": times[::step].tolist(),
            "positions_km": (result.cell_positions_m / 1000).tolist(),
            "rho_jam": rho_jam_map.get(road_type, 140),
            "incident_cell_km": 12 * 0.2,
            "max_queue_km": round(result.max_queue_km, 2),
            "peak_queue_time_min": round(result.peak_queue_time_min, 1),
            "clearance_time_min": round(result.clearance_time_min, 1),
        },
        "recommendation": {
            "officers": rec.officers_recommended,
            "barricades": rec.barricades_recommended,
        },
    }

# ── API: calibration stats ────────────────────────────────────────────────────
@app.get("/api/calibration")
def api_calibration():
    cal_exists = (ROOT / "reports" / "calibration_plot.png").exists()
    shap_exists = (ROOT / "reports" / "shap_summary.png").exists()
    dq_path = ROOT / "reports" / "data_quality.md"
    dq_text = dq_path.read_text() if dq_path.exists() else ""
    return {
        "calibration_plot": "/reports/calibration_plot.png" if cal_exists else None,
        "shap_plot": "/reports/shap_summary.png" if shap_exists else None,
        "data_quality_md": dq_text,
    }
