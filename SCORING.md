# How a location becomes a score

This document lists every step from a latitude/longitude to the total location score.
It covers what `siteline.score_site()` computes and what the SiteLine map shows,
including which CSV column each rule reads. Rules follow Georgia DCA's 2024–2025
Qualified Allocation Plan (QAP); section numbers like **§XI** are QAP sections. Column
details are in [`data/DATA_DICTIONARY.md`](data/DATA_DICTIONARY.md).

## The whole calculation on one page

```text
score(lat, lon, tenancy = "family", round_year = 2026):

    tract   = first polygon in tracts.csv containing (lat, lon)
    county  = characters 3–5 of tract.geoid
    if county is not one of the 11 ARC counties:  stop, "out of scope"
    pool    = "atlanta metro" if county in {Cobb, DeKalb, Fulton, Gwinnett} else "other metro"
    city    = first polygon in municipalities.csv containing (lat, lon), or none

    XI    = desirable / undesirable activities     0 – 20
    XII   = transit                                 0 – 5   (6th point is not location-based)
    XIII  = zoned school quality                    0 – 3
    XVIII = previous LIHTC awards nearby            0 – 5
    XXII  = National Register district              0 or 2

    XV    = stable-community indicators             0 – 10  ┐ the 10-point block:
    XVI   = CNI / Purpose Built area                0 or 10 │ only the highest one counts
    XIX   = housing need (Other Metro only)         0, 5, 10┘

    block = max(XV, XVI, XIX if pool == "other metro")
    total = XI + XII + XIII + XVIII + XXII + block             out of 46
```

The rest of this document defines each line.

---

## 1. Shared definitions

These building blocks are used throughout.

**Straight-line distance** `d(site, place)` is the great-circle (haversine) distance in
miles with Earth radius R = 3958.7613 mi.

**Route estimate** `r = 1.15 × d`. The QAP measures actual driving or walking routes;
we don't route, so we inflate straight-line distance by 15%. Unless a rule says
"straight-line", distance cutoffs are compared against `r`.

**Nearest place** in a table is the row with the smallest `d`. If two rows tie exactly
(e.g. several providers at one address), the row that comes first in the file wins.

**Inside a polygon.** A point on the boundary counts as inside. When a rule needs a
single polygon and several contain the point, the first one in file order is used.

**Distance to a polygon** is 0 if the site is inside. Otherwise it is the shortest
distance from the site to the polygon's edge, measured on a flat map centered on the
site: x = Δlon × 69.0934 × cos(site lat), y = Δlat × 69.0934 (miles). Over the short
distances involved, this is accurate to well under 1%.

**Tier function.** `T(r; c₁, c₂, c₃; p₁, p₂, p₃)` returns p₁ if r ≤ c₁, p₂ if
r ≤ c₂, p₃ if r ≤ c₃, and 0 otherwise.

**Flags.** Some results carry a "verify" flag. For example, a route estimate within
±15% of a cutoff (0.85·c ≤ r ≤ 1.15·c) is flagged, because the real route could land on
the other side. Flags never change a score.

---

## 2. Site context and pools

1. **Tract.** Find the first row of `tracts.csv` whose polygon contains the site. Its
   `geoid` is the 11-digit census tract ID: state (13), then county (3 digits), then
   tract.
2. **County.** `county_fips` = characters 3–5 of the GEOID (e.g. `13121001600` → `121`,
   Fulton).
3. **Scope.** Only the 11 ARC counties are scored: Cherokee 057, Clayton 063, Cobb 067,
   DeKalb 089, Douglas 097, Fayette 113, Forsyth 117, Fulton 121, Gwinnett 135,
   Henry 151, Rockdale 247. Anywhere else returns `in_scope = False` and no score.
4. **Pool.** The QAP assigns each site to a geographic pool, and some rules depend on it.
   - **Atlanta Metro:** Cobb, DeKalb, Fulton, Gwinnett. The QAP defines this pool by
     these four counties.
   - **Other Metro:** the other seven counties.

   > **Policy: every one of the 11 counties is Metro Pool.** The QAP also has a *Rural
   > Pool* for USDA-eligible rural areas outside the four Atlanta-Metro counties. On
   > Invest Atlanta's recommendation, this project never applies it. USDA's rural
   > designations are outdated for a region where sprawl is steadily erasing rural
   > areas, and Invest Atlanta treats all 11 counties as metro. As a result, the
   > Rural-only rules are not implemented: the 2.5-mile outer tier in §XI, the
   > county-share test in §XVIII.C, and the rural transit option in §XII.
