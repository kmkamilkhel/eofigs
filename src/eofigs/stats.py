"""Trend statistics (Theil–Sen slope, Mann–Kendall test) and false discovery rate control."""

from __future__ import annotations

import warnings
from typing import Any, NamedTuple

import numpy as np
import xarray as xr
from scipy.special import ndtr

DAYS_PER_YEAR = 365.2425
_PER_YEARS = {"year": 1.0, "decade": 10.0}
#: Seasons with fewer valid values than this are left out of the seasonal test (as in rkt).
MIN_SEASON_VALUES = 4
#: The Hirsch-Slack correction needs at least this many complete years (Hirsch and Slack 1984).
MIN_CORRECTION_YEARS = 10
#: A median time step shorter than this (days) counts as sub-annual data.
SUBANNUAL_DAYS = 300


class TrendWarning(UserWarning):
    """Warning from :func:`trend` about seasonal data.

    Raised for sub-annual data without ``seasonal``, and for records too short for the
    Hirsch-Slack correction.
    """


def trend(
    data: xr.DataArray,
    dim: str = "time",
    per: str = "decade",
    alpha: float = 0.05,
    min_valid: int = 8,
    memory_mb: float = 256,
    seasonal: Any = None,
    seasonal_correction: bool = True,
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
    seasonal : {"month", "none"}, array-like or None, default None
        Seasonal Mann–Kendall test and seasonal Kendall slope (Hirsch et al. 1982) for
        sub-annual series: the test and the slope compare only values of the same season
        in different years, so a seasonal cycle does not distort them. ``"month"`` uses the
        calendar month of each date; an array gives one season label per time step (for
        16- or 8-day composites, for example the composite's day of year). Each season may
        have one value per calendar year. ``"none"`` (or None for annual data) keeps the
        plain test; None with sub-annual data also keeps it but warns.
    seasonal_correction : bool, default True
        With ``seasonal``: correct the variance of the test statistic for correlation
        between seasons (Hirsch and Slack 1984, as in the R package rkt). Needs at least
        10 complete years; with fewer the uncorrected test is used, with a warning.

    Returns
    -------
    xarray.Dataset
        ``slope`` (data units per ``per``), ``intercept`` (value at the first date,
        stored as ``reference_time``), ``pvalue`` (two-sided Mann–Kendall),
        ``significant`` (``pvalue < alpha``) and ``n_valid`` (int32). Spatial coordinates
        and CRS are kept. ``slope`` is labelled as a trend of the input variable (no
        ``standard_name``), so ``eofigs.variable(result.slope)`` returns the variable's
        trend with zero-centred colours.

    Raises
    ------
    ValueError
        If ``dim`` is missing or not a datetime coordinate, an argument is invalid, the
        seasonal labels do not match the time steps, there are fewer than 2 seasons, or a
        season has more than one value in a calendar year.

    Warns
    -----
    TrendWarning
        For sub-annual data without ``seasonal``, and when the record is too short for the
        Hirsch–Slack correction.

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
    labels = _season_labels(seasonal, data, dim)
    data = data.sortby(dim)
    years = (data[dim].values - data[dim].values[0]) / np.timedelta64(1, "D") / DAYS_PER_YEAR
    if np.any(np.diff(years) <= 0):
        raise ValueError(f"The {dim!r} coordinate has duplicate dates.")
    if seasonal is None and years.size > 2:
        step = float(np.median(np.diff(years))) * DAYS_PER_YEAR
        if step < SUBANNUAL_DAYS:
            warnings.warn(
                f"The data have time steps shorter than a year (median {step:.0f} days) and "
                "seasonal= is not set: a seasonal cycle distorts the Mann-Kendall test and the "
                'slope. Pass seasonal="month" (or season labels), aggregate to annual values, '
                'or pass seasonal="none" to keep the plain test.',
                TrendWarning,
                stacklevel=2,
            )
    if labels is not None:
        return _seasonal_trend(data, dim, labels, seasonal, seasonal_correction, years, per,
                               alpha, min_valid, memory_mb)  # fmt: skip

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
    first_date = str(data[dim].values[0])[:10]
    slope_attrs, source_name, label = _slope_attrs(data, per)
    source_units = data.attrs.get("units", "")
    out = xr.Dataset(
        {
            "slope": _with_attrs(slope * _PER_YEARS[per], slope_attrs),
            "intercept": _with_attrs(
                intercept,
                {
                    "long_name": f"{label} at the reference time (Theil-Sen intercept)",
                    "units": source_units,
                    "reference_time": first_date,
                },
            ),
            "pvalue": _with_attrs(pvalue, {"long_name": "Mann-Kendall p-value (two-sided)"}),
            "significant": _with_attrs(pvalue < alpha, {"long_name": f"p < {alpha}"}),
            "n_valid": _with_attrs(
                n_valid.astype("int32"), {"long_name": "Number of valid observations"}
            ),
        },
        attrs={
            "method": "Theil-Sen slope, Mann-Kendall test (tie and continuity corrected)",
            "autocorrelation": "not corrected",
            "alpha": alpha,
            "min_valid": min_valid,
            "seasonal": "none",
            "seasonal_correction": "none",
            "time_start": first_date,
            "time_end": str(data[dim].values[-1])[:10],
            "source_variable": source_name,
        },
    )
    return out


class FdrResult(NamedTuple):
    """Result of :func:`fdr_mask`."""

    #: True where the test is significant after false discovery rate control (same shape
    #: as the p-values; a DataArray for DataArray input).
    mask: Any
    #: Largest raw p-value among the significant tests (``p <= p_threshold`` is
    #: significant), or None when no test is significant.
    p_threshold: float | None
    #: Number of tests in the family (finite p-values, within ``valid``).
    n_tests: int
    #: Number of significant tests.
    n_rejected: int


def fdr_mask(pvalues: Any, q: float = 0.10, valid: Any = None) -> FdrResult:
    """Benjamini–Hochberg false discovery rate control over a field of p-values.

    The family of tests is every finite p-value (within ``valid`` when given); NaN is
    "not tested". A test is significant when its Benjamini–Hochberg adjusted p-value is
    at most ``q`` (Benjamini and Hochberg 1995; computed with
    ``scipy.stats.false_discovery_control``). For spatially correlated fields Wilks (2016,
    BAMS 97: 2263–2273) recommends ``q = 2 × alpha``, for example 0.10 for a field test at
    0.05.

    Parameters
    ----------
    pvalues : array-like or xarray.DataArray
        P-values of any shape.
    q : float, default 0.10
        False discovery rate, in (0, 1).
    valid : array-like of bool, optional
        Pixels that belong to the family of tests (same shape as ``pvalues``); others are
        not tested.

    Returns
    -------
    FdrResult
        ``mask`` (same shape as ``pvalues``), ``p_threshold`` (the equivalent per-test
        p-value, or None), ``n_tests`` and ``n_rejected``.

    Examples
    --------
    >>> import numpy as np
    >>> from eofigs.stats import fdr_mask
    >>> p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216])
    >>> result = fdr_mask(p, q=0.10)
    >>> result.n_rejected, result.p_threshold
    (6, 0.06)
    """
    from scipy.stats import false_discovery_control

    if not 0 < q < 1:
        raise ValueError(f"q must be between 0 and 1 (got {q}).")
    values = np.asarray(pvalues.values if isinstance(pvalues, xr.DataArray) else pvalues,
                        dtype="float64")  # fmt: skip
    tested = np.isfinite(values)
    if valid is not None:
        valid = np.asarray(valid.values if isinstance(valid, xr.DataArray) else valid, bool)
        if valid.shape != values.shape:
            raise ValueError(
                f"valid has shape {valid.shape}; the p-values have shape {values.shape}."
            )
        tested &= valid
    p = values[tested]
    if p.size and (p.min() < 0 or p.max() > 1):
        raise ValueError("p-values must be between 0 and 1.")
    mask = np.zeros(values.shape, bool)
    threshold = None
    if p.size:
        rejected = false_discovery_control(p, method="bh") <= q
        mask[tested] = rejected
        if rejected.any():
            threshold = float(p[rejected].max())
    n_rejected = int(mask.sum())
    if isinstance(pvalues, xr.DataArray):
        mask = xr.DataArray(mask, coords=pvalues.coords, dims=pvalues.dims, name="significant")
    return FdrResult(mask, threshold, int(p.size), n_rejected)


def _season_labels(seasonal, data, dim) -> np.ndarray | None:
    """Season label of each time step, in the order of the sorted dates; None for no seasons."""
    if seasonal is None or (isinstance(seasonal, str) and seasonal == "none"):
        return None
    if isinstance(seasonal, str):
        if seasonal != "month":
            raise ValueError(
                f"seasonal must be 'month', 'none', None or an array of labels (got {seasonal!r})."
            )
        labels = data[dim].dt.month.values
    else:
        labels = np.asarray(seasonal)
        if labels.ndim != 1 or labels.size != data.sizes[dim]:
            raise ValueError(
                f"seasonal needs one label per time step ({data.sizes[dim]}); got shape "
                f"{labels.shape}."
            )
    order = np.argsort(data[dim].values, kind="stable")
    return labels[order]


def _seasonal_trend(data, dim, labels, seasonal, correction, years, per, alpha, min_valid,
                    memory_mb) -> xr.Dataset:  # fmt: skip
    names, codes = np.unique(labels, return_inverse=True)
    n_seasons = names.size
    if n_seasons < 2:
        raise ValueError(
            "The seasonal test needs at least 2 seasons; these data have one value per year. "
            'Use seasonal="none" for annual data.'
        )
    calendar_year = data[dim].dt.year.values
    year_index = calendar_year - calendar_year.min()
    n_years = int(year_index.max()) + 1
    slot = year_index * n_seasons + codes
    counts = np.bincount(slot, minlength=n_years * n_seasons)
    if (counts > 1).any():
        crowded = np.nonzero(counts > 1)[0]
        where = [f"{calendar_year.min() + c // n_seasons} season {names[c % n_seasons]} "
                 f"({counts[c]} values)" for c in crowded[:5]]  # fmt: skip
        more = f" and {crowded.size - 5} more" if crowded.size > 5 else ""
        raise ValueError(
            "The seasonal test takes one value per season and calendar year, but there is "
            "more than one value in a season and year: " + "; ".join(where) + more + ". "
            "Resample to one value per season and year (for example monthly means), or pass "
            "season labels that tell the values apart."
        )
    complete = int((counts.reshape(n_years, n_seasons) > 0).all(axis=1).sum())
    note = "Hirsch-Slack 1984" if correction else "none"
    if correction and complete < MIN_CORRECTION_YEARS:
        warnings.warn(
            f"The record has {complete} complete years; the Hirsch-Slack correction for "
            f"correlation between seasons needs at least {MIN_CORRECTION_YEARS} complete "
            "years. The uncorrected seasonal test is used.",
            TrendWarning,
            stacklevel=3,
        )
        correction = False
        note = f"not applied: fewer than {MIN_CORRECTION_YEARS} complete years"
    when = np.full(n_years * n_seasons, np.nan)
    when[slot] = years
    when = when.reshape(n_years, n_seasons)

    values = data.astype("float64")
    if values.chunks is not None:
        values = values.chunk({dim: -1})
    slope, intercept, pvalue, n_valid = xr.apply_ufunc(
        _seasonal_block_array,
        values,
        input_core_dims=[[dim]],
        output_core_dims=[[], [], [], []],
        kwargs={
            "slot": slot,
            "when": when,
            "years": years,
            "min_valid": min_valid,
            "memory_mb": memory_mb,
            "correction": correction,
        },  # fmt: skip
        dask="parallelized",
        output_dtypes=[float, float, float, float],
    )
    first_date = str(data[dim].values[0])[:10]
    slope_attrs, source_name, label = _slope_attrs(data, per)
    return xr.Dataset(
        {
            "slope": _with_attrs(slope * _PER_YEARS[per], slope_attrs),
            "intercept": _with_attrs(
                intercept,
                {
                    "long_name": f"{label} at the reference time (seasonal Kendall intercept)",
                    "units": data.attrs.get("units", ""),
                    "reference_time": first_date,
                },
            ),
            "pvalue": _with_attrs(
                pvalue, {"long_name": "Seasonal Mann-Kendall p-value (two-sided)"}
            ),
            "significant": _with_attrs(pvalue < alpha, {"long_name": f"p < {alpha}"}),
            "n_valid": _with_attrs(
                n_valid.astype("int32"), {"long_name": "Number of valid observations"}
            ),
        },
        attrs={
            "method": "Seasonal Kendall slope, seasonal Mann-Kendall test (Hirsch et al. "
            "1982; tie and continuity corrected)",
            "seasonal": "month" if isinstance(seasonal, str) else "labels",
            "seasons": int(n_seasons),
            "seasonal_correction": note,
            "autocorrelation": "not corrected",
            "alpha": alpha,
            "min_valid": min_valid,
            "time_start": first_date,
            "time_end": str(data[dim].values[-1])[:10],
            "source_variable": source_name,
        },
    )


def _seasonal_block_array(values, slot, when, years, min_valid, memory_mb, correction):
    """Seasonal test on an array whose last axis is time, in memory-bounded blocks."""
    shape = values.shape[:-1]
    flat = values.reshape(-1, values.shape[-1])
    n_years, n_seasons = when.shape
    pairs = n_years * (n_years - 1) // 2
    per_pixel = 8 * (4 * pairs * n_seasons + 2 * n_years * n_years + 4 * n_seasons**2)
    block = max(1, int(memory_mb * 2**20 // per_pixel))
    out = np.full((4, flat.shape[0]), np.nan)
    for start in range(0, flat.shape[0], block):
        out[:, start : start + block] = _seasonal_rows(
            flat[start : start + block], slot, when, years, min_valid, correction
        )
    return tuple(part.reshape(shape) for part in out)


def _seasonal_rows(y, slot, when, years, min_valid, correction) -> np.ndarray:
    """Seasonal Kendall slope, S, variance (optionally Hirsch-Slack) and p for rows of y."""
    n_valid = np.sum(~np.isnan(y), axis=1).astype("float64")
    result = np.full((4, y.shape[0]), np.nan)
    result[3] = n_valid
    keep = n_valid >= min_valid
    if not keep.any():
        return result
    rows = y[keep]
    n_years, n_seasons = when.shape
    grid = np.full((rows.shape[0], n_years * n_seasons), np.nan)
    grid[:, slot] = rows
    grid = grid.reshape(rows.shape[0], n_years, n_seasons)
    valid = ~np.isnan(grid)
    count = valid.sum(axis=1).astype("float64")  # values per season
    used = count >= MIN_SEASON_VALUES

    i, j = np.triu_indices(n_years, k=1)
    dy = grid[:, j, :] - grid[:, i, :]  # (rows, pairs, seasons); NaN when a value is missing
    dt = when[j, :] - when[i, :]
    sign = np.where(np.isnan(dy), 0.0, np.sign(dy)) * used[:, None, :]
    s = sign.sum(axis=(1, 2))
    with np.errstate(invalid="ignore", divide="ignore"):
        slopes = np.where(used[:, None, :], dy / dt[None, :, :], np.nan)
    slope = _row_median(slopes.reshape(rows.shape[0], -1))
    intercept = np.nanmedian(rows - slope[:, None] * years[None, :], axis=1)

    ties = np.stack([_tie_term(grid[:, :, g]) for g in range(n_seasons)], axis=1)
    season_var = (count * (count - 1) * (2 * count + 5) - ties) / 18.0
    variance = np.sum(np.where(used, season_var, 0.0), axis=1)
    if correction:
        # ranks within each season (ties averaged), missing values at the mean rank
        diff = grid[:, :, None, :] - grid[:, None, :, :]
        rank = (
            count[:, None, :] + 1 + np.where(np.isnan(diff), 0.0, np.sign(diff)).sum(axis=2)
        ) / 2
        rank = np.where(valid, rank, (count[:, None, :] + 1) / 2)
        k = np.einsum("rpg,rph->rgh", sign, sign)
        g_sum = np.einsum("rig,rih->rgh", rank, rank)
        gamma = (k + 4 * g_sum - n_years * (count[:, :, None] + 1) * (count[:, None, :] + 1)) / 3
        both = used[:, :, None] & used[:, None, :]
        variance = np.sum(np.where(both, gamma, 0.0), axis=(1, 2))
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.where(variance > 0, (s - np.sign(s)) / np.sqrt(variance), 0.0)
    result[0, keep] = slope
    result[1, keep] = intercept
    result[2, keep] = 2.0 * ndtr(-np.abs(z))
    return result


def _with_attrs(da: xr.DataArray, attrs: dict) -> xr.DataArray:
    """Replace all attributes, so nothing (such as standard_name) leaks from the input."""
    da = da.copy()
    da.attrs = dict(attrs)
    return da


def _slope_attrs(data: xr.DataArray, per: str) -> tuple[dict, str, str]:
    """Attributes that mark the slope as a trend of its source variable."""
    from eofigs.variables import PER_UNITS, cf_units_to_mathtext, variable

    try:
        source = variable(data)
    except ValueError:
        source = None
    if source is not None:
        derived = source.trend(per)
        attrs = {"long_name": derived.long_name, "units": derived.units}
        source_name, label = source.name, source.long_name
    else:
        label = str(data.attrs.get("long_name") or data.name or "Value")
        units = cf_units_to_mathtext(str(data.attrs.get("units", "")))
        time_unit = f"{PER_UNITS[per]}$^{{-1}}$"
        attrs = {"long_name": f"{label} trend", "units": f"{units} {time_unit}".strip()}
        source_name = str(data.name) if data.name is not None else ""
    attrs.update(source_variable=source_name, eofigs_derived="trend", per=per)
    return attrs, source_name, label


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
