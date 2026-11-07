"""Build the example figure shown on the "Trends" page.

Run from the repository root:  python docs/scripts/trend_example.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr
from matplotlib.colors import ListedColormap

import eofigs

OUT = Path(__file__).resolve().parents[1] / "assets"

# Synthetic annual NDVI, 2000-2024, 120 x 160 pixels: greening in the north-west, browning
# in the south-east, noise everywhere.
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

with eofigs.style("elsevier", font="serif"):
    fig, (ax1, ax2) = eofigs.new_figure("double", height_mm=70, ncols=2)
    image = result.slope.plot.imshow(
        ax=ax1, cmap=var.cmap, vmin=-limit, vmax=limit, add_colorbar=False
    )
    fig.colorbar(image, ax=ax1, label=var.short_label, shrink=0.85)
    mask = result.significant.astype(float).plot.imshow(
        ax=ax2, cmap=ListedColormap(["#F1EFEA", "#455B69"]), add_colorbar=False
    )
    bar = fig.colorbar(mask, ax=ax2, ticks=[0.25, 0.75], shrink=0.85)
    bar.ax.set_yticklabels(["p ≥ 0.05", "p < 0.05"])
    for ax in (ax1, ax2):
        ax.set_title("")
        ax.set_axis_off()
    eofigs.label_panels([ax1, ax2])
    eofigs.save_figure(fig, OUT / "trend_example.png", dpi=200, check=False)
    print(eofigs.check_figure(fig))
    print(f"significant pixels: {float(result.significant.mean()):.0%}")
