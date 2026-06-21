    # GRIDLOCK
    ### Event-Driven Congestion Forecasting & Response Simulation
    ### Flipkart Hackathon — Problem Statement: "Planned & Unplanned Congestion"

    ---

    ```
    GR●●●DLOCK
    [ predict → simulate → recommend ]
    ```

    ---

    ## What This System Does

    Bengaluru loses thousands of person-hours daily to traffic incidents—vehicle breakdowns on the ORR, tree falls after a monsoon shower, VIP convoys on arterials. Today, traffic police deploy resources from experience alone, with no quantified impact forecast and no post-event learning loop.

    **GRIDLOCK** changes that in three steps:

    | Step | What it does |
    |------|-------------|
    | **Predict** | ML model (XGBoost) forecasts how long an incident will last and how much road capacity it removes |
    | **Simulate** | Cell Transmission Model (CTM) solves the LWR traffic-flow PDE and shows the shockwave queue forming and clearing as a space-time diagram |
    | **Recommend** | Converts simulation output into a concrete deployment plan: officers, barricades, diversion route |

    ---

    ## Quick Start

    ```bash
    # 1. Install dependencies
    pip install -r requirements.txt

    # 2. Run the full pipeline (takes ~2–3 minutes)
    cd gridlock/
    python src/clean.py          # Phase 0+1: clean & parse
    python src/features.py       # Phase 2:   feature engineering
    python src/graph_build.py    # Phase 2b:  road network graph
    python src/forecast_model.py # Phase 3:   train XGBoost models + SHAP
    python src/calibrate.py      # Phase 5:   calibrate CTM vs real data

    # 3. Launch the dashboard
    streamlit run app/dashboard.py
    ```

    ---

    ## Repository Structure

    ```
    gridlock/
    ├── data/
    │   ├── raw/          → original Bengaluru Traffic Police CSV (~8 000 rows)
    │   └── processed/    → cleaned.parquet, features.parquet, ML models, road graph
    ├── reports/
    │   ├── data_quality.md      → cleaning audit (missing values, label distributions)
    │   ├── calibration_plot.png → simulated vs actual duration scatter (R² annotated)
    │   └── shap_summary.png     → feature importance for the duration model
    ├── src/
    │   ├── clean.py             → Phase 0+1: load, parse, deduplicate, quality report
    │   ├── features.py          → Phase 2:   temporal, spatial, event, historical features
    │   ├── graph_build.py       → Phase 2b:  NetworkX road graph (junctions + corridors)
    │   ├── forecast_model.py    → Phase 3:   XGBoost duration & capacity-loss models
    │   ├── ctm_simulation.py    → Phase 4:   CTM / LWR PDE solver (Godunov scheme)
    │   ├── calibrate.py         → Phase 5:   scipy optimisation + calibration plot
    │   └── recommend.py         → Phase 6:   officers / barricades / Dijkstra diversion
    └── app/
        └── dashboard.py         → Phase 7:   Streamlit interactive dashboard
    ```

    ---

    ## The Simulation Engine (Phase 4)

    The centerpiece is a **Cell Transmission Model (CTM)** — the standard finite-difference discretisation of the **Lighthill–Whitham–Richards (LWR)** kinematic wave PDE:

    ```
    ∂ρ/∂t + ∂q/∂x = 0
    ```

    Each corridor is modelled as **25 cells × 200 m = 5 km**, with the incident placed at cell 12. The solver runs the Godunov update scheme at a 12-second timestep:

    ```
    S_i  = min(ρ_i · v_free, capacity_i)         # sending function
    R_i  = min(capacity_i, w · (ρ_jam − ρ_i))   # receiving function
    y_i  = min(S_i, R_{i+1})                     # inter-cell flow
    ρ_i(t+Δt) = ρ_i(t) + (Δt/Δx) · (y_{i-1} − y_i)
    ```

    **Road type parameters:**

    | Road type | v_free (km/h) | ρ_jam (veh/km) | Capacity (veh/h) |
    |-----------|--------------|----------------|------------------|
    | Ring road (ORR, Bellary Rd) | 60 | 120 | 1 800 |
    | Arterial (Hosur, Bannerghatta, Magadi, Tumkur, Mysore) | 40 | 140 | 1 500 |
    | Local / Non-corridor | 25 | 160 | 900 |

    The output is a **space-time density heatmap** (shockwave diagram) showing the queue forming upstream of the incident and dissipating after capacity is restored.

    ---

    ## ML Models (Phase 3)

    | Model | Target | Algorithm | Notes |
    |-------|--------|-----------|-------|
    | Duration | `duration_minutes` | XGBoost regressor | Log-transformed target; trained on resolved incidents only |
    | Capacity loss | `capacity_loss_fraction` | XGBoost regressor | **Heuristic label** (see Assumptions); not directly observed |

    **Top features (from SHAP):** `hist_avg_duration`, `hour_of_day`, `corridor_incident_7d`, `priority_num`, `event_cause_enc`

    ---

    ## Assumptions (Transparent by Design)

    Being explicit about assumptions is a scientific strength, not a weakness.

    **(a) Synthetic corridor cells** — The dataset contains point coordinates, not road polylines. We model each corridor as a uniform 1-D array of 25 × 200 m cells. The incident is placed at the midpoint. This is standard for single-link CTM studies and is explicitly documented.

    **(b) Heuristic capacity-loss label** — There is no ground-truth sensor data for capacity loss. We derive a rule-based label from `requires_road_closure`, `priority`, and `event_cause`, then train the model to reproduce this heuristic. The label logic is published in `src/forecast_model.py` and tuned against real durations in Phase 5.

    **(c) Dataset composition** — The ~8 000 rows are dominated by reactive micro-incidents (breakdowns, punctures, pot-holes) rather than planned mega-events (rallies, festivals). GRIDLOCK generalises by treating every incident as "a capacity drop of estimated magnitude at a network point for a predicted duration" — the physics applies regardless of cause.

    **(d) Road graph approximation** — Junction connectivity is reconstructed from the `junction` and `corridor` columns of the CSV. Edge lengths are approximated from the coordinate spread of incidents along each corridor. This is adequate for diversion routing at hackathon scope; production would use OpenStreetMap polylines.

    ---

    ## Dashboard Views

    | Tab | What you see |
    |-----|-------------|
    | 🗺 **Replay Mode** | Timeline slider steps through a historical day; incidents appear on a dark Plotly map of Bengaluru coloured by event cause |
    | 🔬 **Incident Detail** | Select any incident → ML prediction + CTM space-time diagram + officer/barricade/diversion recommendation |
    | 📊 **Calibration** | Scatter plot of simulated clearance time vs actual duration (R² annotated) + SHAP feature importance |
    | ⚙️ **What-If** | Adjust corridor / duration / priority / closure → live CTM re-run |

    ---

    ## Demo Script (3 minutes)

    1. **Problem** (15 s) — "Bengaluru loses thousands of hours to incidents that could be managed faster. GRIDLOCK quantifies the impact before you deploy."
    2. **Replay** (30 s) — Hit play on the replay slider; incidents appear across the day on the Bengaluru map.
    3. **Incident deep-dive** (60 s) — Click a high-priority `vehicle_breakdown` on the ORR. Watch the CTM space-time diagram show the queue forming and clearing. Read off predicted duration and capacity loss.
    4. **Recommendation** (30 s) — Show the officer count, barricade count, and Dijkstra diversion route.
    5. **Calibration close** (30 s) — Switch to the calibration tab. "This isn't a guess — it's tuned against 8 000 real incidents, and every incident we resolve makes it sharper."

    ---

    ## Tech Stack

    `pandas` · `numpy` · `scikit-learn` · `xgboost` · `shap` · `networkx` · `scipy` · `plotly` · `folium` · `streamlit`

    ---

    *Built for the Flipkart Hackathon — June 2026*
