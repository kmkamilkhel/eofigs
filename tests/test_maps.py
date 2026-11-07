import hashlib
import io
import urllib.error
import zipfile
from pathlib import Path

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib as mpl
import numpy as np
import pyproj
import pytest
import rioxarray  # noqa: F401
import xarray as xr
from matplotlib.colors import ListedColormap
from shapely.geometry import Point, Polygon, box

import eofigs
from eofigs import _countries, maps
from eofigs.check import overlay_contrast

UTM = "EPSG:32643"
SWAT = Path(__file__).resolve().parents[1] / "docs" / "data" / "swat"


# ----------------------------------------------------------------------------- synthetic data


def _tall_aoi():
    """A tall, leaning study area (like a valley): empty corners top-left and bottom-right."""
    poly = Polygon(
        [(250_000, 3_820_000), (275_000, 3_820_000), (310_000, 3_960_000), (285_000, 3_960_000)]
    )
    return gpd.GeoDataFrame({"name": ["valley"]}, geometry=[poly], crs=UTM)


def _wide_aoi():
    poly = Polygon(
        [(200_000, 3_880_000), (330_000, 3_900_000), (330_000, 3_930_000), (200_000, 3_915_000)]
    )
    return gpd.GeoDataFrame(geometry=[poly], crs=UTM)


def _full_aoi():
    """A rectangle that fills its own map: no empty corner anywhere."""
    return gpd.GeoDataFrame(geometry=[box(250_000, 3_820_000, 310_000, 3_960_000)], crs=UTM)


def _dem(bounds=(180_000, 3_800_000, 340_000, 3_980_000), cell=1000.0):
    x0, y0, x1, y1 = bounds
    x = np.arange(x0 + cell / 2, x1, cell)
    y = np.arange(y1 - cell / 2, y0, -cell)
    xx, yy = np.meshgrid((x - x0) / (x1 - x0), (y - y0) / (y1 - y0))
    z = 800 + 3500 * yy + 600 * np.sin(12 * xx) * np.cos(9 * yy)
    da = xr.DataArray(z.astype("float32"), dims=("y", "x"), coords={"y": y, "x": x})
    da.attrs = {"units": "m", "long_name": "Elevation"}
    return da.rio.write_crs(UTM)


def _cover(dem):
    values = (np.sin(dem.x.values / 9000)[None, :] * np.cos(dem.y.values / 7000)[:, None] + 1) * 50
    da = xr.DataArray(values.astype("float32"), dims=("y", "x"), coords=dem.coords)
    da.attrs = {"units": "%", "long_name": "Tree cover"}
    return da.rio.write_crs(UTM)


def _towns():
    pts = [Point(262_000, 3_830_000), Point(264_000, 3_833_000), Point(290_000, 3_930_000)]
    return gpd.GeoDataFrame({"name": ["Lowtown", "Neartown", "Hightown"]}, geometry=pts, crs=UTM)


@pytest.fixture
def custom_style(sans_font):
    with eofigs.style("custom", font=sans_font):
        yield


@pytest.fixture
def arial_style():
    """Arial, or its metric-compatible twin Liberation Sans (the gallery's fonts)."""
    from matplotlib import font_manager

    installed = {f.name for f in font_manager.fontManager.ttflist}
    font = next((f for f in ("Arial", "Liberation Sans") if f in installed), None)
    if font is None:
        pytest.skip("Neither Arial nor Liberation Sans is installed")
    with eofigs.style("elsevier", font=font):
        yield


# ----------------------------------------------------------------------------- inputs and CRS


def test_map_crs_keeps_projected_and_chooses_utm():
    assert maps.map_crs(_tall_aoi()) == pyproj.CRS(UTM)
    wgs = _tall_aoi().to_crs("EPSG:4326")
    assert maps.map_crs(wgs).to_epsg() == 32643


def test_geometry_inputs_need_a_crs(tmp_path):
    with pytest.raises(ValueError, match="without a CRS"):
        maps._as_gdf(box(0, 0, 1, 1), "aoi")
    with pytest.raises(ValueError, match="has no CRS"):
        maps._as_gdf(gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)]), "aoi")
    with pytest.raises(TypeError, match="GeoDataFrame, GeoSeries or vector file"):
        maps._as_gdf(42, "aoi")
    path = tmp_path / "aoi.geojson"
    _tall_aoi().to_file(path)
    assert len(maps._as_gdf(path, "aoi")) == 1
    assert len(maps._as_gdf(_tall_aoi().geometry, "aoi")) == 1


