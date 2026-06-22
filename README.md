# GR🚦DLOCK BUTTERMASALA
### Event-Driven Congestion Forecasting & Response Simulation

Flipkart Hackathon — Problem Statement: "Planned & Unplanned Congestion"

---

## Overview
Bengaluru loses thousands of person-hours daily to traffic incidents — vehicle breakdowns on the ORR, tree falls after a monsoon shower, VIP convoys on arterials. Today, traffic police deploy resources from experience alone, with no quantified impact forecast and no post-event learning loop.

GRIDLOCK BUTTERMASALA changes that in three steps:

| Step | What it does |
| :--- | :--- |
| **Predict** | XGBoost ML model forecasts incident duration and road capacity loss |
| **Simulate** | Cell Transmission Model (CTM) solves the LWR traffic-flow PDE and renders a shockwave space-time diagram |
| **Recommend** | Converts simulation output into a concrete deployment plan: officers, barricades, and diversion route |

---

## Quick Start
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the full pipeline (~2–3 minutes)
cd gridlock/
python src/clean.py         
python src/features.py       
python src/graph_build.py    
python src/forecast_model.py 
python src/calibrate.py      # calibrate CTM vs real data

# 3. Launch the dashboard
streamlit run app/dashboard.py
```

---

## Repository Structure
```
gridlock/
├── data/
│   ├── raw/                     # Original Bengaluru Traffic Police CSV (~8,000 rows)
│   └── processed/               # cleaned.parquet, features.parquet, ML models, road graph
├── reports/
│   ├── data_quality.md          # Cleaning audit (missing values, label distributions)
│   ├── calibration_plot.png     # Simulated vs actual duration scatter (R² annotated)
│   └── shap_summary.png         # Feature importance for the duration model
├── src/
│   ├── clean.py                 # Phase 0+1: load, parse, deduplicate, quality report
│   ├── features.py              # Phase 2:   temporal, spatial, event, historical features
│   ├── graph_build.py           # Phase 2b:  NetworkX road graph (junctions + corridors)
│   ├── forecast_model.py        # Phase 3:   XGBoost duration & capacity-loss models
│   ├── ctm_simulation.py        # Phase 4:   CTM / LWR PDE solver (Godunov scheme)
│   ├── calibrate.py             # Phase 5:   scipy optimisation + calibration plot
│   └── recommend.py             # Phase 6:   officers / barricades / Dijkstra diversion
└── app/
    └── dashboard.py             # Phase 7:   Streamlit interactive dashboard
```

---

## Simulation Engine
The simulation uses a **Cell Transmission Model (CTM)**, the standard discrete-time approximation of the Lighthill–Whitham–Richards (LWR) kinematic wave PDE:

$$\frac{\partial\rho}{\partial t} + \frac{\partial q}{\partial x} = 0$$

with a triangular fundamental diagram and Godunov flux.

### What the model does
Each affected corridor is divided into $N$ equal cells. When an incident is reported, the incident cell's capacity drops by a predicted fraction for the predicted duration. The CTM update rule propagates the resulting density wave backward (upstream), forming a queue that grows until capacity is restored, then dissipates forward.

Each corridor is modelled as 25 cells × 200 m = 5 km, with the incident placed at cell 12. The solver runs the Godunov update scheme at a 12-second timestep:

#### Variables
```
  ρ_i       density in cell i       [veh/km]
  v_free    free-flow speed         [km/h]
  w         backward wave speed     [km/h]
  ρ_jam     jam density             [veh/km]
  Δt        timestep  =  12 s
  Δx        cell length = 200 m
```

#### Godunov Update
```
  S_i  =  min( ρ_i · v_free,  capacity_i )           (sending function)
  R_i  =  min( capacity_i,    w · (ρ_jam − ρ_i) )    (receiving function)
  y_i  =  min( S_i,  R_{i+1} )                        (inter-cell flow)

  ρ_i(t + Δt)  =  ρ_i(t)  +  (Δt / Δx) · ( y_{i−1} − y_i )
```

Road type parameters used by the solver:

| Road Type | v_free (km/h) | ρ_jam (veh/km) | Capacity (veh/h) |
| :--- | :---: | :---: | :---: |
| Ring road (ORR, Bellary Rd) | 60 | 120 | 1,800 |
| Arterial (Hosur, Bannerghatta, Magadi, Tumkur, Mysore) | 40 | 140 | 1,500 |
| Local / Non-corridor | 25 | 160 | 900 |

The output is a space-time density heatmap (shockwave diagram) showing the queue forming upstream of the incident and dissipating after capacity is restored.

### What the dataset provides
The dataset contains incident location, cause, priority, corridor, and resolved timestamps but no speed, density, or flow sensor readings. Initial conditions and capacity parameters are therefore derived from corridor type, not measured directly.

---

## ML Models
| Model | Target | Algorithm | Notes |
| :--- | :--- | :--- | :--- |
| **Duration** | duration_minutes | XGBoost regressor | Log-transformed target; trained on resolved incidents only |
| **Capacity loss** | capacity_loss_fraction | XGBoost regressor | Heuristic label (see Assumptions); not directly observed |

Top features (SHAP): `hist_avg_duration`, `hour_of_day`, `corridor_incident_7d`, `priority_num`, `event_cause_enc`.

---

## Dashboard Views
| Tab | What you see |
| :--- | :--- |
| **Replay Mode** | Timeline slider steps through a historical day; incidents appear on a dark Plotly map of Bengaluru coloured by event cause |
| **Incident Detail** | Select any incident to view ML prediction + CTM space-time diagram + officer/barricade/diversion recommendation |
| **Calibration** | Scatter plot of simulated clearance time vs actual duration (R² annotated) + SHAP feature importance |
| **What-If** | Adjust corridor / duration / priority / closure and trigger a live CTM re-run |

---

## Assumptions
Being explicit about assumptions is a scientific strength, not a weakness.

- **Synthetic corridor cells** — The dataset contains point coordinates, not road polylines. Each corridor is modelled as a uniform 1-D array of 25 × 200 m cells with the incident placed at the midpoint. This is standard for single-link CTM studies and is explicitly documented.
- **Heuristic capacity-loss label** — There is no ground-truth sensor data for capacity loss. A rule-based label is derived from `requires_road_closure`, `priority`, and `event_cause`, then the model is trained to reproduce this heuristic. The label logic is published in `src/forecast_model.py` and tuned against real durations in Phase 5.
- **Dataset composition** — The ~8,000 rows are dominated by reactive micro-incidents (breakdowns, punctures, potholes) rather than planned mega-events (rallies, festivals). GRIDLOCK generalises by treating every incident as "a capacity drop of estimated magnitude at a network point for a predicted duration" — the physics applies regardless of cause.
- **Road graph approximation** — Junction connectivity is reconstructed from the junction and corridor columns of the CSV. Edge lengths are approximated from the coordinate spread of incidents along each corridor. This is adequate for diversion routing at hackathon scope; production would use OpenStreetMap polylines.

---

## Tech Stack
`pandas` · `numpy` · `scikit-learn` · `xgboost` · `shap` · `networkx` · `scipy` · `plotly` · `folium` · `streamlit`

---
Built for the Flipkart Hackathon — June 2026
