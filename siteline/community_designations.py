"""§XVI Community Designations (max 10). Mirrors scoring/community_designations.py.

10 pts if the site is inside a HUD Choice Neighborhoods (CNI) grant area (A) or a
Purpose Built Communities (PBC) neighborhood (B). The points are shown as earned, but the
award also requires the CNI awardee / PBC member to select the application.
§XVI is one of the mutually exclusive 10-point block (see site.py).
"""
from __future__ import annotations

import numpy as np

from . import data
from .base import result

KINDS = {"CNI": "Choice Neighborhoods grant area", "PBC": "Purpose Built Communities neighborhood"}


def _closest(layer, lat, lon, kind):
    mask = np.asarray(layer.df["kind"] == kind)
    inside = [i for i in layer.containing_idx(lat, lon) if mask[i]]
    if inside:
        r = layer.records[inside[0]]
        return {"inside": True, "name": r["name"], "detail": r["detail"], "distance_mi": 0.0}
    r, mi = layer.nearest(lat, lon, mask=mask)
    if r is None:
        return {"inside": False, "name": None, "detail": None, "distance_mi": None}
    return {"inside": False, "name": r["name"], "detail": r["detail"], "distance_mi": round(mi, 3)}


def score(lat: float, lon: float, ctx: dict | None = None) -> dict:
    layer = data.polygon_layer("community_designations")
    areas = {kind: _closest(layer, lat, lon, kind) for kind in KINDS}
    met = [k for k, a in areas.items() if a["inside"]]
    sc = 10 if met else 0

    dev = []
    if "CNI" in met:
        dev.append({"id": "XVI.A", "name": "CNI selection required",
                    "description": "The CNI grant awardee must name this application to award the 10 pts."})
    if "PBC" in met:
        dev.append({"id": "XVI.B", "name": "Purpose Built selection required",
                    "description": "Purpose Built Communities must select this application to award the 10 pts."})
    if met:
        which = " and ".join(areas[k]["name"] for k in met)
        expl = f"Site is inside {which} → 10 pts (assumed; requires the designating body's selection)."
    else:
        near = min((a for a in areas.values() if a["distance_mi"] is not None),
                   key=lambda a: a["distance_mi"], default=None)
        expl = ("Site is not inside a CNI grant area or a Purpose Built Communities neighborhood → 0 pts"
                + (f" (closest: {near['name']}, {near['distance_mi']:.2f} mi)." if near else "."))

    return result(
        "XVI", "Community Designations", score=sc, max_score=10, explanation=expl, developer_inputs=dev,
        components=[{"id": "XVI", "name": "Community Designations", "score": sc, "max_score": 10,
                     "explanation": expl}],
        details={"cni": areas["CNI"], "pbc": areas["PBC"], "conditions_met": len(met)},
        data_vintage="HUD Choice Neighborhoods + Purpose Built Communities")
