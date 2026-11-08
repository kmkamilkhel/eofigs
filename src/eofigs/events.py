"""Event composites: anomaly maps before, during and after a set of events, and their series."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any

import matplotlib as mpl
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from eofigs import maps, trends
from eofigs._colour import NO_DATA_COLOUR, SECONDARY_COLOUR, TEXT_COLOUR
from eofigs._presets import get_journal, resolve_width
from eofigs.styling import _STATE, label_panels, new_figure, tidy_axes
from eofigs.variables import Variable
from eofigs.variables import variable as lookup_variable

__all__ = ["event_composite"]

PHASES = ("before", "during", "after")
KINDS = ("anomaly", "zscore")
CLIMATOLOGIES = ("auto", "month", None)
DETRENDS = ("linear", None)
TESTS = ("ttest", "wilcoxon", None)
#: A significance test needs at least this many events.
MIN_EVENTS = 3
#: A z-score needs at least this many baseline values for its month.
MIN_ZSCORE_VALUES = 5
#: Each event in the composite series.
EVENT_LINE_COLOUR = "#7F7F7F"
#: Shading of the event period in the series (light muted mustard: hot and dry).
EVENT_PERIOD_COLOUR = "#F1E2C4"


class EventWarning(UserWarning):
    """An event was left out of the composite (window past the record, or overlap)."""


@dataclass
class _Event:
    start: int  # index of the first event step
    end: int  # index of the last event step
    first: int  # first window step
    last: int  # last window step
    label: str = ""


@dataclass
class _Composite:
    phases: dict[str, xr.DataArray] = field(default_factory=dict)
    pvalues: dict[str, np.ndarray | None] = field(default_factory=dict)
    series: np.ndarray | None = None  # events x relative steps (area means)
    offsets: np.ndarray | None = None  # relative steps of the series


def event_composite(
    data: xr.DataArray,
    events: Any,
    *,
    window: tuple[int, int] = (-3, 6),
    freq: str | None = None,
    baseline: tuple[Any, Any] | None = None,
    kind: str = "anomaly",
    climatology: str | None = "auto",
    detrend: str | None = "linear",
    test: str | None = "ttest",
    variable: str | Variable | None = None,
    maps: tuple[str, ...] = PHASES,
    series: bool = True,
    event_rule: str | None = None,
    alpha: float = 0.05,
    sig_fraction: float = 0.5,
    dot_spacing_mm: float = 1.6,
    stipple: str | None = "dots",
    limits: str | float | None = "p98",
    exclude: str | float | xr.DataArray | None = "auto",
    exclude_label: str = "Not vegetated",
    aoi: Any = None,
    aoi_label: str = "Study area",
    graticule: bool = True,
    north_arrow: bool = True,
    scale_bar: bool = True,
    legend: bool = True,
    labels: str | list[str] | None = None,
    width: str | float = "double",
    height_mm: float | None = None,
    journal: str | None = None,
    ax: Axes | None = None,
    subfigure: Any = None,
) -> Figure:
    """Composite anomaly maps before, during and after a set of events, with their series.

    For each event the anomalies are averaged over the steps before the event (the whole
    pre-event part of the window), during it and after it (the post-event part); the maps
    show the mean of these per-event means across events. Anomalies are computed at full
    resolution against a baseline climatology from the steps outside every event window,
    after removing a per-pixel linear trend fitted to those steps. Significance is tested
    across events per pixel and marked at print size as in :func:`trend_map`.

    Parameters
    ----------
    data : xarray.DataArray
        Time series cube (``time``, ``y``, ``x``) with a datetime ``time`` coordinate and a
        CRS.
    events : list of (start, end) or boolean time series
        Event periods as date pairs (inclusive), or a boolean series on the data's time
        steps (True during an event; each run of True values is one event).
    window : (int, int), default (-3, 6)
        Steps before the event start and after the event end.
    freq : str, optional
        A pandas offset alias (for example ``"MS"``) to resample the data to first (mean);
        ``window`` then counts these steps.
    baseline : (start, end), optional
        Period for the climatology; only its steps outside every event window are used.
        Default: all steps outside every event window.
    kind : {"anomaly", "zscore"}, default "anomaly"
        Anomalies, or anomalies divided by the baseline standard deviation of the same
        calendar month (pixels with fewer than 5 baseline values for it get NaN).
    climatology : {"auto", "month"} or None, default "auto"
        Remove a climatology per calendar month (``"month"``), one mean (``None``), or
        per month for sub-annual data and one mean for annual data (``"auto"``).
    detrend : {"linear"} or None, default "linear"
        Remove a per-pixel linear trend fitted to the baseline steps first, so that a long
        greening or warming trend does not make late events look better than early ones.
    test : {"ttest", "wilcoxon"} or None, default "ttest"
        Significance across events per pixel: one-sample t-test or Wilcoxon signed-rank
        test of the event-mean anomalies against zero. Both need at least 3 events, and a
        two-sided Wilcoxon test at 0.05 can only reach significance with at least 6 events.
        ``None`` draws no marks.
    variable : str or Variable, optional
        The variable (for example ``"ndvi"``); sets the anomaly colours and labels.
        Recognised from the data by default.
    maps : tuple of {"before", "during", "after"}, default all three
        Phase maps to draw, in order.
    series : bool, default True
        Add the composite series: the area mean for each event (thin grey), their mean
        (black) and spread (interquartile range, or the range with fewer than 4 events).
    event_rule : str, optional
        How the events were chosen, for the caption sentence.
    alpha, sig_fraction, dot_spacing_mm, stipple, limits, exclude, exclude_label
        As in :func:`trend_map`; the colour limits are shared by all phase maps.
    aoi : GeoDataFrame, GeoSeries or path, optional
        Study area outline: drawn on each map, and the area the series averages over.
    aoi_label : str, default "Study area"
        Legend entry for the outline.
    graticule, north_arrow, scale_bar, legend : bool, default True
        Map elements; the north arrow and scale bar go on the first map.
    labels : str or list of str, optional
        Panel labels (style default when omitted).
    width : str or float, default "double"
        Named journal width or width in mm.
    height_mm : float, optional
        Figure height; by default it follows the maps' shape, up to 75 % of the
        journal's maximum height.
    journal : str, optional
        Journal preset (defaults to the one set by :func:`set_style`).
    ax : None
        Not supported: this recipe has several panels; use ``subfigure=``.
    subfigure : matplotlib SubFigure, optional
        Draw within a subfigure of a larger figure.

    Returns
    -------
    matplotlib.figure.Figure
        The figure. ``fig.eofigs_layout`` records the events used and dropped, the steps
        of each phase, the colour limits, the clipped and significant shares, and a ready
        caption sentence (``fig.eofigs_layout["caption"]``).

    Raises
    ------
    ValueError
        For data without a CRS or datetime axis, no usable events, an unknown ``kind``,
        ``climatology``, ``detrend``, ``test`` or phase name, a malformed ``window``, or
        ``ax``.

    Examples
    --------
    >>> import numpy as np, pandas as pd, xarray as xr, rioxarray
    >>> import eofigs
    >>> time = pd.date_range("2001-01-01", periods=120, freq="MS")
    >>> y, x = np.arange(3_900_000, 3_880_000, -1000.0), np.arange(500_000, 520_000, 1000.0)
    >>> values = 0.5 + np.zeros((120, y.size, x.size))
    >>> cube = xr.DataArray(values, dims=("time", "y", "x"),
    ...                     coords={"time": time, "y": y, "x": x}, name="ndvi")
    >>> events = [("2003-06-01", "2003-07-01"), ("2006-06-01", "2006-06-01"),
    ...           ("2009-07-01", "2009-08-01")]
    >>> fig = eofigs.event_composite(cube.rio.write_crs("EPSG:32643"), events)
    >>> len(fig.eofigs_layout["events"])
    3
    """
    _check_arguments(window, kind, climatology, detrend, test, maps, stipple, ax)
    data = trends._with_crs(data, "data")
    if "time" not in data.dims or not np.issubdtype(data["time"].dtype, np.datetime64):
        raise ValueError("data needs a datetime 'time' dimension (for example monthly steps).")
    if freq is not None:
        crs = data.rio.crs
        data = data.resample(time=freq).mean().rio.write_crs(crs)
    times = pd.DatetimeIndex(data["time"].values)
    used, dropped = _events(events, times, window)
    if not used:
        raise ValueError(
            "No usable events: every event window runs past the record or overlaps an "
            "earlier one. Check the dates, or use a shorter window."
        )
    in_window = np.zeros(times.size, bool)
    for event in [*used, *dropped]:
        in_window[max(event.first, 0) : min(event.last, times.size - 1) + 1] = True
    base = ~in_window
    if baseline is not None:
        lo, hi = (pd.Timestamp(v) for v in baseline)
        base &= (times >= lo) & (times <= hi)
    if base.sum() < 2:
        raise ValueError("The baseline has fewer than 2 steps outside the event windows.")

    var = _anomaly_variable(variable, data, kind)
    monthly = _monthly(climatology, times)
    values = data.transpose("time", ...).values.astype("float64")
    if detrend == "linear":
        values = _remove_trend(values, times, base)
    anomalies = _anomalies(values, times, base, monthly, kind)
    grid = data.isel(time=0, drop=True)
    excluded, threshold = trends._excluded(exclude, data, "time", _base_variable(var), grid)
    composite = _composite(anomalies, used, maps, grid, excluded, test, aoi)

    options = dict(locals())  # every argument, plus the events used and dropped
    return _draw(
        composite, used, maps, var, grid, excluded, threshold, data, times, aoi, aoi_label, options
    )


# ============================================================================ inputs


def _check_arguments(window, kind, climatology, detrend, test, phases, stipple, ax):
    if ax is not None:
        raise ValueError(
            "event_composite draws several panels; pass subfigure= (one panel of a larger "
            "figure) instead of ax=."
        )
    if (
        len(window) != 2
        or not all(isinstance(v, int | np.integer) for v in window)
        or window[0] > 0
        or window[1] < 0
    ):
        raise ValueError(f"window must be (steps before <= 0, steps after >= 0) (got {window}).")
    for name, value, allowed in (
        ("kind", kind, KINDS),
        ("climatology", climatology, CLIMATOLOGIES),
        ("detrend", detrend, DETRENDS),
        ("test", test, TESTS),
    ):
        if value not in allowed:
            raise ValueError(f"{name} must be one of {allowed} (got {value!r}).")
    if not phases or any(p not in PHASES for p in phases):
        raise ValueError(f"maps must be a non-empty selection of {PHASES} (got {phases!r}).")
    if window[0] == 0 and "before" in phases:
        raise ValueError("maps include 'before' but window has no steps before the events.")
    if window[1] == 0 and "after" in phases:
        raise ValueError("maps include 'after' but window has no steps after the events.")
    if stipple is not None and stipple not in trends.STIPPLES:
        raise ValueError(f"stipple must be one of {trends.STIPPLES} or None (got {stipple!r}).")


def _events(events, times: pd.DatetimeIndex, window) -> tuple[list[_Event], list[_Event]]:
    """Event steps on the data's time axis; windows past the record or overlapping are dropped."""
    spans = _spans(events, times)
    spans.sort()
    used: list[_Event] = []
    dropped: list[_Event] = []
    for start, end in spans:
        event = _Event(
            start,
            end,
            start + window[0],
            end + window[1],
            f"{times[start]:%Y-%m}" + (f" to {times[end]:%Y-%m}" if end > start else ""),
        )
        if event.first < 0 or event.last >= times.size:
            warnings.warn(
                f"Event {event.label} left out: its window runs past the record.",
                EventWarning,
                stacklevel=3,
            )
            dropped.append(event)
        elif used and event.first <= used[-1].last:
            warnings.warn(
                f"Event {event.label} left out: its window overlaps event {used[-1].label}.",
                EventWarning,
                stacklevel=3,
            )
            dropped.append(event)
        else:
            used.append(event)
    return used, dropped


