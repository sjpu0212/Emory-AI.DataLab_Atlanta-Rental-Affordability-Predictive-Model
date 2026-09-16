"""Score a list of sites, then a whole grid of sites.

    python examples/02_score_many_sites.py         # sample sites + City of Atlanta grid (~5 s)
    python examples/02_score_many_sites.py --arc   # also all 11 counties at 0.25 mi (~1.5 min)

Writes CSVs to outputs/.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import pandas as pd  # noqa: E402

import siteline  # noqa: E402

OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

# ── 1. A handful of candidate sites (any DataFrame with lat/lon columns works) ──
sites = pd.DataFrame([
    {"site": "The Vortex, Little Five Points", "lat": 33.766384, "lon": -84.349133},
    {"site": "Five Points, Downtown Atlanta", "lat": 33.753746, "lon": -84.391573},
    {"site": "Jonesboro (Clayton Co.)", "lat": 33.521500, "lon": -84.353800},
    {"site": "Lawrenceville (Gwinnett Co.)", "lat": 33.956200, "lon": -83.988000},
    {"site": "Canton (Cherokee Co.)", "lat": 34.236800, "lon": -84.490800},
])
scored = siteline.score_sites(sites)          # one row per site; extra columns (site) are kept
cols = ["site", "municipality", "pool", "total_score", "score_XI", "score_XII", "score_XIII",
        "block_winner", "block_score", "score_XVIII", "score_XXII", "xi_c_name", "xi_c_mi"]
print(scored[cols].to_string(index=False))
scored.to_csv(OUT / "sample_sites.csv", index=False)

# ── 2. A grid over the City of Atlanta (cell centres every 0.25 mi) ──
grid = siteline.score_grid("atlanta", cell_mi=0.25)
grid.to_csv(OUT / "atlanta_grid_0.25mi.csv", index=False)
print(f"\n{len(grid):,} Atlanta cells; total score distribution:")
print(grid["total_score"].describe().round(1).to_string())
print("\nTop 10 cells:")
print(grid.nlargest(10, "total_score")[["lat", "lon", "tract_geoid", "total_score", "block_winner"]]
      .to_string(index=False))

# ── 3. Optionally, the whole 11-county region ──
if "--arc" in sys.argv:
    arc = siteline.score_grid("arc", cell_mi=0.25)
    arc.to_csv(OUT / "arc_grid_0.25mi.csv", index=False)
    print("\nMean total score by county:")
    print(arc.groupby("county")["total_score"].agg(["size", "mean", "max"]).round(1).to_string())

print(f"\nCSVs written to {OUT.relative_to(HERE)}/")
