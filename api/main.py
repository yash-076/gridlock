"""
GRIDLOCK FastAPI Backend
Wraps src/ pipeline modules and serves data to the React frontend.
Run: uvicorn api.main:app --port 8000 --reload
"""

import sys
import os
import base64
import pickle
import json
import warnings

warnings.filterwarnings("ignore")

# Add src/ to Python path so we can import pipeline modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# ── Load pipeline modules ─────────────────────────────────────────────────────
from ctm_simulation import simulate_incident, get_road_type, ROAD_PARAMS
from recommend import recommend as _recommend

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
REPORTS   = ROOT / "reports"

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="GRIDLOCK API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Cache loaded artefacts ────────────────────────────────────────────────────
_df: Optional[pd.DataFrame] = None
_models: dict = {}
_encoders: dict = {}


def get_df() -> pd.DataFrame:
    global _df
    if _df is None:
        path = PROCESSED / "features.parquet"
        if not path.exists():
            raise HTTPException(status_code=503, detail="Pipeline not yet run. Execute src/ scripts first.")
        _df = pd.read_parquet(path)
        if "start_datetime" in _df.columns:
            _df["start_datetime"] = pd.to_datetime(_df["start_datetime"], utc=True, errors="coerce")
    return _df


def get_models():
    global _models
    if not _models:
        dur = PROCESSED / "model_duration.joblib"
        cap = PROCESSED / "model_capacity.joblib"
        if dur.exists():
            _models["duration"] = joblib.load(dur)
        if cap.exists():
            _models["capacity"] = joblib.load(cap)
    return _models


def get_encoders():
    global _encoders
    if not _encoders:
        enc_path = PROCESSED / "label_encoders.joblib"
        if enc_path.exists():
            _encoders = joblib.load(enc_path)
    return _encoders


# ── Pydantic schemas ──────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    hour_of_day: int = 8
    day_of_week: int = 0
    is_weekend: int = 0
    is_peak_hour: int = 1
    month: int = 6
    requires_road_closure_bin: int = 0
    priority_num: int = 2
    is_unplanned: int = 1
    location_cluster: int = 0
    corridor_incident_7d: int = 0
    corridor_incident_30d: int = 0
    hist_avg_duration: float = 60.0
    event_cause_enc: int = 0
    corridor_enc: int = 0
    zone_enc: int = 0
    junction_enc: int = 0
    veh_type_enc: int = 0


class SimulateRequest(BaseModel):
    corridor: str = "ORR East 1"
    duration_min: float = 60.0
    capacity_loss: float = 0.55
    upstream_demand_frac: float = 0.70
    incident_cell: int = 12


class RecommendRequest(BaseModel):
    corridor: str
    predicted_duration_min: float
    predicted_capacity_loss: float
    max_queue_km: float
    peak_queue_time_min: float
    clearance_time_min: float
    incident_cell: int = 12
    requires_closure: bool = False
    priority_high: bool = False


class WhatIfRequest(BaseModel):
    corridor: str = "ORR East 1"
    duration_min: int = 60
    capacity_loss: float = 0.35
    upstream_demand_frac: float = 0.70
    requires_closure: bool = False
    priority_high: bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/dates")
def get_dates():
    df = get_df()
    dates = sorted(df["start_datetime"].dt.date.dropna().unique().tolist())
    return {"dates": [str(d) for d in dates]}


