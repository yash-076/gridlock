"""
Phase 6: Recommendation engine.
Given CTM simulation output + incident metadata, produce:
  - officers_recommended
  - barricades_recommended
  - diversion_route (list of nodes from networkx shortest path)
"""

import pickle
import math
import numpy as np
import networkx as nx
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

ROOT       = Path(__file__).resolve().parent.parent
GRAPH_PATH = ROOT / "data" / "processed" / "road_graph.gpickle"


OFFICER_COVERAGE_KM = {
    "ring_road": 1.0,
    "arterial":  0.5,
    "local":     0.3,
}

BARRICADE_SPACING_M = {
    "ring_road": 250.0,
    "arterial":  150.0,
    "local":     100.0,
}

BASE_OFFICERS = {
    "ring_road": 4,
    "arterial":  3,
    "local":     2,
}


@dataclass
class Recommendation:
    predicted_duration_min:  float
    predicted_capacity_loss: float
    max_queue_km:            float
    peak_queue_time_min:     float
    clearance_time_min:      float
    officers_recommended:    int
    barricades_recommended:  int
    diversion_routes:        list          # list of node-lists
    road_type:               str
    corridor:                str
    incident_cell:           int


def get_road_type(corridor: str) -> str:
    from ctm_simulation import get_road_type as _g
    return _g(corridor)


def load_graph() -> Optional[nx.DiGraph]:
    try:
        with open(GRAPH_PATH, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None


def _nearest_nodes(G: nx.DiGraph, corridor: str, n_upstream: int = 1, n_downstream: int = 1):
    """
    Return candidate upstream and downstream nodes for a given corridor.
    """
    corr_nodes = [
        n for n, d in G.nodes(data=True)
        if d.get("corridor", "") == corridor or str(n).startswith(corridor)
    ]
    if not corr_nodes:
        # Fall back to all nodes
        corr_nodes = list(G.nodes())[:10]

    # Try corridor endpoints
    ep_a = f"{corridor}_A"
    ep_b = f"{corridor}_B"
    upstream   = ep_a if ep_a in G.nodes() else (corr_nodes[0]  if corr_nodes else None)
    downstream = ep_b if ep_b in G.nodes() else (corr_nodes[-1] if corr_nodes else None)
    return upstream, downstream


def find_diversion(G: nx.DiGraph, corridor: str, requires_closure: bool) -> list:
    """
    Temporarily mark incident corridor as high-cost (or remove if closure),
    then find alternate shortest paths.
    """
    upstream, downstream = _nearest_nodes(G, corridor)
    if upstream is None or downstream is None or upstream == downstream:
        return []

    G_tmp = G.copy()

    # Penalise / remove incident edges
    incident_edges = [
        (u, v) for u, v, d in G_tmp.edges(data=True)
        if d.get("corridor", "") == corridor
    ]
    for u, v in incident_edges:
        if requires_closure:
            G_tmp.remove_edge(u, v)
        else:
            # Set very high travel time but don't remove
            G_tmp[u][v]["travel_time_min"] = G_tmp[u][v].get("travel_time_min", 10) * 10

    try:
        paths = list(
            nx.shortest_simple_paths(G_tmp, upstream, downstream, weight="travel_time_min")
        )
        return paths[:2]   # top 2 alternates
    except (nx.NetworkXNoPath, nx.NodeNotFound, nx.exception.NetworkXError):
        return []


def recommend(
    corridor: str,
    predicted_duration_min: float,
    predicted_capacity_loss: float,
    max_queue_km: float,
    peak_queue_time_min: float,
    clearance_time_min: float,
    incident_cell: int,
    requires_closure: bool = False,
    priority_high: bool = False,
) -> Recommendation:

    road_type = get_road_type(corridor)

    # ── Officer calculation ────────────────────────────────────────────────────
    base    = BASE_OFFICERS.get(road_type, 3)
    cov_km  = OFFICER_COVERAGE_KM.get(road_type, 0.5)
    queue_officers = math.ceil(max_queue_km / cov_km) if max_queue_km > 0 else 0

    # Junction officers: +1 per junction within queue extent
    G = load_graph()
    junction_count = 0
    if G is not None:
        corr_nodes = [n for n, d in G.nodes(data=True)
                      if d.get("node_type") == "junction"]
        # Estimate how many junctions within queue_km of incident location
        # (simplified: use fraction of total corridor junctions)
        all_corr_nodes = [n for n, d in G.nodes(data=True)
                          if d.get("corridor", "") == corridor
                          and d.get("node_type") == "junction"]
        junction_count = min(len(all_corr_nodes), max(0, int(max_queue_km / 0.5)))

    extra_junction = junction_count if priority_high else 0
    officers = base + queue_officers + extra_junction
    officers = max(officers, base)

    # ── Barricade calculation ──────────────────────────────────────────────────
    spacing_m   = BARRICADE_SPACING_M.get(road_type, 150.0)
    queue_m     = max_queue_km * 1000.0
    barricades  = math.ceil(queue_m / spacing_m) if queue_m > 0 else 2

    # Count side junctions in queue extent
    side_junctions_in_queue = junction_count
    barricades += side_junctions_in_queue  # one barricade per side junction
    barricades  = max(barricades, 2)

    # ── Diversion routes ──────────────────────────────────────────────────────
    diversions: list = []
    if G is not None:
        try:
            diversions = find_diversion(G, corridor, requires_closure)
        except Exception:
            diversions = []

    return Recommendation(
        predicted_duration_min  = predicted_duration_min,
        predicted_capacity_loss = predicted_capacity_loss,
        max_queue_km            = max_queue_km,
        peak_queue_time_min     = peak_queue_time_min,
        clearance_time_min      = clearance_time_min,
        officers_recommended    = officers,
        barricades_recommended  = barricades,
        diversion_routes        = diversions,
        road_type               = road_type,
        corridor                = corridor,
        incident_cell           = incident_cell,
    )


def format_recommendation(rec: Recommendation) -> str:
    """Return a plain-English summary of the recommendation."""
    lines = [
        f"🚦 INCIDENT RESPONSE PLAN",
        f"{'─'*40}",
        f"Corridor         : {rec.corridor} ({rec.road_type.replace('_', ' ').title()})",
        f"Predicted duration: {rec.predicted_duration_min:.0f} min",
        f"Capacity loss    : {rec.predicted_capacity_loss*100:.0f}%",
        f"Max queue length : {rec.max_queue_km:.2f} km",
        f"Peak queue at    : {rec.peak_queue_time_min:.0f} min after incident",
        f"Clearance time   : {rec.clearance_time_min:.0f} min (simulated)",
        f"",
        f"Officers recommended  : {rec.officers_recommended}",
        f"Barricades recommended: {rec.barricades_recommended}",
    ]
    if rec.diversion_routes:
        lines.append("")
        lines.append("Diversion routes:")
        for i, route in enumerate(rec.diversion_routes, 1):
            route_str = " → ".join(str(n) for n in route[:6])
            if len(route) > 6:
                route_str += f" → ... ({len(route)} nodes)"
            lines.append(f"  Route {i}: {route_str}")
    else:
        lines.append("No alternate graph route found (limited graph coverage)")
    return "\n".join(lines)


if __name__ == "__main__":
    rec = recommend(
        corridor="ORR East 1",
        predicted_duration_min=75.0,
        predicted_capacity_loss=0.55,
        max_queue_km=1.2,
        peak_queue_time_min=30.0,
        clearance_time_min=95.0,
        incident_cell=12,
        requires_closure=False,
        priority_high=True,
    )
    print(format_recommendation(rec))
