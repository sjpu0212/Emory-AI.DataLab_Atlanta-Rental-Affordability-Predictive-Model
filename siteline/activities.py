"""§XI Desirable / Undesirable Activities (max 20). Mirrors scoring/activities.py.

Desirable (A): each category scores by the route-estimate distance (straight-line x1.15)
to its nearest amenity — Group 1 earns 2.5 / 2 / 1.5 pts and Group 2 earns 2 / 1.5 / 1 pts
within 0.5 / 1.0 / 1.5 mi. A national big-box store may also satisfy grocery (c).

Undesirable (B): -2 for each nuisance use or environmental hazard within a 0.25-mi
straight-line radius, and -2 if the site's tract is a USDA food desert (LILA 1-and-20)
and grocery (c) earned no points.

Section total = clamp(sum of desirable - 2 x deductions, 0, 20).
"""
from __future__ import annotations

from . import base, data
from .base import clamp, clean, result
from .geo import near_cutoff, route_est, tier_points

TIERS = (0.5, 1.0, 1.5)
GROUP_PTS = {1: (2.5, 2.0, 1.5), 2: (2.0, 1.5, 1.0)}
UNDESIRABLE_RADIUS = 0.25

# id → (display name, QAP point group). QAP item k is not location-scorable, so it's absent.
CATEGORIES = {
    "a": ("National big-box store", 1), "b": ("Retail / department store", 2),
    "c": ("Supermarket / grocery", 1), "d": ("Restaurant", 2), "e": ("Hospital", 1),
    "f": ("Medical provider", 1), "g": ("Pharmacy", 1), "h": ("Childcare (DECAL)", 1),
    "i": ("Technical college", 2), "j": ("Elementary/middle/high school", 1),
    "l": ("Community / rec center", 1), "m": ("Public park >= 25,000 sq ft", 1),
    "n": ("Public park < 25,000 sq ft", 2), "o": ("Public library", 1),
    "p": ("Fire / police station", 2), "q": ("Bank", 2), "r": ("Place of worship", 2),
    "s": ("Post office", 2),
}
UNDESIRABLE = {"a": "Nuisance use", "b": "Environmental hazard"}


def _place(row, straight_mi):
    return {"name": row["name"], "address": clean(row.get("address")), "subtype": clean(row.get("subtype")),
            "lat": round(float(row["lat"]), 6), "lon": round(float(row["lon"]), 6),
            "straight_mi": round(straight_mi, 3), "distance_mi": round(route_est(straight_mi), 3),
            "source": row.get("source")}


def score(lat: float, lon: float, ctx: dict | None = None) -> dict:
    ctx = ctx or base.site_context(lat, lon)
    desirable, components, flags = [], [], []
    total = 0.0

    for cid, (cname, group) in CATEGORIES.items():
        row, dist = data.amenity_layer(cid).nearest(lat, lon)
        via_bigbox = False
        if cid == "c":                                   # QAP: a national big-box can count as grocery
            brow, bdist = data.amenity_layer("a").nearest(lat, lon)
            if bdist < dist:
                row, dist, via_bigbox = brow, bdist, True
        route_mi = route_est(dist)
        pts, tier = tier_points(route_mi, TIERS, GROUP_PTS[group]) if row is not None else (0.0, "no data")
        total += pts
        if row is not None and pts > 0 and near_cutoff(route_mi, TIERS):
            flags.append(f"§XI.A({cid}) {cname}: {route_mi:.2f} mi is within 15% of a tier cutoff — verify route.")
        if row is None:
            expl = f"No {cname.lower()} in the data."
        else:
            expl = (f"Nearest {cname.lower()}{' (a big-box store)' if via_bigbox else ''}: {row['name']} "
                    f"≈ {route_mi:.2f} mi → Group {group}, {tier} → {pts} pts.")
        entry = {"id": f"XI.A.{cid}", "name": cname, "group": group, "score": pts,
                 "max_score": GROUP_PTS[group][0], "tier": tier,
                 "distance_mi": round(route_mi, 3) if row is not None else None,
                 "nearest": _place(row, dist) if row is not None else None,
                 "explanation": expl}
        desirable.append(entry)
        components.append({k: entry[k] for k in ("id", "name", "score", "max_score", "explanation")})

    # ── undesirables: -2 each within a 0.25-mi straight-line radius ──
    undesirable, nearest_undesirable, deductions = [], {}, 0
    for uid, uname in UNDESIRABLE.items():
        layer = data.undesirable_layer(uid)
        for h in layer.within_records(lat, lon, UNDESIRABLE_RADIUS):
            deductions += 1
            undesirable.append({"id": f"XI.B.{uid}", "name": uname, "deduction": -2,
                                "place": h["name"], "subtype": clean(h.get("subtype")),
                                "lat": round(float(h["lat"]), 6), "lon": round(float(h["lon"]), 6),
                                "distance_mi": round(float(h["distance_mi"]), 3)})
        row, dist = layer.nearest(lat, lon)
        if row is not None:
            nearest_undesirable[uname] = {"name": row["name"], "subtype": clean(row.get("subtype")),
                                          "lat": round(float(row["lat"]), 6), "lon": round(float(row["lon"]), 6),
                                          "straight_mi": round(dist, 3)}
            if near_cutoff(dist, (UNDESIRABLE_RADIUS,)):
                flags.append(f"§XI.B({uid}) {uname} at {dist:.2f} mi is near the 0.25-mi deduction radius — verify.")

    # ── food desert: -2 if the site tract is a USDA food desert AND grocery scored nothing ──
    grocery_scored = any(d["id"] == "XI.A.c" and d["score"] > 0 for d in desirable)
    in_fd = bool(ctx.get("usda_food_desert"))
    fd_applied = in_fd and not grocery_scored
    deductions += int(fd_applied)
    food_desert = {"in_food_desert_tract": in_fd, "deduction_applied": fd_applied,
                   "waived_reason": "grocery scored under XI.A(c)" if (in_fd and grocery_scored) else None}

    net = clamp(total - 2 * deductions, 0.0, 20.0)
    n_hit = sum(1 for d in desirable if d["score"] > 0)
    expl = (f"{n_hit} desirable categories score (sum {total:.1f} pts); "
            f"{deductions} undesirable deduction(s) (-{2 * deductions}); section total {net:.1f}/20.")
    return result(
        "XI", "Desirable / Undesirable Activities", score=net, max_score=20, explanation=expl,
        components=components, flags=flags,
        details={"desirable": desirable, "undesirable_within_radius": undesirable,
                 "nearest_undesirable": nearest_undesirable, "food_desert": food_desert,
                 "raw_desirable_total": round(total, 1), "deductions": deductions},
        data_vintage="SNAP/Overture/CMS/NPPES/DECAL/TCSG/ParkServe/IMLS/FDIC + EPA/EPD/USDA")