5. **City.** Find the first row of `municipalities.csv` containing the site. It serves as
   the site's "Local Government Boundary" in §XVIII. The table includes census-designated
   places (`class_fp` U1/U2). A site inside no place is *unincorporated*.
6. **Tract flags** carried along for later steps: `in_qct` and `usda_food_desert`.

---

## 3. §XI Desirable / Undesirable Activities (20 points)

**Data:** `amenities_desirable.csv`, `amenities_undesirable.csv`, and
`tracts.csv: usda_food_desert`.

### A. Desirable activities

For each of 18 categories *k*, find the nearest row of `amenities_desirable.csv` with
`category_id = k`. Let d_k be its straight-line distance and r_k = 1.15 × d_k.

- **Grocery exception.** For category `c` (supermarket/grocery), also find the nearest
  big-box store (`a`). If it is strictly closer, use it as the grocery. The QAP lets a
  national big-box store count as grocery.
- **Points.** P_k = T(r_k; 0.5, 1.0, 1.5; group points), where:

| Group | ≤ 0.5 mi | ≤ 1.0 mi | ≤ 1.5 mi | Categories |
|:-:|:-:|:-:|:-:|---|
| 1 | 2.5 | 2 | 1.5 | a big-box, c grocery, e hospital, f medical provider, g pharmacy, h childcare, j school, l community/rec center, m park ≥ 25,000 sq ft, o library |
| 2 | 2 | 1.5 | 1 | b retail, d restaurant, i technical college, n park < 25,000 sq ft, p fire/police, q bank, r place of worship, s post office |

(QAP item *k* is not location-based, so there is no category `k`.)

The raw desirable total ΣP_k can reach 41 (10 × 2.5 + 8 × 2). The section is capped at
20, so a site does not need every category to max out.

### B. Undesirable activities (deductions)

Each deduction costs 2 points.

- **Nuisances and hazards.** Count every row of `amenities_undesirable.csv`
  (`category_id` a or b) within **0.25 mi straight-line** (no ×1.15). Each row is one
  deduction, so three hazards inside the radius mean three deductions.
- **Food desert.** Add one deduction if the site's tract has `usda_food_desert = True`
  **and** grocery (c) earned 0 points in part A.

### Section score

```text
XI = min(20, max(0, ΣP_k − 2 × (N_nuisance + N_hazard + food_desert_deduction)))
```

---

## 4. §XII Community Transportation Options (6 points; 5 from location)

**Data:** `transit_hubs.csv` and `transit_stops.csv`. Both are limited to stops served
at least 5 days a week. Hubs are rail stations or stops with 3+ routes, and every hub
is also a stop.

```text
A = T(1.15 × d(nearest hub);  0.25, 0.5, 1.0;  5, 4.5, 4)    # Option A2: transit-oriented
B = T(1.15 × d(nearest stop); 0.25, 0.5, 1.0;  3, 2, 1)      # Option B1: any public transit
XII = max(A, B)
```

The applicant claims one option, so the higher one counts. Option A1 (6 points) requires
the transit agency to own the site. That is a documentation claim, not a distance, and
is not scored.

---

## 5. §XIII Quality Education Areas (3 points)

**Data:** `school_zones.csv`, which holds traditional public-school attendance zones
only. Charter zones are excluded.

1. **Find the zoned schools.** For each band (elementary, middle, high), take the first
   zone of that band in file order that contains the site.
2. **Fallback.** If no zone of a band contains the site (a gap in the zone data, common
   downtown), use the nearest zone of that band by distance-to-polygon, and flag it.
3. **Count qualifying grades.**
   N = Σ over the three bands of `qualifying_grades` (only when `qualifies`).
   `grades_in_band` is fixed: elementary 6 (K–5), middle 3 (6–8), high 4 (9–12), so a
   site whose three zoned schools all qualify reaches 13.
