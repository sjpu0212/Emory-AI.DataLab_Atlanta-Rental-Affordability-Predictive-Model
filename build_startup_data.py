"""Export this repo's CSVs (data/) from the SiteLine site repo's pipeline data.

MAINTAINER SCRIPT — students do not need to run this. The CSVs in data/ are committed,
and the `siteline` package reads only those.

It reads the site repo's (https://github.com/kmcalist682336/sitelineLIHTC) git-ignored
pipeline outputs — scoring_data/, data/shapefiles/, data_pipeline/_cache/ — the same
sources as its data_pipeline/build_frontend_bundles.py, and applies the same filters, so
every row the website scores is here. Unlike the site bundles, it keeps the full
attributes (addresses, agencies, school-quality fields) and near-full-resolution polygons.

Run it with the site repo's Python environment (it has geopandas):

    /path/to/sitelineLIHTC/venv/bin/python build_startup_data.py --site-repo /path/to/sitelineLIHTC
    # or set SITELINE_REPO=/path/to/sitelineLIHTC

Polygons are written as WKT (EPSG:4326, lon/lat order) in a `geometry_wkt` column,
rounded to 6 dp and lightly simplified: ~1 m (SIMPLIFY_DEG) for ARC tracts, cities,
counties, and designations; ~2 m for school zones; ~10 m for non-ARC tracts, which only
matter for §XV's 0.25-mi borrowing along the ARC edge.
"""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT: Path   # the sitelineLIHTC checkout (set in main)
SD: Path     # its scoring_data/
OUT = Path(__file__).resolve().parent / "data"
SIMPLIFY_DEG = 0.00001

ATLANTA_METRO = {"067", "089", "121", "135"}
OTHER_METRO = {"057", "063", "097", "113", "117", "151", "247"}
COUNTY_NAME = {
    "057": "Cherokee", "063": "Clayton", "067": "Cobb", "089": "DeKalb", "097": "Douglas",
    "113": "Fayette", "117": "Forsyth", "121": "Fulton", "135": "Gwinnett", "151": "Henry",
    "247": "Rockdale",
}


def pool_of(fips):
    return "atlanta metro" if fips in ATLANTA_METRO else ("other metro" if fips in OTHER_METRO else None)


def wkt(geoms, tol=SIMPLIFY_DEG):
    g = gpd.GeoSeries(geoms, crs=4326).simplify(tol, preserve_topology=True)
    return g.to_wkt(rounding_precision=6).values


def join_cols(df, cols):
    """Join address columns per row, skipping blanks; zips stored as floats lose their '.0'."""
    if not cols:
        return pd.Series([None] * len(df), index=df.index)
    out = []
    for tup in zip(*(df[c].astype(object).values for c in cols)):
        parts = []
        for x in tup:
            if x is None or (isinstance(x, float) and math.isnan(x)):
                continue
            if isinstance(x, float) and x.is_integer():
                x = int(x)
            s = str(x).strip()
            if s:
                parts.append(s)
        out.append(", ".join(parts) or None)
    return pd.Series(out, index=df.index)


def write(name, df):
    path = OUT / name
    df.to_csv(path, index=False)
    print(f"  {name:<32} {len(df):>7,} rows  {path.stat().st_size / 1e6:6.2f} MB")


