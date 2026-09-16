"""§XXII Historic Preservation (max 2). Mirrors scoring/historic.py.

2 pts if the site is inside a National Register of Historic Places boundary. This is a
location flag: the points also require historic tax credits and adaptive reuse.
When the site is outside every boundary, `details` reports the nearest one.
"""
from __future__ import annotations

from . import data
from .base import clean, result

VINTAGE = "NPS National Register of Historic Places"


def score(lat: float, lon: float, ctx: dict | None = None) -> dict:
    layer = data.polygon_layer("historic_districts")
    hit = layer.containing_idx(lat, lon)
    if len(hit) == 0:
        near, mi = layer.nearest(lat, lon)
        nearest = None if near is None else {"name": near["name"], "distance_mi": round(mi, 3)}
        return result("XXII", "Historic Preservation", score=0, max_score=2,
                      explanation="Site is not within a National Register historic district or resource → 0 pts.",
                      details={"inside": False, "nearest_district": nearest}, data_vintage=VINTAGE)

    row = layer.records[hit[0]]
    expl = (f"Site is inside the National Register boundary of “{row['name']}” → 2 pts eligible "
            f"— requires historic tax credits and adaptive reuse.")
    return result(
        "XXII", "Historic Preservation", score=2, max_score=2, explanation=expl,
        components=[{"id": "XXII", "name": "Historic Preservation", "score": 2, "max_score": 2,
                     "explanation": expl}],
        developer_inputs=[{"id": "XXII", "name": "Historic tax credits + adaptive reuse",
                           "description": "2 pts require historic tax credits and adaptive reuse of / units "
                                          "in the certified historic structure."}],
        details={"inside": True, "designation": row["name"], "boundary_type": clean(row["boundary_type"]),
                 "contributing_resources": clean(row["contributing_resources"])},
        data_vintage=VINTAGE)
