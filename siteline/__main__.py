"""Command line:  python -m siteline LAT LON [--tenancy elderly] [--json]"""
import argparse
import json

from . import report, score_site

p = argparse.ArgumentParser(prog="python -m siteline", description="Score one metro-Atlanta LIHTC site.")
p.add_argument("lat", type=float)
p.add_argument("lon", type=float)
p.add_argument("--tenancy", default="family", help="family (default), elderly, hfop, ... (affects §XIII only)")
p.add_argument("--json", action="store_true", help="print the full result as JSON")
a = p.parse_args()
res = score_site(a.lat, a.lon, tenancy=a.tenancy)
print(json.dumps(res, indent=2, default=str) if a.json else report(res))
