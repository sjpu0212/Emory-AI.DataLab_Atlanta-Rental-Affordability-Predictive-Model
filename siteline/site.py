"""Total location score — runs every scorer, resolves the 10-pt block, and totals up.

    import siteline
    res = siteline.score_site(33.766384, -84.349133)
    res["total_score"], res["scores"]            # 39.0, {'XI': 20.0, ...}
    print(siteline.report(res))                   # human-readable breakdown

    df = siteline.score_sites(my_points)          # many sites → one row each
    grid = siteline.score_grid("atlanta", cell_mi=0.25)

Scoring structure (the eight location-based criteria, 46 points max):
  independent:  §XI (20) + §XII (6) + §XIII (3) + §XVIII (5) + §XXII (2)
  10-pt block:  max(§XV, §XVI, §XIX) — mutually exclusive; only the best counts.
                §XIV (a developer-entry claim) can also compete for this block.
The fifteen other QAP sections are developer-entry and are not scored here.
"""
from __future__ import annotations

import math
import time

import numpy as np
import pandas as pd
import shapely

from . import (activities, base, community_designations, data, education, historic,
               housing_needs, previous_projects, stable_communities, transportation)
from .geo import MI_PER_DEG

BLOCK_MAX = 10
MAX_TOTAL = 20 + 6 + 3 + 5 + 2 + BLOCK_MAX      # = 46
INDEPENDENT = ("XI", "XII", "XIII", "XVIII", "XXII")
BLOCK = ("XV", "XVI", "XIX")
DEVELOPER_SECTIONS = [  # (section, name, max pts) — scored by developer entry on the site
    ("III", "Extended Affordability", 6), ("IV", "MBE/WBE Engagement", 2),
    ("V", "Favorable Financing", 5), ("VI", "Compliance Performance", 10),
    ("VII", "Integrated Supportive Housing", 5), ("VIII", "Readiness to Proceed", 13),
    ("IX", "Deeper Targeting", 3), ("X", "HCV & PHA Notices", 2),
    ("XIV", "Revitalization/Redevelopment", 10), ("XVII", "Phased Development", 4),
    ("XX", "Economic Development Proximity", 1), ("XXI", "Mixed Income", 1),
    ("XXIII", "Enriched Property Services", 2), ("XXIV", "DCA Community Initiatives (GICH)", 2),
    ("XXV", "Preservation Scoring", 62),
]


def score_site(lat: float, lon: float, tenancy: str = "family", round_year: int | None = None) -> dict:
    """Score one location. `tenancy` ('family', 'elderly', ...) only affects §XIII."""
    lat, lon = float(lat), float(lon)
    ctx = base.site_context(lat, lon)
    if not ctx["in_arc"]:
        return {"site": ctx, "in_scope": False, "total_score": None, "max_total_scored": MAX_TOTAL,
                "scores": {}, "sections": {}, "block": None,
                "message": "Site is outside the ARC 11-county region; scoring not available."}

    xv = stable_communities.score(lat, lon, ctx)
    sections = {
        "XI": activities.score(lat, lon, ctx),
        "XII": transportation.score(lat, lon, ctx),
        "XIII": education.score(lat, lon, tenancy, ctx),
        "XV": xv,
        "XVI": community_designations.score(lat, lon, ctx),
        "XVIII": previous_projects.score(lat, lon, round_year, ctx),
        "XIX": housing_needs.score(lat, lon, ctx, xv_score=xv["score"]),
        "XXII": historic.score(lat, lon, ctx),
    }

    # 10-pt block: first highest applicable score wins (ties keep §XV, as on the site)
    winner = None
    for sec in BLOCK:
        r = sections[sec]
        if r["applicable"] and r["score"] > 0 and (winner is None or r["score"] > sections[winner]["score"]):
            winner = sec
    block_pts = sections[winner]["score"] if winner else 0.0

    total = sum(sections[s]["score"] for s in INDEPENDENT) + block_pts
    scores = {s: (r["score"] if r["applicable"] else None) for s, r in sections.items()}
    scores.update({"block": block_pts, "total": round(total, 2)})
    return {
        "site": ctx,
        "in_scope": True,
        "round_year": round_year or previous_projects.ROUND_YEAR,
        "tenancy": tenancy,
        "total_score": round(total, 2),
        "max_total_scored": MAX_TOTAL,
        "scores": scores,
        "sections": sections,
        "block": {"members": list(BLOCK), "winner": winner, "points": block_pts, "max_score": BLOCK_MAX,
                  "note": "§XIV Revitalization (developer-entry) can also compete for this 10-pt block."},
        "flags": [f for r in sections.values() for f in r["flags"]],
        "developer_sections": [{"criterion": c, "name": n, "max_score": m, "scored_here": False}
                               for c, n, m in DEVELOPER_SECTIONS],
    }


