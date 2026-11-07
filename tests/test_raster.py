import time

import numpy as np
import pytest
import rasterio
import rioxarray  # noqa: F401
import xarray as xr
from rasterio.transform import from_origin

from eofigs import fit_raster
from eofigs.raster import _mode_last_axes, pixel_budget


def _grid(values, res=30.0, crs="EPSG:32643", x0=500000.0, y0=3900000.0):
    ny, nx = values.shape[-2:]
    x = x0 + (np.arange(nx) + 0.5) * res
    y = y0 - (np.arange(ny) + 0.5) * res
    da = xr.DataArray(values, dims=("y", "x"), coords={"y": y, "x": x})
    return da.rio.write_crs(crs) if crs else da


def test_pixel_budget():
    assert pixel_budget(90, 60, 600) == (2126, 1417)
    assert pixel_budget(25.4, None, 100) == (100, None)
    with pytest.raises(ValueError, match="positive"):
        pixel_budget(0, None, 600)


def test_factor_from_width_and_height():
    da = _grid(np.ones((1000, 800)))
    # width only: 50 mm at 100 dpi = 197 px -> factor 800/197 = 4.06 -> k = 4
    assert fit_raster(da, 50, dpi=100).shape == (250, 200)
    # height limits: 40 mm = 157 px -> 1000/157 = 6.4 -> k = 6
    assert fit_raster(da, 50, height_mm=40, dpi=100).shape == (166, 133)


def test_output_never_has_fewer_pixels_than_needed():
    da = _grid(np.ones((3000, 3000)))
    out = fit_raster(da, 90, dpi=300)
    assert out.sizes["x"] >= pixel_budget(90, None, 300)[0]


def test_no_upsampling():
    da = _grid(np.arange(12.0).reshape(3, 4))
    assert fit_raster(da, 190, dpi=600) is da


def test_mean_ignores_nan_and_applies_min_valid():
    values = np.array(
        [
            [1.0, 3.0, 1.0, np.nan],
            [5.0, np.nan, np.nan, np.nan],
            [2.0, 2.0, 0.0, 0.0],
            [2.0, 2.0, 0.0, 0.0],
        ]
    )
    out = fit_raster(_grid(values), width_mm=25.4, dpi=2)  # 2 px wide -> factor 2
    assert out.shape == (2, 2)
    assert out.values[0, 0] == pytest.approx(3.0)  # mean of 1, 3, 5 (3 of 4 valid)
    assert np.isnan(out.values[0, 1])  # 1 of 4 valid < 0.5
    assert out.values[1, 0] == 2.0
    assert out.values[1, 1] == 0.0
    loose = fit_raster(_grid(values), width_mm=25.4, dpi=2, min_valid=0.25)
    assert loose.values[0, 1] == 1.0


def test_encoded_nodata_is_ignored():
    values = np.array([[10, 20], [-9999, -9999]], dtype="int16")
    da = _grid(values).rio.write_nodata(-9999)
    out = fit_raster(da, width_mm=25.4, dpi=1, min_valid=0.5)
    assert out.shape == (1, 1) and out.values[0, 0] == 15.0


def test_mask_fraction():
    mask = np.zeros((4, 4), dtype=bool)
    mask[:2, :2] = [[True, True], [True, False]]
    out = fit_raster(_grid(mask), width_mm=25.4, dpi=2)
    assert out.attrs["eofigs_reduction"]["method"] == "fraction"
    assert out.values[0, 0] == pytest.approx(0.75)
    assert out.values[1, 1] == 0.0


def test_categorical_mode():
    classes = np.array(
        [
            [1, 1, 2, 2],
            [1, 3, 2, 3],
            [4, 4, 5, 6],
            [4, 7, 5, 6],
        ]
    )
    da = _grid(classes)
    da.attrs["flag_values"] = [1, 2, 3, 4, 5, 6, 7]
    out = fit_raster(da, width_mm=25.4, dpi=2)
    assert out.attrs["eofigs_reduction"]["method"] == "mode"
    np.testing.assert_array_equal(out.values, [[1, 2], [4, 5]])  # 5 vs 6 tie -> smaller


def test_mode_helper_handles_nan_and_empty_blocks():
    block = np.array([[[[np.nan, 2.0], [2.0, 3.0]], [[np.nan, np.nan], [np.nan, np.nan]]]])
    result = _mode_last_axes(block)
    assert result[0, 0] == 2.0 and np.isnan(result[0, 1])