# ----------------------------------------------------------------------------- north arrow


@pytest.mark.parametrize("x", [270_000, 500_000, 730_000])
def test_north_arrow_points_to_true_north(x, custom_style):
    fig, ax = eofigs.new_figure("single", subplot_kw={"projection": ccrs.UTM(43)})
    ax.set_extent([x - 30_000, x + 30_000, 3_820_000, 3_960_000], crs=ccrs.UTM(43))
    arrow = eofigs.add_north_arrow(ax)
    lon, lat = pyproj.Transformer.from_crs(UTM, 4326, always_xy=True).transform(x, 3_890_000)
    convergence = pyproj.Proj(UTM).get_factors(lon, lat).meridian_convergence
    assert arrow.angle == pytest.approx(-convergence, abs=0.02)
    assert arrow in ax.artists


def test_north_arrow_on_plain_axes_points_up(custom_style):
    fig, ax = eofigs.new_figure("single")
    assert eofigs.add_north_arrow(ax, loc="upper left").angle == 0.0


def test_north_arrow_near_the_pole(custom_style):
    fig, ax = eofigs.new_figure("single", subplot_kw={"projection": ccrs.NorthPolarStereo()})
    ax.set_extent([-180, 180, 89.95, 90], crs=ccrs.PlateCarree())
    assert np.isfinite(eofigs.add_north_arrow(ax).angle)


# ----------------------------------------------------------------------------- scale bar


@pytest.mark.parametrize(
    ("target", "expected"), [(13.2, 10), (17, 20), (2.3, 2.5), (0.42, 0.5), (3.6, 5), (0.9, 1)]
)
def test_nice_length(target, expected):
    assert maps.nice_length(target) == pytest.approx(expected)


def test_nice_length_rejects_zero():
    with pytest.raises(ValueError, match="positive"):
        maps.nice_length(0)


def test_scale_bar_length_and_true_distance(custom_style):
    fig, ax = eofigs.new_figure("single", subplot_kw={"projection": ccrs.UTM(43)})
    ax.set_extent([240_000, 300_000, 3_820_000, 3_960_000], crs=ccrs.UTM(43))
    bar = eofigs.add_scale_bar(ax)
    assert bar.length_km == 10  # 22 % of 60 km is 13.2 km -> 10 km
    lon, lat = pyproj.Transformer.from_crs(UTM, 4326, always_xy=True).transform(270_000, 3.89e6)
    k = pyproj.Proj(UTM).get_factors(lon, lat).parallel_scale
    assert bar.dx == pytest.approx(1 / k)  # ground metres per map metre
    assert eofigs.add_scale_bar(ax, length_km=0.5, loc="lower right").fixed_units == "m"


def test_scale_bar_on_a_geographic_map(custom_style):
    fig, ax = eofigs.new_figure("single", subplot_kw={"projection": ccrs.PlateCarree()})
    ax.set_extent([72.0, 73.0, 34.5, 35.9], crs=ccrs.PlateCarree())
    bar = eofigs.add_scale_bar(ax)
    assert bar.dx == pytest.approx(111_320 * np.cos(np.radians(35.2)), rel=0.01)
    assert bar.length_km == 20  # 22 % of 91 km


def test_scale_bar_needs_a_map(custom_style):
    fig, ax = eofigs.new_figure("single")
    with pytest.raises(ValueError, match="needs a map"):
        eofigs.add_scale_bar(ax)


# ----------------------------------------------------------------------------- graticule


@pytest.mark.parametrize(
    ("low", "high"), [(72.11, 72.83), (34.5, 35.9), (60.0, 78.0), (-10.0, 50.0), (0.0, 0.05)]
)
def test_graticule_has_at_most_four_lines(low, high):
    values = maps._graticule_values(low, high)
    assert 1 <= len(values) <= 4
    assert all(low - 1e-9 <= v <= high + 1e-9 for v in values)


def test_graticule_step_falls_back_to_the_largest():
    assert maps.graticule_step(-180, 180, max_lines=1) == 90


# ----------------------------------------------------------------------------- placement


