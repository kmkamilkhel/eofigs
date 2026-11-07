"""Build the example figure shown on the "Large rasters" page.

Run from the repository root:  python docs/scripts/raster_example.py
"""

from pathlib import Path

import numpy as np
import rioxarray  # noqa: F401
import xarray as xr

import eofigs

OUT = Path(__file__).resolve().parents[1] / "assets"

# A synthetic 6000 x 6000 terrain model (36 million pixels) in UTM zone 43N.
n = 6000
y, x = np.mgrid[0:n, 0:n] / n
dem = 1200 + 2600 * np.exp(-((x - 0.62) ** 2 + (y - 0.35) ** 2) / 0.05) + 400 * np.sin(9 * x) * y
dem = xr.DataArray(
    dem.astype("float32"),
    dims=("y", "x"),
    coords={"y": 3_900_000 - (np.arange(n) + 0.5) * 10, "x": 750_000 + (np.arange(n) + 0.5) * 10},
    name="elevation",
).rio.write_crs("EPSG:32643")

elevation = eofigs.variable("elevation")

with eofigs.style("elsevier", font="serif"):
    fig, ax = eofigs.new_figure("single", height_mm=75)
    small = eofigs.fit_raster(dem, width_mm=90, height_mm=75, dpi=600)
    image = small.plot.imshow(ax=ax, cmap=elevation.cmap, add_colorbar=False)
    fig.colorbar(image, ax=ax, label=elevation.label, shrink=0.85)
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.set_title("")
    ax.ticklabel_format(style="plain")
    ax.tick_params(axis="x", labelrotation=30)
    print(dem.shape, "->", small.shape, small.attrs["eofigs_reduction"])
    eofigs.save_figure(fig, OUT / "raster_example.png", dpi=200, check=False)
    print(eofigs.check_figure(fig))
