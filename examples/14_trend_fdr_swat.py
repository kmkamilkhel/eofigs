"""Trend map with false discovery rate control.

Theil–Sen trend of growing-season NDVI (MODIS Terra MOD13A1 v6.1, 500 m, May–September
median), 2001–2024, around the Swat valley (pre-2026 district boundary): the former Swat
district (before January 2026), now Swat and Bar Swat (geoBoundaries); the same data as
the Swat trend map. Dots: at least 50 % of the 500 m pixels in a cell significant. (a) Each
pixel's Mann–Kendall test at p < 0.05, not adjusted for multiple comparisons: 59.3 % of the
43 109 vegetated pixels with a valid trend are significant. (b) Benjamini–Hochberg false
discovery rate control at q = 0.1 (`fdr="bh"`, q = 2 × alpha; Wilks 2016) over the same
43 109 pixels: 61.3 % are significant, equivalent to p ≤ 0.061. Greening is so widespread
that the false discovery rate threshold is less strict here than p < 0.05: the procedure
bounds the expected share of false discoveries among the marked pixels at 10 %, rather than
the share of marked pixels among those without a trend. Where few pixels have a trend, the
same q is far stricter than p < 0.05 (see the trend map page). Per-pixel Mann–Kendall tests
assume serial independence. Grey with diagonal hatching: mean NDVI below 0.1 over the record
(not vegetated); grey with cross-hatching: no valid trend (too few observations). MODIS
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
cube = swat_ndvi()
fig, ax0 = eofigs.new_figure("double", height_mm=180, layout="none")
ax0.remove()
left, right = fig.subfigures(1, 2)
outline = {
    "aoi": DATA / "swat_boundary.geojson",
    "aoi_label": "Swat valley\n(pre-2026 district boundary)",
}
eofigs.trend_map(cube, subfigure=left, **outline)  # each pixel at p < 0.05
eofigs.trend_map(cube, subfigure=right, fdr="bh", **outline)  # FDR at q = 2 x 0.05
eofigs.label_panels([left.axes[0], right.axes[0]])

if __name__ == "__main__":
    for name, panel in (("(a)", left), ("(b)", right)):
        layout = panel.eofigs_layout  # each panel's record is on its subfigure
        print(name, layout["significant_percent"], layout["fdr"])
        print(layout["caption"])
    print(eofigs.save_figure(fig, "trend_fdr_swat"))