def test_place_items_uses_the_emptiest_corners():
    occupied = box(0, 0, 50, 100)  # left half of a 100 x 100 mm map is full
    placed = maps.place_items(
        {"inset": (30, 20), "legend": (25, 10), "furniture": (20, 15)}, occupied, 100, 100
    )
    for name, (_, (x0, _, _, _), empty) in placed.items():
        assert x0 >= 50 and empty == 1.0, name
    assert placed["inset"][0] == "upper right"
    assert placed["legend"][0] == "lower right"
    boxes = [box(*b) for _, b, _ in placed.values()]
    assert not any(a.intersects(b) for i, a in enumerate(boxes) for b in boxes[i + 1 :])


def test_place_items_without_obstacles():
    placed = maps.place_items({"inset": (10, 10)}, None, 50, 50)
    assert placed["inset"] == ("upper right", (38.5, 38.5, 48.5, 48.5), 1.0)


# ----------------------------------------------------------------------------- study_area_map


def _layout_ok(fig, width_mm):
    w, h = (v * 25.4 for v in fig.get_size_inches())
    assert w == pytest.approx(width_mm, abs=0.01)
    assert h <= 240.5
    return fig.eofigs_layout


def test_tall_aoi_single_column_places_items_in_empty_corners(custom_style):
    aoi = _tall_aoi()
    fig = eofigs.study_area_map(aoi, dem=_dem(), points=_towns())
    layout = _layout_ok(fig, 90)
    assert layout["layout"] == "inside"
    assert set(layout["items"]) == {"inset", "legend", "furniture"}
    lay = fig._eofigs_layout
    for name in ("inset", "legend"):
        assert lay.items[name][2] >= maps.MIN_EMPTY
    # the inset sits on the empty side of the leaning valley
    assert layout["items"]["inset"] in ("upper left", "lower right", "center left", "center right")
    assert layout["labels_clear"] is True
    # height follows the tall shape: much taller than wide
    w, h = fig.get_size_inches()
    assert h > 1.4 * w
    report = eofigs.check_figure(fig)
    assert report.passed, str(report)


def test_tall_aoi_wide_figure_uses_a_side_column(custom_style):
    fig = eofigs.study_area_map(_tall_aoi(), dem=_dem(), width="onehalf", journal="elsevier")
    layout = _layout_ok(fig, 140)
    assert layout["layout"] == "side"
    assert set(layout["items"]) == {"furniture"}
    inset = [a for a in fig.axes if hasattr(a, "focus")][0]
    main = fig.axes[0]
    assert inset.get_position().x0 > main.get_position().x1  # beside the map


def test_wide_aoi_is_short_and_inside(custom_style):
    fig = eofigs.study_area_map(_wide_aoi(), dem=_dem(), inset=None, width="double")
    layout = _layout_ok(fig, 190)
    w, h = fig.get_size_inches()
    assert h < 0.6 * w
    assert layout["layout"] == "inside"
    assert "inset" not in layout["items"]


def test_full_aoi_moves_the_inset_beside_the_map(custom_style):
    fig = eofigs.study_area_map(_full_aoi(), dem=_dem(), width="single")
    layout = fig.eofigs_layout
    assert layout["layout"] == "side"  # no corner of the map is 85 % empty
    inset = [a for a in fig.axes if hasattr(a, "focus")][0]
    assert inset.get_position().x0 > fig.axes[0].get_position().x1


def test_explicit_layouts_and_height(custom_style):
    fig = eofigs.study_area_map(_tall_aoi(), layout="side", width="single", height_mm=120)
    assert fig.eofigs_layout["layout"] == "side"
    assert fig.get_size_inches()[1] * 25.4 == pytest.approx(120)
    with pytest.raises(ValueError, match="layout must be one of"):
        eofigs.study_area_map(_tall_aoi(), layout="below")


def test_height_is_capped_at_the_journal_maximum(custom_style):
    very_tall = gpd.GeoDataFrame(
        geometry=[box(250_000, 3_400_000, 260_000, 3_960_000)], crs=UTM
    )  # 10 x 560 km
    fig = eofigs.study_area_map(very_tall, inset=None, legend=False, width="single")
    assert fig.get_size_inches()[1] * 25.4 <= 240.5


def test_overlay_threshold_and_legend(custom_style):
    dem = _dem()
    fig = eofigs.study_area_map(
        _tall_aoi(), dem=dem, overlay=_cover(dem), inset=None, overlay_label="Forest"
    )
    ax = fig.axes[0]
    overlay = [im for im in ax.get_images() if im.get_cmap().N == 1][0]
    shown = overlay.get_array()
    cover = _cover(dem).values
    assert 0.3 < (~shown.mask).mean() < 0.7  # about half of a 0-100 % field is >= 50
    assert np.all(cover.max() > 50)
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert labels == ["Study area", "Forest"]
    result = [r for r in eofigs.check_figure(fig).results if r.name == "overlay contrast"][0]
    assert result.status == "pass"


