"""Reduce rasters to the pixels a printed figure needs (the pixel budget)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from eofigs._presets import MM_PER_INCH

REDUCTIONS = ("continuous", "categorical", "mask")
_METHOD = {"continuous": "mean", "categorical": "mode", "mask": "fraction"}


def pixel_budget(width_mm: float, height_mm: float | None, dpi: float) -> tuple[int, int | None]:
    """Count the printed pixels across (and down) a figure area.

    Parameters
    ----------
    width_mm : float
        Printed width of the map area in mm.
    height_mm : float, optional
        Printed height in mm; ``None`` constrains the width only.
    dpi : float
        Output resolution.

    Returns
    -------
    (int, int or None)
        Pixels across and down.

    Examples
    --------
    >>> from eofigs.raster import pixel_budget
    >>> pixel_budget(90, 60, 600)
    (2126, 1417)
    """
    if width_mm <= 0 or dpi <= 0 or (height_mm is not None and height_mm <= 0):
        raise ValueError("width_mm, height_mm and dpi must be positive.")
    width_px = max(1, round(width_mm / MM_PER_INCH * dpi))
    height_px = None if height_mm is None else max(1, round(height_mm / MM_PER_INCH * dpi))
    return width_px, height_px


def _factor(ny: int, nx: int, width_px: int, height_px: int | None) -> float:
    """Source pixels per printed pixel when the raster fits inside the budget box."""
    factor = nx / width_px
    if height_px is not None:
        factor = max(factor, ny / height_px)
    return factor


def fit_raster(
    data: Any,
    width_mm: float,
    height_mm: float | None = None,
    dpi: float = 600,
    kind: str | None = None,
    min_valid: float = 0.5,
    band: int = 1,
) -> Any:
    """Reduce a raster to the resolution of the printed figure.

    A map printed 90 mm wide at 600 dpi shows about 2 100 pixels across, however large
    the raster is. ``fit_raster`` reads or aggregates the raster to that size before
    plotting, so large rasters fit in memory, plot quickly and give small vector PDFs.
    It never upsamples.

    Parameters
    ----------
    data : str, pathlib.Path, xarray.DataArray or xarray.Dataset
        A GeoTIFF/COG path, or a georeferenced DataArray/Dataset (rioxarray CRS set).
        Arrays may be dask-backed; the result then stays lazy.
    width_mm : float
        Printed width of the map area in mm.
    height_mm : float, optional
        Printed height in mm; if given, the raster fits inside width x height.
    dpi : float, default 600
        Output resolution.
    kind : {"continuous", "categorical", "mask"}, optional
        Reduction: mean of valid pixels (continuous), most frequent class (categorical)
        or fraction of True pixels (mask, e.g. p < 0.05). Inferred if omitted: boolean
        data are masks; data with ``flag_values`` attributes, a GeoTIFF colour table or
        a categorical library variable are categorical; everything else is continuous.
    min_valid : float, default 0.5
        Minimum fraction of valid (not nodata/NaN) source pixels; output pixels with
        fewer valid pixels are NaN.
    band : int, default 1
        Band to read from a file.

    Returns
    -------
    xarray.DataArray or xarray.Dataset
        The reduced raster with CRS and transform. ``attrs["eofigs_reduction"]``
        records the method, factor and source shape.

    Raises
    ------
    ValueError
        For a raster without a CRS, an unknown ``kind``, ``min_valid`` outside 0-1, or
        a rotated GeoTIFF.
    FileNotFoundError
        If the file does not exist.

    Notes
    -----
    Files are read with ``rasterio`` at the output size, so GDAL uses overviews when the
    file has them and never loads the full-resolution array. Pre-built overviews keep
    the resampling they were built with (often nearest or average), which then applies
    instead of ``kind``. Arrays are aggregated by an integer factor; up to factor - 1
    edge rows and columns (less than one printed pixel) are dropped so the grid stays
    regular.

    Examples
    --------
    >>> import numpy as np, xarray as xr, rioxarray  # noqa: F401
    >>> from eofigs import fit_raster
    >>> da = xr.DataArray(np.ones((4000, 6000)), dims=("y", "x"),
    ...                   coords={"y": np.arange(4000.0)[::-1], "x": np.arange(6000.0)})
    >>> da = da.rio.write_crs("EPSG:32643")
    >>> fit_raster(da, width_mm=90, dpi=300).shape  # 1063 px needed; factor 5 keeps 1200
    (800, 1200)
    """
    if not 0 <= min_valid <= 1:
        raise ValueError(f"min_valid must be between 0 and 1 (got {min_valid}).")
    if kind is not None and kind not in REDUCTIONS:
        raise ValueError(f"kind must be one of {REDUCTIONS} (got {kind!r}).")
    width_px, height_px = pixel_budget(width_mm, height_mm, dpi)
    if isinstance(data, str | Path):
        return _fit_file(Path(data), width_px, height_px, kind, min_valid, band)
    if isinstance(data, xr.Dataset):
        fitted = {
            name: _fit_array(da, width_px, height_px, kind, min_valid)
            for name, da in data.data_vars.items()
            if _has_spatial_dims(da)
        }
        if not fitted:
            raise ValueError("The Dataset has no variables with spatial dimensions.")
        out = xr.Dataset(fitted, attrs=dict(data.attrs))
        for name, da in data.data_vars.items():
            if name not in fitted:
                out[name] = da
        return out
    if isinstance(data, xr.DataArray):
        return _fit_array(data, width_px, height_px, kind, min_valid)
    raise TypeError(
        f"fit_raster takes a file path, DataArray or Dataset (got {type(data).__name__})."
    )


# ----------------------------------------------------------------------------- arrays


def _has_spatial_dims(da: xr.DataArray) -> bool:
    try:
        return da.rio.x_dim in da.dims and da.rio.y_dim in da.dims
    except Exception:  # rioxarray raises when it cannot find spatial dimensions
        return False


def _infer_kind(da: xr.DataArray, kind: str | None) -> str:
    if kind is not None:
        return kind
    if da.dtype == bool:
        return "mask"
    if "flag_values" in da.attrs or "flag_meanings" in da.attrs:
        return "categorical"
    from eofigs.variables import variable

    try:
        var_kind = variable(da).kind
    except ValueError:
        return "continuous"
    return var_kind if var_kind in ("categorical", "mask") else "continuous"


def _fit_array(
    da: xr.DataArray, width_px: int, height_px: int | None, kind: str | None, min_valid: float
) -> xr.DataArray:
    import rioxarray  # noqa: F401  (registers the .rio accessor)

    if not _has_spatial_dims(da):
        raise ValueError(
            "Could not find the spatial dimensions (x/y or lon/lat). "
            "Name them, or set them with da.rio.set_spatial_dims(x_dim=..., y_dim=...)."
        )
    crs = da.rio.crs
    if crs is None:
        raise ValueError(
            "The raster has no CRS. Set it explicitly, for example "
            "da.rio.write_crs('EPSG:4326'); eofigs never assumes a CRS."
        )
    method = _infer_kind(da, kind)
    x_dim, y_dim = da.rio.x_dim, da.rio.y_dim
    ny, nx = da.sizes[y_dim], da.sizes[x_dim]
    k = int(math.floor(_factor(ny, nx, width_px, height_px)))
    if k <= 1:
        return da
    window = {x_dim: k, y_dim: k}
    values = da.astype("float64") if method == "mask" or da.dtype == bool else da
    nodata = da.rio.nodata
    if nodata is not None and not (isinstance(nodata, float) and math.isnan(nodata)):
        values = values.where(values != nodata)
    coarse = values.coarsen(window, boundary="trim")
    if method == "categorical":
        reduced = _coarsen_mode(values, window)
    else:
        reduced = coarse.mean()  # NaN-skipping for float data
    valid_fraction = coarse.count() / (k * k)
    out = reduced.where(valid_fraction >= min_valid)
    out.attrs = dict(da.attrs)
    out.attrs["eofigs_reduction"] = {
        "method": _METHOD[method],
        "factor": k,
        "source_shape": [ny, nx],
        "min_valid": min_valid,
    }
    out = out.rio.write_crs(crs)
    return out.rio.write_transform(out.rio.transform(recalc=True))


def _coarsen_mode(da: xr.DataArray, window: dict[str, int]) -> xr.DataArray:
    x_dim, y_dim = list(window)
    blocks = da.coarsen(window, boundary="trim").construct(
        {x_dim: (x_dim, "_eofigs_kx"), y_dim: (y_dim, "_eofigs_ky")}
    )
    mode = xr.apply_ufunc(
        _mode_last_axes,
        blocks,
        input_core_dims=[["_eofigs_ky", "_eofigs_kx"]],
        dask="parallelized",
        output_dtypes=[float],
        dask_gufunc_kwargs={"allow_rechunk": True},
    )
    coords = {
        x_dim: da[x_dim].coarsen({x_dim: window[x_dim]}, boundary="trim").mean(),
        y_dim: da[y_dim].coarsen({y_dim: window[y_dim]}, boundary="trim").mean(),
    }
    return mode.assign_coords(coords)


def _mode_last_axes(values: np.ndarray) -> np.ndarray:
    """Most frequent non-NaN value over the last two axes (smallest value on ties)."""
    flat = values.reshape(*values.shape[:-2], -1).astype("float64")
    ordered = np.sort(flat, axis=-1)  # NaN sorts last
    n = ordered.shape[-1]
    index = np.arange(n)
    starts = np.ones(ordered.shape, dtype=bool)
    starts[..., 1:] = ordered[..., 1:] != ordered[..., :-1]
    run_start = np.maximum.accumulate(np.where(starts, index, 0), axis=-1)
    run_length = np.where(np.isnan(ordered), 0, index - run_start + 1)
    best = np.argmax(run_length, axis=-1)
    result = np.take_along_axis(ordered, best[..., None], axis=-1)[..., 0]
    return np.where(run_length.max(axis=-1) > 0, result, np.nan)


# ----------------------------------------------------------------------------- files


def _fit_file(
    path: Path, width_px: int, height_px: int | None, kind: str | None, min_valid: float, band: int
) -> xr.DataArray:
    import rasterio
    import rioxarray  # noqa: F401

    if not path.exists():
        raise FileNotFoundError(path)
    with rasterio.open(path) as src:
        if src.crs is None:
            raise ValueError(
                f"{path.name} has no CRS. Assign one first (for example with "
                "'gdal_edit.py -a_srs EPSG:4326' or rioxarray's write_crs); "
                "eofigs never assumes a CRS."
            )
        if not src.transform.is_rectilinear:
            raise ValueError(f"{path.name} has a rotated transform; warp it first.")
        method = kind or _file_kind(src, band)
        factor = _factor(src.height, src.width, width_px, height_px)
        dtype = np.dtype(src.dtypes[band - 1])
        out_dtype = "float32" if dtype.itemsize <= 4 else "float64"
        if factor > 1 and dtype == np.uint8 and method != "categorical":
            # GDAL rounds averages of 8-bit data to integers; aggregate exactly in strips
            array, transform = _read_strips(src, band, int(math.floor(factor)), min_valid)
        else:
            array, transform = _read_gdal(src, band, factor, method, min_valid)
        array = array.astype(out_dtype)
        attrs = {"long_name": src.descriptions[band - 1] or path.stem}
        if src.units and src.units[band - 1]:
            attrs["units"] = src.units[band - 1]
        crs, source_shape = src.crs, [src.height, src.width]

    out_h, out_w = array.shape
    x = transform.c + (np.arange(out_w) + 0.5) * transform.a
    y = transform.f + (np.arange(out_h) + 0.5) * transform.e
    attrs["eofigs_reduction"] = {
        "method": _METHOD[method],
        "factor": round(_src_factor(source_shape, (out_h, out_w)), 3),
        "source_shape": source_shape,
        "min_valid": min_valid,
    }
    out = xr.DataArray(array, dims=("y", "x"), coords={"y": y, "x": x}, name=path.stem, attrs=attrs)
    out = out.rio.write_crs(crs)
    return out.rio.write_transform(transform)


def _read_gdal(src: Any, band: int, factor: float, method: str, min_valid: float):
    """Read at the output size with GDAL resampling (uses overviews when present)."""
    from affine import Affine
    from rasterio.enums import Resampling

    if factor > 1:
        out_h = max(1, math.ceil(src.height / factor))
        out_w = max(1, math.ceil(src.width / factor))
    else:
        out_h, out_w = src.height, src.width
    resampling = Resampling.mode if method == "categorical" else Resampling.average
    out_dtype = None if method == "categorical" else "float64"
    values = src.read(
        band, out_shape=(out_h, out_w), resampling=resampling, masked=True, out_dtype=out_dtype
    )
    valid = src.read_masks(band, out_shape=(out_h, out_w), resampling=Resampling.average)
    array = np.ma.filled(values.astype("float64"), np.nan)
    array[valid / 255.0 < min_valid] = np.nan
    transform = src.transform @ Affine.scale(src.width / out_w, src.height / out_h)
    return array, transform


def _read_strips(src: Any, band: int, k: int, min_valid: float, max_pixels: int = 2**24):
    """Average k x k blocks exactly, reading a few rows of blocks at a time."""
    from affine import Affine
    from rasterio.windows import Window

    out_h, out_w = src.height // k, src.width // k
    array = np.full((out_h, out_w), np.nan)
    rows_per_read = max(1, max_pixels // (k * k * out_w))
    for row in range(0, out_h, rows_per_read):
        rows = min(rows_per_read, out_h - row)
        window = Window(0, row * k, out_w * k, rows * k)
        block = src.read(band, window=window, masked=True).astype("float64").filled(np.nan)
        block = block.reshape(rows, k, out_w, k)
        count = np.sum(~np.isnan(block), axis=(1, 3))
        total = np.nansum(block, axis=(1, 3))
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = total / count
        mean[count / (k * k) < min_valid] = np.nan
        array[row : row + rows] = mean
    return array, src.transform @ Affine.scale(k, k)


def _src_factor(source_shape: list[int], out_shape: tuple[int, int]) -> float:
    """Reduction factor between a source and an output shape (largest axis ratio)."""
    return max(source_shape[0] / out_shape[0], source_shape[1] / out_shape[1])


def _file_kind(src: Any, band: int) -> str:
    try:
        src.colormap(band)
    except ValueError:
        return "continuous"
    return "categorical"
