"""Study area map: single column.

The Swat valley map at single-column width (90 mm). With no room beside the map, eofigs
puts the locator inset and the north arrow with the scale bar in the emptiest parts of the
map, clear of the outline, the towns and their labels; the legend finds no such place, so
it goes below the map with the elevation colour bar. The figure height follows the shape of
the study area, up to 75 % of the journal's maximum height. Outline: former Swat district (before
January 2026), now Swat and Bar Swat (geoBoundaries). Produced using Copernicus
WorldDEM™-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided
under COPERNICUS by the European Union and ESA; all rights reserved. © ESA WorldCover
project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA
WorldCover consortium. Towns: GeoNames (CC BY 4.0). Locator inset: Natural Earth (default
worldview). Boundaries and names shown do not imply any opinion on the legal status of any
country or territory.
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
    width="single",
)

if __name__ == "__main__":
    print(fig.eofigs_layout)  # where the inset, legend and furniture went
    print(eofigs.save_figure(fig, "study_area_single_column"))