# ── §XI amenities ────────────────────────────────────────────────────────────
# id, category, QAP group, file, name col, address cols, lat, lon, row filter, subtype col, source
DESIRABLE = [
    ("a", "National big-box store", 1, "a_national_big_box/snap_bigbox_arc.csv", "Store_Name",
     ["Store_Street_Address", "City", "State", "Zip_Code"], "Latitude", "Longitude", None, "Store_Type", "USDA SNAP retailers"),
    ("b", "Retail / department store", 2, "b_retail_department_store/overture_retail_arc.csv", "name",
     [], "lat", "lon", None, "category", "Overture Maps places"),
    ("c", "Supermarket / grocery", 1, "c_supermarket_grocery/snap_grocery_arc.csv", "Store_Name",
     ["Store_Street_Address", "City", "State", "Zip_Code"], "Latitude", "Longitude", None, "Store_Type", "USDA SNAP retailers"),
    ("d", "Restaurant", 2, "d_restaurants/overture_restaurants_arc.csv", "name",
     [], "lat", "lon", None, "category", "Overture Maps places"),
    ("e", "Hospital", 1, "e_hospital/cms_hospitals_arc.csv", "facility_name",
     ["address", "citytown", "state", "zip_code"], "lat", "lon",
     ("hospital_type", {"Acute Care Hospitals", "Childrens"}), "hospital_type", "CMS Hospital General Information"),
    ("f", "Medical provider", 1, "f_medical_provider/npi_medical_arc.csv", "name",
     ["street", "city", "state", "zip"], "lat", "lon", None, "taxonomies", "CMS NPPES (NPI registry)"),
    ("g", "Pharmacy", 1, "g_pharmacy/npi_pharmacies_arc.csv", "name",
     ["street", "city", "state", "zip"], "lat", "lon", None, None, "CMS NPPES (NPI registry)"),
    ("h", "Childcare (DECAL)", 1, "h_childcare/decal_childcare_arc.csv", "name",
     ["address", "city", "state", "zip"], "lat", "lon", None, "program_type", "GA DECAL licensed providers"),
    ("i", "Technical college", 2, "i_technical_college/tcsg_technical_colleges.csv", "name",
     ["address", "city", "zip"], "lat", "lon", None, None, "Technical College System of GA"),
    ("j", "Elementary/middle/high school", 1, "j_school/schools_arc.csv", "name",
     ["street", "city", "zipcode"], "lat", "lon", None, "schoolType", "GreatSchools school directory"),
    ("l", "Community / rec center", 1, "l_community_rec_center/overture_community_rec_arc.csv", "name",
     [], "lat", "lon", None, "category", "Overture Maps places"),
    ("m", "Public park >= 25,000 sq ft", 1, "mn_public_park/parkserve_parks_arc.csv", "park_name",
     [], "lat", "lon", ("mn_class", {"m"}), "park_designation", "Trust for Public Land ParkServe"),
    ("n", "Public park < 25,000 sq ft", 2, "mn_public_park/parkserve_parks_arc.csv", "park_name",
     [], "lat", "lon", ("mn_class", {"n"}), "park_designation", "Trust for Public Land ParkServe"),
    ("o", "Public library", 1, "o_public_library/imls_libraries_arc.csv", "LIBNAME",
     ["ADDRESS", "CITY", "ZIP"], "lat", "lon", None, "C_OUT_TY", "IMLS Public Libraries Survey"),
    ("p", "Fire / police station", 2, "p_fire_police_station/overture_fire_police_arc.csv", "name",
     [], "lat", "lon", None, "category", "Overture Maps places"),
    ("q", "Bank", 2, "q_bank/fdic_bank_branches_arc.csv", "NAME",
     ["ADDRESS", "CITY", "ZIP"], "LATITUDE", "LONGITUDE", None, "SERVTYPE_DESC", "FDIC BankFind"),
    ("r", "Place of worship", 2, "r_place_of_worship/overture_worship_arc.csv", "name",
     [], "lat", "lon", None, "category", "Overture Maps places"),
    ("s", "Post office", 2, "s_post_office/overture_post_office_arc.csv", "name",
     [], "lat", "lon", None, "category", "Overture Maps places"),
]
UNDESIRABLE = [
    ("a", "Nuisance use", "a_nuisance_uses/overture_nuisance_arc.csv", "category", "Overture Maps places"),
    ("b", "Environmental hazard", "b_environmental_hazards/epa_gaepd_hazards_arc.csv", "hazard_type", "EPA / GA EPD"),
]


def _amenity_frame(path, name_col, addr_cols, lat_col, lon_col, filt, sub_col):
    df = pd.read_csv(path, low_memory=False)
    if filt:
        col, keep = filt
        df = df[df[col].isin(keep)]
    out = pd.DataFrame({
        "name": df[name_col].astype(str),
        "address": join_cols(df, addr_cols),
        "subtype": df[sub_col].astype(object) if sub_col else None,
        "lat": pd.to_numeric(df[lat_col], errors="coerce"),
        "lon": pd.to_numeric(df[lon_col], errors="coerce"),
    })
    return out.dropna(subset=["lat", "lon"])