def _spans(events, times: pd.DatetimeIndex) -> list[tuple[int, int]]:
    if isinstance(events, xr.DataArray | pd.Series):
        flags = (
            events.reindex(time=times)
            if isinstance(events, xr.DataArray)
            else (events.reindex(times))
        )
        flags = np.asarray(flags, dtype=float)
        if np.isnan(flags).any():
            raise ValueError("A boolean event series must cover every time step of the data.")
        on = flags.astype(bool)
        spans, start = [], None
        for i, flag in enumerate(on):
            if flag and start is None:
                start = i
            if not flag and start is not None:
                spans.append((start, i - 1))
                start = None
        if start is not None:
            spans.append((start, on.size - 1))
        return spans
    spans = []
    for pair in events:
        if len(pair) != 2:
            raise ValueError(f"Each event must be a (start, end) pair (got {pair!r}).")
        lo, hi = (pd.Timestamp(v) for v in pair)
        if hi < lo:
            raise ValueError(f"Event end {hi:%Y-%m-%d} is before its start {lo:%Y-%m-%d}.")
        first = int(times.searchsorted(lo, side="left"))
        last = int(times.searchsorted(hi, side="right")) - 1
        if first >= times.size or last < first:
            warnings.warn(
                f"Event {lo:%Y-%m-%d} has no time step in the data; left out.",
                EventWarning,
                stacklevel=4,
            )
            continue
        spans.append((first, last))
    return spans


