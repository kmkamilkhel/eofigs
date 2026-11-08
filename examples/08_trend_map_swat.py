"""Trend map: Swat valley NDVI 2001–2024.

Theil–Sen trend of growing-season NDVI (May–September median of MODIS Terra MOD13A1 v6.1
16-day composites at 500 m, pixel reliability 0–1, at least three good composites per
year), 2001–2024, around the Swat valley (pre-2026 district boundary): the former Swat
district (before January 2026), now Swat and Bar Swat (geoBoundaries). Browning is
terracotta and greening slate teal. Colours are limited to ±0.08 decade⁻¹ (98th
percentile of |slope|); 1.9 % of pixels exceed this. Dots: at least 50 % of 500 m pixels
significant (Mann–Kendall, p < 0.05; no correction for serial autocorrelation). Hatched
grey: mean NDVI below 0.1 over the record (not vegetated) or no valid trend (too few
valid observations). The caption sentences on colour limits, dots and grey come from
`fig.eofigs_layout["caption"]`. MODIS data: NASA LP DAAC, accessed through the Microsoft
Planetary Computer. Boundaries and names shown do not imply any opinion on the legal
status of any country or territory.
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
fig = eofigs.trend_map(swat_ndvi(), aoi=DATA / "swat_boundary.geojson", width="onehalf")

if __name__ == "__main__":
    print(fig.eofigs_layout["caption"])
    print(eofigs.save_figure(fig, "trend_map_swat"))
