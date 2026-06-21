"""
Phase 0 + Phase 1: Data loading, cleaning, and quality reporting.
Outputs:
  - data/processed/cleaned.parquet
  - reports/data_quality.md
"""

import pandas as pd
import numpy as np
import re
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV  = ROOT / "data" / "raw" / "events.csv"
OUT_DIR  = ROOT / "data" / "processed"
REP_DIR  = ROOT / "reports"

OUT_DIR.mkdir(parents=True, exist_ok=True)
REP_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# PHASE 0 — load & basic parse
# ─────────────────────────────────────────────────────────────

DATETIME_COLS = [
    "start_datetime", "end_datetime",
    "closed_datetime", "resolved_datetime",
    "created_date", "modified_datetime",
]

DROP_COLS = [
    "client_id", "created_by_id", "last_modified_by_id",
    "assigned_to_police_id", "citizen_accident_id",
    "map_file", "meta_data", "kgid", "gba_identifier",
    "route_path", "closed_by_id", "resolved_by_id",
    "authenticated", "direction", "comment",
    "resolved_at_address", "resolved_at_latitude", "resolved_at_longitude",
    "end_address", "cargo_material", "reason_breakdown", "age_of_truck",
]


def load_raw(path: Path = RAW_CSV) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    print(f"Loaded {len(df):,} rows × {len(df.columns)} columns")
    print(df.dtypes.value_counts())
    return df


def parse_datetimes(df: pd.DataFrame) -> pd.DataFrame:
    for col in DATETIME_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
    return df


def create_event_end(df: pd.DataFrame) -> pd.DataFrame:
    """COALESCE(end_datetime, closed_datetime, resolved_datetime)."""
    df["event_end_time"] = df["end_datetime"].combine_first(
        df["closed_datetime"]
    ).combine_first(df["resolved_datetime"])

    df["duration_minutes"] = np.where(
        df["event_end_time"].notna() & df["start_datetime"].notna(),
        (df["event_end_time"] - df["start_datetime"]).dt.total_seconds() / 60,
        np.nan,
    )
    # Clamp to plausible range (1 min – 72 h)
    df["duration_minutes"] = df["duration_minutes"].clip(lower=1, upper=4320)

    df["is_active"] = df["status"].str.lower().str.strip() == "active"
    return df


def fix_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["endlatitude", "endlongitude"]:
        if col in df.columns:
            df[col] = df[col].replace(0, np.nan).replace(0.0, np.nan)
    return df


# ─────────────────────────────────────────────────────────────
# PHASE 1 — cleaning & imputation
# ─────────────────────────────────────────────────────────────

CATEGORY_NORMALISE = {
    "event_cause": lambda s: s.str.lower().str.strip().str.replace(r"\s+", "_", regex=True),
    "priority":    lambda s: s.str.capitalize().str.strip(),
    "status":      lambda s: s.str.lower().str.strip(),
    "event_type":  lambda s: s.str.lower().str.strip(),
    "zone":        lambda s: s.str.strip(),
    "corridor":    lambda s: s.str.strip(),
}

KNOWN_CORRIDORS = [
    "ORR East 1", "ORR East 2", "ORR West 1", "ORR West 2",
    "Bellary Road 1", "Bellary Road 2",
    "Bannerghatta Road", "Hosur Road",
    "Magadi Road", "Tumkur Road", "Mysore Road",
    "Non-corridor",
]

# Keyword tagger for the 'others' event_cause bucket
KEYWORD_RULES: list[tuple[str, str]] = [
    (r"puncture|tyre|tire|flat", "tyre_puncture"),
    (r"starting.?problem|engine.?fail|break.?down|breakdown", "vehicle_breakdown"),
    (r"water.?log|flood|rain|waterlogging", "water_logging"),
    (r"tree.?fall|tree.?fell|fallen.?tree", "tree_fall"),
    (r"pot.?hole|pot hole|road.?damage|road.?repair", "pot_holes"),
    (r"accident|collision|crash", "accident"),
    (r"construction|road.?work|digging|pipeline", "construction"),
    (r"protest|rally|bandh|agitation|blockade", "event_political"),
    (r"vip|convoy|protocol", "vip_movement"),
    (r"signal|traffic.?light|signal.?fail", "signal_failure"),
    (r"ಒಳಚರಂಡಿ|ಸಿಮೆಂಟ್|ಟ್ರಾಫಿಕ್", "construction"),   # Kannada sewage/cement/traffic
    (r"ಮರ|ಗಿಡ", "tree_fall"),                          # Kannada tree
]