def test_kind_from_variable_library_and_override():
    da = _grid(np.ones((4, 4)))
    da.name = "ndvi"
    assert fit_raster(da, 25.4, dpi=2).attrs["eofigs_reduction"]["method"] == "mean"
    out = fit_raster(da, 25.4, dpi=2, kind="categorical")
    assert out.attrs["eofigs_reduction"]["method"] == "mode"


def test_crs_and_transform_are_kept():
    da = _grid(np.ones((100, 100)), res=30.0)
    out = fit_raster(da, 25.4, dpi=20)  # 20 px -> factor 5
    assert out.rio.crs.to_epsg() == 32643
    assert out.rio.resolution() == pytest.approx((150.0, -150.0))
    assert out.rio.bounds() == pytest.approx(da.rio.bounds())
    assert out.attrs["eofigs_reduction"]["factor"] == 5


def test_dask_input_stays_lazy():
    pytest.importorskip("dask")
    values = np.random.default_rng(0).random((400, 600))
    da = _grid(values).chunk({"y": 100, "x": 150})
    out = fit_raster(da, 25.4, dpi=60)  # 60 px -> factor 10
    assert out.chunks is not None
    expected = fit_raster(_grid(values), 25.4, dpi=60)
    np.testing.assert_allclose(out.values, expected.values)
    classes = _grid(np.random.default_rng(1).integers(0, 4, (400, 600))).chunk({"y": 100, "x": 150})
    lazy_mode = fit_raster(classes, 25.4, dpi=60, kind="categorical")
    eager_mode = fit_raster(classes.compute(), 25.4, dpi=60, kind="categorical")
    np.testing.assert_array_equal(lazy_mode.values, eager_mode.values)


def test_dataset_input():
    ds = xr.Dataset({"ndvi": _grid(np.ones((100, 100))), "scale": ((), 2.0)})
    ds = ds.rio.write_crs("EPSG:32643")
    out = fit_raster(ds, 25.4, dpi=20)
    assert out["ndvi"].shape == (20, 20)
    assert float(out["scale"]) == 2.0
    with pytest.raises(ValueError, match="no variables with spatial dimensions"):
        fit_raster(xr.Dataset({"scale": ((), 1.0)}), 25.4)


def test_input_errors():
    with pytest.raises(ValueError, match="has no CRS"):
        fit_raster(_grid(np.ones((10, 10)), crs=None), 25.4, dpi=2)
    with pytest.raises(ValueError, match="spatial dimensions"):
        fit_raster(xr.DataArray(np.ones((4, 4)), dims=("a", "b")), 25.4, dpi=2)
    with pytest.raises(ValueError, match="min_valid"):
        fit_raster(_grid(np.ones((4, 4))), 25.4, min_valid=2)
    with pytest.raises(ValueError, match="kind must be one of"):
        fit_raster(_grid(np.ones((4, 4))), 25.4, kind="median")
    with pytest.raises(TypeError, match="takes a file path"):
        fit_raster(np.ones((4, 4)), 25.4)


# ----------------------------------------------------------------------------- files


def _write_tif(path, values, crs="EPSG:32643", nodata=None, colormap=None):
    ny, nx = values.shape
    profile = {
        "driver": "GTiff",
        "height": ny,
        "width": nx,
        "count": 1,
        "dtype": values.dtype.name,
        "transform": from_origin(500000, 3900000, 30, 30),
        "nodata": nodata,
    }
    if crs:
        profile["crs"] = crs
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(values, 1)
        dst.set_band_description(1, "test band")
        dst.set_band_unit(1, "m")
        if colormap:
            dst.write_colormap(1, colormap)
    return path


def test_file_mean_with_nodata(tmp_path):
    values = np.full((40, 60), 2.0, dtype="float32")
    values[:20, :30] = 4.0
    values[20:, 30:] = -9999  # nodata quarter
    path = _write_tif(tmp_path / "a.tif", values, nodata=-9999)
    out = fit_raster(path, 25.4, dpi=6)  # 6 px wide -> factor 10
    assert out.shape == (4, 6)
    assert out.values[0, 0] == pytest.approx(4.0)
    assert out.values[3, 0] == pytest.approx(2.0)
    assert np.isnan(out.values[3, 5])
    assert out.rio.crs.to_epsg() == 32643
    assert out.rio.resolution() == pytest.approx((300.0, -300.0))
    assert out.attrs["long_name"] == "test band" and out.attrs["units"] == "m"
    assert out.attrs["eofigs_reduction"]["source_shape"] == [40, 60]


