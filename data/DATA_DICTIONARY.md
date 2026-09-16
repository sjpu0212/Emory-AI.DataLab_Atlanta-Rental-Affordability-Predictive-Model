# Data dictionary: `data/`

These twelve CSVs hold all the data behind SiteLine's location scoring. The `siteline`
package reads nothing else, and each file holds exactly the rows the website scores.
The same filters are applied as on the site (e.g. only acute-care and children's
hospitals, only transit stops served ≥ 5 days a week, only public school zones).

**Conventions**

- **Region:** the Atlanta Regional Commission (ARC) 11-county area: Cherokee, Clayton,
  Cobb, DeKalb, Douglas, Fayette, Forsyth, Fulton, Gwinnett, Henry, and Rockdale.
  `tracts.csv` covers all of Georgia (see below).
- **Coordinates:** WGS84 (EPSG:4326) decimal degrees. Point tables have `lat` and `lon`
  columns.
- **Polygons:** a `geometry_wkt` column holds
  [WKT](https://en.wikipedia.org/wiki/Well-known_text_representation_of_geometry) in
  **lon/lat order**. Geometry is lightly simplified (about 1 m; about 2 m for school
  zones; about 10 m for tracts outside the ARC). Load it with
  `siteline.data.geodataframe("tracts")`, `shapely.from_wkt(...)`, or
  `sf::st_as_sf(df, wkt = "geometry_wkt", crs = 4326)` in R.
- **Codes are text.** Read `geoid`, `county_fips`, and `stop_id` as strings so leading
  zeros survive. `siteline.data.table()` does this for you.
- **Booleans** are written `True` / `False`. A blank cell means unknown or not applicable.
- **Vintages:** most sources were pulled 2026-07-11 to 2026-07-13. Per-source provenance
  is in the site repo's [`data_pipeline/README.md`](https://github.com/kmcalist682336/sitelineLIHTC/blob/main/data_pipeline/README.md).

| File | Rows | What it is | Used by |
|---|---:|---|---|
| `amenities_desirable.csv` | 41,846 | 18 categories of nearby amenities | §XI.A |
| `amenities_undesirable.csv` | 638 | Nuisance uses and environmental hazards | §XI.B |
| `transit_hubs.csv` | 428 | Transit hubs (rail stations or stops with 3+ routes) | §XII.A, §XVIII.B |
| `transit_stops.csv` | 8,660 | All transit stops | §XII.B |
| `school_zones.csv` | 904 | Public-school attendance zones, with QAP quality tests | §XIII |
| `tracts.csv` | 2,796 | Georgia census tracts: §XV indicators, QCT, food desert, CHAS / §XIX | §XV, §XIX, §XI food desert |
| `tract_pool_medians.csv` | 3 | Median of each §XV indicator, per DCA pool | §XV |
| `community_designations.csv` | 4 | Choice Neighborhoods and Purpose Built Communities areas | §XVI |
| `lihtc_awards.csv` | 603 | Past LIHTC awards (HUD database plus DCA award lists) | §XVIII |
| `municipalities.csv` | 101 | Census places, used as local government boundaries | §XVIII.A, site context |
| `counties.csv` | 11 | ARC counties and their DCA pool | region masks |
| `historic_districts.csv` | 125 | National Register of Historic Places boundaries | §XXII |

---

## `amenities_desirable.csv`: §XI.A desirable activities

One row per amenity. A site earns points per category based on the distance to that
category's **nearest** row. Distances are straight-line miles × 1.15, an estimate of the
route distance.

| Column | Meaning |
|---|---|
| `category_id` | QAP item letter: `a`–`s` (there is no `k`) |
| `category` | Category name |
| `qap_group` | 1 = 2.5 / 2 / 1.5 pts, 2 = 2 / 1.5 / 1 pts, within 0.5 / 1.0 / 1.5 mi |
| `name` | Place name |
| `address` | Street address where the source has one (blank for Overture and ParkServe rows) |
| `subtype` | Source-specific type: SNAP store type, Overture category, hospital type, NPI taxonomies, DECAL program type, park designation, library outlet type, bank service type |
| `lat`, `lon` | Location |
| `source` | Dataset |

| id | Category | Group | Source (vintage) | Rows |
|---|---|:-:|---|---:|
| a | National big-box store | 1 | USDA SNAP authorized retailers (live, pulled Jul 2026) | 117 |
| b | Retail / department store | 2 | Overture Maps places 2026-06-17 | 817 |
| c | Supermarket / grocery (a big-box store also counts) | 1 | USDA SNAP authorized retailers | 866 |
| d | Restaurant | 2 | Overture Maps places | 16,912 |
| e | Hospital (acute care and children's only) | 1 | CMS Hospital General Information | 17 |
| f | Medical provider (family and internal medicine, pediatrics, dentists, clinics) | 1 | CMS NPPES / NPI registry | 6,739 |
| g | Pharmacy | 1 | CMS NPPES / NPI registry | 1,370 |
| h | Licensed childcare | 1 | GA DECAL provider export (manual, Jul 2026) | 1,839 |
| i | Technical college | 2 | NCES postsecondary locations (TCSG subset) | 22 |
| j | Elementary, middle, or high school | 1 | GreatSchools directory (scraped Jul 2026) | 1,468 |
| l | Community / recreation center | 1 | Overture Maps places | 582 |
| m | Public park ≥ 25,000 sq ft | 1 | Trust for Public Land ParkServe | 1,163 |
| n | Public park < 25,000 sq ft | 2 | Trust for Public Land ParkServe | 409 |
| o | Public library | 1 | IMLS Public Libraries Survey | 119 |
| p | Fire / police station | 2 | Overture Maps places | 448 |
| q | Bank branch | 2 | FDIC BankFind | 907 |
| r | Place of worship | 2 | Overture Maps places | 7,511 |
| s | Post office | 2 | Overture Maps places | 540 |

## `amenities_undesirable.csv`: §XI.B undesirable activities

Each row within **0.25 mi** (straight line) of a site deducts 2 points.

| Column | Meaning |
|---|---|
| `category_id` | `a` = nuisance use (61 rows, Overture: junkyards, scrap metal, quarries); `b` = environmental hazard (577 rows: EPA Toxics Release Inventory facilities and GA EPD Hazardous Site Inventory) |
| `category`, `name`, `lat`, `lon`, `source` | As above |
| `subtype` | Overture category or hazard type (e.g. `TRI toxic-release facility`, `GA HSI hazardous site (class II)`) |

The third §XI.B deduction, the USDA food desert, is a tract flag
(`tracts.csv: usda_food_desert`). It applies only when grocery (c) earns no points.

## `transit_hubs.csv` and `transit_stops.csv`: §XII

Built from agency GTFS feeds (MARTA, CobbLinc, Ride Gwinnett, Cherokee CATS, Atlanta
Streetcar, Xpress) via the Mobility Database, July 2026. Both files are limited to stops
served **≥ 5 days a week**. A hub is also a stop.

| Column | Meaning |
|---|---|
| `agency` | Transit agency |
| `stop_id`, `stop_name` | GTFS stop identifiers |
| `route_count` | Distinct routes serving the stop |
| `has_rail` | MARTA rail serves the stop (streetcar stops are not flagged) |
| `days_per_week` | Days with scheduled service |
| `lat`, `lon`, `county` | Location and ARC county |

## `school_zones.csv`: §XIII quality education

This file holds GreatSchools attendance-zone polygons for **traditional public schools
only**. Charter-school "zones" are excluded because they are lottery or district-wide
areas. School quality comes from the GA DOE CCRPI and GOSA *Beating the Odds* files
that DCA publishes for the QAP.

| Column | Meaning |
|---|---|
| `zone_id` | GreatSchools school id |
| `level_band` | `elementary` / `middle` / `high` |
| `school_name`, `district` | Zoned school and its district |
| `grades_in_band` | K-12 grades this zone contributes |
| `qualifies` | Meets at least one QAP test (A, B, or C) |
| `qualifying_grades` | Grades counted toward §XIII when `qualifies` |
| `qualifies_via` | First test met: `A`, `B`, `C`, or blank |
| `cond_a_above_avg_ccrpi` | Test A: above-average CCRPI |
| `cond_b_beating_odds` | Test B: "Beating the Odds" |
| `cond_c_positive_trend` | Test C: positive CCRPI trend and in the top 75% |
| `ccrpi_avg` | Average CCRPI score used |
| `beating_the_odds` | GOSA label: `Beating the Odds` / `Within Expected Range` / `Below Expected Range` |
| `new_school` | School too new to be rated; a substitute rating was used |
| `rating_source` | `direct`, `district-substitute`, or `cross-cluster` |
| `rating_note` | Explanation when a substitute rating was used |
| `school_address`, `school_lat`, `school_lon` | School building location |
| `geometry_wkt` | Zone polygon |

**Known quirk:** some districts split elementary grades across two schools with
overlapping zones, e.g. Decatur (Clairemont K–2 and Talley Street 3–5) and Acworth
(McCall Primary and Acworth Intermediate). Both zones are recorded with
`grades_in_band = 6`, and the scorer counts only the first zone per band in file order,
as the website does. Scores at these sites deserve a manual check.

## `tracts.csv`: census tracts (all of Georgia)

This table is **all 2,796 Georgia tracts** (2020 tract definitions, TIGER 2024
geometry). §XV lets a site borrow indicators from any tract within 0.25 mi, including
tracts just outside the region. Use `in_arc` to restrict to the 11 counties (1,248
tracts). Flags sourced only for the ARC (`in_qct`, `usda_food_desert`, `chas_*`,
`xix_*`) are blank outside it.

| Column | Meaning |
|---|---|
| `geoid` | 11-digit tract GEOID (state + county + tract), **the join key** for any tract-level data |
| `county_fips`, `county` | 3-digit county code and county name |
| `in_arc` | Tract is in the 11-county region |
| `pool` | DCA geographic pool: `atlanta metro` (Cobb, DeKalb, Fulton, Gwinnett) or `other metro` (the other 7 counties). The source's `rural` label appears only on 117 tracts outside the region. See [SCORING.md](../SCORING.md#2-site-context-and-pools) for the all-metro policy |
| `tract_name` | e.g. "Census Tract 16" |
| `land_area_sqmi`, `water_area_sqmi` | TIGER land and water area (for density calculations) |
| `internal_lat`, `internal_lon` | TIGER internal point (a representative point inside the tract) |
| `env_health_index` | §XV: Environmental Health Index (HUD AFFH / GA Housing Needs Assessment) |
| `transit_access_index` | §XV: Transit Access Index (same source) |
| `jobs_proximity_index` | §XV: Jobs Proximity Index (same source) |
| `pct_above_poverty` | §XV: % of population above the poverty level (Census ACS) |
| `median_income` | §XV: median household income, $ (Census ACS) |
| `above_median_<indicator>` | QAP "above the pool's 50th percentile" flag. It comes precomputed in the source data and the score uses it as given. It equals "value > pool median" for Atlanta-Metro tracts but not for Other-Metro tracts; see [SCORING.md §XV](../SCORING.md#6-xv-stable-communities-10-points-block-member) |
| `n_above_median` | Count of the five flags. 2 / 3 / 4+ earn 6 / 8 / 10 §XV points |
| `in_qct` | HUD 2025 Qualified Census Tract (ARC only) |
| `usda_food_desert` | USDA Food Access Research Atlas 2019 low-income / low-access (1 mi urban, 20 mi rural) tract (ARC only) |
| `chas_renter_le80_units` | HUD CHAS: renter units with household income ≤ 80% of AMI (7 Other-Metro counties only) |
| `chas_renter_le80_severe_units` | HUD CHAS: those units with a severe housing problem (same coverage) |
| `xix_severe_housing_pct` | Ratio of the two CHAS columns (0–1). §XIX.A needs ≥ 0.45 |
| `xix_severe_ge_45` | `xix_severe_housing_pct >= 0.45` |
| `xix_pop_growth`, `xix_emp_growth` | County growth rates (see note below) |
| `xix_county_growth` | County growth > 1% (population or employment) |
| `xix_qualifies_a` | Meets §XIX.A: not a QCT, severe share ≥ 45%, and county growing |
| `geometry_wkt` | Tract polygon |

§XIX applies only to the Other-Metro pool, so the CHAS and `xix_*` columns cover only
Cherokee, Clayton, Douglas, Fayette, Forsyth, Henry, and Rockdale. Population growth is
the 2018–2021 ACS average. Employment growth is a single metro-wide figure, so every
county passes the growth test in this vintage. Henry's population growth is blank.
Pulling CHAS for the other four counties is a natural first extension; see the site
repo's [`data_pipeline/pull_chas.py`](https://github.com/kmcalist682336/sitelineLIHTC/blob/main/data_pipeline/pull_chas.py).

## `tract_pool_medians.csv`

The median of each §XV indicator within each DCA pool, taken over all Georgia tracts that
the source labels with that pool. Columns are `pool` plus the five indicator columns.
For the Atlanta-Metro pool these medians reproduce the `above_median_*` flags; for
Other Metro they do not (see [SCORING.md §XV](../SCORING.md#6-xv-stable-communities-10-points-block-member)).
The scorer shows these values for reference only and scores from the flags.

## `community_designations.csv`: §XVI

| Column | Meaning |
|---|---|
| `kind` | `CNI` = HUD Choice Neighborhoods grant area; `PBC` = Purpose Built Communities neighborhood |
| `name` | Area name (University Homes; East Lake; The Villages at East Lake) |
| `detail` | Grantee and grant, or PBC member |
| `geometry_wkt` | Area polygon |

## `lihtc_awards.csv`: §XVIII previous projects

HUD's National LIHTC Database (through 2019), merged with Georgia DCA award lists
(2020 and later). Years run from 1988 to 2025.

| Column | Meaning |
|---|---|
| `name`, `year` | Project name and allocation year |
| `credit_type` | `9%`, `4%`, `4%+9%`, `other`, or blank |
| `units` | Unit count, where known |
| `city`, `county` | As published |
| `lat`, `lon` | Location. How good it is depends on `coord_precision` |
| `coord_precision` | `hud` (HUD geocode), `exact_file` (DCA file), `osm_search` (geocoded by name), or `random_in_city` (**a random point inside the named city**, used because DCA published no location) |
| `coord_note` | Geocoding note |
| `source` | `HUD` or `DCA` |
| `number`, `dca_score` | DCA application number and score (DCA rows) |

§XVIII.A counts every award inside the site's city. §XVIII.B (within 1 mile) **excludes**
`random_in_city` rows, since their location is not real.

## `municipalities.csv`

Census TIGER 2024 places in the region.

| Column | Meaning |
|---|---|
| `geoid`, `name`, `name_full` | Place identifiers |
| `class_fp` | `C1` = incorporated city (78 rows); `U1` / `U2` = **census-designated place**, which is unincorporated (23 rows, e.g. North Druid Hills, Redan, Vinings) |
| `geometry_wkt` | Boundary |

§XVIII.A treats the place containing a site as its Local Government Boundary. To match
the reference scorer, this includes census-designated places. A site outside every place
is "unincorporated" and scores 0 on §XVIII.A.

## `counties.csv`

The 11 ARC counties: `geoid`, `county_fips`, `name`, `pool`, and `geometry_wkt`.

## `historic_districts.csv`: §XXII

National Register of Historic Places boundary polygons (NPS).

| Column | Meaning |
|---|---|
| `name` | Listed district or resource |
| `boundary_type` | NPS boundary type |
| `contributing_resources` | NPS count (often "Unknown") |
| `geometry_wkt` | Boundary |

---

**Rebuilding.** These files are exported from the full pipeline data in the
[sitelineLIHTC](https://github.com/kmcalist682336/sitelineLIHTC) repo (`scoring_data/`, which git ignores there) by this repo's
`build_startup_data.py`. Maintainers run it after refreshing the pipeline; students
don't need to.
