"""§XIX Housing Needs Characteristics (max 10). Mirrors scoring/housing_needs.py.

Applies only to the Other-Metro pool (Cherokee, Clayton, Douglas, Fayette, Forsyth,
Henry, Rockdale); Atlanta-Metro sites get applicable=False.

A (5): the site tract is not a QCT, >= 45% of its <= 80%-AMI renter units have a severe
       housing problem (HUD CHAS), and the county is growing.
B (+5): A holds and the site earns >= 5 pts under §XV (or §XIV, a developer claim).
§XIX is one of the mutually exclusive 10-point block (see site.py).
"""
from __future__ import annotations

from . import base
from .base import clean, result

SEVERE_THRESHOLD = 0.45
VINTAGE = "HUD CHAS + ACS/BLS growth"


def score(lat: float, lon: float, ctx: dict | None = None, xv_score: float | None = None) -> dict:
    ctx = ctx or base.site_context(lat, lon)
    if ctx.get("pool") != "other metro":
        return result("XIX", "Housing Needs Characteristics", score=0, max_score=10, applicable=False,
                      explanation="Not applicable — §XIX applies only to the Other-Metro pool "
                                  "(this site is not in it).", data_vintage=VINTAGE)

    row = base.tract_row(ctx.get("tract_geoid"))
    if row is None or clean(row["xix_qualifies_a"]) is None:
        return result("XIX", "Housing Needs Characteristics", score=0, max_score=10,
                      explanation="Site's tract has no §XIX eligibility data.", data_vintage=VINTAGE)

    severe_pct = clean(row["xix_severe_housing_pct"])
    in_qct = bool(row["in_qct"])
    severe_ok = bool(row["xix_severe_ge_45"])
    growing = bool(row["xix_county_growth"])
    a_ok = bool(row["xix_qualifies_a"])
    a_pts = 5 if a_ok else 0

    if xv_score is None:
        from . import stable_communities
        xv_score = stable_communities.score(lat, lon, ctx)["score"]
    b_ok = a_ok and xv_score >= 5
    b_pts = 5 if b_ok else 0
    sc = a_pts + b_pts

    pct = "n/a" if severe_pct is None else f"{severe_pct:.0%}"
    if not a_ok:
        reasons = []
        if in_qct:
            reasons.append("tract is a QCT")
        if not severe_ok:
            reasons.append(f"severe-housing share {pct} < 45%")
        if not growing:
            reasons.append("county not growing")
        expl = f"Site's tract fails §XIX.A ({'; '.join(reasons) or 'criteria not met'}) → 0 pts."
    else:
        expl = (f"Tract qualifies under §XIX.A (not a QCT, severe-housing share {pct} >= 45%, county growing) → 5 pts"
                + (f"; §XV = {xv_score} >= 5 → §XIX.B +5 → 10." if b_ok else "."))

    return result(
        "XIX", "Housing Needs Characteristics", score=sc, max_score=10, explanation=expl,
        components=[
            {"id": "XIX.A", "name": "Housing Need & Growth", "score": a_pts, "max_score": 5, "explanation": expl},
            {"id": "XIX.B", "name": "Stable/Revitalization combo", "score": b_pts, "max_score": 5,
             "explanation": f"§XV score {xv_score} ({'>= 5' if xv_score >= 5 else '< 5'})."}],
        details={"tract_geoid": ctx.get("tract_geoid"), "not_in_qct": not in_qct,
                 "severe_housing_pct": severe_pct, "severe_threshold": SEVERE_THRESHOLD,
                 "severe_met": severe_ok, "county_pop_growth": clean(row["xix_pop_growth"]),
                 "county_emp_growth": clean(row["xix_emp_growth"]), "county_growth": growing,
                 "qualifies_A": a_ok, "B_bonus": {"eligible": b_ok, "via": "XV", "xv_score": xv_score}},
        data_vintage=VINTAGE)