def test_boolean_and_fraction_overlays(custom_style):
    dem = _dem()
    mask = (_cover(dem) > 60).rio.write_crs(UTM)
    fig = eofigs.study_area_map(_tall_aoi(), overlay=mask, inset=None, legend=False)
    assert any(im.get_cmap().N == 1 for im in fig.axes[0].get_images())
    fraction = (_cover(dem) / 100).rio.write_crs(UTM)
    fraction.attrs = {}
    values = maps._overlay_mask(fraction.values, {}, None)
    assert np.array_equal(values, fraction.values >= 0.5)
    assert np.array_equal(maps._overlay_mask(fraction.values, {}, 0.2), fraction.values >= 0.2)


def test_dem_in_another_crs_is_reprojected(custom_style):
    dem = _dem().rio.reproject("EPSG:4326")
    fig = eofigs.study_area_map(_tall_aoi(), dem=dem, inset=None, legend=False)
    tint = [im for im in fig.axes[0].get_images() if im.get_cmap().N > 1]
    assert len(tint) == 2  # hillshade and elevation colours
    bar_axes = fig.axes[-1]
    assert bar_axes.get_xlabel() == "Elevation (m)"


def test_draw_into_existing_axes(custom_style):
    fig, ax = eofigs.new_figure(
        "double", height_mm=120, subplot_kw={"projection": ccrs.UTM(43)}, layout="none"
    )
    out = eofigs.study_area_map(_tall_aoi(), dem=_dem(), points=_towns(), ax=ax)
    assert out is fig
    assert out.eofigs_layout["layout"] == "inside"
    with pytest.raises(ValueError, match="cartopy GeoAxes"):
        eofigs.study_area_map(_tall_aoi(), ax=eofigs.new_figure("single")[1])


def test_minimal_map_without_extras(custom_style):
    fig = eofigs.study_area_map(
        _tall_aoi(), inset=None, graticule=False, north_arrow=False, scale_bar=False, legend=False
    )
    ax = fig.axes[0]
    assert ax.get_legend() is None and not ax.artists
    assert fig.eofigs_layout["crs"] == "EPSG:32643"


def test_inset_with_own_countries_and_aoi_at_sea(custom_style):
    land = gpd.GeoDataFrame(
        {"code": ["AAA", "BBB"], "name": ["Westland", "Eastland"]},
        geometry=[box(60, 20, 70, 40), box(70, 20, 80, 40)],
        crs="EPSG:4326",
    )
    fig = eofigs.study_area_map(_tall_aoi(), inset=land, legend=False)
    inset = [a for a in fig.axes if hasattr(a, "focus")][0]
    assert inset.focus == ["Eastland"]  # the AOI (72-73 E) lies in Eastland
    sea = gpd.GeoDataFrame(geometry=[box(85, 10, 86, 11)], crs="EPSG:4326")
    fig2, ax2 = eofigs.new_figure("single", subplot_kw={"projection": ccrs.PlateCarree()})
    ax2.set_extent([84, 87, 9, 12], crs=ccrs.PlateCarree())
    assert eofigs.add_inset(ax2, sea, countries=land, loc="lower left").focus == ["Eastland"]
    assert eofigs.add_inset(ax2, sea, countries=land, width_mm=25).focus == ["Eastland"]


def test_default_inset_shows_pakistan_for_swat_area(custom_style):
    aoi = _tall_aoi()
    fig, ax = eofigs.new_figure("single", subplot_kw={"projection": ccrs.UTM(43)})
    ax.set_extent([240_000, 320_000, 3_810_000, 3_970_000], crs=ccrs.UTM(43))
    inset = eofigs.add_inset(ax, aoi)
    assert inset.focus == ["Pakistan"]
    assert maps.inset_aspect(aoi) > 0.5


# ----------------------------------------------------------------------------- labels


