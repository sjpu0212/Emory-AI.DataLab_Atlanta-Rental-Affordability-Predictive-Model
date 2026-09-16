"""§XII Community Transportation Options (max 6). Mirrors scoring/transportation.py.

Claim Option A (transit hub) or Option B (any stop) — whichever scores higher. Distances
are route estimates (straight-line x1.15) to the nearest hub/stop served >= 5 days/week.
Hub tiers 0.25 / 0.5 / 1.0 mi → 5 / 4.5 / 4 pts; stop tiers → 3 / 2 / 1 pts.
Option A1 (6 pts, transit-agency-owned site) is a documentation claim, not a distance.
"""
from __future__ import annotations

from . import data
from .base import result
from .geo import near_cutoff, route_est, tier_points

TIERS = (0.25, 0.5, 1.0)
HUB_PTS = (5.0, 4.5, 4.0)
STOP_PTS = (3.0, 2.0, 1.0)


def _stop(row, straight_mi):
    return {"name": row["stop_name"], "agency": row["agency"], "stop_id": row["stop_id"],
            "route_count": int(row["route_count"]), "has_rail": bool(row["has_rail"]),
            "days_per_week": int(row["days_per_week"]),
            "lat": round(float(row["lat"]), 6), "lon": round(float(row["lon"]), 6),
            "straight_mi": round(straight_mi, 3), "distance_mi": round(route_est(straight_mi), 3)}


def score(lat: float, lon: float, ctx: dict | None = None) -> dict:
    hub, hd = data.point_layer("transit_hubs").nearest(lat, lon)
    stop, sd = data.point_layer("transit_stops").nearest(lat, lon)
    hub_mi, stop_mi = route_est(hd), route_est(sd)
    a_pts, a_tier = tier_points(hub_mi, TIERS, HUB_PTS)
    b_pts, b_tier = tier_points(stop_mi, TIERS, STOP_PTS)

    flags = [f"§XII {label} distance {mi:.2f} mi is within 15% of a tier cutoff — verify route."
             for label, mi, pts in (("hub", hub_mi, a_pts), ("stop", stop_mi, b_pts))
             if pts > 0 and near_cutoff(mi, TIERS)]

    if a_pts >= b_pts and a_pts > 0:
        chosen, sc = "A", a_pts
        expl = (f"Nearest transit hub ({hub['stop_name']}, {int(hub['route_count'])} routes"
                f"{', rail' if hub['has_rail'] else ''}) ≈ {hub_mi:.2f} mi → Option A {a_tier} → {a_pts} pts"
                + (f"; Option B (stop) would give {b_pts}." if b_pts else "."))
    elif b_pts > 0:
        chosen, sc = "B", b_pts
        expl = (f"Nearest transit stop ({stop['stop_name']}) ≈ {stop_mi:.2f} mi → Option B {b_tier} → {b_pts} pts"
                + (f"; Option A (hub) would give {a_pts}." if a_pts else "."))
    else:
        chosen, sc = None, 0.0
        expl = f"Nearest hub ≈ {hub_mi:.2f} mi and nearest stop ≈ {stop_mi:.2f} mi — both beyond 1 mi → 0 pts."

    return result(
        "XII", "Community Transportation Options", score=sc, max_score=6, explanation=expl, flags=flags,
        components=[
            {"id": "XII.A", "name": "Transit-Oriented Development (hub)", "score": a_pts, "max_score": 6,
             "explanation": f"Nearest qualifying hub ≈ {hub_mi:.2f} mi → {a_tier} → {a_pts} pts."},
            {"id": "XII.B", "name": "Access to Public Transportation (stop)", "score": b_pts, "max_score": 3,
             "explanation": f"Nearest qualifying stop ≈ {stop_mi:.2f} mi → {b_tier} → {b_pts} pts."}],
        developer_inputs=[{"id": "XII.A1", "name": "Transit-agency land ownership",
                           "description": "6 pts requires the site to be owned/strategically targeted by the "
                                          "transit agency and adjacent to a hub — a documentation claim."}],
        details={"nearest_hub": _stop(hub, hd) if hub is not None else None,
                 "nearest_stop": _stop(stop, sd) if stop is not None else None,
                 "claimed_option": chosen},
        data_vintage="Agency GTFS via Mobility Database, 2026-07")