def summarize(res: dict) -> dict:
    """Flatten a score_site() result into one row: scores + the key 'closest things'."""
    site = res["site"]
    row = {k: site[k] for k in ("lat", "lon", "tract_geoid", "county", "pool", "municipality",
                                "in_qct", "usda_food_desert")}
    row["in_scope"] = res["in_scope"]
    if not res["in_scope"]:
        return row
    S = res["sections"]
    for sec in S:
        row[f"score_{sec}"] = res["scores"][sec]
    row.update(block_winner=res["block"]["winner"], block_score=res["block"]["points"],
               total_score=res["total_score"], n_flags=len(res["flags"]))

    xi = S["XI"]["details"]
    for d in xi["desirable"]:
        cid = d["id"].rsplit(".", 1)[1]
        row[f"xi_{cid}_mi"] = d["distance_mi"]
        row[f"xi_{cid}_name"] = d["nearest"]["name"] if d["nearest"] else None
    row["xi_undesirables_within_0_25mi"] = len(xi["undesirable_within_radius"])
    row["xi_food_desert_deduction"] = xi["food_desert"]["deduction_applied"]

    xii = S["XII"]["details"]
    for key, tag in (("nearest_hub", "hub"), ("nearest_stop", "stop")):
        o = xii[key] or {}
        row[f"xii_{tag}_mi"], row[f"xii_{tag}_name"] = o.get("distance_mi"), o.get("name")

    xiii = S["XIII"]["details"]
    for s in xiii["schools"]:
        row[f"xiii_{s['band']}_school"] = s["name"]
        row[f"xiii_{s['band']}_qualifies"] = s["qualifies"]
    row["xiii_qualifying_grades"] = xiii["qualifying_grades"]

    xv = S["XV"]["details"]
    row["xv_n_above_median"] = xv["site_tract"]["n_above_median"] if xv else None
    row["xv_basis"] = xv["basis"] if xv else None

    xvi = S["XVI"]["details"]
    row["xvi_cni_mi"], row["xvi_pbc_mi"] = xvi["cni"]["distance_mi"], xvi["pbc"]["distance_mi"]

    xviii = S["XVIII"]["details"]
    row["xviii_awards_in_lgb_15yr"] = len(xviii["awards_in_lgb_last_15_yrs"])
    row["xviii_awards_within_1mi"] = len(xviii["awards_within_1_mile"])
    na = xviii["nearest_award"]
    row["xviii_nearest_award"], row["xviii_nearest_award_mi"] = (na["name"], na["distance_mi"]) if na else (None, None)

    xix = S["XIX"]["details"]
    row["xix_severe_housing_pct"] = xix["severe_housing_pct"] if xix else None

    xxii = S["XXII"]["details"]
    nd = xxii.get("nearest_district")
    row["xxii_district"] = xxii.get("designation") if xxii["inside"] else None
    row["xxii_nearest_district_mi"] = 0.0 if xxii["inside"] else (nd["distance_mi"] if nd else None)
    return row


def score_sites(points, lat_col: str = "lat", lon_col: str = "lon", tenancy: str = "family",
                round_year: int | None = None, progress: bool = True) -> pd.DataFrame:
    """Score many sites. `points` is a DataFrame (with lat/lon columns) or a list of (lat, lon).

    Returns one summary row per input row (see summarize()), with any extra input columns
    kept on the left. Roughly 1–3 ms per site.
    """
    if isinstance(points, pd.DataFrame):
        src = points.reset_index(drop=True)
        lats, lons = src[lat_col].to_numpy(float), src[lon_col].to_numpy(float)
        extra = src.drop(columns=[lat_col, lon_col])
    else:
        arr = np.asarray(list(points), float).reshape(-1, 2)
        lats, lons, extra = arr[:, 0], arr[:, 1], None
    rows, t0, n = [], time.time(), len(lats)
    for i, (la, lo) in enumerate(zip(lats, lons)):
        rows.append(summarize(score_site(la, lo, tenancy, round_year)))
        if progress and n >= 500 and ((i + 1) % 2000 == 0 or i + 1 == n):
            el = time.time() - t0
            print(f"  scored {i + 1:,}/{n:,} sites  ({el:.0f}s elapsed, ~{el / (i + 1) * (n - i - 1):.0f}s left)")
    out = pd.DataFrame(rows)
    return out if extra is None or extra.empty else pd.concat([extra, out], axis=1)