4. **Points.**

| Qualifying grades N | Family tenancy | Other tenancy (elderly, etc.) |
|---|:-:|:-:|
| 13 (all of K–12) | 3 | 2 |
| 7–12 | 1.5 | 1.5 |
| 3–6 | 1 | 1 |
| 0–2 | 0 | 0 |

**What "qualifies" means.** The flags are precomputed in the CSV from DCA's published
school data. A school qualifies if it passes **any** of three tests:

- **A:** its average CCRPI score over 2018–2019 (years available) is above the state
  average for its grade cluster over the same years. The state averages are
  elementary 77.8 / 79.9, middle 76.2 / 77.0, high 75.3 / 78.8.
- **B:** GOSA designated it "Beating the Odds" in 2019.
- **C:** its CCRPI average is rising year over year, and its average score is at or
  above the applicable 25th percentile.

Schools too new to have ratings take their district's grade-cluster rating
(`rating_source = district-substitute`, `new_school = True`); these are flagged.

The scorer only reads `qualifies` and `qualifying_grades`. The `cond_*`, `ccrpi_avg`, and
`beating_the_odds` columns are there for explanation.

**Known quirk.** A few districts split elementary grades across two schools with
overlapping zones (Decatur: Clairemont K–2 and Talley Street 3–5; Acworth: McCall
Primary and Acworth Intermediate). Both zones record 6 grades, and step 1 keeps only
the first zone, so these sites deserve a manual check.

---

## 6. §XV Stable Communities (10 points, block member)

**Data:** `tracts.csv`, specifically the five `above_median_*` flags and
`n_above_median`.

The five QAP indicators are environmental health, transit access, jobs proximity,
percent above poverty, and median income. A tract "has" an indicator when it sits above
its pool's 50th percentile, which is exactly what the `above_median_<indicator>` flag
records.

```text
pts(c, near) = 0            if c < 2
             = 6 / 8 / 10   for c = 2 / 3 / ≥4        (within the site's tract)
             = 5 / 7 / 9    for c = 2 / 3 / ≥4        (when borrowing from nearby tracts)

W = the site tract's set of true flags
N = W ∪ (true flags of every other tract whose polygon is within 0.25 mi of the site)

XV = max( pts(|W|, near = False),  pts(|N|, near = True) )
```

Borrowing only helps when nearby tracts add indicators the site's tract lacks. For
example, a tract with 1 flag next to a tract with a different flag gives |N| = 2 and
5 points. A missing indicator value never counts; the QAP's "use the nearest tract with
data" fallback is not applied.

**About the flags.** The flags come precomputed in the project's source data (DCA's
Stable Communities data), and the score uses them exactly as given.

- **Atlanta-Metro tracts:** each flag equals *value > the Atlanta-Metro median* from
  `tract_pool_medians.csv`, except for 2 tracts that sit at or a hair below the median.
- **Other-Metro tracts:** the flags are consistent, but with cutoffs that are **not** the
  medians of the tract values in this file. They behave like these cutoffs:

| Indicator | Flag = True when value is above about | Median of this file's Other-Metro values |
|---|---|---|
| Environmental health index | 0.430 | 0.575 |
| Transit access index | 0.609 | 0.566 |
| Jobs proximity index | 0.597 | 0.584 |
| % above poverty | 86.45 | 86.3 |
| Median income | $60,000 | $57,500 |

The likely explanation is that DCA computed its Other-Metro percentiles over a smaller
set of tracts than this file labels "other metro". This is being verified. Until then,
treat §XV (and §XIX.B, which depends on it) with some caution in the seven Other-Metro
counties. `score_site()` still reports the file median as `pool_median` for context.

---

## 7. §XVI Community Designations (10 points, block member)

**Data:** `community_designations.csv`.

```text
XVI = 10  if the site is inside any CNI polygon or any PBC polygon
      0   otherwise
```

- **CNI** is a HUD Choice Neighborhoods grant area: University Homes.
- **PBC** is a Purpose Built Communities neighborhood: East Lake and The Villages at
  East Lake.

The 10 points are shown as earned, but DCA awards them only if the CNI grantee or PBC
member selects the application. The result also reports the distance to the nearest
area of each kind.

