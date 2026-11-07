"""Large raster at print size.

A synthetic 6000 × 6000 terrain model (36 million pixels, 10 m cells in UTM zone 43N)
reduced by `fit_raster` to the 2000 × 2000 pixels a 90 mm map needs at 600 dpi, drawn
with the library's elevation colours (`batlow`). Synthetic data.
"""

import numpy as np
import rioxarray  # noqa: F401  (adds the .rio accessor)
import xarray as xr

import eofigs

n = 6000
y = (np.arange(n, dtype="float32") / n)[:, None]
x = (np.arange(n, dtype="float32") / n)[None, :]
dem = 1200 + 2600 * np.exp(-((x - 0.62) ** 2 + (y - 0.35) ** 2) / 0.05) + 400 * np.sin(9 * x) * y
dem = xr.DataArray(
    dem.astype("float32"),
    dims=("y", "x"),
    coords={"y": 3_900_000 - (np.arange(n) + 0.5) * 10, "x": 750_000 + (np.arange(n) + 0.5) * 10},
    name="elevation",
).rio.write_crs("EPSG:32643")

elevation = eofigs.variable("elevation")

eofigs.set_style("elsevier")
fig, ax = eofigs.new_figure("single", height_mm=75)
small = eofigs.fit_raster(dem, width_mm=90, height_mm=75, dpi=600)  # 6000 x 6000 -> 2000 x 2000
image = small.plot.imshow(ax=ax, cmap=elevation.cmap, add_colorbar=False)
bar = fig.colorbar(image, ax=ax, label=elevation.label, shrink=0.85)
ax.set_xlabel("Easting (km)")
ax.set_ylabel("Northing (km)")
ax.set_title("")
ax.xaxis.set_major_formatter(lambda v, _: f"{v / 1000:g}")
ax.yaxis.set_major_formatter(lambda v, _: f"{v / 1000:g}")
eofigs.tidy_axes(ax, bar, max_ticks=4)

if __name__ == "__main__":
    print(dem.shape, "->", small.shape, small.attrs["eofigs_reduction"])
    print(eofigs.save_figure(fig, "large_raster"))
