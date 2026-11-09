"""Study area map: Swat valley.

Swat valley (pre-2026 district boundary), Khyber Pakhtunkhwa, Pakistan, as a 1.5-column
(140 mm) study area map with the locator inset and legend beside the map. The outline is
the former Swat district (before January 2026), now Swat and Bar Swat (geoBoundaries,
2019 boundaries). Grey hillshade with light elevation colours (Copernicus DEM GLO-90),
90 m cells where at least half of the 10 m pixels are tree cover (ESA WorldCover 2021,
hillshade showing through), towns (GeoNames), north arrow to true north, scale bar and
graticule. Produced using Copernicus WorldDEM™-90 © DLR e.V. 2010-2014 and © Airbus
Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA;
all rights reserved. © ESA
WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by
ESA WorldCover consortium. Towns: GeoNames (CC BY 4.0). Locator inset: Natural Earth
(default worldview). Boundaries and names shown do not imply any opinion on the legal
status of any country or territory.
"""

from pathlib import Path

import eofigs

DATA = Path(__file__).resolve().parents[1] / "docs" / "data" / "swat"

eofigs.set_style("elsevier")
fig = eofigs.study_area_map(
    DATA / "swat_boundary.geojson",
    dem=DATA / "swat_dem_90m.tif",
    overlay=DATA / "swat_tree_cover_90m.tif",
    points=DATA / "swat_towns.geojson",
    aoi_label="Swat valley\n(pre-2026 district boundary)",
    overlay_label="Tree cover ≥ 50 %",
    points_label="Town",
    width="onehalf",
)


# README card: the upper valley with the towns, the locator inset and the legend
readme_card = [(fig.axes[0], (0.0, 0.45, 1.0, 1.0)), fig.axes[1], *fig.legends]

if __name__ == "__main__":
    print(fig.eofigs_layout)
    print(eofigs.save_figure(fig, "study_area_swat"))
