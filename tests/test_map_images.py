"""Image comparisons for the map recipes (compared on the Linux CI job with ``--mpl``).

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


def _trend_grids():
    """A tall slope grid with greening in the west, browning in the east and a bare strip."""
    y = np.arange(3_899_750, 3_840_000, -500.0)
    x = np.arange(250_250, 280_000, 500.0)
    xx, yy = np.meshgrid((x - x[0]) / (x[-1] - x[0]), (y - y[-1]) / (y[0] - y[-1]))
    slope = 0.06 * np.cos(np.pi * xx) + 0.02 * np.sin(6 * yy)
    slope[:12, 40:] = np.nan  # no data in the north-east corner
    pvalue = np.where(np.abs(slope) > 0.03, 0.01, 0.4)
    coords = {"y": y, "x": x}
    s = xr.DataArray(slope, dims=("y", "x"), coords=coords).rio.write_crs(UTM)
    p = xr.DataArray(pvalue, dims=("y", "x"), coords=coords).rio.write_crs(UTM)
    return s, p


@pytest.mark.mpl_image_compare(**COMPARE)
def test_trend_map_dots_image():
    slope, pvalue = _trend_grids()
    with eofigs.style("custom", font="DejaVu Sans"):
        return eofigs.trend_map(slope=slope, pvalue=pvalue, variable="ndvi", width="single")


@pytest.mark.mpl_image_compare(**COMPARE)
def test_trend_map_hatch_image():
    slope, pvalue = _trend_grids()
    with eofigs.style("custom", font="DejaVu Sans"):
        return eofigs.trend_map(
            slope=slope, pvalue=pvalue, variable="ndvi", stipple="hatch", width="single"
        )


@pytest.mark.mpl_image_compare(**COMPARE)
def test_trend_map_profile_image():
    slope, pvalue = _trend_grids()
    with eofigs.style("custom", font="DejaVu Sans", labels="(a)"):
        return eofigs.trend_map(
            slope=slope, pvalue=pvalue, variable="ndvi", latitude_profile=True, width="double"
        )


def _event_cube():
    """A small monthly cube with a seasonal cycle and five two-month dry events."""
    import pandas as pd

    time = pd.date_range("2001-01-01", "2012-12-01", freq="MS")
    rng = np.random.default_rng(2)
    season = 0.1 * np.sin(2 * np.pi * (time.month.to_numpy() - 4) / 12)
    east = np.linspace(0, 1, 30)[None, :] * np.ones((24, 1))
    values = 0.5 + season[:, None, None] + rng.normal(0, 0.015, (time.size, 24, 30))
    events = []
    for start in ("2002-06", "2004-07", "2006-05", "2008-08", "2010-06"):
        i = time.get_loc(pd.Timestamp(f"{start}-01"))
        values[i : i + 2] -= 0.02 + 0.06 * east
        values[i + 2 : i + 5] -= 0.01 + 0.03 * east
        events.append((time[i], time[i + 1]))
    y = 3_899_500 - np.arange(24) * 1000.0
    x = 250_500 + np.arange(30) * 1000.0
    cube = xr.DataArray(values, dims=("time", "y", "x"), coords={"time": time, "y": y, "x": x},
                        name="ndvi", attrs={"long_name": "NDVI", "units": "1"})  # fmt: skip
    return cube.rio.write_crs(UTM), events


@pytest.mark.mpl_image_compare(**COMPARE)
def test_event_composite_image():
    cube, events = _event_cube()
    with eofigs.style("custom", font="DejaVu Sans", labels="(a)"):
        return eofigs.event_composite(cube, events)


@pytest.mark.mpl_image_compare(**COMPARE)
def test_event_composite_two_phases_image():
    cube, events = _event_cube()
    with eofigs.style("custom", font="DejaVu Sans"):
        return eofigs.event_composite(
            cube, events, maps=("during", "after"), series=False, width="onehalf"
        )


def _accuracy_pairs(n, seed):
    rng = np.random.default_rng(seed)
    observed = rng.gamma(4, 40, n)
    return observed, 15 + 0.85 * observed + rng.normal(0, 25, n)


@pytest.mark.mpl_image_compare(**COMPARE)
def test_accuracy_scatter_groups_image():
    observed, predicted = _accuracy_pairs(300, 4)
    groups = np.where(np.arange(300) % 3 == 0, "Conifer", "Broadleaf")
    with eofigs.style("custom", font="DejaVu Sans"):
        return eofigs.accuracy_scatter(observed, predicted, variable="agb", groups=groups)


@pytest.mark.mpl_image_compare(**COMPARE)
def test_accuracy_scatter_density_image():
    observed, predicted = _accuracy_pairs(4000, 5)
    with eofigs.style("custom", font="DejaVu Sans"):
        return eofigs.accuracy_scatter(observed, predicted, variable="agb", fit="rma")
