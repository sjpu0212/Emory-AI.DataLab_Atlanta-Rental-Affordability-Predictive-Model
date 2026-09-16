"""Load the StartUp CSVs (cached). Everything the scorers use comes through here.

    from siteline import data
    data.table("tracts")            # plain pandas DataFrame (geometry as WKT text)
    data.geodataframe("tracts")     # GeoDataFrame — needs `pip install geopandas`
    data.list_tables()              # what's available

See data/DATA_DICTIONARY.md for every column.
"""
from __future__ import annotations

import functools
from pathlib import Path

import pandas as pd

from .geo import PointLayer, PolygonLayer

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Keep FIPS/GEOID-style codes as text so leading zeros survive.
_DTYPES = {
    "tracts": {"geoid": str, "county_fips": str},
    "counties": {"geoid": str, "county_fips": str},
    "municipalities": {"geoid": str, "class_fp": str},
    "transit_hubs": {"stop_id": str},
    "transit_stops": {"stop_id": str},
    "lihtc_awards": {"number": str},
}


def list_tables() -> list[str]:
    return sorted(p.stem for p in DATA_DIR.glob("*.csv"))


@functools.lru_cache(maxsize=None)
def _read(name: str) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No table '{name}' in {DATA_DIR}. Available: {list_tables()}")
    return pd.read_csv(path, dtype=_DTYPES.get(name), low_memory=False)


def table(name: str) -> pd.DataFrame:
    """A copy of one CSV as a DataFrame (safe to modify)."""
    return _read(name).copy()


def geodataframe(name: str):
    """One polygon table as a GeoDataFrame (EPSG:4326). Requires geopandas."""
    import geopandas as gpd
    df = table(name)
    if "geometry_wkt" not in df.columns:
        return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326)
    geom = gpd.GeoSeries.from_wkt(df.pop("geometry_wkt"), crs=4326)
    return gpd.GeoDataFrame(df, geometry=geom, crs=4326)


# ── indexed layers used by the scorers ───────────────────────────────────────
@functools.lru_cache(maxsize=None)
def amenity_layer(category_id: str) -> PointLayer:
    """§XI desirable amenities of one category (a–s)."""
    df = _read("amenities_desirable")
    return PointLayer(df[df["category_id"] == category_id])


@functools.lru_cache(maxsize=None)
def undesirable_layer(category_id: str) -> PointLayer:
    """§XI undesirables: 'a' nuisance uses, 'b' environmental hazards."""
    df = _read("amenities_undesirable")
    return PointLayer(df[df["category_id"] == category_id])


@functools.lru_cache(maxsize=None)
def point_layer(name: str) -> PointLayer:
    """transit_hubs, transit_stops, lihtc_awards."""
    return PointLayer(_read(name))


@functools.lru_cache(maxsize=None)
def polygon_layer(name: str) -> PolygonLayer:
    """tracts, school_zones, municipalities, counties, community_designations, historic_districts."""
    return PolygonLayer(_read(name))


@functools.lru_cache(maxsize=None)
def pool_medians() -> dict:
    """pool → {indicator column → statewide-within-pool median}."""
    df = _read("tract_pool_medians").set_index("pool")
    return {pool: row.to_dict() for pool, row in df.iterrows()}
