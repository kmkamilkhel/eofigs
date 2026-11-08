"""trend_map: exact numbers on synthetic grids, inputs, layout and the Swat sample."""

from pathlib import Path

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib as mpl
import numpy as np
import pandas as pd
import pytest
import rioxarray  # noqa: F401
import xarray as xr
from shapely.geometry import box

import eofigs
from eofigs import trends

UTM = "EPSG:32643"
SWAT = Path(__file__).resolve().parents[1] / "docs" / "data" / "swat"


@pytest.fixture
def custom_style(sans_font):
    with eofigs.style("custom", font=sans_font):
        yield


def _grid(values, cell=500.0, crs=UTM, x0=500_000.0, y0=3_900_000.0, name="slope"):
    rows, cols = values.shape
    y = y0 - (np.arange(rows) + 0.5) * cell
    x = x0 + (np.arange(cols) + 0.5) * cell
    da = xr.DataArray(values.astype("float64"), dims=("y", "x"), coords={"y": y, "x": x})
    da.name = name
    return da.rio.write_crs(crs)


def _cube(slope_per_year, years=15, noise=0.0, base=0.5, seed=0, name="ndvi"):
    rows, cols = slope_per_year.shape
    time = pd.date_range("2001-01-01", periods=years, freq="YS")
    t = np.arange(years)[:, None, None]
    rng = np.random.default_rng(seed)
    values = base + slope_per_year[None] * t + rng.normal(0, noise, (years, rows, cols))
    grid = _grid(np.zeros((rows, cols)))
    cube = xr.DataArray(values, dims=("time", "y", "x"),
                        coords={"time": time, "y": grid.y, "x": grid.x}, name=name)  # fmt: skip
    cube.attrs = {"long_name": "NDVI", "units": "1"}
    return cube.rio.write_crs(UTM)


# ----------------------------------------------------------------------------- significance cells


def test_significance_cells_share_and_the_half_rule():
    sig = np.zeros((4, 6), bool)
    sig[:2, :2] = True  # cell (0, 0): 4 of 4
    sig[0, 2:4] = True  # cell (0, 1): 2 of 4 -> exactly 50 %
    sig[2, 4] = True  # cell (1, 2): 1 of 4
    valid = np.ones((4, 6), bool)
    share, valid_share = trends.significance_cells(sig, valid, 2)
    assert share.tolist() == [[1.0, 0.5, 0.0], [0.0, 0.0, 0.25]]
    assert valid_share.tolist() == [[1.0] * 3, [1.0] * 3]
    valid[0, 0] = valid[1, 1] = False  # excluded pixels do not count
    share, valid_share = trends.significance_cells(sig, valid, 2)
    assert share[0, 0] == 1.0 and valid_share[0, 0] == 0.5


def test_trailing_partial_cells_are_dropped():
    share, _ = trends.significance_cells(np.ones((5, 7), bool), np.ones((5, 7), bool), 2)
    assert share.shape == (2, 3)