def test_labels_avoid_each_other_and_the_outline(custom_style):
    fig = eofigs.study_area_map(_tall_aoi(), points=_towns(), inset=None, legend=False)
    ax = fig.axes[0]
    renderer = fig.canvas.get_renderer()
    texts = [t for t in ax.texts if t.get_text() in ("Lowtown", "Neartown", "Hightown")]
    assert len(texts) == 3
    boxes = [t.get_window_extent(renderer) for t in texts]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            assert not a.overlaps(b)
    outline = maps._outline_pixels(ax, _tall_aoi().geometry, 0.5)
    for b in boxes:
        assert not box(b.x0, b.y0, b.x1, b.y1).intersects(outline)
    assert all(t.get_fontweight() == "bold" for t in texts)
    assert all(t.get_path_effects() for t in texts)


def test_crowded_labels_report_conflicts(custom_style):
    pts = gpd.GeoDataFrame(
        {"name": [f"Town {i}" for i in range(12)]},
        geometry=[Point(270_000 + 300 * i, 3_850_000) for i in range(12)],
        crs=UTM,
    )
    fig = eofigs.study_area_map(_tall_aoi(), points=pts, inset=None, legend=False)
    assert fig.eofigs_layout["labels_clear"] is False


# ----------------------------------------------------------------------------- overlay check


def test_overlay_contrast_numbers():
    batlow = mpl.colormaps["cmc.batlow"]
    sage = overlay_contrast("#A4B9A8", 0.85, batlow, 0.45)
    green = overlay_contrast("#009E73", 0.85, batlow, 0.45)
    assert sage["normal"] < 10 and min(sage["protan"], sage["deutan"]) < 6
    assert green["normal"] >= 10 and min(green[v] for v in ("protan", "deutan", "tritan")) >= 6


def test_overlay_check_warns_for_close_colours(custom_style):
    fig, ax = eofigs.new_figure("single")
    z = np.linspace(0, 1, 100).reshape(10, 10)
    ax.imshow(z, cmap="cmc.batlow", alpha=0.45, zorder=1)
    ax.imshow(np.ma.masked_less(z, 0.5), cmap=ListedColormap(["#A4B9A8"]), alpha=0.85, zorder=2)
    ax.imshow(z, cmap="gray", zorder=0)  # greyscale shading is not compared
    result = [r for r in eofigs.check_figure(fig).results if r.name == "overlay contrast"][0]
    assert result.status == "warn" and "cmc.batlow" in result.message
    assert "gray" not in result.message


def test_no_overlay_no_overlay_check(custom_style):
    fig, ax = eofigs.new_figure("single")
    ax.imshow(np.ones((3, 3)), cmap=ListedColormap(["#009E73"]))
    assert "overlay contrast" not in {r.name for r in eofigs.check_figure(fig).results}


# ----------------------------------------------------------------------------- Swat sample


@pytest.mark.skipif(not SWAT.exists(), reason="Swat sample data are in the repository only")
@pytest.mark.parametrize("width", ["onehalf", "single"])
def test_swat_layout(width, arial_style):
    fig = eofigs.study_area_map(
        SWAT / "swat_boundary.geojson",
        dem=SWAT / "swat_dem_90m.tif",
        overlay=SWAT / "swat_tree_cover_90m.tif",
        points=SWAT / "swat_towns.geojson",
        aoi_label="Swat valley\n(pre-2026 district boundary)",
        overlay_label="Tree cover ≥ 50 %",
        points_label="Town",
        width=width,
    )
    layout = fig.eofigs_layout
    assert layout["labels_clear"] is True  # no label overlaps another label or the outline
    assert layout["layout"] == ("side" if width == "onehalf" else "inside")
    for name, (_, _, empty) in fig._eofigs_layout.items.items():
        if name in ("inset", "legend"):
            assert empty >= maps.MIN_EMPTY
    report = eofigs.check_figure(fig)
    assert report.passed, str(report)
    assert [r.name for r in report.warnings] == [], str(report)


# ----------------------------------------------------------------------------- worldviews