def _anomaly_variable(variable, data, kind) -> Variable:
    if variable is not None:
        base = lookup_variable(variable)
    else:
        try:
            base = lookup_variable(data)
        except ValueError:
            name = str(data.attrs.get("long_name") or data.name or "Value")
            base = Variable(
                name="value", long_name=name, symbol=name, units=str(data.attrs.get("units", ""))
            )
    if base.name.endswith("_anomaly"):
        var = base
    else:
        var = base.anomaly()
    if kind == "zscore":
        symbol = var.symbol.removesuffix(" anomaly")
        var = Variable(
            name=var.name,
            long_name=f"{base.long_name} anomaly (z-score)",
            symbol=f"{symbol} z-score",
            units="",
            cmap=var.cmap,
            anomaly_cmap=var.anomaly_cmap,
            kind="diverging",
        )
    return var


def _base_variable(var: Variable) -> Variable:
    """Return a stand-in variable carrying the base name (for the vegetation-index rule)."""
    base = var.name.removesuffix("_anomaly")
    return Variable(name=f"{base}_trend", long_name=var.long_name, symbol=var.symbol)


def _monthly(climatology, times: pd.DatetimeIndex) -> bool:
    if climatology == "month":
        return True
    if climatology is None:
        return False
    step = np.median(np.diff(times.values).astype("timedelta64[D]").astype(float))
    return bool(step < 300)