def _left_half_significant(rows=40, cols=40, p_left=0.01, p_right=0.5):
    slope = _grid(np.full((rows, cols), 0.02))
    p = np.full((rows, cols), p_right)
    p[:, : cols // 2] = p_left
    return slope, _grid(p, name="pvalue")


def _two_by_two(slope, **kwargs):
    """Draw with significance cells of exactly 2 x 2 source pixels."""
    kwargs.setdefault("variable", "ndvi")
    probe = eofigs.trend_map(slope=slope, **kwargs)
    map_w = probe._eofigs_layout.map_box[2]
    spacing = 2 * map_w / slope.sizes["x"]
    fig = eofigs.trend_map(slope=slope, dot_spacing_mm=spacing, **kwargs)
    assert fig.eofigs_layout["mark_cell_mm"] == pytest.approx(spacing, rel=1e-3)
    return fig


def _dots(fig):
    marks = fig.eofigs_layout["marks"]
    found = [c for c in fig.axes[0].collections
             if hasattr(c, "get_offsets") and c.get_offsets().shape[0] == marks]  # fmt: skip
    return found[0].get_offsets()


def test_dots_fill_exactly_the_significant_half(custom_style):
    slope, pvalue = _left_half_significant()  # 40 x 40, left 20 columns significant
    fig = _two_by_two(slope, pvalue=pvalue, width="single")
    layout = fig.eofigs_layout
    assert layout["marks"] == 20 * 10  # 20 rows of cells x 10 columns of cells
    x = _dots(fig)[:, 0]
    assert np.all(x < 500_000 + 20 * 500)  # all in the left half
    assert layout["significant_percent"] == 50.0


def test_cell_at_exactly_half_gets_a_dot_and_below_half_does_not(custom_style):
    slope = _grid(np.full((4, 4), 0.02))
    p = np.full((4, 4), 0.5)
    p[:2, :1] = 0.01  # cell (0, 0): 2 of 4 significant -> dot
    p[2, 2] = 0.01  # cell (1, 1): 1 of 4 -> no dot
    fig = _two_by_two(slope, pvalue=_grid(p), legend=False, north_arrow=False,
                      scale_bar=False, graticule=False)  # fmt: skip
    assert fig.eofigs_layout["marks"] == 1
    ((x, y),) = _dots(fig)
    assert x == pytest.approx(500_000 + 500) and y == pytest.approx(3_900_000 - 500)
    fewer = _two_by_two(slope, pvalue=_grid(p), sig_fraction=0.75, legend=False,
                        north_arrow=False, scale_bar=False, graticule=False)  # fmt: skip
    assert fewer.eofigs_layout["marks"] == 0


def test_alpha_changes_the_marks(custom_style):
    slope = _grid(np.full((20, 20), 0.02))
    p = _grid(np.full((20, 20), 0.03))
    loose = eofigs.trend_map(slope=slope, pvalue=p, alpha=0.05, variable="ndvi")
    strict = eofigs.trend_map(slope=slope, pvalue=p, alpha=0.01, variable="ndvi")
    assert loose.eofigs_layout["significant_percent"] == 100.0
    assert strict.eofigs_layout["significant_percent"] == 0.0
    assert loose.eofigs_layout["marks"] > 0 and strict.eofigs_layout["marks"] == 0
    assert "p < 0.01" in strict.eofigs_layout["caption"]


def test_slope_without_pvalues_draws_no_marks(custom_style):
    fig = eofigs.trend_map(slope=_grid(np.full((20, 20), 0.02)), variable="ndvi")
    layout = fig.eofigs_layout
    assert layout["marks"] == 0 and layout["significant_percent"] is None
    assert "Dots" not in layout["caption"]
    labels = [t.get_text() for leg in fig.legends for t in leg.get_texts()]
    assert not any(label.startswith("p <") for label in labels)


def test_hatching_instead_of_dots(custom_style):
    slope, pvalue = _left_half_significant()
    fig = eofigs.trend_map(slope=slope, pvalue=pvalue, variable="ndvi", stipple="hatch")
    hatched = [c for c in fig.axes[0].collections if "...." in (getattr(c, "hatches", None) or [])]
    assert hatched and fig.eofigs_layout["marks"] > 0
    assert "Hatching:" in fig.eofigs_layout["caption"]
    none = eofigs.trend_map(slope=slope, pvalue=pvalue, variable="ndvi", stipple=None)
    assert none.eofigs_layout["marks"] == 0


# ----------------------------------------------------------------------------- limits and ticks


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0731, 0.08), (0.08, 0.08), (0.0101, 0.012), (3.2, 4.0), (0.95, 1.0), (0.0, 1.0)],
)
def test_round_up(value, expected):
    assert trends._round_up(value) == pytest.approx(expected)


def test_limits_rule_clipped_share_and_extend(custom_style):
    values = np.linspace(-0.05, 0.05, 10_000).reshape(100, 100)
    values[0, :50] = 0.2  # 0.5 % far above
    values[1, :50] = -0.2  # 0.5 % far below
    fig = eofigs.trend_map(slope=_grid(values), variable="ndvi")
    layout = fig.eofigs_layout
    assert layout["limits_rule"] == "p98" and layout["limits"] == 0.05
    assert layout["extend"] == "both"
    assert layout["clipped_percent"] == pytest.approx(1.0)
    assert "±0.05 decade⁻¹ (98th percentile of |slope|); 1.0 % of pixels" in layout["caption"]
    fixed = eofigs.trend_map(slope=_grid(values), variable="ndvi", limits=0.3).eofigs_layout
    assert fixed["limits"] == 0.3 and fixed["extend"] == "neither"
    assert "Colours are limited to ±0.3 decade⁻¹; 0.0 %" in fixed["caption"]
    full = eofigs.trend_map(slope=_grid(values), variable="ndvi", limits=None).eofigs_layout
    assert full["limits"] == 0.2 and full["limits_rule"] == "max"
    assert full["caption"].startswith("Colours span the full range (±0.2 decade⁻¹).")


