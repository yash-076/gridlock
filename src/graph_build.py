"""
Phase 2b: Road network graph construction.
Outputs: data/processed/road_graph.gpickle  (NetworkX DiGraph)
"""

import json
import pickle
import numpy as np
import pandas as pd
import networkx as nx
from pathlib import Path

ROOT     = Path(__file__).resolve().parent.parent
FEAT_IN  = ROOT / "data" / "processed" / "features.parquet"
OUT_DIR  = ROOT / "data" / "processed"


# ── Road type parameters ──────────────────────────────────────────────────────

ROAD_PARAMS = {
    "ring_road":  {"v_free": 60, "rho_jam": 120, "capacity": 1800, "seg_km": 2.0},
    "arterial":   {"v_free": 40, "rho_jam": 140, "capacity": 1500, "seg_km": 1.0},
    "local":      {"v_free": 25, "rho_jam": 160, "capacity":  900, "seg_km": 0.5},
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
    for key, rtype in CORRIDOR_TYPE_MAP.items():
        if key.lower() in str(corridor).lower():
            return rtype
    return "local"


# ── Build graph ───────────────────────────────────────────────────────────────

def build_graph(df: pd.DataFrame) -> nx.DiGraph:
    G = nx.DiGraph()

    # Collect unique junctions
    junctions = (
        df["junction"].dropna().astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    # Add junction nodes with approximate coordinates
    junc_coords: dict[str, tuple[float, float]] = {}
    for junc in junctions:
        sub = df[df["junction"].astype(str).str.strip() == junc]
        if len(sub) == 0:
            continue
        lat = sub["latitude"].median()
        lon = sub["longitude"].median()
        junc_coords[junc] = (lat, lon)
        G.add_node(junc, node_type="junction", lat=lat, lon=lon)

    # Add corridor endpoints as synthetic nodes if needed
    corridors_in_data = df["corridor"].dropna().unique()
    corridor_endpoints: dict[str, tuple[str, str]] = {}  # corridor -> (node_a, node_b)

    for corr in corridors_in_data:
        sub = df[df["corridor"] == corr].dropna(subset=["latitude", "longitude"])
        if len(sub) == 0:
            continue

        # Use min/max lat to define two synthetic endpoints
        lat_min_row = sub.loc[sub["latitude"].idxmin()]
        lat_max_row = sub.loc[sub["latitude"].idxmax()]

        node_a = f"{corr}_A"
        node_b = f"{corr}_B"

        G.add_node(node_a, node_type="corridor_endpoint", lat=float(lat_min_row["latitude"]),
                   lon=float(lat_min_row["longitude"]), corridor=corr)
        G.add_node(node_b, node_type="corridor_endpoint", lat=float(lat_max_row["latitude"]),
                   lon=float(lat_max_row["longitude"]), corridor=corr)
        corridor_endpoints[corr] = (node_a, node_b)

    # Add edges: junction → junction within same corridor, or endpoint ↔ endpoint
    # First, link junctions that appear on the same corridor
    for corr in corridors_in_data:
        rtype = get_road_type(corr)
        params = ROAD_PARAMS[rtype]
        
        sub = df[(df["corridor"] == corr) & df["junction"].notna()]
        juncs_on_corr = sub["junction"].astype(str).str.strip().unique().tolist()

        if len(juncs_on_corr) >= 2:
            # Sort by median longitude (approximate west→east ordering)
            juncs_sorted = sorted(
                juncs_on_corr,
                key=lambda j: df[df["junction"].astype(str).str.strip() == j]["longitude"].median()
            )
            for i in range(len(juncs_sorted) - 1):
                u, v = juncs_sorted[i], juncs_sorted[i + 1]
                if u not in G.nodes or v not in G.nodes:
                    continue
                # Approximate distance from coordinates
                try:
                    lat1, lon1 = junc_coords[u]
                    lat2, lon2 = junc_coords[v]
                    dist_km = _haversine(lat1, lon1, lat2, lon2)
                except KeyError:
                    dist_km = params["seg_km"]
                travel_time = dist_km / params["v_free"] * 60  # minutes
                G.add_edge(u, v,
                           corridor=corr, road_type=rtype,
                           length_km=dist_km, travel_time_min=travel_time,
                           capacity=params["capacity"], v_free=params["v_free"],
                           rho_jam=params["rho_jam"])
                G.add_edge(v, u,
                           corridor=corr, road_type=rtype,
                           length_km=dist_km, travel_time_min=travel_time,
                           capacity=params["capacity"], v_free=params["v_free"],
                           rho_jam=params["rho_jam"])
        else:
            # No multiple junctions: connect corridor endpoints
            if corr in corridor_endpoints:
                a, b = corridor_endpoints[corr]
                dist_km = params["seg_km"] * 5  # 5 default segments
                travel_time = dist_km / params["v_free"] * 60
                G.add_edge(a, b, corridor=corr, road_type=rtype,
                           length_km=dist_km, travel_time_min=travel_time,
                           capacity=params["capacity"], v_free=params["v_free"],
                           rho_jam=params["rho_jam"])
                G.add_edge(b, a, corridor=corr, road_type=rtype,
                           length_km=dist_km, travel_time_min=travel_time,
                           capacity=params["capacity"], v_free=params["v_free"],
                           rho_jam=params["rho_jam"])

    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km."""
    R = 6371.0
    φ1, φ2 = np.radians(lat1), np.radians(lat2)
    dφ = np.radians(lat2 - lat1)
    dλ = np.radians(lon2 - lon1)
    a = np.sin(dφ / 2) ** 2 + np.cos(φ1) * np.cos(φ2) * np.sin(dλ / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def save_graph(G: nx.DiGraph, path: Path):
    with open(path, "wb") as f:
        pickle.dump(G, f)
    print(f"Graph saved to {path}")


def load_graph(path: Path = None) -> nx.DiGraph:
    if path is None:
        path = OUT_DIR / "road_graph.gpickle"
    with open(path, "rb") as f:
        return pickle.load(f)


def run():
    df = pd.read_parquet(FEAT_IN)
    G  = build_graph(df)
    save_graph(G, OUT_DIR / "road_graph.gpickle")
    
    # Also save metadata as JSON for dashboard use
    meta = {
        "nodes": list(G.nodes(data=True)),
        "road_params": ROAD_PARAMS,
        "corridor_type_map": CORRIDOR_TYPE_MAP,
    }
    # Convert to JSON-serialisable form
    meta_serialisable = {
        "n_nodes": G.number_of_nodes(),
        "n_edges": G.number_of_edges(),
        "road_params": ROAD_PARAMS,
        "corridor_type_map": CORRIDOR_TYPE_MAP,
    }
    with open(OUT_DIR / "graph_meta.json", "w") as f:
        json.dump(meta_serialisable, f, indent=2)
    
    return G


if __name__ == "__main__":
    run()
