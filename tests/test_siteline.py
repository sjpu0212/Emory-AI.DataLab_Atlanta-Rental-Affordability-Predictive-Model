"""Sanity checks for the siteline package.

    python -m pytest tests          # with pytest
    python tests/test_siteline.py   # without it
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

import siteline  # noqa: E402
from siteline import data  # noqa: E402
from siteline.geo import haversine_mi  # noqa: E402

VORTEX = (33.766384, -84.349133)
# The project's validation site: these must match the website and scoring/ reference.
VORTEX_EXPECTED = {"XI": 20, "XII": 4, "XIII": 3, "XV": 10, "XVI": 0, "XVIII": 0, "XIX": None, "XXII": 2}


def test_vortex_matches_reference():
    res = siteline.score_site(*VORTEX)
    assert res["in_scope"]
    for sec, want in VORTEX_EXPECTED.items():
        assert res["scores"][sec] == want, (sec, res["scores"][sec], want)
    assert res["block"]["winner"] == "XV"
    assert res["total_score"] == 39 and res["max_total_scored"] == 46


def test_tenancy_changes_only_education():
    fam, eld = siteline.score_site(*VORTEX), siteline.score_site(*VORTEX, tenancy="elderly")
    assert eld["scores"]["XIII"] == 2 and eld["total_score"] == fam["total_score"] - 1


def test_outside_region_is_out_of_scope():
    res = siteline.score_site(33.9519, -83.3576)       # Athens, GA
    assert not res["in_scope"] and res["total_score"] is None
    assert siteline.summarize(res)["in_scope"] is False


def test_other_metro_site_scores_housing_needs():
    res = siteline.score_site(33.5215, -84.3538)       # Jonesboro, Clayton County
    assert res["site"]["pool"] == "other metro"
    assert res["sections"]["XIX"]["applicable"]


def test_tables_load():
    for name in data.list_tables():
        assert len(data.table(name)) > 0, name
    assert set(data.table("amenities_desirable")["category_id"]) == set(siteline.activities.CATEGORIES)


def test_nearest_and_within_agree_with_brute_force():
    layer = data.amenity_layer("c")
    lat, lon = 33.70, -84.40
    d = haversine_mi(lat, lon, layer.lat, layer.lon)
    row, mi = layer.nearest(lat, lon)
    assert abs(mi - d.min()) < 1e-9 and row is layer.records[int(np.argmin(d))]
    hits = layer.within(lat, lon, 2.0)
    assert len(hits) == int((d <= 2.0).sum())
    assert hits["distance_mi"].is_monotonic_increasing


def test_grid_scoring():
    grid = siteline.score_grid((33.74, -84.40, 33.76, -84.38), cell_mi=0.5, progress=False)
    assert len(grid) > 0 and grid["total_score"].between(0, 46).all()


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} tests passed")