def test_colour_bar_is_centred_with_round_ticks(custom_style):
    values = np.linspace(-0.07, 0.07, 400).reshape(20, 20)
    fig = eofigs.trend_map(slope=_grid(values), variable="ndvi")
    image = fig.axes[0].get_images()[0]
    assert image.norm.vmin == -image.norm.vmax == -0.08
    assert image.get_cmap().name == "eofigs.terra_slate"
    bar_axes = [a for a in fig.axes if a.get_xlabel().startswith("NDVI trend")][0]
    assert bar_axes.get_xlabel() == "NDVI trend (decade$^{-1}$)"
    assert bar_axes.get_xticks().tolist() == [-0.08, -0.04, 0.0, 0.04, 0.08]


@pytest.mark.parametrize(
    ("limit", "expected"),
    [
        (0.1, [-0.1, -0.05, 0.0, 0.05, 0.1]),
        (0.08, [-0.08, -0.04, 0.0, 0.04, 0.08]),
        (3.0, [-3.0, -1.5, 0.0, 1.5, 3.0]),
        (20, [-20, -10, 0, 10, 20]),
    ],
)
def test_diverging_ticks(limit, expected):
    assert trends.diverging_ticks(limit).tolist() == pytest.approx(expected)


def test_diverging_ticks_respect_a_small_tick_limit():
    assert len(trends.diverging_ticks(0.08, max_ticks=3)) <= 3


# ----------------------------------------------------------------------------- data and exclusion


def test_cube_is_tested_at_full_resolution_and_reduced(custom_style):
    slope = np.zeros((30, 40))
    slope[:, :20] = 0.01  # strong greening in the west, none in the east
    cube = _cube(slope, noise=0.002)
    fig = eofigs.trend_map(cube)
    layout = fig.eofigs_layout
    assert layout["significant_percent"] == pytest.approx(50.0, abs=3)
    assert "Mann–Kendall, p < 0.05" in layout["caption"]
    assert "500 m pixels" in layout["caption"]


def test_auto_exclusion_of_bare_pixels(custom_style):
    slope = np.full((20, 20), 0.005)
    cube = _cube(slope, noise=0.001)
    cube[:, :5, :] = 0.05  # rock: mean NDVI 0.05
    fig = eofigs.trend_map(cube)
    layout = fig.eofigs_layout
    assert layout["excluded_percent"] == 25.0
    assert "Hatched grey: mean NDVI below 0.1 over the record (not vegetated)." in layout["caption"]
    labels = [t.get_text() for leg in fig.legends for t in leg.get_texts()]
    assert "Not vegetated" in labels
    grey = [c for c in fig.axes[0].collections if c.get_hatch() == trends.GREY_HATCH]
    assert grey
    kept = eofigs.trend_map(cube, exclude=None).eofigs_layout
    assert kept["excluded_percent"] == 0.0
    higher = eofigs.trend_map(cube, exclude=0.3).eofigs_layout
    assert higher["excluded_percent"] == 25.0  # the rest has a mean of about 0.54
    temperature = cube.copy()
    temperature.name = "lst"
    temperature.attrs = {"long_name": "Land surface temperature", "units": "K"}
    assert eofigs.trend_map(temperature).eofigs_layout["excluded_percent"] == 0.0


def test_exclusion_grid_and_no_data_label(custom_style):
    values = np.full((20, 20), 0.01)
    values[0, :] = np.nan
    mask = _grid(np.zeros((20, 20))).astype(bool)
    mask[-2:, :] = True
    fig = eofigs.trend_map(slope=_grid(values), variable="ndvi", exclude=mask,
                           exclude_label="Water")  # fmt: skip
    labels = [t.get_text() for leg in fig.legends for t in leg.get_texts()]
    assert "Water or no data" in labels
    assert fig.eofigs_layout["excluded_percent"] == 10.0
    assert "Hatched grey: excluded pixels or no data." in fig.eofigs_layout["caption"]
    only_nan = eofigs.trend_map(slope=_grid(values), variable="ndvi")
    assert "No data" in [t.get_text() for leg in only_nan.legends for t in leg.get_texts()]


def test_grey_labels():
    assert trends._grey_label(False, False, "x") is None
    assert trends._grey_label(True, False, "Rock") == "Rock"
    assert trends._grey_label(False, True, "Rock") == "No data"