def _years(times: pd.DatetimeIndex) -> np.ndarray:
    return (times - times[0]).days.to_numpy() / 365.2425


def _remove_trend(values, times, base) -> np.ndarray:
    """Remove a per-pixel linear trend fitted to the baseline steps (at least 3 values)."""
    t = _years(times)
    y = values[base]
    tb = np.broadcast_to(t[base][:, None, None], y.shape)
    ok = np.isfinite(y)
    n = ok.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        t_mean = np.where(ok, tb, 0).sum(axis=0) / n
        y_mean = np.where(ok, y, 0).sum(axis=0) / n
        dt = np.where(ok, tb - t_mean, 0)
        slope = (dt * np.where(ok, y - y_mean, 0)).sum(axis=0) / (dt**2).sum(axis=0)
    slope = np.where((n >= 3) & np.isfinite(slope), slope, 0.0)
    t_mean = np.where(np.isfinite(t_mean), t_mean, 0.0)
    return values - slope[None] * (t[:, None, None] - t_mean[None])


def _anomalies(values, times, base, monthly, kind) -> np.ndarray:
    """Anomalies (or z-scores) against the baseline climatology, per month or overall."""
    groups = times.month.to_numpy() if monthly else np.zeros(times.size, int)
    out = np.full_like(values, np.nan)
    for g in np.unique(groups):
        steps = groups == g
        ref = values[steps & base]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN pixels
            mean = np.nanmean(ref, axis=0) if ref.size else np.full(values.shape[1:], np.nan)
            out[steps] = values[steps] - mean[None]
            if kind == "zscore":
                n = np.isfinite(ref).sum(axis=0)
                std = np.nanstd(ref, axis=0, ddof=1) if ref.shape[0] > 1 else np.nan * mean
                std = np.where((n >= MIN_ZSCORE_VALUES) & (std > 0), std, np.nan)
                out[steps] = out[steps] / std[None]
    return out


def _phase_steps(event: _Event, phase: str) -> slice:
    if phase == "before":
        return slice(event.first, event.start)
    if phase == "during":
        return slice(event.start, event.end + 1)
    return slice(event.end + 1, event.last + 1)


def _composite(anomalies, used, phases, grid, excluded, test, aoi) -> _Composite:
    result = _Composite()
    for phase in phases:
        per_event = []
        for event in used:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                per_event.append(np.nanmean(anomalies[_phase_steps(event, phase)], axis=0))
        stack = np.stack(per_event)
        stack[:, excluded] = np.nan
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mean = np.nanmean(stack, axis=0)
        result.phases[phase] = grid.copy(data=mean)
        result.pvalues[phase] = event_pvalues(stack, test)
    result.offsets, result.series = _series(anomalies, used, excluded, grid, aoi)
    return result


