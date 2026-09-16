"""siteline — score metro-Atlanta sites against Georgia's 2024–2025 LIHTC QAP.

The Python twin of the SiteLine website's map scoring, reading the CSVs in data/.
Module docstrings that say "Mirrors scoring/<name>.py" (and mention prototype/index.html)
refer to files in the site repo, https://github.com/kmcalist682336/sitelineLIHTC.

    import siteline
    res = siteline.score_site(33.766384, -84.349133)     # one site, full detail
    print(siteline.report(res))
    df  = siteline.score_sites(points_df)                # many sites → DataFrame
    grid = siteline.score_grid("atlanta", cell_mi=0.25)  # a scored grid

Per-criterion scorers (each `score(lat, lon, ...)` returns a standard result dict):
    activities (§XI), transportation (§XII), education (§XIII),
    stable_communities (§XV), community_designations (§XVI),
    previous_projects (§XVIII), housing_needs (§XIX), historic (§XXII)
"""
from . import (activities, community_designations, data, education, historic, housing_needs,  # noqa: F401
               previous_projects, stable_communities, transportation)
from .base import site_context  # noqa: F401
from .site import (MAX_TOTAL, grid_points, report, score_grid, score_site, score_sites,  # noqa: F401
                   summarize)

__all__ = [
    "score_site", "score_sites", "score_grid", "grid_points", "summarize", "report", "site_context",
    "data", "activities", "transportation", "education", "stable_communities",
    "community_designations", "previous_projects", "housing_needs", "historic", "MAX_TOTAL",
]