def test_variable_resolution(custom_style):
    unknown = _grid(np.full((10, 10), 0.01))
    unknown.attrs = {"long_name": "Mystery index trend", "units": "yr$^{-1}$"}
    fig = eofigs.trend_map(slope=unknown)
    bar = [a for a in fig.axes if a.get_xlabel()][-1]
    assert bar.get_xlabel() == "Mystery index trend (yr$^{-1}$)"
    gpp = eofigs.variable("gpp").trend("year")
    assert trends._trend_variable(gpp, unknown, "decade") is gpp
    assert trends._trend_variable("lst", unknown, "year").cmap == "cmc.vik"
    result = eofigs.trend(_cube(np.full((5, 5), 0.01)))
    assert trends._trend_variable(None, result.slope, "decade").name == "ndvi_trend"


# ----------------------------------------------------------------------------- errors


def test_errors(custom_style):
    slope = _grid(np.full((10, 10), 0.01))
    with pytest.raises(ValueError, match="Give data= .* or slope="):
        eofigs.trend_map()
    with pytest.raises(ValueError, match="not both"):
        eofigs.trend_map(_cube(np.zeros((5, 5))), slope=slope)
    with pytest.raises(ValueError, match="stipple must be"):
        eofigs.trend_map(slope=slope, stipple="crosses")
    with pytest.raises(ValueError, match="sig_fraction"):
        eofigs.trend_map(slope=slope, sig_fraction=0)
    with pytest.raises(ValueError, match="no CRS"):
        eofigs.trend_map(slope=xr.DataArray(np.zeros((3, 3)), dims=("y", "x")))
    with pytest.raises(TypeError, match="DataArray"):
        eofigs.trend_map(slope=np.zeros((3, 3)))
    with pytest.raises(ValueError, match="2-D grid"):
        eofigs.trend_map(slope=_cube(np.zeros((3, 3))))
    with pytest.raises(ValueError, match="same grid"):
        eofigs.trend_map(slope=slope, pvalue=_grid(np.zeros((10, 12))))
    with pytest.raises(TypeError, match="pvalue must be"):
        eofigs.trend_map(slope=slope, pvalue=np.zeros((10, 10)))
    with pytest.raises(ValueError, match="limits must be 'p98'"):
        eofigs.trend_map(slope=slope, limits="p95")
    with pytest.raises(ValueError, match="positive"):
        eofigs.trend_map(slope=slope, limits=-1)
    with pytest.raises(ValueError, match="needs data="):
        eofigs.trend_map(slope=slope, exclude=0.1)
    with pytest.raises(ValueError, match="exclude must be 'auto'"):
        eofigs.trend_map(slope=slope, exclude="rock")
    with pytest.raises(TypeError, match="exclude must be"):
        eofigs.trend_map(slope=slope, exclude=[1, 2])
    with pytest.raises(ValueError, match="slope's grid"):
        eofigs.trend_map(slope=slope, exclude=_grid(np.zeros((3, 3))).astype(bool))
    fig, ax = eofigs.new_figure("single", subplot_kw={"projection": ccrs.UTM(43)}, layout="none")
    with pytest.raises(ValueError, match="latitude_profile needs"):
        eofigs.trend_map(slope=slope, ax=ax, latitude_profile=True)
    with pytest.raises(ValueError, match="either ax or subfigure"):
        eofigs.trend_map(slope=slope, ax=ax, subfigure=fig)
    with pytest.raises(ValueError, match="cartopy GeoAxes"):
        eofigs.trend_map(slope=slope, ax=eofigs.new_figure("single")[1])


# ----------------------------------------------------------------------------- layout, profile


def test_profile_bands_follow_latitude(custom_style):
    lat = np.linspace(35.9, 34.5, 141)
    lon = np.linspace(72.0, 72.8, 81)
    values = np.repeat(((lat - 34.5) / 100)[:, None], lon.size, axis=1)  # slope = f(latitude)
    da = xr.DataArray(values, dims=("y", "x"), coords={"y": lat, "x": lon}, name="slope")
    da = da.rio.write_crs("EPSG:4326")
    centres, med, q25, q75, counts = trends.latitude_bands(da, 0.1, 34.5, 35.9)
    assert np.all(np.diff(med) > 0)  # increases northwards, as built
    assert np.allclose(med, (centres - 34.5) / 100, atol=0.0006)
    assert counts.min() >= trends.PROFILE_MIN_PIXELS
    few = trends.latitude_bands(da.isel(x=slice(0, 1)), 0.1, 34.5, 35.9)
    assert few[0].size == 0  # bands with fewer than 20 pixels are skipped
    fig = eofigs.trend_map(slope=da, variable="ndvi", latitude_profile=True, width="double",
                           labels="(a)")  # fmt: skip
    layout = fig.eofigs_layout
    assert layout["layout"] == "profile" and layout["crs"] == "EPSG:32643"  # UTM for degrees
    assert layout["profile_bands"]["bands"] > 5
    prof = [a for a in fig.axes if a.get_xlabel().startswith("Median")][0]
    assert prof.get_xlim() == (-layout["limits"], layout["limits"])
    texts = {t.get_text() for a in fig.axes for t in a.texts}
    assert {"(a)", "(b)"} <= texts
    assert "Profile: median and interquartile range" in layout["caption"]