def test_file_small_raster_read_at_full_resolution(tmp_path):
    path = _write_tif(tmp_path / "s.tif", np.ones((5, 6), dtype="float32"))
    assert fit_raster(str(path), 190, dpi=600).shape == (5, 6)


def test_file_categorical_from_colour_table(tmp_path):
    values = np.zeros((20, 20), dtype="uint8")
    values[:, 10:] = 3
    values[:10, :7] = 1
    path = _write_tif(tmp_path / "c.tif", values, colormap={0: (0, 0, 0, 255), 1: (255, 0, 0, 255)})
    out = fit_raster(path, 25.4, dpi=2)
    assert out.attrs["eofigs_reduction"]["method"] == "mode"
    np.testing.assert_array_equal(out.values, [[1, 3], [0, 3]])


def test_file_mask_fraction(tmp_path):
    values = np.zeros((10, 10), dtype="uint8")
    values[:5, :5] = 1
    path = _write_tif(tmp_path / "m.tif", values)
    out = fit_raster(path, 25.4, dpi=1, kind="mask")
    assert out.values[0, 0] == pytest.approx(0.25)


def test_file_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        fit_raster(tmp_path / "missing.tif", 25.4)
    path = _write_tif(tmp_path / "nocrs.tif", np.ones((4, 4), dtype="float32"), crs=None)
    with pytest.raises(ValueError, match="has no CRS"):
        fit_raster(path, 25.4, dpi=1)


def test_file_integer_average_is_not_rounded(tmp_path):
    values = np.array([[1, 2], [2, 2]], dtype="int16")
    path = _write_tif(tmp_path / "i.tif", values)
    assert fit_raster(path, 25.4, dpi=1).values[0, 0] == pytest.approx(1.75)


def test_file_byte_average_is_exact(tmp_path):
    rng = np.random.default_rng(0)
    values = (rng.random((100, 120)) < 0.3).astype("uint8")
    values[:10, :10] = 255  # nodata block
    path = _write_tif(tmp_path / "b.tif", values, nodata=255)
    out = fit_raster(path, 25.4, dpi=12, kind="mask")  # 12 px -> factor 10
    expected = values[10:].reshape(9, 10, 12, 10).mean(axis=(1, 3))  # block rows without nodata
    np.testing.assert_allclose(out.values[1:], expected, atol=1e-6)
    assert np.isnan(out.values[0, 0])
    assert out.rio.resolution() == pytest.approx((300.0, -300.0))


@pytest.mark.slow
@pytest.mark.parametrize("dtype", ["float32", "int16"])
def test_large_raster_is_fast_and_bounded(tmp_path, dtype):
    """10 000 x 10 000 GeoTIFF (no overviews) drawn at double-column width.

    float32 uses GDAL's average at the output size; int16 (for example scaled NDVI) uses the
    exact strip averaging.
    """
    path = tmp_path / "big.tif"
    n, block = 10_000, 1_000
    profile = {
        "driver": "GTiff", "height": n, "width": n, "count": 1, "dtype": dtype,
        "crs": "EPSG:32643", "transform": from_origin(500000, 3900000, 10, 10),
        "tiled": True, "blockxsize": 512, "blockysize": 512, "compress": "deflate",
    }  # fmt: skip
    x = np.linspace(0, 20, n)
    with rasterio.open(path, "w", **profile) as dst:
        for row in range(0, n, block):
            y = np.linspace(row / n * 20, (row + block) / n * 20, block)
            values = np.sin(x)[None, :] * np.cos(y)[:, None]
            if dtype == "int16":
                values = np.round(values * 10_000)  # scaled like Landsat NDVI
            dst.write(values.astype(dtype), 1, window=((row, row + block), (0, n)))
    start = time.perf_counter()
    out = fit_raster(path, width_mm=190, dpi=600)
    elapsed = time.perf_counter() - start
    print(f"fit_raster 10000x10000 {dtype} -> {out.shape} in {elapsed:.2f} s")
    budget = pixel_budget(190, None, 600)[0]
    assert out.shape[1] >= budget  # at least the printed pixels
    assert out.shape[1] < 2 * budget
    assert out.dtype == np.float32  # 2- and 4-byte sources give float32
    assert elapsed < 10
