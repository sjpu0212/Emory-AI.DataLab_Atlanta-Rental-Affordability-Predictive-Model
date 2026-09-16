"""§XVIII Previous Projects (max 5). Mirrors scoring/previous_projects.py.

Score both options and take the higher:

A (up to 5) — LIHTC awards inside the site's Local Government Boundary (its incorporated
  city) in the last 15 years: none → 5; exactly one, older than 6 years → 4; else 0.
  Sites in unincorporated areas have no city boundary here, so A scores 0.
B (up to 3) — awards within a 1-mile radius: none in the last 6 yrs → 3, none in the last
  4 → 2. If the site is within 1 mi of a transit hub the windows relax to 3 and 2 yrs.
  Awards whose coordinates are a random point in their city (`coord_precision ==
  "random_in_city"`) count for A but are excluded from the 1-mile test.
"""
from __future__ import annotations

import functools

import numpy as np

from . import data
from .base import clean, result
from .geo import haversine_mi

ROUND_YEAR = 2026        # the site scores the 2026 round


@functools.lru_cache(maxsize=None)
def _awards_in_place(place_idx: int) -> np.ndarray:
    """Row indices of lihtc_awards inside municipality `place_idx` (cached per place)."""
    aw = data.point_layer("lihtc_awards")
    inside = data.polygon_layer("municipalities").points_inside(place_idx, aw.lat, aw.lon)
    return np.flatnonzero(inside)


def _award(r):
    return {"name": r["name"], "year": int(r["year"]), "credit_type": clean(r["credit_type"]),
            "units": clean(r["units"]), "city": clean(r["city"]),
            "lat": round(float(r["lat"]), 6), "lon": round(float(r["lon"]), 6),
            "distance_mi": round(float(r["distance_mi"]), 3),
            "coord_precision": clean(r["coord_precision"]), "source": clean(r["source"])}


def score(lat: float, lon: float, round_year: int | None = None, ctx: dict | None = None) -> dict:
    round_year = round_year or ROUND_YEAR
    base15, base6, base4, base3, base2 = (round_year - n for n in (15, 6, 4, 3, 2))
    aw = data.point_layer("lihtc_awards")

    # ── A: awards inside the site's Local Government Boundary (15-yr lookback) ──
    places = data.polygon_layer("municipalities")
    hit = places.containing_idx(lat, lon)
    lgb_name, a_pts, in_lgb = None, 0, []
    if len(hit):
        lgb_name = places.records[hit[0]]["name"]
        idx = [i for i in _awards_in_place(int(hit[0])) if aw.records[i]["year"] >= base15]
        dist = haversine_mi(lat, lon, aw.lat[idx], aw.lon[idx])
        rows = sorted((dict(aw.records[i], distance_mi=d) for i, d in zip(idx, dist)), key=lambda r: r["year"])
        in_lgb = [_award(r) for r in rows]
        if len(rows) == 0:
            a_pts = 5
        elif len(rows) == 1 and rows[0]["year"] < base6:
            a_pts = 4

    # ── B: awards within 1 mile; lookback relaxed when a transit hub is within 1 mile ──
    near = [r for r in aw.within_records(lat, lon, 1.0) if r["coord_precision"] != "random_in_city"]
    _, hub_mi = data.point_layer("transit_hubs").nearest(lat, lon)
    near_hub = hub_mi <= 1.0
    years = np.array([r["year"] for r in near])
    b3, b2 = (base3, base2) if near_hub else (base6, base4)
    b_pts = 3 if (years < b3).all() else (2 if (years < b2).all() else 0)
    within_mile = [_award(r) for r in sorted(near, key=lambda r: -r["year"])]

    nearest_row, nearest_mi = aw.nearest(lat, lon)
    nearest_award = None
    if nearest_row is not None:
        nearest_award = _award(dict(nearest_row, distance_mi=nearest_mi))

    sc = max(a_pts, b_pts)
    if a_pts >= b_pts and a_pts > 0:
        expl = (f"No LIHTC awards in {lgb_name} (site's city) since {base15} → §XVIII.A 5 pts."
                if a_pts == 5 else f"Only one award in {lgb_name} since {base15}, before {base6} → §XVIII.A 4 pts.")
        if b_pts:
            expl += f" (§XVIII.B = {b_pts}.)"
    elif b_pts > 0:
        expl = (f"No awards within 1 mile in the lookback window"
                f"{' (relaxed — a transit hub is within 1 mi)' if near_hub else ''} → §XVIII.B {b_pts} pts.")
    else:
        expl = (f"Recent LIHTC awards both in {lgb_name} and within 1 mile → 0 pts." if lgb_name
                else "Site is unincorporated (§XVIII.A not scored) and recent awards lie within 1 mile → 0 pts.")

    return result(
        "XVIII", "Previous Projects", score=sc, max_score=5, explanation=expl,
        components=[
            {"id": "XVIII.A", "name": "Awards in Local Government Boundary", "score": a_pts, "max_score": 5,
             "explanation": (f"{len(in_lgb)} award(s) in {lgb_name} since {base15}." if lgb_name
                             else "Unincorporated — no city boundary to test.")},
            {"id": "XVIII.B", "name": "Awards within 1 mile", "score": b_pts, "max_score": 3,
             "explanation": f"{len(within_mile)} award(s) within 1 mi; transit hub within 1 mi = {near_hub}."}],
        details={"round_year": round_year, "local_government_boundary": lgb_name,
                 "awards_in_lgb_last_15_yrs": in_lgb, "awards_within_1_mile": within_mile,
                 "nearest_award": nearest_award, "transit_hub_within_1_mile": bool(near_hub),
                 "nearest_hub_straight_mi": round(hub_mi, 3)},
        data_vintage="HUD National LIHTC Database + GA DCA awards + Census TIGER places")