def test_map_in_existing_axes_and_subfigure(custom_style):
    slope, pvalue = _left_half_significant()
    fig, ax = eofigs.new_figure("single", height_mm=90, subplot_kw={"projection": ccrs.UTM(43)},
                                layout="none")  # fmt: skip
    out = eofigs.trend_map(slope=slope, pvalue=pvalue, variable="ndvi", ax=ax)
    assert out is fig and ax.get_legend() is not None
    fig2, ax0 = eofigs.new_figure("double", height_mm=120, layout="none")
    ax0.remove()
    left, _ = fig2.subfigures(1, 2)
    out2 = eofigs.trend_map(slope=slope, pvalue=pvalue, variable="ndvi", subfigure=left)
    assert out2 is fig2 and left.eofigs_layout is fig2.eofigs_layout
    assert all(a.get_window_extent().x1 <= left.bbox.x1 + 1 for a in left.axes)


def test_aoi_outline_and_furniture(custom_style):
    slope, pvalue = _left_half_significant(rows=60, cols=60)
    aoi = gpd.GeoDataFrame(geometry=[box(505_000, 3_875_000, 520_000, 3_895_000)], crs=UTM)
    fig = eofigs.trend_map(slope=slope, pvalue=pvalue, variable="ndvi", aoi=aoi)
    layout = fig.eofigs_layout
    assert "furniture" in layout["items"]
    labels = [t.get_text() for leg in fig.legends for t in leg.get_texts()]
    assert labels[0] == "Study area"
    report = eofigs.check_figure(fig)
    assert report.passed and not report.warnings, str(report)


def test_minimal_map(custom_style):
    fig = eofigs.trend_map(slope=_grid(np.full((10, 10), 0.01)), variable="ndvi", legend=False,
                           graticule=False, north_arrow=False, scale_bar=False)  # fmt: skip
    assert not fig.legends and fig.eofigs_layout["items"] == {}


def test_plain_caption_units():
    assert trends._plain("decade$^{-1}$") == "decade⁻¹"
    assert trends._plain("gC m$^{-2}$ d$^{-1}$ yr$^{-1}$") == "gC m⁻² d⁻¹ yr⁻¹"


# ----------------------------------------------------------------------------- Swat sample


def _swat_cube():
    raw = rioxarray.open_rasterio(SWAT / "swat_ndvi_growing_season_500m.tif", mask_and_scale=True)
    years = [int(y) for y in raw.attrs["long_name"]]
    cube = raw.rename(band="time").assign_coords(time=pd.to_datetime([f"{y}-07-01" for y in years]))
    cube.name = "ndvi"
    cube.attrs = {"long_name": "NDVI", "units": "1"}
    return cube


@pytest.fixture
def arial():
    """Arial, or its metric-compatible twin Liberation Sans (the gallery's fonts)."""
    from matplotlib import font_manager

    installed = {f.name for f in font_manager.fontManager.ttflist}
    font = next((f for f in ("Arial", "Liberation Sans") if f in installed), None)
    if font is None:
        pytest.skip("Neither Arial nor Liberation Sans is installed")
    return font


@pytest.mark.skipif(not SWAT.exists(), reason="Swat sample data are in the repository only")
def test_swat_trend_map(arial):
    with eofigs.style("elsevier", font=arial):
        cube = _swat_cube()
        assert cube.sizes["time"] == 24
        fig = eofigs.trend_map(cube, aoi=SWAT / "swat_boundary.geojson")
        layout = fig.eofigs_layout
        report = eofigs.check_figure(fig)
    assert 30 < layout["significant_percent"] < 90
    assert 5 < layout["excluded_percent"] < 30
    assert layout["marks"] > 1000
    assert layout["clipped_percent"] < 2.5
    w, h = (v * 25.4 for v in fig.get_size_inches())
    assert w == pytest.approx(140) and h <= 180.5
    assert report.passed and not report.warnings, str(report)
    assert mpl.colormaps["eofigs.terra_slate"].name == "eofigs.terra_slate"
