"""Trend statistics: Theil–Sen slope and Mann–Kendall test on time-series cubes."""

from __future__ import annotations

import numpy as np
import xarray as xr
from scipy.special import ndtr

DAYS_PER_YEAR = 365.2425
_PER_YEARS = {"year": 1.0, "decade": 10.0}


def trend(
    data: xr.DataArray,
    dim: str = "time",
    per: str = "decade",
    alpha: float = 0.05,
    min_valid: int = 8,
    memory_mb: float = 256,
) -> xr.Dataset:
    """Theil–Sen slope and Mann–Kendall significance for every pixel of a time series.

    Parameters
    ----------
    data : xarray.DataArray
        Values with a datetime coordinate along ``dim``; any other dimensions (for
        example ``y`` and ``x``) are treated as independent series. numpy or dask.
    dim : str, default "time"
        Time dimension. Its coordinate must be datetime64; slopes are computed against
        the real dates in years, so gaps and irregular steps are handled.
    per : {"decade", "year"}, default "decade"
        Unit of the slope.
    alpha : float, default 0.05
        Significance level for the ``significant`` mask.
    min_valid : int, default 8
        Minimum number of valid (non-NaN) observations; pixels with fewer get NaN.
    memory_mb : float, default 256
        Memory budget for the pairwise slopes. Pixels are processed in blocks that fit
        this budget, so any series length works; long series are only slower.

    Returns
    -------
    xarray.Dataset
        ``slope`` (data units per ``per``), ``intercept`` (value at the first time
        step), ``pvalue`` (two-sided Mann–Kendall), ``significant`` (``pvalue < alpha``)
        and ``n_valid``. Spatial coordinates and CRS are kept.

    Raises
    ------
    ValueError
        If ``dim`` is missing or not a datetime coordinate, or an argument is invalid.

    Notes
    -----
    The slope is the median of all pairwise slopes (Sen 1968) and the intercept is the
    median of ``y - slope * t`` (``scipy.stats.theilslopes(method="joint")``). The
    Mann–Kendall statistic S uses the variance with the tie correction and the continuity
    correction for Z (Kendall 1975). Observations are assumed serially independent: no
    correction for autocorrelation is applied (modified Mann–Kendall or prewhitening are
    not part of v0.1), and seasonality is not removed, so monthly data should be
    deseasonalised or aggregated to annual values first. Memory grows with the number of
    pairs, n(n-1)/2, per pixel; time grows with pixels x pairs.

    Examples
    --------
    >>> import numpy as np, pandas as pd, xarray as xr
    >>> from eofigs import trend
    >>> time = pd.date_range("2001-01-01", periods=20, freq="YS")
    >>> da = xr.DataArray(0.02 * np.arange(20.0), dims="time", coords={"time": time})
    >>> result = trend(da, per="decade")
    >>> round(float(result.slope), 3), bool(result.significant)
    (0.2, True)
    """
    if per not in _PER_YEARS:
        raise ValueError(f"per must be one of {tuple(_PER_YEARS)} (got {per!r}).")
    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be between 0 and 1 (got {alpha}).")
    if min_valid < 3:
        raise ValueError(f"min_valid must be at least 3 (got {min_valid}).")
    if memory_mb <= 0:
        raise ValueError("memory_mb must be positive.")
    if dim not in data.dims:
        raise ValueError(f"No dimension {dim!r}; dimensions are {list(data.dims)}.")
    if dim not in data.coords or not np.issubdtype(data[dim].dtype, np.datetime64):
        raise ValueError(
            f"The {dim!r} coordinate must hold dates (datetime64); slopes are computed against "
            "real time. Convert it, for example with pd.to_datetime, or assign dates."
        )
    data = data.sortby(dim)
    years = (data[dim].values - data[dim].values[0]) / np.timedelta64(1, "D") / DAYS_PER_YEAR
    if np.any(np.diff(years) <= 0):
        raise ValueError(f"The {dim!r} coordinate has duplicate dates.")

    values = data.astype("float64")
    if values.chunks is not None:
        values = values.chunk({dim: -1})
    slope, intercept, pvalue, n_valid = xr.apply_ufunc(
        _trend_block_array,
        values,
        input_core_dims=[[dim]],
        output_core_dims=[[], [], [], []],
        kwargs={"years": years, "min_valid": min_valid, "memory_mb": memory_mb},
        dask="parallelized",
        output_dtypes=[float, float, float, float],
    )
    scale = _PER_YEARS[per]
    units = data.attrs.get("units", "")
    out = xr.Dataset(
        {
            "slope": (slope * scale).assign_attrs(
                long_name="Theil-Sen slope", units=f"{units} per {per}".strip(), per=per
            ),
            "intercept": intercept.assign_attrs(
                long_name="Theil-Sen intercept at the first time step", units=units
            ),
            "pvalue": pvalue.assign_attrs(long_name="Mann-Kendall p-value (two-sided)"),
            "significant": (pvalue < alpha).assign_attrs(long_name=f"p < {alpha}"),
            "n_valid": n_valid.assign_attrs(long_name="Number of valid observations"),
        },
        attrs={
            "method": "Theil-Sen slope, Mann-Kendall test (tie and continuity corrected)",
            "autocorrelation": "not corrected",
            "alpha": alpha,
            "min_valid": min_valid,
            "time_start": str(data[dim].values[0])[:10],
            "time_end": str(data[dim].values[-1])[:10],
            "source_variable": str(data.name) if data.name is not None else "",
        },
    )
    return out