def event_pvalues(stack: np.ndarray, test: str | None) -> np.ndarray | None:
    """Per-pixel p-values of event-mean anomalies against zero (events along axis 0).

    Pixels with fewer than :data:`MIN_EVENTS` valid events get NaN; with fewer events in
    total, or ``test=None``, the result is None.

    Examples
    --------
    >>> import numpy as np
    >>> from eofigs.events import event_pvalues
    >>> stack = np.array([[[1.0]], [[1.2]], [[0.9]], [[1.1]]])
    >>> float(event_pvalues(stack, "ttest")[0, 0]) < 0.01
    True
    """
    from scipy import stats

    if test is None or stack.shape[0] < MIN_EVENTS:
        return None
    valid = np.isfinite(stack).sum(axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if test == "ttest":
            p = stats.ttest_1samp(stack, 0.0, axis=0, nan_policy="omit").pvalue
        else:
            p = stats.wilcoxon(stack, axis=0, nan_policy="omit").pvalue
    p = np.asarray(p, dtype=float)
    p[valid < MIN_EVENTS] = np.nan
    return p


def _series(anomalies, used, excluded, grid, aoi):
    """Area-mean anomaly of each event at each step relative to the event start."""
    inside = ~excluded
    if aoi is not None:
        from rasterio.features import geometry_mask

        gdf = maps._as_gdf(aoi, "aoi").to_crs(grid.rio.crs)
        inside &= ~geometry_mask(gdf.geometry, grid.shape, grid.rio.transform())
    first = min(e.first - e.start for e in used)
    last = max(e.last - e.start for e in used)
    offsets = np.arange(first, last + 1)
    out = np.full((len(used), offsets.size), np.nan)
    for i, event in enumerate(used):
        for j, offset in enumerate(offsets):
            step = event.start + offset
            if event.first <= step <= event.last:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    out[i, j] = np.nanmean(anomalies[step][inside])
    return offsets, out


# ============================================================================ layout


@dataclass
class _Panels:
    fig_w: float
    fig_h: float
    maps: list[tuple[float, float, float, float]]  # left, bottom, width, height (mm)
    colourbar_box: tuple[float, float, float, float]
    legend_anchor: tuple[float, float] | None
    series_box: tuple[float, float, float, float] | None


def _layout(width, height_mm, preset, ratio, n, small, size, legend_mm, series, has_labels):
    fig_w = resolve_width(width, preset)
    max_h = height_mm if height_mm is not None else maps.HEIGHT_SHARE * preset.max_height_mm
    lat_w, _ = maps._text_mm("35°30′N", small)
    lab_h = small * maps._PT
    left, right, gap = lat_w + 3.0, 4.0, 9.0  # gap: room for the edge longitude labels
    title = size * maps._PT + 3.0  # phase title (and panel label) above each map
    bottom = lab_h + 4.0
    cbar_block = 2.5 + 2 * (small * maps._PT + 1.5) + 3.0
    lw, lh = legend_mm if legend_mm is not None else (0.0, 0.0)
    series_h = 0.0
    series_gap = 0.0
    if series:
        series_h = max(32.0, 0.2 * fig_w)
        series_gap = title + 2.0  # label and room above the series
        series_bottom = 2 * lab_h + 7.0  # tick labels and axis label
    else:
        series_bottom = 0.0
    lat_series = lat_w + 6.0  # y tick labels and label of the series

    def block(map_total):
        beside = legend_mm is None or map_total - lw - 6.0 >= 40.0
        return beside, (max(cbar_block, lh + 3.0) if beside else cbar_block + lh + 3.0)

    map_w = (fig_w - left - right - gap * (n - 1)) / n
    beside, below = block(n * map_w)
    map_h = map_w * ratio
    fixed = title + bottom + below + series_gap + series_h + series_bottom
    if fixed + map_h > max_h:
        map_h = max(max_h - fixed, 20.0)
        map_w = map_h / ratio
    fig_h = height_mm if height_mm is not None else fixed + map_h
    total = n * map_w + gap * (n - 1)
    x0 = left + (fig_w - left - right - total) / 2
    y = fig_h - title - map_h
    boxes = [(x0 + i * (map_w + gap), y, map_w, map_h) for i in range(n)]
    under = y - bottom - 1.0
    if legend_mm is None:
        cb_w = min(0.5 * total, 90.0)
        cbar = (x0 + (total - cb_w) / 2, under - 2.5, cb_w, 2.5)
        anchor = None
    elif beside:
        cb_w = min(0.5 * total, total - lw - 6.0, 90.0)
        cbar = (x0, under - 2.5, cb_w, 2.5)
        anchor = (x0 + cb_w + 8.0, under + 1.0)
    else:
        cb_w = min(0.5 * total, 90.0)
        cbar = (x0 + (total - cb_w) / 2, under - 2.5, cb_w, 2.5)
        anchor = (x0, under - cbar_block)
    series_box = None
    if series:
        top = y - bottom - below - series_gap
        series_box = (lat_series, top - series_h, fig_w - lat_series - right, series_h)
    _ = has_labels
    return _Panels(fig_w, fig_h, boxes, cbar, anchor, series_box)


# ============================================================================ drawing


def _draw(
    composite, used, phases, var, grid, excluded, threshold, data, times, aoi, aoi_label, options
) -> Figure:
    import pyproj

    o = options
    src_crs = grid.rio.crs
    aoi_map = None
    if aoi is not None:
        aoi_gdf = maps._as_gdf(aoi, "aoi")
        crs = maps.map_crs(aoi_gdf) if not src_crs.is_projected else src_crs
        aoi_map = aoi_gdf.to_crs(crs)
        extent = maps._extent_from(aoi_map)
    else:
        crs = src_crs if src_crs.is_projected else trends._utm_of(grid)
        extent = trends._bounds_in(grid, crs)
    crs = pyproj.CRS.from_user_input(crs)
    projection = maps._projection(crs)
    ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])
    preset = get_journal(o["journal"] or _STATE["journal"])
    small = maps._small_font()
    size = mpl.rcParams["font.size"]

    stack = np.stack([composite.phases[p].values for p in phases])
    limit, rule = trends._limits(stack, o["limits"])
    finite = np.isfinite(stack)
    clipped = 100.0 * float((np.abs(stack[finite]) > limit).mean()) if finite.any() else 0.0
    # pixels without a value at any step lie outside the data: not drawn, not counted
    footprint = np.isfinite(data.values).any(axis=data.get_axis_num("time"))
    no_data = ~np.isfinite(stack).all(axis=0) & ~excluded & footprint
    tested = any(composite.pvalues[p] is not None for p in phases) and o["stipple"] is not None
    handles = _legend_handles(
        aoi_label if aoi is not None else None,
        tested,
        o["stipple"],
        o["alpha"],
        o["sig_fraction"],
        excluded,
        no_data,
        o["exclude_label"],
        o["test"],
    )
    legend_mm = maps._legend_size(handles, small) if o["legend"] and handles else None
    holder = o["subfigure"]
    width, height_mm = o["width"], o["height_mm"]
    if holder is not None:
        width, height_mm = maps._size_mm(holder)
    has_labels = o["labels"] is not None or _STATE.get("labels") is not None
    lay = _layout(
        width,
        height_mm,
        preset,
        ratio,
        len(phases),
        small,
        size,
        legend_mm,
        o["series"],
        has_labels,
    )
    if holder is None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            fig, ax0 = new_figure(lay.fig_w, height_mm=lay.fig_h, journal=preset.key)
        fig.set_layout_engine("none")
        ax0.remove()
        holder = fig
    else:
        fig = holder.get_figure(root=True)

    def rect(box):
        x, y, w, h = box
        return (x / lay.fig_w, y / lay.fig_h, w / lay.fig_w, h / lay.fig_h)

    dpi = preset.export_dpi
    map_axes, record_phases, image = [], {}, None
    valid_base = ~excluded
    for i, (phase, box) in enumerate(zip(phases, lay.maps, strict=True)):
        ax = holder.add_axes(rect(box), projection=projection)
        ax.set_extent(extent, crs=projection)
        ax.set_facecolor("white")
        ax.spines["geo"].set_linewidth(0.6)
        ax.spines["geo"].set_edgecolor(TEXT_COLOUR)
        shown = composite.phases[phase]
        map_w, map_h = box[2], box[3]
        image = trends._draw_slope(
            ax, shown, var, limit, crs, extent, map_w, map_h, dpi, projection
        )
        phase_no_data = ~np.isfinite(shown.values) & ~excluded & footprint
        for mask, hatch in (
            (excluded, trends.EXCLUDED_HATCH),
            (phase_no_data, trends.NO_DATA_HATCH),
        ):
            grey = xr.DataArray(mask, coords=grid.coords, dims=grid.dims).rio.write_crs(src_crs)
            trends._draw_grey(ax, grey, hatch, crs, extent, map_w, map_h, dpi, projection)
        valid = np.isfinite(shown.values) & valid_base
        p = composite.pvalues[phase]
        marks, cell, significant_percent = 0, None, None
        if p is not None:
            significant = (p < o["alpha"]) & valid
            significant_percent = round(
                100.0 * float(significant.sum()) / max(int(valid.sum()), 1), 2
            )
            if o["stipple"] is not None:
                marks, cell = trends._draw_marks(
                    ax,
                    significant,
                    valid,
                    shown,
                    o["stipple"],
                    o["sig_fraction"],
                    o["dot_spacing_mm"],
                    crs,
                    extent,
                    map_w,
                )
        if aoi_map is not None:
            ax.add_geometries(
                aoi_map.geometry,
                crs=projection,
                facecolor="none",
                edgecolor=maps.AOI_COLOUR,
                linewidth=1.0,
                zorder=5,
            )
        if o["graticule"]:
            gl = maps._add_graticule(ax, projection, extent, small)
            gl.left_labels = i == 0
        if i == 0 and (o["north_arrow"] or o["scale_bar"]):
            _furniture(ax, projection, extent, aoi_map, map_w, map_h, size, o)
        ax.set_title(_phase_title(phase, o["window"], times), size=size, pad=3)
        map_axes.append(ax)
        record_phases[phase] = {
            "significant_percent": significant_percent,
            "marks": marks,
            "mark_cell_mm": cell,
            "no_data_percent": round(
                100.0 * float(phase_no_data.sum()) / max(int(footprint.sum()), 1), 2
            ),
        }

    extend = trends._extend(stack, limit)
    cbar_lay = maps._Layout("inside", lay.fig_w, lay.fig_h, lay.maps[0])
    cbar_lay.colourbar_box = lay.colourbar_box
    trends._draw_colourbar(holder, map_axes[0], cbar_lay, image, var, extend)
    if legend_mm is not None:
        cbar_lay.legend_anchor = lay.legend_anchor
        trends._draw_legend(holder, map_axes[0], cbar_lay, handles, small)
    panels = list(map_axes)
    series_record = None
    if o["series"] and lay.series_box is not None:
        sax = holder.add_axes(rect(lay.series_box))
        series_record = _draw_series(sax, composite, used, var, times, small, size)
        panels.append(sax)
    label_panels(panels, o["labels"])

    steps = {p: [int(_steps(e, p)) for e in used] for p in phases}
    record: dict[str, Any] = {
        "events": [
            {
                "start": f"{times[e.start]:%Y-%m-%d}",
                "end": f"{times[e.end]:%Y-%m-%d}",
                "steps": e.end - e.start + 1,
            }
            for e in used
        ],
        "dropped": [e.label for e in o["dropped"]],
        "phase_steps": steps,
        "limits": limit,
        "limits_rule": rule,
        "extend": extend,
        "clipped_percent": round(clipped, 2),
        "excluded_percent": round(100.0 * float(excluded.sum()) / max(int(footprint.sum()), 1), 2),
        "no_data_percent": round(100.0 * float(no_data.sum()) / max(int(footprint.sum()), 1), 2),
        "phases": record_phases,
        "test": o["test"] if tested else None,
        "detrend": o["detrend"],
        "climatology": "month" if _monthly(o["climatology"], times) else "mean",
    }
    if series_record is not None:
        record["series"] = series_record
    record["caption"] = _caption(record, used, var, grid, times, o, threshold, tested)
    fig.eofigs_layout = record
    if holder is not fig:
        holder.eofigs_layout = record
    return fig


