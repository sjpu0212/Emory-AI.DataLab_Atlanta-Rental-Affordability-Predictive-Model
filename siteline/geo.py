"""Spatial primitives shared by every scorer.

Mirrors scoring/base.py (the project's authoritative reference) and the JS in
prototype/index.html, both in the sitelineLIHTC site repo:

* Distances are great-circle ("straight-line") miles. The QAP measures the actual
  driving/walking route, so desirable-amenity and transit distances are inflated by
  ROUTE_FACTOR (x1.15) as a route estimate.
* A "verify route" flag is raised when a route estimate lands within ±15% of a
  scoring cutoff.

Two small index classes make repeated lookups fast:

* PointLayer   — nearest / within-radius queries on lat-lon points (KD-tree on the
                 unit sphere, so results are exact great-circle nearest neighbours).
* PolygonLayer — point-in-polygon and distance-to-polygon queries (shapely STRtree;
                 distances are computed in a local equirectangular projection
                 centred on the query point, accurate to well under 1% at these scales).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree
from shapely import STRtree

EARTH_MI = 3958.7613
MI_PER_DEG = EARTH_MI * math.pi / 180    # miles per degree of latitude
ROUTE_FACTOR = 1.15                      # straight-line → route-distance estimate
FLAG_MARGIN = 0.15                       # ±15% of a cutoff → "verify route" flag


def haversine_mi(lat, lon, lats, lons):
    """Great-circle miles from one point to one or many points (vectorized)."""
    lat1, lon1 = np.radians(lat), np.radians(lon)
    lat2, lon2 = np.radians(np.asarray(lats, float)), np.radians(np.asarray(lons, float))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return EARTH_MI * 2 * np.arcsin(np.sqrt(a))


def route_est(straight_mi: float) -> float:
    """Estimate route distance from straight-line distance."""
    return straight_mi * ROUTE_FACTOR


def near_cutoff(dist: float, cutoffs) -> bool:
    """True if `dist` is within ±FLAG_MARGIN of any cutoff (borderline → verify the real route)."""
    return any(abs(dist - c) <= FLAG_MARGIN * c for c in cutoffs)


def tier_points(dist: float, tiers, points):
    """First tier whose cutoff the distance meets → (points, label); (0, '> last') otherwise."""
    for cut, pts in zip(tiers, points):
        if dist <= cut:
            return pts, f"<= {cut} mi"
    return 0.0, f"> {tiers[-1]} mi"


def _unit_xyz(lats, lons):
    la, lo = np.radians(np.asarray(lats, float)), np.radians(np.asarray(lons, float))
    return np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def _chord_to_mi(chord):
    return 2 * EARTH_MI * np.arcsin(np.clip(np.asarray(chord) / 2, 0, 1))


def _mi_to_chord(mi):
    return 2 * math.sin(mi / (2 * EARTH_MI))


class PointLayer:
    """A table of lat/lon points with fast nearest-neighbour and radius queries.

    `df` is the table as a DataFrame; `records` holds the same rows as plain dicts
    (what the scorers use — much faster than pulling rows out of pandas one at a time).
    """

    def __init__(self, df: pd.DataFrame, lat_col: str = "lat", lon_col: str = "lon"):
        self.df = df.dropna(subset=[lat_col, lon_col]).reset_index(drop=True)
        self.records = self.df.to_dict("records")
        self.lat = self.df[lat_col].to_numpy(float)
        self.lon = self.df[lon_col].to_numpy(float)
        self.tree = cKDTree(_unit_xyz(self.lat, self.lon)) if len(self.df) else None

    def __len__(self):
        return len(self.df)

    def nearest_many(self, lats, lons):
        """Nearest point to each query → (row index array, straight-line miles array)."""
        if self.tree is None:
            n = len(np.atleast_1d(lats))
            return np.full(n, -1), np.full(n, np.inf)
        k = min(8, len(self.df))
        chord, idx = self.tree.query(_unit_xyz(np.atleast_1d(lats), np.atleast_1d(lons)), k=k)
        if k == 1:
            return idx, _chord_to_mi(chord)
        # Among exact ties, keep the earliest row (matches the site's first-minimum rule).
        tied = chord <= chord[:, :1] + 1e-12
        best = np.where(tied, idx, np.iinfo(idx.dtype).max).min(axis=1)
        return best, _chord_to_mi(chord[:, 0])

    def nearest(self, lat: float, lon: float):
        """(row dict, straight-line miles) for the nearest point, or (None, inf)."""
        idx, mi = self.nearest_many(lat, lon)
        if idx[0] < 0:
            return None, float("inf")
        return self.records[int(idx[0])], float(mi[0])

    def within_records(self, lat: float, lon: float, radius_mi: float) -> list[dict]:
        """Row dicts (plus `distance_mi`) within `radius_mi` straight-line miles, nearest first."""
        if self.tree is None:
            return []
        # pad the chord a hair so floating-point never drops a point sitting right on the radius
        hits = self.tree.query_ball_point(_unit_xyz([lat], [lon])[0], _mi_to_chord(radius_mi) * (1 + 1e-9))
        hits = np.sort(np.asarray(hits, int))
        d = haversine_mi(lat, lon, self.lat[hits], self.lon[hits])
        order = np.argsort(d, kind="stable")
        return [dict(self.records[hits[j]], distance_mi=float(d[j])) for j in order if d[j] <= radius_mi]

    def within(self, lat: float, lon: float, radius_mi: float) -> pd.DataFrame:
        """Rows within `radius_mi` straight-line miles, nearest first, with a `distance_mi` column."""
        return pd.DataFrame(self.within_records(lat, lon, radius_mi),
                            columns=[*self.df.columns, "distance_mi"])


def _to_local_miles(geoms, lat0: float, lon0: float):
    """Project lon/lat geometries to planar miles centred on (lat0, lon0)."""
    kx, ky = MI_PER_DEG * math.cos(math.radians(lat0)), MI_PER_DEG
    return shapely.transform(geoms, lambda c: (c - (lon0, lat0)) * (kx, ky))


class PolygonLayer:
    """A table of polygons (WKT in `geometry_wkt`) with containment and distance queries.

    `geoms` holds the shapely geometries; `df` / `records` hold the attributes (no WKT).
    """

    def __init__(self, df: pd.DataFrame, wkt_col: str = "geometry_wkt"):
        df = df.reset_index(drop=True)
        self.geoms = shapely.from_wkt(df[wkt_col].to_numpy())
        shapely.prepare(self.geoms)
        self.tree = STRtree(self.geoms)
        self.df = df.drop(columns=wkt_col)
        self.records = self.df.to_dict("records")

    def __len__(self):
        return len(self.df)

    def containing_idx(self, lat: float, lon: float) -> np.ndarray:
        """Indices (file order) of polygons containing the point (boundary counts as inside)."""
        return np.sort(self.tree.query(shapely.Point(lon, lat), predicate="intersects"))

    def first_containing(self, lat: float, lon: float) -> dict | None:
        """The first polygon (file order) containing the point, as a row dict, or None."""
        idx = self.containing_idx(lat, lon)
        return self.records[int(idx[0])] if len(idx) else None

    def containing(self, lat: float, lon: float) -> pd.DataFrame:
        return self.df.iloc[self.containing_idx(lat, lon)]

    def distances_mi(self, lat: float, lon: float, idx) -> np.ndarray:
        """Miles from the point to each polygon in `idx` (0 if the point is inside)."""
        idx = np.asarray(idx, int)
        if idx.size == 0:
            return np.zeros(0)
        local = _to_local_miles(self.geoms[idx], lat, lon)
        return shapely.distance(local, shapely.Point(0, 0))

    def within_distance_records(self, lat: float, lon: float, miles: float) -> list[dict]:
        """Row dicts (plus `distance_mi`; inside = 0) for polygons within `miles`, nearest first."""
        kx = MI_PER_DEG * math.cos(math.radians(lat))
        cand = np.sort(self.tree.query(shapely.Point(lon, lat), predicate="dwithin", distance=miles / kx))
        d = self.distances_mi(lat, lon, cand)
        order = np.argsort(d, kind="stable")
        return [dict(self.records[cand[j]], distance_mi=float(d[j])) for j in order if d[j] <= miles]

    def within_distance(self, lat: float, lon: float, miles: float) -> pd.DataFrame:
        """Polygons within `miles` of the point (inside = 0), nearest first, with `distance_mi`."""
        return pd.DataFrame(self.within_distance_records(lat, lon, miles),
                            columns=[*self.df.columns, "distance_mi"])

    def nearest(self, lat: float, lon: float, mask=None):
        """(row dict, miles) for the nearest polygon, optionally restricted by a boolean `mask`."""
        idx = np.arange(len(self.df)) if mask is None else np.flatnonzero(np.asarray(mask))
        if idx.size == 0:
            return None, float("inf")
        pt = shapely.Point(lon, lat)
        # Degree-space distance ranks candidates; a degree of longitude is shorter than one of
        # latitude, so anything within d_min / cos(lat) degrees could still be the true nearest.
        d_deg = shapely.distance(self.geoms[idx], pt)
        cand = idx[d_deg <= d_deg.min() / math.cos(math.radians(lat)) + 1e-12]
        d = self.distances_mi(lat, lon, cand)
        best = int(np.argmin(d))
        return self.records[int(cand[best])], float(d[best])

    def points_inside(self, i: int, lats, lons) -> np.ndarray:
        """Boolean mask: which of the given points fall inside polygon `i`."""
        return shapely.intersects_xy(self.geoms[i], np.asarray(lons, float), np.asarray(lats, float))
