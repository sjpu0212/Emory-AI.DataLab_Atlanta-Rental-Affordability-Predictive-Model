"""Join scores to census tracts: this is where your housing-need measures plug in.

    python examples/03_tracts_and_need.py

Every scored row carries `tract_geoid` (the 11-digit census-tract GEOID), so any
tract-level measure you build (ACS, CHAS, evictions, rent burden, ...) can be merged on
it. The "need" column below is a PLACEHOLDER (share of residents below poverty); swap
in your own measure.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import siteline  # noqa: E402
from siteline import data  # noqa: E402

# ── 1. The tract table (geometry dropped for a lighter frame) ──
tracts = data.table("tracts").drop(columns="geometry_wkt")
arc = tracts[tracts["in_arc"]].set_index("geoid")
print(f"{len(arc):,} tracts in the 11-county region; columns:\n  {list(arc.columns)}\n")

need = (100 - arc["pct_above_poverty"]).rename("need_placeholder")   # ← replace with your measure

# ── 2. Score a grid and roll it up to tracts ──
grid = siteline.score_grid("atlanta", cell_mi=0.25, progress=False)
by_tract = grid.groupby("tract_geoid").agg(cells=("total_score", "size"),
                                           mean_score=("total_score", "mean"),
                                           best_score=("total_score", "max"))
merged = by_tract.join(need).join(arc[["county", "median_income", "in_qct"]])

# ── 3. Where are scores AND need both high? (percentile ranks, then the weaker of the two) ──
merged["score_pctile"] = merged["best_score"].rank(pct=True)
merged["need_pctile"] = merged["need_placeholder"].rank(pct=True)
merged["both"] = merged[["score_pctile", "need_pctile"]].min(axis=1)
print("Atlanta tracts where the best achievable score and the (placeholder) need are both high:")
print(merged.sort_values("both", ascending=False).head(12).round(2).to_string())

# ── 4. Building blocks for your own location-based measures ──
lat, lon = 33.7537, -84.3916
groceries = data.amenity_layer("c").within(lat, lon, 1.0)          # straight-line radius, miles
stops = data.point_layer("transit_stops").within(lat, lon, 0.5)
awards = data.point_layer("lihtc_awards").within(lat, lon, 2.0)
print(f"\nAround ({lat}, {lon}): {len(groceries)} groceries within 1 mi, "
      f"{len(stops)} transit stops within 0.5 mi, {len(awards)} past LIHTC awards within 2 mi")
print(awards[["name", "year", "units", "distance_mi"]].head().round(2).to_string(index=False))

# Every zone covering the point. Downtown sits in a gap in the elementary/middle zone data;
# score_site() falls back to the nearest zone there and raises a flag.
zones = data.polygon_layer("school_zones").containing(lat, lon)
print(zones[["level_band", "school_name", "qualifies"]].to_string(index=False))

# ── 5. Optional map (needs `pip install geopandas matplotlib`) ──
try:
    import matplotlib.pyplot as plt
    gdf = data.geodataframe("tracts").set_index("geoid")[["geometry"]].join(merged, how="inner")
    ax = gdf.plot(column="both", cmap="viridis", legend=True, figsize=(8, 8))
    ax.set_title("Score x need (placeholder), City of Atlanta tracts")
    ax.set_axis_off()
    out = HERE / "outputs" / "score_x_need.png"
    out.parent.mkdir(exist_ok=True)
    plt.savefig(out, dpi=120, bbox_inches="tight")
    print(f"\nMap saved to {out.relative_to(HERE)}")
except ImportError:
    print("\n(Install geopandas + matplotlib to also draw a map.)")