def _steps(event: _Event, phase: str) -> int:
    s = _phase_steps(event, phase)
    return s.stop - s.start


def _unit(times: pd.DatetimeIndex) -> str:
    step = np.median(np.diff(times.values).astype("timedelta64[D]").astype(float))
    if 27 <= step <= 32:
        return "month"
    if 360 <= step <= 370:
        return "year"
    return "step"


def _phase_title(phase: str, window, times) -> str:
    unit = _unit(times)
    plural = f"{unit}s"
    if phase == "before":
        n = -window[0]
        return f"Before ({n} {unit if n == 1 else plural})"
    if phase == "during":
        return "During"
    return f"After ({window[1]} {unit if window[1] == 1 else plural})"


def _furniture(ax, projection, extent, aoi_map, map_w, map_h, size, o) -> None:
    metres_per_unit, _ = maps._ground_scale(projection, extent)
    spec = maps._FurnitureSpec(
        o["north_arrow"], o["scale_bar"], metres_per_unit, extent[1] - extent[0]
    )
    parts = maps._Parts(
        None,
        False,
        1.0,
        spec,
        aoi_map if aoi_map is not None else trends._empty(),
        None,
        None,
        extent,
    )
    occupied, clear = maps._occupied(parts, map_w, map_h, size)
    variants = maps._furniture_variants(spec, map_w, map_h)
    found = maps._place_furniture(variants, occupied, clear, map_w, map_h, [])
    if found is None:
        found = maps._place_furniture(variants, None, None, map_w, map_h, [])
    item, choice = found if found is not None else (None, None)
    maps._draw_furniture(ax, item, choice, map_w, map_h, o["north_arrow"], o["scale_bar"])