def _worldview_zip(tmp_path) -> bytes:
    gdf = gpd.GeoDataFrame(
        {"ADM0_A3": ["PAK", "IND"], "NAME_EN": ["Pakistan", "India"]},
        geometry=[box(61, 24, 75, 37), box(68, 8, 97, 35)],
        crs="EPSG:4326",
    )
    folder = tmp_path / "shp"
    folder.mkdir()
    gdf.to_file(folder / "ne_10m_admin_0_countries_pak.shp")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in folder.iterdir():
            archive.write(path, path.name)
    return buffer.getvalue()


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_worldview_download_is_verified_and_cached(tmp_path, monkeypatch):
    data = _worldview_zip(tmp_path)
    monkeypatch.setenv("EOFIGS_CACHE", str(tmp_path / "cache"))
    monkeypatch.setitem(_countries.WORLDVIEW_SHA256, "pak", hashlib.sha256(data).hexdigest())
    calls = []

    def fake_urlopen(url, timeout=None):
        calls.append(url)
        return _Response(data)

    monkeypatch.setattr(_countries.urllib.request, "urlopen", fake_urlopen)
    world = _countries.countries("PAK")
    assert list(world["code"]) == ["PAK", "IND"]
    assert calls == [_countries.worldview_url("pak")]
    assert "naturalearth/5.1.2/10m/cultural/ne_10m_admin_0_countries_pak.zip" in calls[0]
    _countries.countries("pak")  # cached: no second download
    assert len(calls) == 1
    assert (tmp_path / "cache" / "ne_5.1.2_countries_pak.geojson").exists()


def test_worldview_checksum_mismatch(tmp_path, monkeypatch):
    monkeypatch.setenv("EOFIGS_CACHE", str(tmp_path / "cache"))
    monkeypatch.setitem(_countries.WORLDVIEW_SHA256, "ind", "0" * 64)
    monkeypatch.setattr(
        _countries.urllib.request, "urlopen", lambda url, timeout=None: _Response(b"not a zip")
    )
    with pytest.raises(RuntimeError, match="does not match its checksum"):
        _countries.countries("IND")
    assert not (tmp_path / "cache" / "ne_5.1.2_countries_ind.geojson").exists()


def test_worldview_offline_error(tmp_path, monkeypatch):
    monkeypatch.setenv("EOFIGS_CACHE", str(tmp_path / "cache"))

    def offline(url, timeout=None):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(_countries.urllib.request, "urlopen", offline)
    with pytest.raises(RuntimeError, match="Offline, use worldview=None"):
        _countries.countries("CHN")


def test_worldview_codes_and_checksums():
    assert len(_countries.WORLDVIEWS) == 33
    assert set(_countries.WORLDVIEW_SHA256) == set(_countries.WORLDVIEWS)
    assert all(len(v) == 64 for v in _countries.WORLDVIEW_SHA256.values())
    with pytest.raises(ValueError, match="Unknown worldview"):
        _countries.countries("XYZ")


def test_missing_checksum(tmp_path, monkeypatch):
    monkeypatch.setenv("EOFIGS_CACHE", str(tmp_path / "cache"))
    monkeypatch.delitem(_countries.WORLDVIEW_SHA256, "usa")
    with pytest.raises(RuntimeError, match="No checksum"):
        _countries.countries("USA")


@pytest.mark.parametrize(
    ("platform", "env", "expected"),
    [
        ("win32", {"LOCALAPPDATA": "/data/local"}, "/data/local/eofigs/Cache"),
        ("darwin", {}, "Library/Caches/eofigs"),
        ("linux", {"XDG_CACHE_HOME": "/xdg"}, "/xdg/eofigs"),
    ],
)
def test_cache_dir_per_platform(platform, env, expected, monkeypatch):
    monkeypatch.delenv("EOFIGS_CACHE", raising=False)
    for key in ("LOCALAPPDATA", "XDG_CACHE_HOME"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(_countries.sys, "platform", platform)
    assert _countries.cache_dir().as_posix().endswith(expected)


def test_bundled_countries():
    world = _countries.countries()
    assert world.crs.to_epsg() == 4326
    assert {"code", "name"} <= set(world.columns)
    assert len(world) == 177
    assert "PAK" in set(world["code"])


# ----------------------------------------------------------------------------- fit_raster URLs


def test_fit_raster_reads_urls(tmp_path, monkeypatch):
    import rasterio

    local = tmp_path / "dem.tif"
    _dem().rio.to_raster(local)
    opened = []
    real_open = rasterio.open

    def fake_open(path, *args, **kwargs):
        opened.append(path)
        return real_open(local if str(path).startswith("https://") else path, *args, **kwargs)

    monkeypatch.setattr(rasterio, "open", fake_open)
    out = eofigs.fit_raster("https://example.org/data/dem.tif?token=x", width_mm=20, dpi=100)
    assert opened == ["https://example.org/data/dem.tif?token=x"]
    assert out.name == "dem"
    assert out.shape[1] <= 160
