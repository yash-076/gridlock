"""
Phase 4: Cell Transmission Model (CTM) — LWR kinematic wave PDE solver.

Models each corridor as a 1-D array of N=25 cells × 200m = 5km.
The incident is placed at a configurable cell index.
Produces a space-time density matrix for the space-time diagram.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional


# ── Road-type defaults ─────────────────────────────────────────────────────────

ROAD_PARAMS = {
    "ring_road":  {"v_free": 60.0,  "rho_jam": 120.0, "capacity": 1800.0},
    "arterial":   {"v_free": 40.0,  "rho_jam": 140.0, "capacity": 1500.0},
    "local":      {"v_free": 25.0,  "rho_jam": 160.0, "capacity":  900.0},
}

CORRIDOR_TYPE_MAP = {
    "ORR East 1":      "ring_road",
    "ORR East 2":      "ring_road",
    "ORR West 1":      "ring_road",
    "ORR West 2":      "ring_road",
    "Bellary Road 1":  "arterial",
    "Bellary Road 2":  "arterial",
    "Bannerghatta Road": "arterial",
    "Hosur Road":      "arterial",
    "Magadi Road":     "arterial",
    "Tumkur Road":     "arterial",
    "Mysore Road":     "arterial",
    "Non-corridor":    "local",
}


def get_road_type(corridor: str) -> str:
    if not corridor or str(corridor).lower() in ("nan", "none", ""):
        return "local"
    for key, rtype in CORRIDOR_TYPE_MAP.items():
        if key.lower() in str(corridor).lower():
            return rtype
    return "local"


# ── CTM Configuration ──────────────────────────────────────────────────────────

@dataclass
class CTMConfig:
    N: int = 25                    # number of cells
    dx: float = 200.0              # cell length, metres
    dt: float = 12.0               # time step, seconds
    incident_cell: int = 12        # 0-indexed cell where incident occurs
    road_type: str = "arterial"
    capacity_loss: float = 0.50    # fraction capacity removed by incident (0=none,1=full)
    incident_duration_min: float = 60.0  # predicted duration from ML model
    max_sim_steps: int = 1500      # hard upper bound (~5 hours at dt=12s)
    upstream_demand_frac: float = 0.70   # upstream inflow as fraction of free-flow capacity


@dataclass
class CTMResult:
    density_matrix: np.ndarray     # shape (T, N), vehicles/km/lane
    flow_matrix: np.ndarray        # shape (T, N-1)
    time_axis_min: np.ndarray      # T timestamps in minutes from sim start
    cell_positions_m: np.ndarray   # N cell midpoint positions in metres
    max_queue_km: float
    peak_queue_time_min: float
    clearance_time_min: float
    incident_duration_min: float
    config: CTMConfig


# ── CTM Solver ────────────────────────────────────────────────────────────────

def run_ctm(cfg: CTMConfig) -> CTMResult:
    """
    Godunov scheme CTM implementation of the LWR kinematic wave equation.

    ∂ρ/∂t + ∂q/∂x = 0  (conservation of vehicles)

    Triangular fundamental diagram:
      q = min(v_free * ρ, w * (ρ_jam - ρ))
    where w = backward wave speed = capacity / (ρ_jam - ρ_crit)
    """
    params  = ROAD_PARAMS[cfg.road_type]
    v_free  = params["v_free"]          # km/h
    rho_jam = params["rho_jam"]         # veh/km/lane
    cap_max = params["capacity"]        # veh/h/lane

    # Convert units to metres and seconds for numerical stability
    v_free_ms  = v_free * 1000 / 3600   # m/s
    rho_jam_pm = rho_jam / 1000         # veh/m/lane
    cap_max_ps = cap_max / 3600         # veh/s/lane

    # Critical density and backward wave speed
    rho_crit_pm = cap_max_ps / v_free_ms  # veh/m (from q = v_free * rho_crit)
    w_ms        = cap_max_ps / (rho_jam_pm - rho_crit_pm)  # m/s backward wave

    # CFL stability check: dt <= dx / max(v_free, w)
    dt_max = cfg.dx / max(v_free_ms, w_ms)
    dt     = min(cfg.dt, dt_max * 0.9)  # ensure numerical stability

    # Initial conditions: free-flow at upstream demand fraction
    rho0 = cfg.upstream_demand_frac * rho_crit_pm  # initial density
    rho  = np.full(cfg.N, rho0, dtype=float)       # veh/m/lane

    # Per-cell capacity (incident cell reduced)
    cap  = np.full(cfg.N, cap_max_ps, dtype=float)
    incident_cap = cap_max_ps * (1.0 - cfg.capacity_loss)
    cap[cfg.incident_cell] = max(incident_cap, cap_max_ps * 0.02)  # never fully 0

    # Simulation time
    incident_steps = int(cfg.incident_duration_min * 60 / dt)

    density_hist: list[np.ndarray] = []
    flow_hist:    list[np.ndarray] = []
    time_hist:    list[float]      = []

    baseline_rho = rho0                    # target "cleared" density
    cleared       = False
    clearance_step = cfg.max_sim_steps

    for step in range(cfg.max_sim_steps):
        t_sec = step * dt
        t_min = t_sec / 60.0

        density_hist.append(rho.copy())
        time_hist.append(t_min)

        # Restore capacity once predicted duration elapses
        if step == incident_steps:
            cap[cfg.incident_cell] = cap_max_ps

        # Check clearance: max density falls back near baseline
        if step > incident_steps + 30:
            if np.max(rho) < baseline_rho * 1.10 and not cleared:
                cleared        = True
                clearance_step = step

        # Sending and receiving functions
        S = np.minimum(v_free_ms * rho, cap)
        R = np.minimum(cap, w_ms * (rho_jam_pm - rho))
        R = np.maximum(R, 0.0)

        # Inter-cell flows: y[i] = flow from cell i to cell i+1
        y = np.minimum(S[:-1], R[1:])
        flow_hist.append(y.copy())

        # Boundary conditions
        # Upstream (left) inflow: demand at upstream_demand_frac of capacity
        inflow  = min(cfg.upstream_demand_frac * cap_max_ps, R[0])
        outflow = min(S[-1], cap_max_ps)  # free exit downstream

        # Update densities
        rho_new = rho.copy()
        rho_new[0]    += (dt / cfg.dx) * (inflow    - y[0])
        rho_new[1:-1] += (dt / cfg.dx) * (y[:-1]    - y[1:])
        rho_new[-1]   += (dt / cfg.dx) * (y[-1]     - outflow)
        rho_new = np.clip(rho_new, 0.0, rho_jam_pm)

        rho = rho_new

        # Early exit if cleared
        if cleared and step > clearance_step + 60:
            break

    density_mat_raw = np.array(density_hist)         # (T, N), veh/m/lane
    flow_mat_raw    = np.array(flow_hist)            # (T-1, N-1)

    # Convert back to veh/km/lane for interpretability
    density_mat = density_mat_raw * 1000.0
    cell_pos_m  = np.arange(cfg.N) * cfg.dx + cfg.dx / 2  # midpoints

    # Queue length: cells with density > 80% jam density
    rho_jam_pkm = rho_jam  # veh/km/lane
    jam_thresh  = 0.80 * rho_jam_pkm
    queue_cells = np.sum(density_mat > jam_thresh, axis=1)  # (T,)
    max_queue_cells = int(np.max(queue_cells))
    max_queue_km    = max_queue_cells * cfg.dx / 1000.0

    peak_idx         = int(np.argmax(queue_cells))
    peak_queue_t_min = float(time_hist[peak_idx]) if time_hist else 0.0

    clearance_t_min = float(time_hist[min(clearance_step, len(time_hist) - 1)])

    return CTMResult(
        density_matrix    = density_mat,
        flow_matrix       = flow_mat_raw * 3600.0,    # convert to veh/h/lane
        time_axis_min     = np.array(time_hist),
        cell_positions_m  = cell_pos_m,
        max_queue_km      = max_queue_km,
        peak_queue_time_min = peak_queue_t_min,
        clearance_time_min  = clearance_t_min,
        incident_duration_min = cfg.incident_duration_min,
        config            = cfg,
    )


# ── Convenience wrapper ────────────────────────────────────────────────────────

def simulate_incident(
    corridor: str,
    duration_min: float,
    capacity_loss: float,
    incident_cell: int = 12,
    upstream_demand_frac: float = 0.70,
) -> CTMResult:
    road_type = get_road_type(corridor)
    cfg = CTMConfig(
        road_type=road_type,
        capacity_loss=capacity_loss,
        incident_duration_min=duration_min,
        incident_cell=incident_cell,
        upstream_demand_frac=upstream_demand_frac,
    )
    return run_ctm(cfg)


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running sample CTM simulation (ring road, 60-min breakdown, 55% capacity loss)...")
    result = simulate_incident(
        corridor="ORR East 1",
        duration_min=60.0,
        capacity_loss=0.55,
    )
    print(f"Max queue:         {result.max_queue_km:.2f} km")
    print(f"Peak queue time:   {result.peak_queue_time_min:.1f} min")
    print(f"Clearance time:    {result.clearance_time_min:.1f} min")
    print(f"Sim steps (T):     {len(result.time_axis_min)}")
    print(f"Density matrix:    {result.density_matrix.shape}")