def _legend_handles(
    aoi_label, tested, stipple, alpha, sig_fraction, excluded, no_data, label, test
):
    handles = []
    if aoi_label is not None:
        handles.append(Line2D([], [], color=maps.AOI_COLOUR, linewidth=1.0, label=aoi_label))
    if tested:
        text = f"p < {alpha:g} in ≥ {sig_fraction * 100:g} % of pixels"
        if stipple == "dots":
            handles.append(
                Line2D(
                    [],
                    [],
                    marker="o",
                    linestyle="none",
                    markersize=2.0,
                    markerfacecolor=trends.DOT_COLOUR,
                    markeredgecolor="white",
                    markeredgewidth=0.15,
                    label=text,
                )
            )
        else:
            handles.append(
                Patch(
                    facecolor="none", edgecolor=TEXT_COLOUR, hatch="....", linewidth=0.0, label=text
                )
            )
    if excluded.any():
        handles.append(
            Patch(
                facecolor=NO_DATA_COLOUR,
                edgecolor="white",
                hatch=trends.EXCLUDED_HATCH,
                linewidth=0.0,
                label=label,
            )
        )
    if no_data.any():
        handles.append(
            Patch(
                facecolor=NO_DATA_COLOUR,
                edgecolor="white",
                hatch=trends.NO_DATA_HATCH,
                linewidth=0.0,
                label="No data",
            )
        )
    return handles


def _draw_series(ax, composite, used, var, times, small, size) -> dict[str, Any]:
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    offsets, values = composite.offsets, composite.series
    lengths = [e.end - e.start + 1 for e in used]
    period = int(np.median(lengths))
    ax.axvspan(-0.5, period - 0.5, color=EVENT_PERIOD_COLOUR, linewidth=0, zorder=0)
    ax.axhline(0, color=SECONDARY_COLOUR, linewidth=0.6, linestyle=(0, (3, 2)), zorder=1)
    for row in values:
        ax.plot(offsets, row, color=EVENT_LINE_COLOUR, linewidth=0.6, alpha=0.9, zorder=2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = np.nanmean(values, axis=0)
        if values.shape[0] >= 4:
            low, high = np.nanpercentile(values, [25, 75], axis=0)
            spread = "interquartile range"
        else:
            low, high = np.nanmin(values, axis=0), np.nanmax(values, axis=0)
            spread = "range"
    band = ax.fill_between(
        offsets, low, high, color=trends.ENVELOPE_COLOUR, alpha=0.5, linewidth=0, zorder=1.5
    )
    band._eofigs_envelope = True
    ax.plot(offsets, mean, color=TEXT_COLOUR, linewidth=1.2, zorder=3)
    unit = _unit(times)
    ax.set_xlabel(
        f"{unit.capitalize()}s from event start" if unit != "step" else "Steps from event start",
        size=size,
    )
    ax.set_ylabel(var.short_label, size=size)
    ax.set_xlim(offsets[0] - 0.5, offsets[-1] + 0.5)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=min(12, offsets.size)))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: trends.tick_label(v)))
    ax.tick_params(labelsize=small)
    tidy_axes(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=min(12, offsets.size)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: trends.tick_label(v)))
    handles = [
        Line2D([], [], color=EVENT_LINE_COLOUR, linewidth=0.6, label="Each event"),
        Line2D([], [], color=TEXT_COLOUR, linewidth=1.2, label="Mean of events"),
        Patch(facecolor=trends.ENVELOPE_COLOUR, alpha=0.5, label=spread.capitalize()),
        Patch(facecolor=EVENT_PERIOD_COLOUR, label="Event period (median length)"),
    ]
    leg = ax.legend(
        handles=handles,
        loc="lower right",
        bbox_to_anchor=(1.0, 1.0),
        prop={"size": small, "weight": "bold"},
        frameon=False,
        ncols=4,
        borderaxespad=0.3,
        handlelength=1.6,
    )
    leg.set_zorder(8)
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)
    return {
        "offsets": [int(v) for v in offsets],
        "mean": [_round(v) for v in mean],
        "spread": spread,
        "period_steps": period,
    }