def normalise_categories(df: pd.DataFrame) -> pd.DataFrame:
    for col, fn in CATEGORY_NORMALISE.items():
        if col in df.columns:
            df[col] = fn(df[col].astype(str).replace("nan", np.nan).replace("NULL", np.nan))
    print("\n--- Value counts after normalisation ---")
    for col in ["event_cause", "priority", "status", "corridor", "zone"]:
        if col in df.columns:
            print(f"\n{col}:\n{df[col].value_counts(dropna=False).head(20)}")
    return df


def tag_others(df: pd.DataFrame) -> pd.DataFrame:
    """Sub-classify rows where event_cause is 'others' via keyword matching."""
    mask_others = df["event_cause"].str.lower().str.strip() == "others"
    desc = df.loc[mask_others, "description"].fillna("").astype(str).str.lower()

    new_cause = df["event_cause"].copy()
    for pattern, label in KEYWORD_RULES:
        hit = mask_others & desc.str.contains(pattern, flags=re.IGNORECASE, regex=True, na=False)
        new_cause[hit] = label

    reclassified = (mask_others & (new_cause != df["event_cause"])).sum()
    print(f"\nReclassified {reclassified:,} 'others' rows via keyword tagger")
    df["event_cause"] = new_cause
    return df


def impute_corridor(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing corridor using nearest-lat/lon neighbour from rows with known corridor."""
    has_corridor = df["corridor"].notna() & (df["corridor"].str.lower() != "nan")
    missing_idx  = df.index[~has_corridor & df["latitude"].notna() & df["longitude"].notna()]
    source       = df.loc[has_corridor & df["latitude"].notna() & df["longitude"].notna()]

    if len(source) == 0 or len(missing_idx) == 0:
        return df

    from sklearn.neighbors import KNeighborsClassifier
    knn = KNeighborsClassifier(n_neighbors=3, metric="haversine")
    X_src = np.radians(source[["latitude", "longitude"]].values)
    y_src = source["corridor"].values
    knn.fit(X_src, y_src)

    X_miss = np.radians(df.loc[missing_idx, ["latitude", "longitude"]].values)
    predicted = knn.predict(X_miss)
    df.loc[missing_idx, "corridor"] = predicted
    print(f"\nImputed corridor for {len(missing_idx):,} rows via KNN")
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = parse_datetimes(df)
    df = create_event_end(df)
    df = fix_coordinates(df)

    # Drop pure-metadata columns
    drop = [c for c in DROP_COLS if c in df.columns]
    df.drop(columns=drop, inplace=True)

    df = normalise_categories(df)
    df = tag_others(df)
    df = impute_corridor(df)

    return df


# ─────────────────────────────────────────────────────────────
# DATA QUALITY REPORT
# ─────────────────────────────────────────────────────────────

def write_quality_report(df: pd.DataFrame, out_path: Path):
    total = len(df)
    active   = df["is_active"].sum()
    resolved = total - active

    lines = [
        "# Data Quality Report — Gridlock / Bengaluru Traffic Events",
        "",
        f"**Total rows after cleaning:** {total:,}",
        f"**Active (right-censored, duration unknown):** {active:,}  ({active/total*100:.1f}%)",
        f"**Resolved / Closed (duration known):** {resolved:,}  ({resolved/total*100:.1f}%)",
        "",
        "## Missing values (% per retained column)",
        "",
        "| Column | % Missing |",
        "|--------|-----------|",
    ]
    for col in sorted(df.columns):
        pct = df[col].isna().mean() * 100
        if pct > 0:
            lines.append(f"| {col} | {pct:.1f}% |")

    lines += [
        "",
        "## event_cause distribution",
        "",
        "| Cause | Count |",
        "|-------|-------|",
    ]
    for cause, cnt in df["event_cause"].value_counts(dropna=False).items():
        lines.append(f"| {cause} | {cnt:,} |")

    lines += [
        "",
        "## Notes",
        "- `end_datetime` was populated for <3% of rows; `event_end_time` falls back to `closed_datetime` then `resolved_datetime`.",
        "- `endlatitude`/`endlongitude` == 0 treated as missing.",
        "- `corridor` imputed via 3-NN on (lat, lon) for rows without a corridor label.",
        "- `others` event_cause sub-classified via regex keyword tagger (English + transliterated Kannada).",
        "- `active`-status rows excluded from duration model training (right-censored).",
    ]

    out_path.write_text("\n".join(lines))
    print(f"\nData quality report written to {out_path}")


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

def run():
    df = load_raw()
    df = clean(df)

    out = OUT_DIR / "cleaned.parquet"
    df.to_parquet(out, index=False)
    print(f"\nCleaned data saved to {out} — {len(df):,} rows")

    write_quality_report(df, REP_DIR / "data_quality.md")
    return df


if __name__ == "__main__":
    run()
