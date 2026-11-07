"""Trend and significance.

Theil–Sen slope and Mann–Kendall test of a synthetic annual NDVI series (2000–2024,
120 × 160 pixels) with greening in the north-west, browning in the south-east and noise:
(a) the slope per decade with the library's zero-centred trend colours (`vik`, limits at
the 98th percentile of absolute values), (b) the pixels where p < 0.05. Synthetic data.
"""

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401  (adds the .rio accessor)
import xarray as xr
from matplotlib.colors import ListedColormap

import eofigs
from eofigs import palettes

rng = np.random.default_rng(7)
years = pd.date_range("2000-01-01", periods=25, freq="YS")
y, x = np.mgrid[0:120, 0:160]
y, x = y / 120, x / 160
pattern = 0.004 * np.cos(np.pi * x) * np.cos(np.pi * y)  # NDVI per year
t = np.arange(25)[:, None, None]
ndvi = 0.55 + pattern[None] * t + rng.normal(0, 0.03, (25, 120, 160))
cube = xr.DataArray(
    ndvi,
    dims=("time", "y", "x"),
    coords={
        "time": years,
        "y": 3_900_000 - (np.arange(120) + 0.5) * 250,
        "x": 750_000 + (np.arange(160) + 0.5) * 250,
    },
    name="ndvi",
).rio.write_crs("EPSG:32643")

result = eofigs.trend(cube, per="decade")
var = eofigs.variable("ndvi").trend("decade")
limit = float(np.nanpercentile(np.abs(result.slope), 98))

eofigs.set_style("elsevier")
fig, (ax1, ax2) = eofigs.new_figure("double", height_mm=70, ncols=2)
image = result.slope.plot.imshow(ax=ax1, cmap=var.cmap, vmin=-limit, vmax=limit, add_colorbar=False)
bar = fig.colorbar(image, ax=ax1, label=var.short_label, shrink=0.85)
mask = result.significant.astype(float).plot.imshow(
    ax=ax2, cmap=ListedColormap([palettes.terra_slate[3], palettes.slate[-1]]), add_colorbar=False
)
legend = fig.colorbar(mask, ax=ax2, ticks=[0.25, 0.75], shrink=0.85)
legend.ax.set_yticklabels(["p ≥ 0.05", "p < 0.05"])
for ax in (ax1, ax2):
    ax.set_title("")
    ax.set_axis_off()
eofigs.tidy_axes(bar)
eofigs.label_panels([ax1, ax2])

if __name__ == "__main__":
    print(f"significant pixels: {float(result.significant.mean()):.0%}")
    print(eofigs.save_figure(fig, "trend_significance"))
