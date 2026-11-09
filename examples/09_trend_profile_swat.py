"""Trend map with latitude profile.

(a) Theil–Sen trend of growing-season NDVI (MODIS Terra MOD13A1 v6.1, 500 m, May–September
median), 2001–2024, around the Swat valley (pre-2026 district boundary): the former Swat
district (before January 2026), now Swat and Bar Swat (geoBoundaries). Dots: at least 50 %
of 500 m pixels significant (Mann–Kendall, p < 0.05); the per-pixel tests assume serial
independence and are not adjusted for multiple comparisons. Grey with diagonal hatching: mean
NDVI below 0.1 over the record (not vegetated); grey with cross-hatching: no valid trend
(too few observations). (b) Median and interquartile range of
the full-resolution slope in 0.02° latitude bands, vegetated pixels only, bands with at
least 20 valid pixels; the bands line up with the map's latitudes. Greening is strongest
in the south (lower valley) and weakens towards the high mountains in the north. MODIS
data: NASA LP DAAC, accessed through the Microsoft Planetary Computer. Boundaries and names
shown do not imply any opinion on the legal status of any country or territory.
"""

from pathlib import Path

import pandas as pd
import rioxarray

import eofigs

DATA = Path(__file__).resolve().parents[1] / "docs" / "data" / "swat"


def swat_ndvi():
    """Load the annual growing-season NDVI cube (one band per year) with a time axis."""
    raw = rioxarray.open_rasterio(DATA / "swat_ndvi_growing_season_500m.tif", mask_and_scale=True)
    years = [int(year) for year in raw.attrs["long_name"]]  # band descriptions
    cube = raw.rename(band="time").assign_coords(
        time=pd.to_datetime([f"{year}-07-01" for year in years])
    )
    cube.name = "ndvi"
    cube.attrs = {"long_name": "NDVI", "units": "1"}
    return cube


eofigs.set_style("elsevier")
fig = eofigs.trend_map(
    swat_ndvi(),
    aoi=DATA / "swat_boundary.geojson",
    aoi_label="Swat valley\n(pre-2026 district boundary)",
    latitude_profile=True,
    width="double",
)

if __name__ == "__main__":
    print(fig.eofigs_layout["caption"])
    print(eofigs.save_figure(fig, "trend_profile_swat"))
