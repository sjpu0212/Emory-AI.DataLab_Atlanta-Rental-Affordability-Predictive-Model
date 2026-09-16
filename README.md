# SiteLine StartUp Pack

The [SiteLine map](https://kmcalist682336.github.io/sitelineLIHTC/) scores a location in
metro Atlanta against Georgia's 2024–2025 Qualified Allocation Plan (QAP), the rulebook
DCA uses to award Low-Income Housing Tax Credits (LIHTC). This pack gives you the same
scoring in Python, plus the data behind it as CSVs. You can then score thousands of
places, look up what drives each score, and combine the results with your own
measures of **housing need**.

This repo is the companion to [sitelineLIHTC](https://github.com/kmcalist682336/sitelineLIHTC), which holds the website itself,
the data pipeline, and the reference Python scorer.

It has three parts:

1. **`data/`**: twelve CSVs with every layer the map scores against: amenities,
   transit, school zones, census tracts, past LIHTC awards, and boundaries. See
   [`data/DATA_DICTIONARY.md`](data/DATA_DICTIONARY.md).
2. **Per-criterion scorers** (`siteline.activities`, `siteline.transportation`, and six
   more). Each takes a lat/lon and returns the sub-scores plus the "closest things"
   behind them: nearest grocery, zoned schools, census tract, awards within a mile, and
   so on.
3. **A total scorer** (`siteline.score_site`, `score_sites`, `score_grid`). It combines
   everything into the 46-point location score the map shows.

### Documentation

| Doc | Read it for |
|---|---|
| This README | Setup, quick start, what a result contains, and where housing-need work plugs in |
| [`SCORING.md`](SCORING.md) | **Exactly how a lat/lon becomes a score.** It covers every rule and cutoff, which CSV columns each rule reads, how ties and boundaries are handled, the 10-point block, the all-metro pool policy, and a step-by-step worked example (the Vortex, 39/46). Read this before interpreting or changing any score |
| [`data/DATA_DICTIONARY.md`](data/DATA_DICTIONARY.md) | Every CSV: its columns, sources, vintages, filters, and known quirks |

## Setup

You need Python 3.10 or newer.

```bash
git clone https://github.com/kmcalist682336/SitelineLIHTCStartUp.git
cd SitelineLIHTCStartUp
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[geo]"              # siteline + pandas/numpy/shapely/scipy (+ geopandas/matplotlib)
python tests/test_siteline.py
```

The last command should end with `7 tests passed`. If you'd rather not install the
package, run `pip install -r requirements.txt` instead and work from the repository
root. The example scripts find the package either way.

## Quick start

```python
import siteline

# One site: full detail
res = siteline.score_site(33.766384, -84.349133)      # the Vortex, Little Five Points
res["total_score"]              # 39.0  (out of res["max_total_scored"] = 46)
res["scores"]                   # {'XI': 20.0, 'XII': 4.0, 'XIII': 3.0, 'XV': 10.0, 'XVI': 0.0,
                                #  'XVIII': 0.0, 'XIX': None, 'XXII': 2.0, 'block': 10.0, 'total': 39.0}
print(siteline.report(res))     # readable breakdown, with nearest amenities and zoned schools

# Many sites: one row each, with scores and nearest-thing columns
import pandas as pd
sites = pd.DataFrame({"lat": [33.7537, 33.5215], "lon": [-84.3916, -84.3538]})
df = siteline.score_sites(sites)

# A grid over a region: 'atlanta', 'arc' (all 11 counties), a county name, or a bbox
grid = siteline.score_grid("atlanta", cell_mi=0.25)   # about 2,200 cells in about 4 s
```

From the command line:

```bash
python -m siteline 33.766384 -84.349133            # readable report
python -m siteline 33.766384 -84.349133 --json     # the full result
```

Then work through the examples. Each writes its output to `outputs/`.

| Script | Shows |
|---|---|
| `examples/01_score_one_site.py [lat lon]` | Reading one result: sub-scores, nearest amenities, schools, tract indicators, nearby awards |
| `examples/02_score_many_sites.py [--arc]` | Scoring a site list and a grid; `--arc` scores all 11 counties (about 52k cells, about 1.5 min) |
| `examples/03_tracts_and_need.py` | Joining scores to tracts and ranking "high score and high need"; direct layer queries; a map |

## What's here

```
SitelineLIHTCStartUp/
  README.md                 this file
  SCORING.md                exactly how (lat, lon) becomes a score, rule by rule
  data/                     the CSVs (about 26 MB) + DATA_DICTIONARY.md
  siteline/                 the Python package
    site.py                 score_site / score_sites / score_grid / summarize / report
    activities.py           §XI   desirable / undesirable activities   (20 pts)
    transportation.py       §XII  transit                              (6)
    education.py            §XIII quality school zones                 (3)
    stable_communities.py   §XV   tract indicators                     (10, block)
    community_designations.py §XVI Choice Neighborhoods / Purpose Built (10, block)
    previous_projects.py    §XVIII prior LIHTC awards nearby           (5)
    housing_needs.py        §XIX  CHAS severe housing need             (10, block)
    historic.py             §XXII National Register districts          (2)
    base.py  geo.py  data.py   site context, spatial helpers, CSV loading
  examples/                 runnable walkthroughs
  tests/                    sanity checks (includes the reference site)
  build_startup_data.py     maintainers only: regenerates data/
```

## How the score works

This is the short version. [`SCORING.md`](SCORING.md) has every rule, the CSV columns
each one reads, and a worked example.

Eight QAP criteria depend only on location. That is all the map, and this package, can
score:

| § | Criterion | Max | Rule (short version) |
|---|---|---:|---|
| XI | Desirable / Undesirable Activities | 20 | For each of 18 amenity types, points by distance to the nearest one (0.5 / 1 / 1.5 mi). −2 for each nuisance or hazard within 0.25 mi, and −2 for a food-desert tract with no nearby grocery |
| XII | Community Transportation | 6 | Nearest transit hub (5 / 4.5 / 4) or nearest stop (3 / 2 / 1) within 0.25 / 0.5 / 1 mi, whichever is higher |
| XIII | Quality Education Areas | 3 | Grades covered by qualifying *zoned* public schools: ≥ 3 → 1, ≥ 7 → 1.5, all 13 → 3 (family) or 2 (other tenancy) |
| XV | Stable Communities | 10 | Tract indicators above the pool median: 2 / 3 / 4 → 6 / 8 / 10 (one point less if borrowed from tracts within 0.25 mi) |
| XVI | Community Designations | 10 | Inside a Choice Neighborhoods or Purpose Built Communities area |
| XVIII | Previous Projects | 5 | No recent LIHTC awards in the site's city (5) or within 1 mile (3) |
| XIX | Housing Needs Characteristics | 10 | *Other-Metro counties only.* Tract is not a QCT, ≥ 45% severe renter housing problems, county growing (5); +5 if §XV ≥ 5 |
| XXII | Historic Preservation | 2 | Inside a National Register district |

**Pools.** Cobb, DeKalb, Fulton, and Gwinnett form the QAP's Atlanta Metro pool; the
other 7 counties are Other Metro. Following Invest Atlanta's guidance, all 11 counties
get Metro Pool rules; the QAP's USDA-based Rural Pool is not applied.

**The 10-point block.** §XV, §XVI, and §XIX are mutually exclusive, so only the highest
one counts. §XIV, a developer claim, can also compete for this block.
**Total = §XI + §XII + §XIII + §XVIII + §XXII + block, out of 46.**

The other 15 QAP sections (financing, readiness, services, and so on) depend on what the
developer proposes, not where. The map handles them as a questionnaire, and they are not
included here.

**Distances.** The QAP measures real driving or walking routes. We use straight-line
distance × 1.15 as an estimate. A result within ±15% of a cutoff appears in the result's
`flags` so you know to check it. The undesirable 0.25-mi radius uses plain straight-line
distance.

## What a result contains

`score_site()` returns a dict:

| Key | Contents |
|---|---|
| `site` | `tract_geoid`, `county`, `pool`, `municipality`, `in_qct`, `usda_food_desert`, `in_arc` |
| `in_scope` | `False` outside the 11 counties. Scores are then empty |
| `total_score`, `max_total_scored`, `scores` | The headline numbers (`scores[sec]` is `None` when a section doesn't apply) |
| `sections["XI"]` … `sections["XXII"]` | One dict per criterion: `score`, `max_score`, `applicable`, `explanation`, `components` (sub-scores), `flags`, `details` |
| `block` | Which of §XV / §XVI / §XIX won the 10-point block |
| `flags` | All "verify this" notes in one list |

The "closest things" are in each section's `details`:

- **§XI**: for each of the 18 categories, the nearest place with name, address,
  coordinates, distance, and points; undesirables within 0.25 mi; the nearest
  undesirable of each type; food-desert status
- **§XII**: nearest hub and nearest stop (agency, route count, rail, distance)
- **§XIII**: zoned elementary, middle, and high schools (district, quality tests, CCRPI,
  distance to the school building, and whether a nearest-zone fallback was used)
- **§XV**: tract GEOID, pool, each indicator's value against the pool median, and nearby
  tracts that lend indicators
- **§XVI**: inside or not, and the distance to the nearest CNI and PBC areas
- **§XVIII**: city (local government boundary), awards in that city in the last 15
  years, awards within 1 mile, the nearest award, and whether a transit hub is within 1 mile
- **§XIX**: CHAS severe-housing share, QCT status, and county growth
- **§XXII**: the district the site is inside, or the nearest one and its distance

`score_sites()` and `score_grid()` flatten each result with `summarize()` into about 80
columns: every sub-score, the block winner, the total, and for each amenity category
the nearest name and its distance (`xi_c_name`, `xi_c_mi`, …), plus hub and stop,
zoned schools, award counts, and more.

## Where your housing-need work plugs in

Every scored row carries **`tract_geoid`**, the 11-digit census-tract GEOID. That is the
join key for almost any public housing-need data: ACS tables, HUD CHAS, eviction
filings, and so on. A typical workflow:

```python
import siteline
from siteline import data

grid = siteline.score_grid("arc", cell_mi=0.25)                  # where could a site score well?
tracts = data.table("tracts").drop(columns="geometry_wkt")        # tract attributes (all of GA)
my_need = ...                                                      # your tract-level measure, indexed by GEOID
best = grid.groupby("tract_geoid")["total_score"].max()
ranked = best.to_frame().join(my_need)                             # high score AND high need
```

Some of this is already in `data/tracts.csv`:

- the five §XV indicators, including poverty and median income
- QCT status
- USDA food-desert status
- **HUD CHAS severe-housing counts, but only for the 7 Other-Metro counties.** §XIX only
  applies there. Extending CHAS to Cobb, DeKalb, Fulton, and Gwinnett is an obvious
  first step; see [`data_pipeline/pull_chas.py`](https://github.com/kmcalist682336/sitelineLIHTC/blob/main/data_pipeline/pull_chas.py)
  in the site repo.

For point-based measures (access, proximity, clustering), use the layer indexes
directly:

```python
data.amenity_layer("c").within(lat, lon, 1.0)          # groceries within 1 mile (DataFrame)
data.point_layer("lihtc_awards").nearest(lat, lon)      # (row as a dict, miles)
data.polygon_layer("school_zones").containing(lat, lon) # every zone covering the point
data.geodataframe("tracts")                             # GeoDataFrame for mapping and spatial joins
```

Layer names: `amenity_layer("a"…"s")`, `undesirable_layer("a"|"b")`,
`point_layer("transit_hubs"|"transit_stops"|"lihtc_awards")`, and
`polygon_layer("tracts"|"school_zones"|"municipalities"|"counties"|"community_designations"|"historic_districts")`.

## Accuracy and caveats

- **Validated.** On 3,000 random points across the region, `siteline` matches the
  project's reference Python scorer ([`scoring/`](https://github.com/kmcalist682336/sitelineLIHTC/tree/main/scoring) in the site
  repo) on every criterion at
  2,992 points. The other 8 are the split-grade school-zone case below. It also
  reproduces the reference site exactly (the Vortex: 20 / 4 / 3 / 10 / 0 / 0 / N/A / 2 →
  39 of 46; `tests/` checks this).
- **It is not an official score.** Distances are estimates, data vintages vary (mostly
  July 2026; the USDA food-desert atlas is from 2019), and several items still need
  documentation or the approval of an outside body. For example, §XVI needs the
  designating body's selection and §XXII needs historic tax credits.
- **The map can differ slightly.** The website uses simplified geometry (tens of meters),
  and its §XV "nearby tract" test measures to polygon corners rather than edges. It can
  therefore miss a nearby tract that this package catches. Treat this package's number
  as the more precise one.
- **Known quirks.** Split-grade elementary zones (Decatur, Acworth) count only one of
  the two schools; see the data dictionary. §XVIII.A treats census-designated places as
  cities and scores 0 for unincorporated sites. Geometry is simplified to about 1–2 m, so
  a point sitting exactly on a boundary can land on either side.
- **Speed.** About 2 ms per site after a half-second warm-up. All 11 counties at 0.25 mi
  (52k cells) take about 1.5 minutes.

## For maintainers

The scoring logic lives in three places that must agree. Two are in the
[site repo](https://github.com/kmcalist682336/sitelineLIHTC): `scoring/` (the reference) and the JavaScript in
`prototype/index.html`. The third is `siteline/` here. If you change a rule, change all
three and re-run `tests/test_siteline.py`.

The CSVs are exported from the site repo's pipeline outputs (`scoring_data/`, which git
ignores there). After refreshing that pipeline, regenerate them from this repo, using the
site repo's Python environment (it has geopandas):

```bash
/path/to/sitelineLIHTC/venv/bin/python build_startup_data.py --site-repo /path/to/sitelineLIHTC
# or: export SITELINE_REPO=/path/to/sitelineLIHTC
```

Then re-run the tests and commit the updated `data/`.

## Disclaimer

SiteLine assists with LIHTC site analysis but does **not** guarantee scoring accuracy.
Verify all calculations against the official 2024–2025 Georgia DCA QAP and consult
qualified professionals before relying on any result for an application. The data comes
from the public sources listed in [`data/DATA_DICTIONARY.md`](data/DATA_DICTIONARY.md),
each under its own terms.