---

## 8. §XVIII Previous Projects (5 points)

**Data:** `lihtc_awards.csv`, `municipalities.csv`, and `transit_hubs.csv`.
The round year is Y = 2026 by default; the years below assume it.

### A. Awards in the site's city (up to 5)

Look at awards inside the site's city polygon from the last 15 years (year ≥ Y − 15 =
**2011**). Every award counts here, including `coord_precision = random_in_city`.

| Awards in the city since 2011 | A |
|---|:-:|
| none | 5 |
| exactly one, from before Y − 6 (year ≤ **2019**) | 4 |
| anything else | 0 |

An unincorporated site has no city polygon, so A = 0.

### B. Awards within one mile (up to 3)

1. Take awards within **1 mile straight-line**, excluding
   `coord_precision = random_in_city`, since those have no real location.
2. The lookback window depends on transit. A site is **near a hub** if the nearest
   `transit_hubs.csv` row is within 1 mile straight-line (no ×1.15).

| Site | B = 3 if no award in | else B = 2 if no award in | else |
|---|---|---|:-:|
| not near a hub | the last 6 years (year ≥ **2020**) | the last 4 years (year ≥ **2022**) | 0 |
| near a hub | the last 3 years (year ≥ **2023**) | the last 2 years (year ≥ **2024**) | 0 |

### Section score

```text
XVIII = max(A, B)
```

---

## 9. §XIX Housing Needs Characteristics (10 points, block member)

**Data:** `tracts.csv`, specifically the `chas_*`, `xix_*`, and `in_qct` columns. Only
the seven Other-Metro counties have these values.

If the pool is Atlanta Metro, §XIX is **not applicable**. It returns no score and is left
out of the block entirely.

For an Other-Metro site, using the site's tract:

```text
severe_share = chas_renter_le80_severe_units / chas_renter_le80_units
               (renter households at or below 80% of area median income that have a
                severe housing problem, divided by all such renter households; HUD CHAS)
growing      = county population growth > 1%  OR  county employment growth > 1%
A_ok         = (not in_qct) AND severe_share ≥ 0.45 AND growing       # = xix_qualifies_a

A   = 5 if A_ok else 0
B   = 5 if A_ok AND XV ≥ 5 else 0          # §XIV could substitute for XV; not scored here
XIX = A + B                                  # 0, 5, or 10
```

The employment growth figure in this data vintage is a metro-wide rate (about 3.9%), so
every Other-Metro county passes `growing`. In practice, A comes down to *not a QCT* and
*severe share ≥ 45%*. A tract with no CHAS data scores 0.

---

## 10. §XXII Historic Preservation (2 points)

**Data:** `historic_districts.csv`.

```text
XXII = 2  if the site is inside any National Register of Historic Places boundary
       0  otherwise
```

The points also require historic tax credits and adaptive reuse, which are developer
commitments.

---

## 11. The 10-point block and the total

§XV, §XVI, and §XIX are mutually exclusive; an application gets points from only one.
§XIV (Revitalization) also belongs to this group but is a developer claim, so it isn't
scored here.

```text
candidates = [XV, XVI] + ([XIX] if pool == "other metro")
block      = the highest candidate (ties go to the earlier one in that list; 0 if all are 0)

total = XI + XII + XIII + XVIII + XXII + block
max   = 20 +  6  +  3   +   5   +  2   +  10   = 46
```

The practical ceiling from location alone is 45, because §XII's sixth point needs
transit-agency site ownership. A non-family tenancy caps §XIII at 2, which lowers the
ceiling further.

**Not included.** The 15 other QAP sections (financing, readiness, affordability
commitments, services, and so on) depend on the proposal, not the place. The map
collects them in a questionnaire; they are not part of this total. The QCT flag in the
result is informational: it feeds §XIX here and the federal basis boost elsewhere, but it
is not a score.

---

## 12. Worked example: the Vortex, Little Five Points (33.766384, −84.349133)

**Context:** tract `13121001600`, Fulton County, so the pool is Atlanta Metro. The city
is Atlanta. The tract is not a QCT and not a food desert.

