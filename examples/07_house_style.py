"""House style.

The same Swat valley map with the package defaults (Elsevier preset) and with an author's
house style set in one call: `set_style(journal="custom", font="Arial", bold=True,
labels="A", max_ticks=5)`, which makes all text bold and sets bold capital panel letters
and a five-tick rule. Outline: former Swat district (before January 2026), now Swat and
Bar Swat (geoBoundaries). Produced using Copernicus WorldDEM™-90 © DLR e.V. 2010-2014 and ©
Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and
ESA; all rights reserved. © ESA WorldCover project 2021 / Contains modified Copernicus
Sentinel data (2021) processed by ESA WorldCover consortium. Towns: GeoNames (CC BY 4.0).
Locator inset: Natural Earth (default worldview). Boundaries and names shown do not imply
any opinion on the legal status of any country or territory.
"""

from pathlib import Path

import eofigs

DATA = Path(__file__).resolve().parents[1] / "docs" / "data" / "swat"


def swat_map():
    """Draw the Swat map in the current style."""
    return eofigs.study_area_map(
        DATA / "swat_boundary.geojson",
        dem=DATA / "swat_dem_90m.tif",
        overlay=DATA / "swat_tree_cover_90m.tif",
        points=DATA / "swat_towns.geojson",
        aoi_label="Swat valley\n(pre-2026 district boundary)",
        overlay_label="Tree cover ≥ 50 %",
        points_label="Town",
        width=140,
    )


with eofigs.style("elsevier"):
    default = swat_map()

with eofigs.style(journal="custom", font="Arial", bold=True, labels="A", max_ticks=5):
    house = swat_map()

figures = {"Package default": default, "House style in one call": house}

if __name__ == "__main__":
    eofigs.save_figure(default, "swat_default")
    eofigs.save_figure(house, "swat_house_style")