def _region_geometry(region):
    if region == "atlanta":
        places = data.polygon_layer("municipalities")
        return places.geoms[int(np.flatnonzero(places.df["name"] == "Atlanta")[0])]
    if region == "arc":
        return shapely.union_all(data.polygon_layer("counties").geoms)
    counties = data.polygon_layer("counties")
    match = np.flatnonzero(counties.df["name"].str.lower() == str(region).lower())
    if len(match):
        return counties.geoms[int(match[0])]
    raise ValueError(f"Unknown region {region!r}: use 'atlanta', 'arc', a county name, or a bbox tuple.")


def grid_points(region="atlanta", cell_mi: float = 0.25) -> pd.DataFrame:
    """Cell-centre points on a ~cell_mi grid covering a region.

    region: 'atlanta' (city limits), 'arc' (all 11 counties), an ARC county name
            ('Fulton', 'Clayton', ...), or a bbox tuple (south, west, north, east).
    """
    if isinstance(region, (tuple, list)):
        s, w, n, e = region
        geom = shapely.box(w, s, e, n)
    else:
        geom = _region_geometry(region)
        w, s, e, n = geom.bounds
    dlat = cell_mi / MI_PER_DEG
    dlon = cell_mi / (MI_PER_DEG * math.cos(math.radians((s + n) / 2)))
    lat_c = s + (np.arange(int(math.ceil((n - s) / dlat))) + 0.5) * dlat
    lon_c = w + (np.arange(int(math.ceil((e - w) / dlon))) + 0.5) * dlon
    LON, LAT = np.meshgrid(lon_c, lat_c)
    inside = shapely.intersects_xy(geom, LON.ravel(), LAT.ravel())
    return pd.DataFrame({"lat": LAT.ravel()[inside].round(6), "lon": LON.ravel()[inside].round(6)})


def score_grid(region="atlanta", cell_mi: float = 0.25, **kwargs) -> pd.DataFrame:
    """Score every cell of grid_points(region, cell_mi). kwargs pass to score_sites()."""
    pts = grid_points(region, cell_mi)
    print(f"Scoring {len(pts):,} grid cells ({cell_mi} mi) over {region!r}…")
    return score_sites(pts, **kwargs)


def report(res: dict) -> str:
    """A plain-text breakdown of a score_site() result."""
    s = res["site"]
    where = (f"({s['lat']:.6f}, {s['lon']:.6f})  tract {s['tract_geoid']} · {s['county']} County · "
             f"{s['pool'] or 'outside ARC'} pool · {s['municipality'] or 'unincorporated'}"
             f"{' · QCT' if s.get('in_qct') else ''}")
    if not res["in_scope"]:
        return f"{where}\n{res['message']}"
    lines = [where, f"TOTAL {res['total_score']:g} / {res['max_total_scored']}"
                    f"   (10-pt block → {res['block']['winner'] or 'none'} = {res['block']['points']:g})", ""]
    for sec, r in res["sections"].items():
        tag = "N/A" if not r["applicable"] else f"{r['score']:g}/{r['max_score']:g}"
        blk = "  [block]" if sec in BLOCK else ""
        lines.append(f"§{sec:<6}{tag:>8}  {r['name']}{blk}")
        lines.append(f"          {r['explanation']}")
    xi = res["sections"]["XI"]["details"]
    lines += ["", "Nearest amenities (route estimate):"]
    for d in xi["desirable"]:
        nm = d["nearest"]["name"] if d["nearest"] else "—"
        mi = f"{d['distance_mi']:.2f} mi" if d["distance_mi"] is not None else "—"
        lines.append(f"  {d['id'][-1]}  {d['name']:<31} {mi:>9}  {d['score']:>4g} pts  {nm}")
    for u in xi["undesirable_within_radius"]:
        lines.append(f"  -2 {u['name']}: {u['place']} ({u['distance_mi']:.2f} mi)")
    lines += ["", "Zoned schools:"]
    for sch in res["sections"]["XIII"]["details"]["schools"]:
        q = "qualifies" if sch["qualifies"] else "does not qualify"
        fb = "  [nearest-zone fallback]" if sch["fallback_distance_mi"] is not None else ""
        lines.append(f"  {sch['band']:<11} {sch['name']} ({sch['district']}) — {q}{fb}")
    if res["flags"]:
        lines += ["", "Flags:"] + [f"  ! {f}" for f in res["flags"]]
    return "\n".join(lines)
