"""§XV Stable Communities (max 10). Mirrors scoring/stable_communities.py.

Count the site tract's five indicators that sit above its pool's median:
2 / 3 / 4+ → 6 / 8 / 10 pts ("within"). Indicators from tracts within 0.25 mi can be
added at the "near" rate, one point lower (5 / 7 / 9). The higher of the two counts.
§XV is one of the mutually exclusive 10-point block (see site.py).
"""
from __future__ import annotations

from . import base, data
from .base import clean, result

INDICATORS = {  # tracts.csv column → display label
    "env_health_index": "Environmental Health",
    "transit_access_index": "Transit Access",
    "jobs_proximity_index": "Jobs Proximity",
    "pct_above_poverty": "Above Poverty",
    "median_income": "Median Income",
}
WITHIN_PTS = {2: 6, 3: 8, 4: 10}
NEAR_MILES = 0.25


def points(count: int, near: bool = False) -> int:
    count = min(count, 4)
    if count < 2:
        return 0
    return WITHIN_PTS[count] - (1 if near else 0)


def score(lat: float, lon: float, ctx: dict | None = None) -> dict:
    ctx = ctx or base.site_context(lat, lon)
    geoid = ctx.get("tract_geoid")
    row = base.tract_row(geoid)
    if row is None:
        return result("XV", "Stable Communities", score=0, max_score=10,
                      explanation="Site is not inside a tract in the Stable Communities data.",
                      data_vintage="GA DCA Stable Communities / HUD AFFH / ACS")
    pool = row["pool"]
    p50 = data.pool_medians().get(pool, {})

    above = {c for c in INDICATORS if row[f"above_median_{c}"]}
    indicators = {label: {"value": clean(row[c]), "pool_median": round(p50.get(c, float("nan")), 4),
                          "above_median": c in above}
                  for c, label in INDICATORS.items()}

    # nearby tracts (≤ 0.25 mi) can lend their above-median indicators at the near rate
    near_inds, near_detail = set(above), []
    tracts = data.polygon_layer("tracts")
    for nt in tracts.within_distance_records(lat, lon, NEAR_MILES):
        if nt["geoid"] == geoid:
            continue
        adds = [c for c in INDICATORS if nt[f"above_median_{c}"] and c not in near_inds]
        near_inds.update(adds)
        near_detail.append({"geoid": nt["geoid"], "distance_mi": round(float(nt["distance_mi"]), 3),
                            "n_above_median": int(nt["n_above_median"]),
                            "adds_indicators": [INDICATORS[c] for c in adds]})

    within_count, near_count = len(above), len(near_inds)
    within_pts, near_pts = points(within_count), points(near_count, near=True)
    sc, basis = (within_pts, "within") if within_pts >= near_pts else (near_pts, "near")

    names = ", ".join(INDICATORS[c] for c in INDICATORS if c in above)
    if sc == 0:
        expl = (f"Site's tract is above the {pool} median on only {within_count} of 5 indicators "
                f"(need >= 2) → 0 pts.")
    elif basis == "within":
        expl = (f"Site's tract is above the {pool} median on {within_count} indicators ({names}) "
                f"→ {sc} pts (within-tract).")
    else:
        expl = (f"With nearby tracts (<= 0.25 mi), {near_count} indicators qualify → {sc} pts "
                f"(near-tract rate, -1).")

    return result(
        "XV", "Stable Communities", score=sc, max_score=10, explanation=expl,
        components=[{"id": "XV", "name": "Stable Communities indicators", "score": sc, "max_score": 10,
                     "explanation": expl}],
        details={"pool": pool, "basis": basis, "within_points": within_pts, "near_points": near_pts,
                 "site_tract": {"geoid": geoid, "n_above_median": within_count, "indicators": indicators},
                 "near_tracts": near_detail},
        data_vintage="GA DCA Stable Communities / HUD AFFH / ACS")
