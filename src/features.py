"""
Phase 2: Feature engineering.
Outputs: data/processed/features.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.preprocessing import LabelEncoder
import joblib

ROOT      = Path(__file__).resolve().parent.parent
CLEAN_IN  = ROOT / "data" / "processed" / "cleaned.parquet"
OUT_DIR   = ROOT / "data" / "processed"

IST_OFFSET = pd.Timedelta(hours=5, minutes=30)

PEAK_MORNING = (7, 10)   # IST
PEAK_EVENING = (17, 20)  # IST

N_CLUSTERS = 20   # KMeans spatial clusters


def load_cleaned() -> pd.DataFrame:
    return pd.read_parquet(CLEAN_IN)


# ─── Temporal ───────────────────────────────────────────────────────────────

def add_temporal(df: pd.DataFrame) -> pd.DataFrame:
    ist_start = df["start_datetime"] + IST_OFFSET
    df["hour_of_day"]  = ist_start.dt.hour
    df["day_of_week"]  = ist_start.dt.dayofweek          # 0=Mon … 6=Sun
    df["is_weekend"]   = df["day_of_week"].isin([5, 6]).astype(int)
    df["month"]        = ist_start.dt.month
    df["date"]         = ist_start.dt.date

    def is_peak(h):
        return int((PEAK_MORNING[0] <= h < PEAK_MORNING[1]) or
                   (PEAK_EVENING[0] <= h < PEAK_EVENING[1]))

    df["is_peak_hour"] = df["hour_of_day"].apply(is_peak)
    return df


# ─── Spatial ────────────────────────────────────────────────────────────────

def add_spatial_clusters(df: pd.DataFrame) -> pd.DataFrame:
    valid = df[["latitude", "longitude"]].dropna()
    if len(valid) < N_CLUSTERS:
        df["location_cluster"] = 0
        return df

    km = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init="auto")
    km.fit(valid)
    df["location_cluster"] = -1
    df.loc[valid.index, "location_cluster"] = km.labels_

    model_path = OUT_DIR / "kmeans_spatial.joblib"
    joblib.dump(km, model_path)
    print(f"KMeans model saved to {model_path}")
    return df


# ─── Event features ─────────────────────────────────────────────────────────

def add_event_features(df: pd.DataFrame) -> pd.DataFrame:
    df["requires_road_closure_bin"] = (
        df["requires_road_closure"].astype(str).str.upper().str.strip() == "TRUE"
    ).astype(int)

    # Priority encoding
    priority_map = {"Low": 0, "Medium": 1, "High": 2}
    df["priority_num"] = df["priority"].map(priority_map).fillna(1).astype(int)

    # event_type binary
    df["is_unplanned"] = (df["event_type"] == "unplanned").astype(int)

    return df


# ─── Historical context ──────────────────────────────────────────────────────

def add_historical_context(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("start_datetime").reset_index(drop=True)
    df["start_dt_utc"] = pd.to_datetime(df["start_datetime"], utc=True, errors="coerce")

    # Rolling incident count on same corridor in trailing 7 / 30 days
    df["corridor_incident_7d"]  = 0
    df["corridor_incident_30d"] = 0

    window7  = pd.Timedelta(days=7)
    window30 = pd.Timedelta(days=30)
    for corridor, grp in df.groupby("corridor", dropna=True):
        times = grp["start_dt_utc"]
        counts7, counts30 = [], []
        for t in times:
            counts7.append(int(((times >= t - window7) & (times < t)).sum()))
            counts30.append(int(((times >= t - window30) & (times < t)).sum()))
        df.loc[grp.index, "corridor_incident_7d"]  = counts7
        df.loc[grp.index, "corridor_incident_30d"] = counts30

    # Average historical duration for (corridor, event_cause) pair
    # Using expanding mean over time to prevent data leakage
    hist_means: dict[tuple, list] = {}
    avg_col = []
    for _, row in df.iterrows():
        key = (row["corridor"], row["event_cause"])
        vals = hist_means.get(key, [])
        avg_col.append(np.mean(vals) if vals else np.nan)
        if not np.isnan(row["duration_minutes"]):
            hist_means.setdefault(key, []).append(row["duration_minutes"])

    df["hist_avg_duration"] = avg_col

    # Global fallback mean per event_cause
    global_means = df.groupby("event_cause")["duration_minutes"].transform("mean")
    df["hist_avg_duration"] = df["hist_avg_duration"].fillna(global_means)

    return df


# ─── Encode categoricals ──────────────────────────────────────────────────────

CATEGORICAL_COLS = ["event_cause", "corridor", "zone", "junction", "veh_type"]


def encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    encoders = {}
    for col in CATEGORICAL_COLS:
        if col not in df.columns:
            continue
        le = LabelEncoder()
        filled = df[col].fillna("__missing__").astype(str)
        df[f"{col}_enc"] = le.fit_transform(filled)
        encoders[col] = le

    enc_path = OUT_DIR / "label_encoders.joblib"
    joblib.dump(encoders, enc_path)
    print(f"Label encoders saved to {enc_path}")
    return df


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

MODEL_FEATURES = [
    "hour_of_day", "day_of_week", "is_weekend", "is_peak_hour", "month",
    "requires_road_closure_bin", "priority_num", "is_unplanned",
    "location_cluster",
    "corridor_incident_7d", "corridor_incident_30d", "hist_avg_duration",
    "event_cause_enc", "corridor_enc", "zone_enc", "junction_enc", "veh_type_enc",
]


def run():
    df = load_cleaned()
    df = add_temporal(df)
    df = add_spatial_clusters(df)
    df = add_event_features(df)
    df = add_historical_context(df)
    df = encode_categoricals(df)

    out = OUT_DIR / "features.parquet"
    df.to_parquet(out, index=False)
    print(f"\nFeature table saved to {out} — {len(df):,} rows, {len(df.columns)} columns")
    return df


if __name__ == "__main__":
    run()
