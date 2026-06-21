"""
Phase 3: ML impact forecast model.
Trains XGBoost for:
  - Target 1: duration_minutes (regression)
  - Target 2: capacity_loss_fraction (heuristic-derived label)
Outputs: data/processed/model_duration.joblib, model_capacity.joblib
         reports/shap_summary.png
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import joblib
import shap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import xgboost as xgb

ROOT     = Path(__file__).resolve().parent.parent
FEAT_IN  = ROOT / "data" / "processed" / "features.parquet"
OUT_DIR  = ROOT / "data" / "processed"
REP_DIR  = ROOT / "reports"
REP_DIR.mkdir(parents=True, exist_ok=True)


FEATURE_COLS = [
    "hour_of_day", "day_of_week", "is_weekend", "is_peak_hour", "month",
    "requires_road_closure_bin", "priority_num", "is_unplanned",
    "location_cluster",
    "corridor_incident_7d", "corridor_incident_30d", "hist_avg_duration",
    "event_cause_enc", "corridor_enc", "zone_enc", "junction_enc",
]


# ── Heuristic capacity loss label ─────────────────────────────────────────────

def derive_capacity_loss(df: pd.DataFrame) -> pd.Series:
    """
    Derive a heuristic capacity_loss_fraction [0, 1] from observable fields.
    0 = no loss, 1 = full closure.
    NOTE: this is calibrated, not directly observed — documented in README.
    """
    loss = pd.Series(0.25, index=df.index, dtype=float)  # default 25% loss

    closure = df["requires_road_closure_bin"].fillna(0).astype(bool)
    priority_high   = df["priority_num"].fillna(1) >= 2
    priority_low    = df["priority_num"].fillna(1) <= 0
    cause = df["event_cause"].fillna("").astype(str).str.lower()

    # Full closure rows
    loss[closure] = 0.92

    # High-priority breakdown/accident
    mask = ~closure & priority_high & cause.isin(["vehicle_breakdown", "accident"])
    loss[mask] = 0.55

    # Water logging
    mask = ~closure & cause.str.contains("water_log|waterlogging", na=False, regex=True)
    loss[mask] = 0.50

    # Tree fall on Non-corridor
    mask = (cause == "tree_fall") & (df["corridor"].fillna("").str.contains("Non-corridor", na=False))
    loss[mask] = 0.95

    # Pot holes / low priority
    mask = ~closure & priority_low & cause.isin(["pot_holes", "pothole"])
    loss[mask] = 0.12

    # VIP movement
    mask = cause.isin(["vip_movement"])
    loss[mask] = 0.30

    # Clamp
    loss = loss.clip(0.05, 0.95)
    return loss


# ── Train ─────────────────────────────────────────────────────────────────────

def train_duration_model(df: pd.DataFrame):
    # Only rows with known duration, exclude active (right-censored)
    mask = df["duration_minutes"].notna() & ~df["is_active"]
    sub  = df[mask].copy()
    print(f"\nDuration model training rows: {len(sub):,}")

    available_features = [c for c in FEATURE_COLS if c in sub.columns]
    X = sub[available_features].fillna(-1)
    y = np.log1p(sub["duration_minutes"])   # log transform for skewed target

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBRegressor(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.5,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=False)

    y_pred = model.predict(X_te)
    mae  = mean_absolute_error(np.expm1(y_te), np.expm1(y_pred))
    r2   = r2_score(y_te, y_pred)
    print(f"Duration model — MAE: {mae:.1f} min | R² (log): {r2:.3f}")

    # Per-cause breakdown — use .loc since X_te preserves original df labels
    te_idx = X_te.index
    cause_results = []
    for cause, grp in sub.loc[te_idx].groupby("event_cause"):
        idx = grp.index
        if len(idx) < 5:
            continue
        yp = np.expm1(model.predict(sub.loc[idx, available_features].fillna(-1)))
        ya = sub.loc[idx, "duration_minutes"].values
        cause_results.append({
            "event_cause": cause,
            "n": len(idx),
            "MAE_min": round(mean_absolute_error(ya, yp), 1),
            "R2": round(r2_score(ya, yp) if len(idx) > 1 else float("nan"), 3),
        })
    print("\nPer-cause MAE (test set):")
    print(pd.DataFrame(cause_results).sort_values("MAE_min").to_string(index=False))

    # Save SHAP summary plot
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_te[:500])  # use a sample for speed
    plt.figure(figsize=(10, 6))
    shap.summary_plot(shap_values, X_te[:500], feature_names=available_features,
                      show=False, plot_size=(10, 6))
    plt.tight_layout()
    plt.savefig(REP_DIR / "shap_summary.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"SHAP summary saved to {REP_DIR / 'shap_summary.png'}")

    # Save model
    model_path = OUT_DIR / "model_duration.joblib"
    joblib.dump({"model": model, "features": available_features}, model_path)
    print(f"Duration model saved to {model_path}")
    return model, available_features


def train_capacity_model(df: pd.DataFrame):
    df["capacity_loss_fraction"] = derive_capacity_loss(df)

    mask = df["duration_minutes"].notna() & ~df["is_active"]
    sub  = df[mask].copy()

    available_features = [c for c in FEATURE_COLS if c in sub.columns]
    X = sub[available_features].fillna(-1)
    y = sub["capacity_loss_fraction"]

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )
    model.fit(X_tr, y_tr)

    y_pred = model.predict(X_te).clip(0.05, 0.95)
    mae = mean_absolute_error(y_te, y_pred)
    r2  = r2_score(y_te, y_pred)
    print(f"\nCapacity-loss model — MAE: {mae:.3f} | R²: {r2:.3f}")
    print("(NOTE: target is a heuristic label, not directly observed — see README)")

    model_path = OUT_DIR / "model_capacity.joblib"
    joblib.dump({"model": model, "features": available_features,
                 "derive_fn": "derive_capacity_loss"}, model_path)
    print(f"Capacity model saved to {model_path}")
    return model, available_features


# ── Public inference helper ───────────────────────────────────────────────────

def predict_for_row(row: dict) -> dict:
    """
    Given a dict of raw feature values (matching FEATURE_COLS),
    return {predicted_duration_min, predicted_capacity_loss}.
    """
    dur_bundle = joblib.load(OUT_DIR / "model_duration.joblib")
    cap_bundle = joblib.load(OUT_DIR / "model_capacity.joblib")

    def _predict(bundle, row_dict):
        feats = bundle["features"]
        X = pd.DataFrame([{f: row_dict.get(f, -1) for f in feats}])
        return bundle["model"].predict(X)[0]

    log_dur = _predict(dur_bundle, row)
    cap     = _predict(cap_bundle, row)

    return {
        "predicted_duration_min": float(np.expm1(log_dur)),
        "predicted_capacity_loss": float(np.clip(cap, 0.05, 0.95)),
    }


def run():
    df = pd.read_parquet(FEAT_IN)
    train_duration_model(df)
    train_capacity_model(df)


if __name__ == "__main__":
    run()
