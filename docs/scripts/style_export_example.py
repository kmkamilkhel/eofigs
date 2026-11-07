"""Build the example figure shown on the "Style and export" page.

Run from the repository root:  python docs/scripts/style_export_example.py
"""

from pathlib import Path

import cmcrameri.cm as cmc
import numpy as np

import eofigs

OUT = Path(__file__).resolve().parents[1] / "assets"

rng = np.random.default_rng(42)
years = np.arange(2001, 2025)
ndvi_forest = 0.72 + 0.002 * (years - 2001) + rng.normal(0, 0.01, years.size)
ndvi_shrub = 0.48 - 0.001 * (years - 2001) + rng.normal(0, 0.012, years.size)
y, x = np.mgrid[0:60, 0:80]
trend = 0.004 * np.sin(x / 12) * np.cos(y / 15) + rng.normal(0, 0.0004, (60, 80))

with eofigs.style("elsevier", font="serif"):
    fig, (ax1, ax2) = eofigs.new_figure("double", height_mm=65, ncols=2)

    ax1.plot(years, ndvi_forest, marker="o", label="Forest")
    ax1.plot(years, ndvi_shrub, marker="s", label="Shrubland")
    ax1.set_xlabel("Year")
    ax1.set_ylabel("NDVI")
    ax1.legend(loc="center right")

    limit = np.abs(trend).max()
    image = ax2.imshow(trend, cmap=cmc.vik, vmin=-limit, vmax=limit)
    ax2.set_xticks([])
    ax2.set_yticks([])
    fig.colorbar(image, ax=ax2, label=r"NDVI trend (decade$^{-1}$)", shrink=0.9)

    eofigs.label_panels([ax1, ax2])
    eofigs.save_figure(fig, OUT / "style_export_example.png", dpi=200, check=False)
    print(eofigs.check_figure(fig))
