"""Image comparisons for map elements (compared on the Linux CI job with ``--mpl``).

Without ``--mpl`` these tests only build the figures. Baselines are in tests/baseline and
were rendered on Linux with DejaVu Sans; font rendering differs between operating systems,
so the comparison runs on Linux only.
"""

import cartopy.crs as ccrs
import geopandas as gpd
import numpy as np
import pytest
import rioxarray  # noqa: F401
import xarray as xr
from shapely.geometry import Point, Polygon

import eofigs

UTM = "EPSG:32643"
COMPARE = {
    "baseline_dir": "baseline",
    "tolerance": 5,
    "style": "default",
    "savefig_kwargs": {"dpi": 100},
}


def _aoi():
    poly = Polygon(
        [(250_000, 3_820_000), (275_000, 3_820_000), (310_000, 3_960_000), (285_000, 3_960_000)]
    )
    return gpd.GeoDataFrame(geometry=[poly], crs=UTM)


def _dem():
    x = np.arange(180_500, 340_000, 1000.0)
    y = np.arange(3_979_500, 3_800_000, -1000.0)
    xx, yy = np.meshgrid((x - x[0]) / 160_000, (y - y[-1]) / 180_000)
    z = 800 + 3500 * yy + 600 * np.sin(12 * xx) * np.cos(9 * yy)
    da = xr.DataArray(z.astype("float32"), dims=("y", "x"), coords={"y": y, "x": x})
    return da.rio.write_crs(UTM)


@pytest.mark.mpl_image_compare(**COMPARE)
def test_north_arrow_and_scale_bar_image():
    with eofigs.style("custom", font="DejaVu Sans"):
        fig, ax = eofigs.new_figure(
            60, height_mm=60, subplot_kw={"projection": ccrs.UTM(43)}, layout="none"
        )
        ax.set_extent([240_000, 300_000, 3_850_000, 3_910_000], crs=ccrs.UTM(43))
        eofigs.add_north_arrow(ax, loc="upper right")
        eofigs.add_scale_bar(ax, loc="lower left")
    return fig


@pytest.mark.mpl_image_compare(**COMPARE)
def test_study_area_map_inside_image():
    towns = gpd.GeoDataFrame(
        {"name": ["Lowtown", "Hightown"]},
        geometry=[Point(263_000, 3_832_000), Point(290_000, 3_930_000)],
        crs=UTM,
    )
    with eofigs.style("custom", font="DejaVu Sans"):
        fig = eofigs.study_area_map(_aoi(), dem=_dem(), points=towns, width="single")
    assert fig.eofigs_layout["layout"] == "inside"
    return fig


@pytest.mark.mpl_image_compare(**COMPARE)
def test_study_area_map_side_image():
    with eofigs.style("custom", font="DejaVu Sans"):
        fig = eofigs.study_area_map(_aoi(), dem=_dem(), width="onehalf", journal="elsevier")
    assert fig.eofigs_layout["layout"] == "side"
    return fig