def _round(value) -> float | None:
    return None if not np.isfinite(value) else round(float(value), 4)


# ============================================================================ caption


def _caption(record, used, var, grid, times, o, threshold, tested) -> str:
    n = len(used)
    unit = _unit(times)
    dates = "; ".join(_event_text(e, times) for e in used)
    parts = [f"{n} event{'s' if n != 1 else ''} ({dates})."]
    if o["event_rule"]:
        parts.append(f"Events: {o['event_rule'].rstrip('.')}.")
    baseline = f"the {'monthly ' if record['climatology'] == 'month' else ''}climatology"
    years = f"{times[0]:%Y}–{times[-1]:%Y}"
    base = f"of the {unit}s outside the event windows ({years})"
    if o["baseline"] is not None:
        lo, hi = (pd.Timestamp(v) for v in o["baseline"])
        base = f"of the {unit}s from {lo:%Y-%m} to {hi:%Y-%m} outside the event windows"
    what = "Anomalies" if o["kind"] == "anomaly" else "Standardised anomalies (z-scores)"
    trend = (
        f", after removing a per-pixel linear trend fitted to those {unit}s"
        if (o["detrend"] == "linear")
        else ""
    )
    parts.append(f"{what} from {baseline} {base}{trend}.")
    w0, w1 = o["window"]
    parts.append(
        f"Before: mean of the {-w0} {unit}s before each event; after: mean of the "
        f"{w1} {unit}s after it; maps show the mean over events."
    )
    units = trends._plain(var.units)
    limit = f"±{record['limits']:g}{' ' + units if units else ''}"
    if record["limits_rule"] == "p98":
        parts.append(
            f"Colours are limited to {limit} (98th percentile of |anomaly| over all "
            f"maps); {trends.percent(record['clipped_percent'])} % of pixels exceed this."
        )
    elif record["limits_rule"] == "fixed":
        parts.append(
            f"Colours are limited to {limit}; {trends.percent(record['clipped_percent'])} % of "
            "pixels exceed this."
        )
    else:
        parts.append(f"Colours span the full range ({limit}).")
    res = abs(float(grid.rio.resolution()[0]))
    size = f"{res:g} m" if grid.rio.crs.is_projected else f"{res:g}°"
    if tested:
        name = "t-test" if o["test"] == "ttest" else "Wilcoxon signed-rank test"
        what = "Dots" if o["stipple"] == "dots" else "Hatching"
        parts.append(
            f"{what}: at least {o['sig_fraction'] * 100:g} % of {size} pixels "
            f"significant ({name} across {n} events, p < {o['alpha']:g})."
        )
    elif o["test"] is not None and n < MIN_EVENTS:
        parts.append(f"No significance test: fewer than {MIN_EVENTS} events.")
    if record["excluded_percent"] > 0:
        name = var.symbol.removesuffix(" anomaly").removesuffix(" z-score")
        what = (
            f"mean {name} below {threshold:g} over the record (not vegetated; "
            if threshold is not None
            else "excluded pixels ("
        )
        parts.append(
            f"Grey with diagonal hatching: {what}"
            f"{trends.percent(record['excluded_percent'])} % of pixels)."
        )
    if record["no_data_percent"] > 0:
        parts.append(
            f"Grey with cross-hatching: no data in at least one map "
            f"({trends.percent(record['no_data_percent'])} % of pixels)."
        )
    if "series" in record:
        area = "study area" if o["aoi"] is not None else "map"
        parts.append(
            f"Series: {area}-mean anomaly for each event (grey), their mean (black) "
            f"and {record['series']['spread']} (band); shading marks the median event "
            "length."
        )
    return " ".join(parts)


def _event_text(event: _Event, times) -> str:
    start, end = times[event.start], times[event.end]
    if event.end == event.start:
        return f"{start:%Y-%m}"
    if start.year == end.year:
        return f"{start:%Y-%m} to {end:%m}"
    return f"{start:%Y-%m} to {end:%Y-%m}"