| § | Inputs | Score |
|---|---|:-:|
| XI | 16 of 18 categories score, for ΣP = 33.5. Examples: grocery Sevananda at 0.066 mi straight-line (0.076 route) → 2.5; big-box Target at 0.79 mi → 2; hospital Grady at 2.28 mi → 0; technical college at 5.68 mi → 0. The nearest hazard is 0.72 mi away (beyond 0.25), so there are no deductions. min(20, 33.5) | **20** |
| XII | Hub: Seaboard Ave @ Brantley St, 0.552 mi → 0.635 route → A = 4. Stop: Moreland Ave @ Euclid Ave, 0.036 → 0.041 → B = 3. max(4, 3) | **4** |
| XIII | Springdale Park ES (test A, 6 grades) + Howard MS (test C, 3) + Midtown HS (test A, 4) = 13, family tenancy | **3** |
| XV | 4 of 5 flags: transit 0.720 > 0.600, jobs 0.693 > 0.632, above-poverty 97.0% > 91.2%, income $109,505 > $78,538. Environmental health 0.107 < 0.286 is not flagged. Within = 10. Two tracts within 0.25 mi add nothing (near = 9) | **10** |
| XVI | Outside both areas (nearest: The Villages at East Lake, 2.13 mi) | **0** |
| XVIII | A: 75 awards in Atlanta since 2011 → 0. B: a hub is within 1 mi, so the relaxed window applies, but William Booth Towers (2025) is 0.49 mi away → 0 | **0** |
| XIX | Atlanta Metro pool | **N/A** |
| XXII | Inside the Inman Park–Moreland Historic District (Boundary Increase) | **2** |
| Block | max(XV 10, XVI 0) → §XV | **10** |
| **Total** | 20 + 4 + 3 + 0 + 2 + 10 | **39 / 46** |

To reproduce this, run `python -m siteline 33.766384 -84.349133`, or
`python tests/test_siteline.py`, which checks these numbers.

---

## 13. Where each rule lives in code

The same rules exist in three places, and a change must be made in all three. The
reference Python and the website code live in the [sitelineLIHTC](https://github.com/kmcalist682336/sitelineLIHTC) repo.

| § | This pack | Reference Python ([`scoring/`](https://github.com/kmcalist682336/sitelineLIHTC/tree/main/scoring)) | Website ([`prototype/index.html`](https://github.com/kmcalist682336/sitelineLIHTC/blob/main/prototype/index.html)) |
|---|---|---|---|
| context | [`siteline/base.py`](siteline/base.py) | `scoring/base.py` | `tractOf` |
| shared math | [`siteline/geo.py`](siteline/geo.py) | `scoring/base.py` | `havMi`, `featHas`, `tierPts` |
| XI | [`siteline/activities.py`](siteline/activities.py) | `scoring/activities.py` | `applyXI` |
| XII | [`siteline/transportation.py`](siteline/transportation.py) | `scoring/transportation.py` | `applyXII` |
| XIII | [`siteline/education.py`](siteline/education.py) | `scoring/education.py` | `applyXIII` |
| XV | [`siteline/stable_communities.py`](siteline/stable_communities.py) | `scoring/stable_communities.py` | `applyXV` |
| XVI | [`siteline/community_designations.py`](siteline/community_designations.py) | `scoring/community_designations.py` | `applyXVI` |
| XVIII | [`siteline/previous_projects.py`](siteline/previous_projects.py) | `scoring/previous_projects.py` | `applyXVIII` |
| XIX | [`siteline/housing_needs.py`](siteline/housing_needs.py) | `scoring/housing_needs.py` | `applyXIX` |
| XXII | [`siteline/historic.py`](siteline/historic.py) | `scoring/historic.py` | `applyXXII` |
| block + total | [`siteline/site.py`](siteline/site.py) | `scoring/site.py` | `applyAll` + the engine's block logic |

**How the website's numbers can differ.** The rules are the same, but the map's
implementation differs in a few ways:

- It uses geometry simplified to tens of meters.
- Its §XV "within 0.25 mi" test measures to polygon corners rather than edges, so it can
  miss a nearby tract.
- It always assumes family tenancy.
- It does not stop at the 11-county edge.
- It shows no "verify" flags.

Where the two disagree, this pack's number is the more precise one.
