"""Score one site and dig into the result.

    python examples/01_score_one_site.py                  # the Vortex, Little Five Points
    python examples/01_score_one_site.py 33.7537 -84.3916  # any lat/lon in the 11-county region
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))          # lets `import siteline` work without installing it

import siteline  # noqa: E402

lat, lon = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) == 3 else (33.766384, -84.349133)
res = siteline.score_site(lat, lon)

# 1. Human-readable breakdown (the same text as `python -m siteline LAT LON`)
print(siteline.report(res))
if not res["in_scope"]:
    sys.exit(0)

# 2. Headline numbers
print("\n--- headline ---")
print("total:", res["total_score"], "/", res["max_total_scored"])
print("by section:", res["scores"])            # None = not applicable (§XIX outside Other-Metro)
print("10-pt block winner:", res["block"]["winner"])

# 3. Each section has the same keys: score, max_score, explanation, components, flags, details.
#    `details` holds the "closest things" behind the score.
S = res["sections"]
print("\n--- closest things ---")
grocery = next(d for d in S["XI"]["details"]["desirable"] if d["id"] == "XI.A.c")
print("nearest grocery:", grocery["nearest"]["name"], "|", grocery["nearest"]["address"],
      "|", grocery["distance_mi"], "mi (route est.)")

hub = S["XII"]["details"]["nearest_hub"]
print("nearest transit hub:", hub["name"], f"({hub['agency']}, {hub['route_count']} routes)", hub["distance_mi"], "mi")

for school in S["XIII"]["details"]["schools"]:
    print(f"zoned {school['band']} school: {school['name']} — qualifies={school['qualifies']} "
          f"(CCRPI {school['ccrpi_avg']}, {school['site_to_school_mi']} mi away)")

xv = S["XV"]["details"]
print("census tract:", xv["site_tract"]["geoid"], "| pool:", xv["pool"])
for name, ind in xv["site_tract"]["indicators"].items():
    print(f"   {name:<22} {ind['value']!s:>10}  (pool median {ind['pool_median']})  above={ind['above_median']}")

xviii = S["XVIII"]["details"]
print("city (local government boundary):", xviii["local_government_boundary"])
print("LIHTC awards within 1 mile:", [(a["name"], a["year"]) for a in xviii["awards_within_1_mile"]][:5])

# 4. Everything, as JSON
out = HERE / "outputs" / "site_result.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(res, indent=2, default=str))
print(f"\nFull result written to {out.relative_to(HERE)}")
