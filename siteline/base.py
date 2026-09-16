"""Site context and the standard result shape (mirrors scoring/base.py)."""
from __future__ import annotations

import functools

from . import data

# DCA pool by county FIPS (the ARC 11-county region). Policy: all 11 counties get Metro Pool
# rules; the QAP's USDA-based Rural Pool is not applied (Invest Atlanta guidance: the rural
# designations are outdated for this fast-urbanizing region). See SCORING.md.
ATLANTA_METRO = {"067", "089", "121", "135"}                     # Cobb, DeKalb, Fulton, Gwinnett
OTHER_METRO = {"057", "063", "097", "113", "117", "151", "247"}  # Cherokee, Clayton, Douglas,
#                                                                  Fayette, Forsyth, Henry, Rockdale
COUNTY_NAME = {
    "057": "Cherokee", "063": "Clayton", "067": "Cobb", "089": "DeKalb", "097": "Douglas",
    "113": "Fayette", "117": "Forsyth", "121": "Fulton", "135": "Gwinnett", "151": "Henry",
    "247": "Rockdale",
}


def pool_of(county_fips: str | None) -> str | None:
    if county_fips in ATLANTA_METRO:
        return "atlanta metro"
    if county_fips in OTHER_METRO:
        return "other metro"
    return None


@functools.lru_cache(maxsize=None)
def _tracts_by_geoid() -> dict:
    return {r["geoid"]: r for r in data.polygon_layer("tracts").records}


def tract_row(geoid: str | None) -> dict | None:
    """The tracts.csv row (minus geometry) for a GEOID, as a dict, or None."""
    return _tracts_by_geoid().get(geoid) if geoid else None


def site_context(lat: float, lon: float) -> dict:
    """Resolve the once-per-site geographic facts every scorer shares."""
    tract = data.polygon_layer("tracts").first_containing(lat, lon)
    geoid = tract["geoid"] if tract else None
    fips = geoid[2:5] if geoid else None
    place = data.polygon_layer("municipalities").first_containing(lat, lon)
    return {
        "lat": lat, "lon": lon,
        "tract_geoid": geoid,
        "county_fips": fips,
        "county": tract["county"] if tract else None,
        "pool": pool_of(fips),
        "in_arc": fips in (ATLANTA_METRO | OTHER_METRO),
        "municipality": place["name"] if place else None,   # None = unincorporated
        "in_qct": clean(tract["in_qct"]) if tract else None,
        "usda_food_desert": clean(tract["usda_food_desert"]) if tract else None,
    }


def result(criterion, name, *, score, max_score, explanation, applicable=True,
           components=None, flags=None, developer_inputs=None, details=None,
           data_vintage=None) -> dict:
    """One scorer's standardized output (same keys as scoring.base.result)."""
    return {
        "criterion": criterion,
        "name": name,
        "applicable": applicable,
        "score": round(float(score), 3),
        "max_score": float(max_score),
        "explanation": explanation,
        "components": components or [],
        "flags": flags or [],
        "developer_inputs": developer_inputs or [],
        "details": details,
        "data_vintage": data_vintage,
    }


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def clean(v):
    """Pandas/numpy scalars → plain Python (NaN → None) so results print and JSON-serialize cleanly."""
    if hasattr(v, "item"):
        v = v.item()
    return None if v is None or (isinstance(v, float) and v != v) else v
