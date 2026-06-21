# GRIDLOCK 🚦

### Event-Driven Congestion Forecasting & Response Simulation
*Built for the Flipkart Hackathon — June 2026*

---

```
GR●●●DLOCK
[ predict → simulate → recommend ]
```

---

## 📖 Project Overview

Bengaluru loses thousands of person-hours daily to traffic incidents—vehicle breakdowns on the ORR, tree falls after a monsoon shower, VIP convoys on arterials. Today, traffic police deploy resources from experience alone, with no quantified impact forecast and no post-event learning loop.

**GRIDLOCK** changes that in three steps:

| Step | What it does |
|------|-------------|
| **1. Predict** | ML model (XGBoost) forecasts how long an incident will last and how much road capacity it removes. |
| **2. Simulate** | Cell Transmission Model (CTM) solves the LWR traffic-flow PDE and shows the shockwave queue forming and clearing as a space-time diagram. |
| **3. Recommend** | Converts simulation output into a concrete deployment plan: officers, barricades, and diversion routes. |

---

## 🏗️ Project Architecture

This project is built using a decoupled client-server architecture:
- **Backend (Python / FastAPI):** Serves ML predictions, runs the CTM simulation, solves shortest path routing, and exposes APIs.
- **Frontend (React / Vite):** Modern interactive dashboard with map visualisations, real-time what-if simulations, and calibration metrics.
- **Data Pipeline (Python / Pandas / Scikit-Learn):** Scripts to clean, process raw data, build road graphs, and train models.
- **Alternative Monolith (Streamlit):** A single-file Streamlit dashboard for quick local demos.

---

## 🚀 Getting Started

### 📋 Prerequisites
Ensure you have the following installed:
- Python 3.10+
- Node.js 18+ & npm

---

### ⚙️ 1. Set Up the Data Pipeline
Before running either the React app or Streamlit dashboard, you need to run the data preprocessing and model training pipeline.

```bash
# Clone the repository
git clone https://github.com/yash-076/gridlock.git
cd gridlock

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Run the full data pipeline (takes ~2–3 minutes)
python src/clean.py          # Phase 0+1: clean & parse
python src/features.py       # Phase 2:   feature engineering
python src/graph_build.py    # Phase 2b:  road network graph
python src/forecast_model.py # Phase 3:   train XGBoost models & generate SHAP plots
python src/calibrate.py      # Phase 5:   calibrate CTM vs real data
```

---

### 🖥️ 2. Running Locally (FastAPI + React)

#### 🔸 Option A: Start the Backend (FastAPI)
From the root directory:
```bash
uvicorn api.main:app --port 8000 --reload
```
The API documentation will be available at `http://127.0.0.1:8000/docs`.

#### 🔸 Option B: Start the Frontend (React + Vite)
In a new terminal window:
```bash
cd web
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

> [!NOTE]
> By default, the React app connects to `http://127.0.0.1:8000`. You can configure a different backend URL by creating a `web/.env` file and setting `VITE_API_URL`.

---

### 📊 3. Running Locally (Streamlit Monolith)
If you prefer to run the single-page Streamlit application:
```bash
# From the root directory:
streamlit run app/dashboard.py
```

---

## 🌐 Deployment Guide

### 1. Deploy the Backend (FastAPI) on Render
1. Sign up on [Render](https://render.com/) and connect your GitHub account.
2. Click **New +** > **Web Service**.
3. Select this repository.
4. Set the following configurations:
   - **Runtime:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free`
5. Click **Deploy**. Once completed, Render will give you a public URL (e.g., `https://your-backend.onrender.com`).

### 2. Deploy the Frontend (React) on Vercel
1. Sign up on [Vercel](https://vercel.com/) and link your GitHub account.
2. Click **Add New** > **Project** and import this repository.
3. Configure the build:
   - **Root Directory:** Choose `web`.
   - **Environment Variables:**
     - Add **Key:** `VITE_API_URL`
     - **Value:** `https://your-backend.onrender.com` (your live Render URL)
4. Click **Deploy**.

---

## 🧠 CTM Simulation Engine (LWR PDE Solver)

The core simulation is a **Cell Transmission Model (CTM)** solving the **Lighthill–Whitham–Richards (LWR)** kinematic wave PDE:

$$\frac{\partial \rho}{\partial t} + \frac{\partial q}{\partial x} = 0$$

Each corridor is modelled as **25 cells × 200 m = 5 km**, with the incident placed at cell 12. The solver runs the Godunov update scheme at a 12-second timestep:
- $S_i = \min(\rho_i \cdot v_{\text{free}}, Q_i)$ (Sending function)
- $R_i = \min(Q_i, w \cdot (\rho_{\text{jam}} - \rho_i))$ (Receiving function)
- $y_i = \min(S_i, R_{i+1})$ (Inter-cell flow)
- $\rho_i(t+\Delta t) = \rho_i(t) + \frac{\Delta t}{\Delta x} \cdot (y_{i-1} - y_i)$ (Density update)

---

## 🛠️ Tech Stack
- **Frontend:** React, Vite, Plotly.js, Vanilla CSS
- **Backend:** FastAPI, Uvicorn, Python
- **Libraries:** Pandas, NumPy, Scikit-Learn, XGBoost, SHAP, NetworkX, SciPy