def build_amenities():
    base = SD / "11_desirable_undesirable_activities"
    frames = []
    for cid, cat, grp, rel, nc, addr, la, lo, filt, sub, src in DESIRABLE:
        f = _amenity_frame(base / "desirable" / rel, nc, addr, la, lo, filt, sub)
        f.insert(0, "qap_group", grp)
        f.insert(0, "category", cat)
        f.insert(0, "category_id", cid)
        f["source"] = src
        frames.append(f)
    write("amenities_desirable.csv", pd.concat(frames, ignore_index=True))

    frames = []
    for cid, cat, rel, sub, src in UNDESIRABLE:
        f = _amenity_frame(base / "undesirable" / rel, "name", [], "lat", "lon", None, sub)
        f.insert(0, "category", cat)
        f.insert(0, "category_id", cid)
        f["source"] = src
        frames.append(f)
    write("amenities_undesirable.csv", pd.concat(frames, ignore_index=True).drop(columns="address"))


# ── §XII transit ─────────────────────────────────────────────────────────────
def build_transit():
    for name in ("transit_hubs", "transit_stops"):
        df = pd.read_csv(SD / "12_community_transportation_options" / name / f"{name}_arc.csv", low_memory=False)
        df = df[pd.to_numeric(df["days_per_week"], errors="coerce") >= 5]          # QAP: ≥5 days/week
        df = df.dropna(subset=["lat", "lon"]).rename(columns={"arc_county": "county"})
        cols = ["agency", "stop_id", "stop_name", "route_count", "has_rail", "days_per_week", "lat", "lon", "county"]
        write(f"{name}.csv", df[cols])


# ── §XVIII awards + boundaries ───────────────────────────────────────────────
def build_awards_and_boundaries():
    aw = pd.read_csv(SD / "18_previous_projects" / "previous_projects_awards_arc.csv")
    yr = pd.to_numeric(aw["year"], errors="coerce")
    aw = aw[(yr >= 1980) & (yr <= 2035)].dropna(subset=["lat", "lon"]).copy()
    aw["year"] = aw["year"].astype(int)
    cols = ["name", "year", "credit_type", "units", "city", "county", "lat", "lon",
            "coord_precision", "coord_note", "source", "number", "dca_score"]
    write("lihtc_awards.csv", aw[cols].sort_values(["year", "name"]))

    mb = SD / "18_previous_projects" / "municipal_boundaries"
    pl = gpd.read_file(mb / "places_arc.geojson").to_crs(4326)
    pl = pl[pl.geometry.notna() & ~pl.geometry.is_empty]
    write("municipalities.csv", pd.DataFrame({
        "geoid": pl["GEOID"], "name": pl["NAME"], "name_full": pl["NAMELSAD"], "class_fp": pl["CLASSFP"],
        "geometry_wkt": wkt(pl.geometry)}))

    co = gpd.read_file(mb / "counties_arc.geojson").to_crs(4326).sort_values("COUNTYFP")
    write("counties.csv", pd.DataFrame({
        "geoid": co["GEOID"], "county_fips": co["COUNTYFP"], "name": co["NAME"],
        "pool": co["COUNTYFP"].map(pool_of), "geometry_wkt": wkt(co.geometry)}))


def _ga_county_names():
    """County FIPS → name for all of Georgia (TIGER cache from the pipeline; ARC-only fallback)."""
    shp = ROOT / "data_pipeline" / "_cache" / "tiger_county" / "tl_2024_us_county.shp"
    if not shp.exists():
        return COUNTY_NAME
    c = gpd.read_file(shp, ignore_geometry=True)
    return dict(c.loc[c["STATEFP"] == "13", ["COUNTYFP", "NAME"]].values)


# ── §XV / §XIX / QCT / food desert → tracts ──────────────────────────────────
INDICATORS = {  # source column → CSV column
    "Environmental Health Index": "env_health_index",
    "Transit Access Index": "transit_access_index",
    "Jobs Proximity Index": "jobs_proximity_index",
    "Percent of Population Above the Poverty Level": "pct_above_poverty",
    "Median Income": "median_income",
}