@app.get("/api/incidents")
def get_incidents(date: str = Query(...)):
    df = get_df()
    day_df = df[df["start_datetime"].dt.date.astype(str) == date].copy()
    day_df = day_df.sort_values("start_datetime")

    COLS = [
        "id", "event_cause", "priority", "corridor", "zone", "junction",
        "latitude", "longitude", "duration_minutes", "start_datetime",
        "address", "event_type", "is_active", "requires_road_closure",
        "hour_of_day", "day_of_week", "is_weekend", "is_peak_hour", "month",
        "requires_road_closure_bin", "priority_num", "is_unplanned",
        "location_cluster", "corridor_incident_7d", "corridor_incident_30d",
        "hist_avg_duration", "event_cause_enc", "corridor_enc", "zone_enc",
        "junction_enc", "veh_type_enc",
    ]
    available = [c for c in COLS if c in day_df.columns]
    subset = day_df[available].copy()

    # Serialize datetimes
    if "start_datetime" in subset.columns:
        subset["start_datetime"] = subset["start_datetime"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")

    records = subset.replace({np.nan: None, float("inf"): None, float("-inf"): None}).to_dict(orient="records")
    return {"date": date, "count": len(records), "incidents": records}


@app.post("/api/predict")
def predict(req: PredictRequest):
    models = get_models()
    if not models:
        raise HTTPException(status_code=503, detail="Models not loaded.")

    row = req.model_dump()

    dur_bundle = models.get("duration")
    cap_bundle = models.get("capacity")

    pred_dur = 60.0
    pred_cap = 0.35

    if dur_bundle:
        feats = dur_bundle["features"]
        X = pd.DataFrame([{f: row.get(f, -1) for f in feats}]).fillna(-1)
        log_dur = dur_bundle["model"].predict(X)[0]
        pred_dur = float(np.expm1(log_dur))

    if cap_bundle:
        feats = cap_bundle["features"]
        X = pd.DataFrame([{f: row.get(f, -1) for f in feats}]).fillna(-1)
        pred_cap = float(np.clip(cap_bundle["model"].predict(X)[0], 0.05, 0.95))

    return {
        "predicted_duration_min": round(pred_dur, 1),
        "predicted_capacity_loss": round(pred_cap, 3),
    }


@app.post("/api/simulate")
def simulate(req: SimulateRequest):
    result = simulate_incident(
        corridor=req.corridor,
        duration_min=req.duration_min,
        capacity_loss=req.capacity_loss,
        incident_cell=req.incident_cell,
        upstream_demand_frac=req.upstream_demand_frac,
    )

    road_type = get_road_type(req.corridor)
    rho_jam_map = {"ring_road": 120, "arterial": 140, "local": 160}
    rho_jam = rho_jam_map.get(road_type, 140)

    density = result.density_matrix.tolist()
    times   = result.time_axis_min.tolist()
    positions = result.cell_positions_m.tolist()

    return {
        "density_matrix": density,
        "time_axis_min": times,
        "cell_positions_m": positions,
        "max_queue_km": round(result.max_queue_km, 3),
        "peak_queue_time_min": round(result.peak_queue_time_min, 1),
        "clearance_time_min": round(result.clearance_time_min, 1),
        "incident_duration_min": round(result.incident_duration_min, 1),
        "incident_cell": result.config.incident_cell,
        "road_type": road_type,
        "rho_jam": rho_jam,
    }


@app.post("/api/recommend")
def recommend_endpoint(req: RecommendRequest):
    rec = _recommend(
        corridor=req.corridor,
        predicted_duration_min=req.predicted_duration_min,
        predicted_capacity_loss=req.predicted_capacity_loss,
        max_queue_km=req.max_queue_km,
        peak_queue_time_min=req.peak_queue_time_min,
        clearance_time_min=req.clearance_time_min,
        incident_cell=req.incident_cell,
        requires_closure=req.requires_closure,
        priority_high=req.priority_high,
    )
    return {
        "officers_recommended": rec.officers_recommended,
        "barricades_recommended": rec.barricades_recommended,
        "diversion_routes": [[str(n) for n in route[:10]] for route in rec.diversion_routes],
        "road_type": rec.road_type,
    }


@app.post("/api/whatif")
def whatif(req: WhatIfRequest):
    # Simulate
    sim_result = simulate_incident(
        corridor=req.corridor,
        duration_min=req.duration_min,
        capacity_loss=req.capacity_loss,
        upstream_demand_frac=req.upstream_demand_frac,
    )

    road_type = get_road_type(req.corridor)
    rho_jam_map = {"ring_road": 120, "arterial": 140, "local": 160}
    rho_jam = rho_jam_map.get(road_type, 140)

    # Recommend
    rec = _recommend(
        corridor=req.corridor,
        predicted_duration_min=req.duration_min,
        predicted_capacity_loss=req.capacity_loss,
        max_queue_km=sim_result.max_queue_km,
        peak_queue_time_min=sim_result.peak_queue_time_min,
        clearance_time_min=sim_result.clearance_time_min,
        incident_cell=12,
        requires_closure=req.requires_closure,
        priority_high=req.priority_high,
    )

    return {
        "density_matrix": sim_result.density_matrix.tolist(),
        "time_axis_min": sim_result.time_axis_min.tolist(),
        "cell_positions_m": sim_result.cell_positions_m.tolist(),
        "max_queue_km": round(sim_result.max_queue_km, 3),
        "peak_queue_time_min": round(sim_result.peak_queue_time_min, 1),
        "clearance_time_min": round(sim_result.clearance_time_min, 1),
        "officers_recommended": rec.officers_recommended,
        "barricades_recommended": rec.barricades_recommended,
        "diversion_routes": [[str(n) for n in route[:10]] for route in rec.diversion_routes],
        "road_type": road_type,
        "rho_jam": rho_jam,
    }


@app.get("/api/calibration")
def calibration():
    cal_path  = REPORTS / "calibration_plot.png"
    shap_path = REPORTS / "shap_summary.png"
    dq_path   = REPORTS / "data_quality.md"

    cal_b64  = ""
    shap_b64 = ""
    dq_text  = ""

    if cal_path.exists():
        with open(cal_path, "rb") as f:
            cal_b64 = base64.b64encode(f.read()).decode()
    if shap_path.exists():
        with open(shap_path, "rb") as f:
            shap_b64 = base64.b64encode(f.read()).decode()
    if dq_path.exists():
        dq_text = dq_path.read_text(encoding="utf-8", errors="ignore")

    return {
        "calibration_plot_b64": cal_b64,
        "shap_plot_b64": shap_b64,
        "data_quality_md": dq_text,
    }


@app.get("/api/stats")
def global_stats():
    df = get_df()
    total = len(df)
    cause_counts = df["event_cause"].value_counts().head(10).to_dict()
    corridor_counts = df["corridor"].value_counts().head(10).to_dict()
    avg_duration = float(df["duration_minutes"].dropna().mean())
    high_priority = int((df["priority"] == "High").sum())

    return {
        "total_incidents": total,
        "avg_duration_min": round(avg_duration, 1),
        "high_priority_count": high_priority,
        "cause_distribution": cause_counts,
        "corridor_distribution": corridor_counts,
    }
