"""
Phase 5: Calibrate CTM capacity-loss parameters against historical durations.
Produces: reports/calibration_plot.png
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.optimize import minimize
from sklearn.metrics import r2_score
from ctm_simulation import simulate_incident, get_road_type, ROAD_PARAMS

ROOT    = Path(__file__).resolve().parent.parent
FEAT_IN = ROOT / "data" / "processed" / "features.parquet"
REP_DIR = ROOT / "reports"
REP_DIR.mkdir(parents=True, exist_ok=True)


# ── Default heuristic capacity-loss table ─────────────────────────────────────

DEFAULT_PARAMS = {
    "closure_true":         0.92,
    "high_breakdown":       0.55,
    "high_accident":        0.55,
    "water_logging":        0.50,
    "tree_fall_noncorr":    0.95,
    "pot_holes_low":        0.12,
    "vip_movement":         0.30,
    "default":              0.25,
}


def row_to_capacity_loss(row: pd.Series, params: dict) -> float:
    cause    = str(row.get("event_cause", "")).lower()
    corridor = str(row.get("corridor", "")).lower()
    closure  = bool(row.get("requires_road_closure_bin", 0))
    priority = int(row.get("priority_num", 1))

    if closure:
        return params["closure_true"]
    if priority >= 2 and "vehicle_breakdown" in cause:
        return params["high_breakdown"]
    if priority >= 2 and "accident" in cause:
        return params["high_accident"]
    if "water_log" in cause:
        return params["water_logging"]
    if "tree_fall" in cause and "non-corridor" in corridor:
        return params["tree_fall_noncorr"]
    if "pot_hole" in cause and priority <= 0:
        return params["pot_holes_low"]
    if "vip" in cause:
        return params["vip_movement"]
    return params["default"]


# ── Run simulation on a subset of historical incidents ────────────────────────

def simulate_batch(df: pd.DataFrame, params: dict, max_rows: int = 300) -> pd.DataFrame:
    """
    Run CTM on resolved incidents with known duration. Return comparison table.
    Limit to max_rows for speed.
    """
    valid = df[
        df["duration_minutes"].notna() &
        ~df["is_active"] &
        df["corridor"].notna() &
        (df["duration_minutes"] > 5) &
        (df["duration_minutes"] < 600)
    ].copy()

    # Stratify by event_cause so all causes are represented
    sampled = (
        valid.groupby("event_cause", group_keys=False)
        .apply(lambda g: g.sample(min(len(g), max(1, max_rows // 20)), random_state=42))
    )
    sampled = sampled.sample(min(len(sampled), max_rows), random_state=42)

    records = []
    for _, row in sampled.iterrows():
        cap_loss = row_to_capacity_loss(row, params)
        corridor = str(row.get("corridor", "Non-corridor"))
        duration = float(row["duration_minutes"])

        try:
            result = simulate_incident(
                corridor=corridor,
                duration_min=duration,      # feed real duration as "input" for calibration
                capacity_loss=cap_loss,
                upstream_demand_frac=0.70,
            )
            sim_clearance = result.clearance_time_min
        except Exception as e:
            sim_clearance = np.nan

        records.append({
            "id":              row.get("id", ""),
            "event_cause":     row.get("event_cause", ""),
            "corridor":        corridor,
            "actual_duration": duration,
            "capacity_loss":   cap_loss,
            "sim_clearance":   sim_clearance,
        })

    return pd.DataFrame(records)


# ── Optimise capacity-loss parameters ─────────────────────────────────────────

def calibrate(df: pd.DataFrame) -> dict:
    print("Running initial simulation batch for calibration...")
    init_table = simulate_batch(df, DEFAULT_PARAMS, max_rows=300)
    init_table = init_table.dropna(subset=["sim_clearance"])

    actual = init_table["actual_duration"].values
    
    def objective(x: np.ndarray) -> float:
        keys = list(DEFAULT_PARAMS.keys())
        params = {k: float(np.clip(x[i], 0.05, 0.98)) for i, k in enumerate(keys)}
        
        sim_vals = []
        for _, row in init_table.iterrows():
            cap_loss = row_to_capacity_loss(row, params)
            corridor = str(row.get("corridor", "Non-corridor"))
            try:
                result = simulate_incident(
                    corridor=corridor,
                    duration_min=float(row["actual_duration"]),
                    capacity_loss=cap_loss,
                )
                sim_vals.append(result.clearance_time_min)
            except Exception:
                sim_vals.append(float(row["actual_duration"]))
        return float(np.mean(np.abs(np.array(sim_vals) - actual)))

    x0     = np.array(list(DEFAULT_PARAMS.values()))
    bounds = [(0.05, 0.98)] * len(x0)

    print("Optimising capacity-loss parameters via scipy.optimize.minimize...")
    try:
        res = minimize(objective, x0, method="Nelder-Mead", bounds=None,
                       options={"maxiter": 80, "xatol": 0.01, "fatol": 0.5})
        keys = list(DEFAULT_PARAMS.keys())
        tuned_params = {k: float(np.clip(res.x[i], 0.05, 0.98))
                        for i, k in enumerate(keys)}
        print(f"Optimisation complete. Final MAE: {res.fun:.1f} min")
    except Exception as e:
        print(f"Optimisation failed ({e}), using defaults")
        tuned_params = DEFAULT_PARAMS.copy()

    return tuned_params


# ── Produce calibration plot ───────────────────────────────────────────────────

def make_calibration_plot(df: pd.DataFrame, params: dict):
    print("Generating calibration dataset...")
    table = simulate_batch(df, params, max_rows=400)
    table = table.dropna(subset=["sim_clearance"])

    actual = table["actual_duration"].values
    simmed = table["sim_clearance"].values

    r2   = r2_score(actual, simmed) if len(actual) > 1 else float("nan")
    mae  = float(np.mean(np.abs(actual - simmed)))

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("#0f1117")

    ax = axes[0]
    ax.set_facecolor("#1a1d26")

    causes    = table["event_cause"].unique()
    colors    = plt.cm.tab20(np.linspace(0, 1, len(causes)))
    color_map = dict(zip(causes, colors))

    for cause, grp in table.groupby("event_cause"):
        ax.scatter(grp["actual_duration"], grp["sim_clearance"],
                   label=cause, alpha=0.7, s=40,
                   color=color_map.get(cause, "white"))

    lim = max(actual.max(), simmed.max()) * 1.05
    ax.plot([0, lim], [0, lim], "w--", lw=1.5, alpha=0.5, label="Perfect fit")
    ax.set_xlabel("Actual Duration (min)", color="white", fontsize=12)
    ax.set_ylabel("Simulated Clearance (min)", color="white", fontsize=12)
    ax.set_title(f"Simulated vs Actual Duration\n R² = {r2:.3f}  |  MAE = {mae:.1f} min",
                 color="white", fontsize=13)
    ax.tick_params(colors="white")
    ax.spines[:].set_color("#333")
    ax.legend(fontsize=7, loc="upper left", facecolor="#1a1d26",
              labelcolor="white", framealpha=0.6)

    # Per-cause box plot
    ax2 = axes[1]
    ax2.set_facecolor("#1a1d26")
    residuals_by_cause = {
        cause: (grp["sim_clearance"] - grp["actual_duration"]).values
        for cause, grp in table.groupby("event_cause")
        if len(grp) >= 3
    }
    if residuals_by_cause:
        labels_sorted = sorted(residuals_by_cause.keys(),
                               key=lambda k: np.median(residuals_by_cause[k]))
        data = [residuals_by_cause[k] for k in labels_sorted]
        bp = ax2.boxplot(data, tick_labels=labels_sorted, patch_artist=True,
                         medianprops={"color": "yellow", "linewidth": 2})
        for patch, cause in zip(bp["boxes"], labels_sorted):
            patch.set_facecolor(color_map.get(cause, "steelblue"))
            patch.set_alpha(0.7)
        ax2.axhline(0, color="white", lw=1.5, linestyle="--", alpha=0.6)
        ax2.set_xlabel("Event Cause", color="white", fontsize=12)
        ax2.set_ylabel("Residual (sim − actual) min", color="white", fontsize=12)
        ax2.set_title("Calibration Residuals by Cause", color="white", fontsize=13)
        ax2.tick_params(colors="white", axis="both")
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=8)
        ax2.spines[:].set_color("#333")

    plt.tight_layout()
    out = REP_DIR / "calibration_plot.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Calibration plot saved to {out}  (R²={r2:.3f}, MAE={mae:.1f} min)")

    return table, r2, mae


def run():
    df = pd.read_parquet(FEAT_IN)
    params = calibrate(df)
    print("\nTuned capacity-loss parameters:")
    for k, v in params.items():
        print(f"  {k:25s}: {v:.3f}")
    table, r2, mae = make_calibration_plot(df, params)
    return params, table, r2, mae


if __name__ == "__main__":
    run()