def build_tracts():
    sc = pd.read_csv(SD / "15_stable_communities" / "stable_communities_indicators.csv")
    sc["GEOID"] = sc["GEOID"].astype(str).str.zfill(11)
    for c in INDICATORS:
        sc[c] = pd.to_numeric(sc[c], errors="coerce")

    # pool medians are statewide-within-pool (the "other metro" pool extends beyond the ARC)
    med = sc.groupby("pool")[list(INDICATORS)].agg(lambda s: float(np.nanmedian(s)))
    write("tract_pool_medians.csv", med.rename(columns=INDICATORS).reset_index())

    qct = set(pd.read_csv(SD / "00_cross_cutting_qct_dda" / "qct" / "qct_tracts_arc.csv", dtype=str)["GEOID"].str.zfill(11))
    fd = pd.read_csv(SD / "11_desirable_undesirable_activities" / "undesirable" / "f_food_desert" / "usda_food_access_arc.csv",
                     usecols=["CensusTract", "LILATracts_1And20"])
    fd["GEOID"] = fd["CensusTract"].astype("Int64").astype(str).str.zfill(11)
    food_desert = set(fd.loc[fd["LILATracts_1And20"] == 1, "GEOID"])
    xix = gpd.read_parquet(SD / "19_housing_needs_characteristics" / "housing_needs_A_eligibility_arc.parquet")
    xix = pd.DataFrame(xix.drop(columns="geometry"))
    xix["GEOID"] = xix["GEOID"].astype(str).str.zfill(11)
    xix = xix.set_index("GEOID")
    chas = pd.DataFrame(gpd.read_parquet(SD / "19_housing_needs_characteristics" / "chas" / "chas_renter_severe_arc.parquet")
                        .drop(columns="geometry"))
    chas["GEOID"] = chas["GEOID"].astype(str).str.zfill(11)
    chas = chas.set_index("GEOID")
    # same definition as data_pipeline/build_housing_needs.py: renter units ≤80% AMI (all / with a severe problem)
    chas["renter_le80_units"] = chas[["T8_EST69", "T8_EST82", "T8_EST95"]].sum(axis=1)
    chas["renter_le80_severe_units"] = chas[["T2_EST128", "T2_EST136", "T2_EST144"]].sum(axis=1)

    # All Georgia tracts: §XV lets a site borrow indicators from any tract within 0.25 mi,
    # including tracts just across the ARC line. Flags sourced only for the ARC are left blank
    # (unknown) outside it.
    tr = gpd.read_file(ROOT / "data" / "shapefiles" / "tl_2024_13_tract" / "tl_2024_13_tract.shp").to_crs(4326)
    tr = tr.sort_values("GEOID").merge(sc, on="GEOID", how="left", validate="1:1")
    in_arc = tr["COUNTYFP"].isin(ATLANTA_METRO | OTHER_METRO)
    assert (tr.loc[in_arc, "pool"] == tr.loc[in_arc, "COUNTYFP"].map(pool_of)).all()

    out = pd.DataFrame({
        "geoid": tr["GEOID"],
        "county_fips": tr["COUNTYFP"],
        "county": tr["COUNTYFP"].map(_ga_county_names()),
        "in_arc": in_arc,
        "pool": tr["pool"],
        "tract_name": tr["NAMELSAD"],
        "land_area_sqmi": (tr["ALAND"] / 2_589_988.11).round(4),
        "water_area_sqmi": (tr["AWATER"] / 2_589_988.11).round(4),
        "internal_lat": pd.to_numeric(tr["INTPTLAT"]),
        "internal_lon": pd.to_numeric(tr["INTPTLON"]),
    })
    for src, col in INDICATORS.items():
        out[col] = tr[src]          # full precision, so the flags reproduce exactly at the median
    for src, col in INDICATORS.items():
        out[f"above_median_{col}"] = tr[f"above_median_{src}"].fillna(0).astype(bool)
    out["n_above_median"] = out[[f"above_median_{c}" for c in INDICATORS.values()]].sum(axis=1)
    out["in_qct"] = tr["GEOID"].isin(qct).where(in_arc)
    out["usda_food_desert"] = tr["GEOID"].isin(food_desert).where(in_arc)
    x = xix.reindex(tr["GEOID"])
    c = chas.reindex(tr["GEOID"])
    out["chas_renter_le80_units"] = c["renter_le80_units"].values
    out["chas_renter_le80_severe_units"] = c["renter_le80_severe_units"].values
    out["xix_severe_housing_pct"] = x["severe_pct"].round(4).values
    out["xix_severe_ge_45"] = x["severe_ge_45"].values
    out["xix_pop_growth"] = x["pop_growth"].values
    out["xix_emp_growth"] = x["emp_growth"].values
    out["xix_county_growth"] = x["county_growth"].values
    out["xix_qualifies_a"] = x["qualifies_A"].values
    geom = pd.Series(wkt(tr.geometry), index=tr.index)
    geom[~in_arc] = wkt(tr.geometry[~in_arc], tol=10 * SIMPLIFY_DEG)
    out["geometry_wkt"] = geom
    write("tracts.csv", out)


