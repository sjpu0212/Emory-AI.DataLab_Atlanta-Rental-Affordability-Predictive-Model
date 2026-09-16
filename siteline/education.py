"""§XIII Quality Education Areas (max 3). Mirrors scoring/education.py.

Point-in-polygon on public-school attendance zones (charter "zones" are excluded — they
are lottery/city-wide areas, not as-of-right attendance zones). Each band (elementary,
middle, high) contributes its grade count when its zoned school qualifies under any of
QAP tests A (above-average CCRPI), B (Beating the Odds), or C (positive trend, top 75%).

Qualifying grades → points: >= 3 → 1, >= 7 → 1.5, all 13 (K-12) → 3 for family
tenancy, 2 otherwise. If no public zone of a band contains the site (a coverage gap),
the nearest zone of that band is used instead and flagged.
"""
from __future__ import annotations

import numpy as np

from . import data
from .base import clean, result
from .geo import haversine_mi

K12_TOTAL = 13
BANDS = ("elementary", "middle", "high")


def _points(n_grades: int, tenancy: str):
    if n_grades >= K12_TOTAL:
        return (3.0 if tenancy == "family" else 2.0), "all K-12"
    if n_grades >= 7:
        return 1.5, ">= 7 grades"
    if n_grades >= 3:
        return 1.0, ">= 3 grades"
    return 0.0, f"{n_grades} grades"


def _school(z, lat, lon, fallback_mi):
    has_loc = z["school_lat"] == z["school_lat"]      # not NaN
    return {
        "band": z["level_band"], "name": z["school_name"], "district": clean(z["district"]),
        "qualifies": bool(z["qualifies"]), "qualifies_via": clean(z["qualifies_via"]),
        "conditions": {"A_above_avg_ccrpi": bool(z["cond_a_above_avg_ccrpi"]),
                       "B_beating_the_odds": bool(z["cond_b_beating_odds"]),
                       "C_positive_trend_top75": bool(z["cond_c_positive_trend"])},
        "ccrpi_avg": clean(z["ccrpi_avg"]), "beating_the_odds": clean(z["beating_the_odds"]),
        "grades_in_band": int(z["grades_in_band"]),
        "qualifying_grades": int(z["qualifying_grades"]) if z["qualifies"] else 0,
        "zone_source": "nearest zone (fallback)" if fallback_mi is not None else "zone contains site",
        "fallback_distance_mi": None if fallback_mi is None else round(fallback_mi, 3),
        "school_address": clean(z["school_address"]),
        "school_lat": clean(z["school_lat"]), "school_lon": clean(z["school_lon"]),
        "site_to_school_mi": (round(float(haversine_mi(lat, lon, z["school_lat"], z["school_lon"])), 3)
                              if has_loc else None),
        "new_school": bool(z["new_school"]), "rating_note": clean(z["rating_note"]),
    }


def score(lat: float, lon: float, tenancy: str = "family", ctx: dict | None = None) -> dict:
    tenancy = (tenancy or "family").lower()
    zones = data.polygon_layer("school_zones")
    by_band = {}
    for i in zones.containing_idx(lat, lon):
        z = zones.records[i]
        by_band.setdefault(z["level_band"], z)          # first zone per band, in file order

    schools, n_qual, fallback_bands = [], 0, []
    for band in BANDS:
        z, fb_mi = by_band.get(band), None
        if z is None:                                  # coverage gap → nearest zone of this band
            z, fb_mi = zones.nearest(lat, lon, mask=np.asarray(zones.df["level_band"] == band))
            if z is None:
                continue
            fallback_bands.append(band)
        n_qual += int(z["qualifying_grades"]) if z["qualifies"] else 0
        schools.append(_school(z, lat, lon, fb_mi))

    pts, label = _points(n_qual, tenancy)
    flags = [s["rating_note"] for s in schools if s["new_school"] and s["rating_note"]]
    if fallback_bands:
        flags.append(f"No zoned public school found for {', '.join(fallback_bands)} at this point "
                     f"(coverage gap) — used the nearest public zone; verify the true attendance zone.")
    if not schools:
        expl = "No public school attendance zone found for this site."
    elif pts > 0:
        names = ", ".join(s["name"] for s in schools if s["qualifies"])
        fb = f" ({len(fallback_bands)} band(s) via nearest-zone fallback)" if fallback_bands else ""
        expl = (f"Qualifying zoned schools ({names}) cover {n_qual} K-12 grades → {label}, "
                f"{tenancy} tenancy → {pts} pts{fb}.")
    else:
        expl = f"Site's zoned public schools qualify for only {n_qual} grades (< 3) → 0 pts."

    return result(
        "XIII", "Quality Education Areas", score=pts, max_score=3, explanation=expl, flags=flags,
        components=[{"id": "XIII", "name": "Attendance-zone quality", "score": pts, "max_score": 3,
                     "explanation": expl}],
        details={"tenancy": tenancy, "qualifying_grades": n_qual, "schools": schools,
                 "fallback_bands": fallback_bands},
        data_vintage="GreatSchools public zones x GA DOE CCRPI / GOSA Beating the Odds")