def _trend_block_array(
    values: np.ndarray, years: np.ndarray, min_valid: int, memory_mb: float
) -> tuple[np.ndarray, ...]:
    """Apply the trend to an array whose last axis is time, in memory-bounded blocks."""
    shape = values.shape[:-1]
    n = values.shape[-1]
    flat = values.reshape(-1, n)
    pairs = n * (n - 1) // 2
    # three float64 arrays of pixels x pairs are alive at once
    block = max(1, int(memory_mb * 2**20 // (3 * 8 * max(pairs, 1))))
    out = np.full((4, flat.shape[0]), np.nan)
    i, j = np.triu_indices(n, k=1)
    dt = years[j] - years[i]
    for start in range(0, flat.shape[0], block):
        rows = flat[start : start + block]
        out[:, start : start + block] = _trend_rows(rows, years, i, j, dt, min_valid)
    return tuple(part.reshape(shape) for part in out)


def _trend_rows(
    y: np.ndarray, years: np.ndarray, i: np.ndarray, j: np.ndarray, dt: np.ndarray, min_valid: int
) -> np.ndarray:
    n_valid = np.sum(~np.isnan(y), axis=1).astype("float64")
    result = np.full((4, y.shape[0]), np.nan)
    result[3] = n_valid
    keep = n_valid >= min_valid
    if not keep.any():
        return result
    y = y[keep]
    k = n_valid[keep]

    dy = y[:, j] - y[:, i]  # NaN when either observation is missing
    slope = _row_median(dy / dt)
    intercept = np.nanmedian(y - slope[:, None] * years[None, :], axis=1)

    s = np.nansum(np.sign(dy), axis=1)
    variance = (k * (k - 1) * (2 * k + 5) - _tie_term(y)) / 18.0
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.where(
            s > 0, (s - 1) / np.sqrt(variance), np.where(s < 0, (s + 1) / np.sqrt(variance), 0.0)
        )
    z = np.where(variance > 0, z, 0.0)
    pvalue = 2.0 * ndtr(-np.abs(z))

    result[0, keep] = slope
    result[1, keep] = intercept
    result[2, keep] = pvalue
    return result


def _row_median(values: np.ndarray) -> np.ndarray:
    """Median of each row ignoring NaN; fast path for rows without NaN."""
    valid = ~np.isnan(values)
    counts = valid.sum(axis=1)
    out = np.full(values.shape[0], np.nan)
    full = counts == values.shape[1]
    if full.any():
        out[full] = np.median(values[full], axis=1)
    partial = ~full & (counts > 0)
    if partial.any():
        ordered = np.sort(values[partial], axis=1)  # NaN last
        c = counts[partial]
        rows = np.arange(ordered.shape[0])
        out[partial] = (ordered[rows, (c - 1) // 2] + ordered[rows, c // 2]) / 2
    return out


def _tie_term(y: np.ndarray) -> np.ndarray:
    """Sum of t(t-1)(2t+5) over groups of tied values in each row (NaN ignored)."""
    ordered = np.sort(y, axis=1)  # NaN last
    n = ordered.shape[1]
    index = np.arange(n)
    starts = np.ones(ordered.shape, dtype=bool)
    starts[:, 1:] = ordered[:, 1:] != ordered[:, :-1]
    run_start = np.maximum.accumulate(np.where(starts, index, 0), axis=1)
    run_length = (index - run_start + 1).astype("float64")
    ends = np.ones(ordered.shape, dtype=bool)
    ends[:, :-1] = starts[:, 1:]
    ends &= ~np.isnan(ordered)
    t = np.where(ends, run_length, 0.0)
    return np.sum(t * (t - 1) * (2 * t + 5), axis=1)