# ── §XIII school attendance zones ────────────────────────────────────────────
def build_zones():
    base = SD / "13_quality_education_areas" / "attendance_zones"
    sch = pd.read_parquet(base / "schools.parquet").drop_duplicates("gs_id").set_index("gs_id")
    z = gpd.read_parquet(base / "school_boundaries_scored.parquet").to_crs(4326)
    z = z[z["gs_id"].map(sch["school_type"]) == "public"]          # public zones only — never charters
    z = z[z.geometry.notna() & ~z.geometry.is_empty]
    s = sch.reindex(z["gs_id"])
    addr = join_cols(s.reset_index(), ["street1", "city", "zip"]).values
    out = pd.DataFrame({
        "zone_id": z["gs_id"].values,
        "level_band": z["level_band"].values,
        "school_name": z["name"].values,
        "district": z["district_name"].values,
        "grades_in_band": z["grades_in_band"].astype(int).values,
        "qualifies": z["qualifies"].astype(bool).values,
        "qualifying_grades": z["qualifying_grades"].astype(int).values,
        "qualifies_via": z["method"].values,
        "cond_a_above_avg_ccrpi": z["qA"].astype(bool).values,
        "cond_b_beating_odds": z["qB"].astype(bool).values,
        "cond_c_positive_trend": z["qC"].astype(bool).values,
        "ccrpi_avg": z["ccrpi_avg"].values,
        "beating_the_odds": z["bto"].values,
        "new_school": z["new_school"].astype(bool).values,
        "rating_source": z["match_source"].values,
        "rating_note": z["substitute_note"].values,
        "school_address": addr,
        "school_lat": s["lat"].values,
        "school_lon": s["lon"].values,
        "geometry_wkt": wkt(z.geometry, tol=2 * SIMPLIFY_DEG),
    })
    write("school_zones.csv", out)


# ── §XVI designations + §XXII historic districts ─────────────────────────────
def build_designations_and_historic():
    d = SD / "16_community_designations"
    cni = gpd.read_parquet(d / "choice_neighborhoods_cni" / "cni_grant_areas_arc.parquet").to_crs(4326)
    pbc = gpd.read_parquet(d / "purpose_built_communities" / "pbc_neighborhoods_arc.parquet").to_crs(4326)
    rows = [pd.DataFrame({
        "kind": "CNI",
        "name": cni["E_PHA_DEV"].astype(str) + " (Choice Neighborhoods)",
        "detail": (cni["LEAD_APP"].astype(str) + " - " + cni["GRANT_TYPE"].astype(str)
                   + " grant " + cni["GRANT_YEAR"].astype(str)),
        "geometry_wkt": wkt(cni.geometry)}),
        pd.DataFrame({
        "kind": "PBC",
        "name": pbc["NAME"].astype(str),
        "detail": "Purpose Built Communities member: " + pbc["pbc_member"].astype(str),
        "geometry_wkt": wkt(pbc.geometry)})]
    write("community_designations.csv", pd.concat(rows, ignore_index=True))

    nr = gpd.read_parquet(SD / "22_historic_preservation" / "national_register" / "nr_boundaries_arc.parquet").to_crs(4326)
    nr = nr[nr.geometry.notna() & ~nr.geometry.is_empty]
    write("historic_districts.csv", pd.DataFrame({
        "name": nr["RESNAME"].values, "boundary_type": nr["BND_TYPE"].values,
        "contributing_resources": nr["CONTRIBRES"].values, "geometry_wkt": wkt(nr.geometry)}))


def main():
    global ROOT, SD
    ap = argparse.ArgumentParser(description="Rebuild data/ from a sitelineLIHTC checkout.")
    ap.add_argument("--site-repo", default=os.environ.get("SITELINE_REPO"),
                    help="path to the sitelineLIHTC repo with its pipeline data built (or set SITELINE_REPO)")
    args = ap.parse_args()
    if not args.site_repo:
        ap.error("pass --site-repo PATH (or set SITELINE_REPO) pointing at your sitelineLIHTC checkout")
    ROOT = Path(args.site_repo).expanduser().resolve()
    SD = ROOT / "scoring_data"
    if not SD.is_dir():
        ap.error(f"{SD} not found — run the site repo's data pipeline (data_pipeline/run_all.py) first")

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Reading {ROOT}\nWriting CSVs → {OUT}")
    build_amenities()
    build_transit()
    build_awards_and_boundaries()
    build_tracts()
    build_zones()
    build_designations_and_historic()
    print("Done.")


if __name__ == "__main__":
    main()
