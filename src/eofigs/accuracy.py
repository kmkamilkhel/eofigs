"""Accuracy scatter: observed against predicted values with the 1:1 line, a fit and statistics."""

from __future__ import annotations

import math
import warnings
from collections.abc import Sequence
from typing import Any

import matplotlib as mpl
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter, LogLocator

from eofigs import maps, palettes
from eofigs._colour import OKABE_ITO, SECONDARY_COLOUR, TEXT_COLOUR
from eofigs._presets import get_journal, resolve_width
from eofigs.styling import _STATE, TICK_STEPS, current_max_ticks, label_panels, new_figure
from eofigs.trends import _plain, tick_label
from eofigs.variables import Variable
from eofigs.variables import variable as lookup_variable

__all__ = ["accuracy_scatter"]

#: Statistics that ``stats=`` accepts, in the order the box lists them.
STATS = ("r2", "r", "nse", "rmse", "rrmse", "mae", "bias", "rbias", "slope", "intercept", "n")
FITS = ("ols", "rma", None)
ORIENTATIONS = ("observed_y", "observed_x")
#: ``density="auto"`` colours points by density above this many pairs.
DENSITY_THRESHOLD = 1000
#: Cells per axis of the grid that counts points for the density colours.
DENSITY_BINS = 60
#: Most groups ``groups=`` takes (one colour and marker each).
MAX_GROUPS = 6
#: Group colours: Okabe-Ito without yellow (weak on white) and black (used for lines).
GROUP_COLOURS = tuple(c for c in OKABE_ITO if c not in ("#F0E442", "#000000"))
GROUP_MARKERS = ("o", "s", "^", "D", "v", "P")
#: Colours for point density: the slate ramp from its third step, so single points show.
DENSITY_CMAP = LinearSegmentedColormap.from_list("eofigs.slate_density", palettes.slate[2:])

_NAMES = {
    "r2": "R²",
    "r": "r",
    "nse": "NSE",
    "rmse": "RMSE",
    "rrmse": "rRMSE",
    "mae": "MAE",
    "bias": "Bias",
    "rbias": "rBias",
    "slope": "Slope",
    "intercept": "Intercept",
    "n": "n",
}
_DEFINITIONS = {
    "r2": "R²: squared Pearson correlation",
    "r": "r: Pearson correlation",
    "nse": "NSE: Nash–Sutcliffe efficiency, 1 − Σ(P − O)²/Σ(O − Ō)²",
    "rmse": "RMSE: root-mean-square error",
    "rrmse": "rRMSE: RMSE as a percentage of the observed mean",
    "mae": "MAE: mean absolute error",
    "bias": "bias: mean of predicted − observed",
    "rbias": "rBias: bias as a percentage of the observed mean",
}
_UNIT_STATS = ("rmse", "mae", "bias", "intercept")
_PERCENT_STATS = ("rrmse", "rbias")
_CORNERS = ("upper left", "lower right", "upper right", "lower left")


def accuracy_scatter(
    observed: Any,
    predicted: Any,
    *,
    variable: str | Variable | None = None,
    groups: Any = None,
    density: bool | str = "auto",
    stats: Sequence[str] = ("r2", "rmse", "bias", "n"),
    fit: str | None = "ols",
    orientation: str = "observed_y",
    one_to_one: bool = True,
    limits: tuple[float, float] | None = None,
    observed_label: str | None = None,
    predicted_label: str | None = None,
    stats_loc: str = "auto",
    legend: bool = True,
    labels: str | list[str] | None = None,
    width: str | float = "single",
    height_mm: float | None = None,
    journal: str | None = None,
    ax: Axes | None = None,
) -> Figure:
    """Scatter of observed against predicted values with the 1:1 line, a fit and statistics.

    By default the predicted values go on the x axis and the observed values on the y
    axis, and the fitted line is the ordinary least-squares regression of observed on
    predicted, so that its slope and intercept read directly as the model's consistency
    and bias (Piñeiro et al. 2008, Ecological Modelling 216: 316–322).

    Parameters
    ----------
    observed, predicted : array-like, pandas Series or xarray DataArray
        Paired values of the same shape; they are flattened, and pairs with a missing
        value in either are left out (and counted in the record).
    variable : str or Variable, optional
        The variable (for example ``"agb"``); sets the axis labels, units and the number
        format of the statistics. Taken from the name of ``observed`` when it matches the
        variable library.
    groups : array-like, optional
        A category for each pair (up to 6), drawn in Okabe-Ito colours with distinct
        markers. Statistics for each group are in the record and the caption.
    density : {"auto", True, False}, default "auto"
        Colour points by the number of points in each cell of a 60 × 60 grid (log scale,
        densest on top, rasterised in vector files). ``"auto"``: above 1 000 pairs and
        without groups.
    stats : sequence of str, default ("r2", "rmse", "bias", "n")
        Statistics in the box: ``"r2"`` (squared Pearson correlation), ``"r"``, ``"nse"``
        (Nash–Sutcliffe efficiency), ``"rmse"``, ``"rrmse"`` (% of the observed mean),
        ``"mae"``, ``"bias"`` (mean of predicted − observed), ``"rbias"`` (%),
        ``"slope"`` and ``"intercept"`` (of the fitted line) and ``"n"``. All of them are
        in the record whatever is shown.
    fit : {"ols", "rma", None}, default "ols"
        Fitted line: ordinary least squares of the y-axis values on the x-axis values,
        reduced major axis, or none.
    orientation : {"observed_y", "observed_x"}, default "observed_y"
        Observed values on the y axis (Piñeiro et al. 2008) or on the x axis.
    one_to_one : bool, default True
        Draw the 1:1 line.
    limits : (float, float), optional
        Shared limits of both axes. By default the data range, rounded outwards to ticks.
    observed_label, predicted_label : str, optional
        Axis labels; by default "Observed" and "Predicted" with the variable and units.
    stats_loc : str, default "auto"
        Corner of the statistics box: ``"auto"`` (the corner with the fewest points) or
        ``"upper left"``, ``"lower right"``, ``"upper right"``, ``"lower left"``.
    legend : bool, default True
        Legend for the lines and groups, above the plot.
    labels : str or list of str, optional
        Panel label. A single-panel figure has none unless given.
    width : str or float, default "single"
        Named journal width or width in mm.
    height_mm : float, optional
        Figure height; by default it follows the square plot.
    journal : str, optional
        Journal preset (defaults to the one set by :func:`set_style`).
    ax : matplotlib Axes, optional
        Draw into an existing axes, for example one panel of a larger figure.

    Returns
    -------
    matplotlib.figure.Figure
        The figure. ``fig.eofigs_layout`` (or ``ax.eofigs_layout`` with ``ax=``) records
        every statistic at full precision, the statistics of each group, the fitted line,
        the limits and a ready caption sentence (``["caption"]``).

    Raises
    ------
    ValueError
        For inputs of different shapes, fewer than 3 pairs, observed values that are all
        equal, an unknown statistic, ``fit``, ``orientation``, ``density`` or
        ``stats_loc``, more than 6 groups, or groups together with ``density=True``.

    Examples
    --------
    >>> import numpy as np
    >>> import eofigs
    >>> rng = np.random.default_rng(0)
    >>> observed = rng.uniform(20, 300, 200)
    >>> predicted = observed + rng.normal(0, 25, 200)
    >>> fig = eofigs.accuracy_scatter(observed, predicted, variable="agb")
    >>> fig.eofigs_layout["stats"]["n"]
    200
    """
    _check_arguments(stats, fit, orientation, density, stats_loc)
    var = _variable(variable, observed)
    obs, pred, grp, dropped = _pairs(observed, predicted, groups)
    names = _group_names(grp, groups)
    if density is True and grp is not None:
        raise ValueError("groups and density=True cannot be combined; pass density=False.")
    use_density = (
        bool(density) if density != "auto" else (grp is None and obs.size > DENSITY_THRESHOLD)
    )
    xy = (pred, obs) if orientation == "observed_y" else (obs, pred)
    record_stats = _stats(obs, pred, *xy, fit)
    group_stats = {}
    if grp is not None:
        for name in names:
            sel = grp == name
            if sel.sum() >= 3:
                gxy = (xy[0][sel], xy[1][sel])
                group_stats[name] = _stats(obs[sel], pred[sel], *gxy, fit)
            else:
                group_stats[name] = {"n": int(sel.sum())}
    lo, hi, ticks = _limits(obs, pred, limits)
    obs_label, pred_label = _axis_labels(var, observed_label, predicted_label)
    x_label, y_label = (
        (pred_label, obs_label) if orientation == "observed_y" else (obs_label, pred_label)
    )

    small = maps._small_font()
    size = mpl.rcParams["font.size"]
    handles = _handles(one_to_one, fit, grp is not None, names) if legend else []
    holder_fig, ax = _axes(
        ax, width, height_mm, journal, ticks, use_density, handles, small, size, labels
    )

    x, y = xy
    if use_density:
        image, max_count = _draw_density(ax, x, y, lo, hi)
    else:
        image, max_count = None, None
        _draw_points(ax, x, y, grp, names)
    if one_to_one:
        ax.plot([lo, hi], [lo, hi], color=SECONDARY_COLOUR, linewidth=0.8, zorder=3,
                solid_capstyle="butt")  # fmt: skip
    if fit is not None:
        s = record_stats
        xs = np.array([x.min(), x.max()])
        ax.plot(xs, s["intercept"] + s["slope"] * xs, color=TEXT_COLOUR, linewidth=1.0,
                linestyle=(0, (4, 2)), zorder=4)  # fmt: skip
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal", adjustable="box")
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_locator(FixedLocator(ticks))
        axis.set_major_formatter(FuncFormatter(lambda v, _: tick_label(v)))
    ax.tick_params(labelsize=small)
    ax.set_xlabel(x_label, size=size)
    ax.set_ylabel(y_label, size=size)
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)

    if image is not None:
        _colour_bar(ax, image, max_count, small, size)
    if handles:
        _legend(ax, handles, small)
    corner = _place_stats(ax, x, y, lo, hi, record_stats, stats, var, small, stats_loc)
    if labels is not None:
        label_panels([ax], labels)

    record: dict[str, Any] = {
        "n": record_stats["n"],
        "dropped": dropped,
        "stats": record_stats,
        "shown": list(stats),
        "groups": group_stats or None,
        "fit": None
        if fit is None
        else {
            "method": fit,
            "y": "observed" if orientation == "observed_y" else "predicted",
            "x": "predicted" if orientation == "observed_y" else "observed",
            "slope": record_stats["slope"],
            "intercept": record_stats["intercept"],
        },
        "orientation": orientation,
        "density": {"bins": DENSITY_BINS, "max_count": max_count} if use_density else None,
        "limits": [lo, hi],
        "ticks": [float(t) for t in ticks],
        "stats_loc": corner,
    }
    record["caption"] = _caption(record, var, fit, one_to_one, grp is not None, groups)
    ax.eofigs_layout = record
    holder_fig.eofigs_layout = record
    return holder_fig


# ============================================================================ inputs


def _check_arguments(stats, fit, orientation, density, stats_loc) -> None:
    unknown = [s for s in stats if s not in STATS]
    if unknown:
        raise ValueError(f"Unknown statistic(s) {unknown}; use any of {STATS}.")
    if fit not in FITS:
        raise ValueError(f"fit must be one of {FITS} (got {fit!r}).")
    if orientation not in ORIENTATIONS:
        raise ValueError(f"orientation must be one of {ORIENTATIONS} (got {orientation!r}).")
    if density not in ("auto", True, False):
        raise ValueError(f"density must be 'auto', True or False (got {density!r}).")
    if stats_loc != "auto" and stats_loc not in _CORNERS:
        raise ValueError(f"stats_loc must be 'auto' or one of {_CORNERS} (got {stats_loc!r}).")


def _variable(variable, observed) -> Variable | None:
    if variable is not None:
        return lookup_variable(variable)
    name = getattr(observed, "name", None)
    if isinstance(name, str):
        try:
            return lookup_variable(name)
        except ValueError:
            return None
    return None


def _values(data) -> np.ndarray:
    if hasattr(data, "values") and not isinstance(data, np.ndarray):
        data = data.values
    return np.asarray(data, dtype="float64")


def _pairs(observed, predicted, groups):
    obs, pred = _values(observed), _values(predicted)
    if obs.shape != pred.shape:
        raise ValueError(
            f"observed and predicted have different shapes: {obs.shape} and {pred.shape}."
        )
    obs, pred = obs.ravel(), pred.ravel()
    grp = None
    if groups is not None:
        raw = groups.values if hasattr(groups, "values") else groups
        grp = np.asarray(raw, dtype=object).ravel()
        if grp.size != obs.size:
            raise ValueError(f"groups has {grp.size} values for {obs.size} pairs.")
    keep = np.isfinite(obs) & np.isfinite(pred)
    if grp is not None:
        keep &= pd.notna(grp)
    dropped = int((~keep).sum())
    obs, pred = obs[keep], pred[keep]
    grp = grp[keep] if grp is not None else None
    if obs.size < 3:
        raise ValueError(f"At least 3 valid pairs are needed (got {obs.size}).")
    if np.ptp(obs) == 0 or np.ptp(pred) == 0:
        raise ValueError("The observed or predicted values are all equal; no statistics.")
    return obs, pred, grp, dropped


def _group_names(grp, groups) -> list:
    if grp is None:
        return []
    raw = groups.values if hasattr(groups, "values") else groups
    if isinstance(getattr(raw, "dtype", None), pd.CategoricalDtype):
        present = set(grp)
        names = [c for c in raw.categories if c in present]
    else:
        names = sorted(set(grp), key=str)
    if len(names) > MAX_GROUPS:
        raise ValueError(
            f"{len(names)} groups; at most {MAX_GROUPS} can be told apart. Merge groups or "
            "draw them as separate panels with ax=."
        )
    return names


# ============================================================================ statistics


def _stats(obs, pred, x, y, fit) -> dict[str, Any]:
    """All statistics at full precision; the fit regresses y on x (plot axes)."""
    diff = pred - obs
    mean_obs = float(obs.mean())
    r = float(np.corrcoef(obs, pred)[0, 1])
    rmse = float(np.sqrt(np.mean(diff**2)))
    bias = float(diff.mean())
    out: dict[str, Any] = {
        "n": int(obs.size),
        "r": r,
        "r2": r * r,
        "nse": float(1.0 - np.sum(diff**2) / np.sum((obs - mean_obs) ** 2)),
        "rmse": rmse,
        "rrmse": 100.0 * rmse / mean_obs if mean_obs != 0 else float("nan"),
        "mae": float(np.mean(np.abs(diff))),
        "bias": bias,
        "rbias": 100.0 * bias / mean_obs if mean_obs != 0 else float("nan"),
    }
    slope, intercept = _fit(x, y, "ols" if fit is None else fit)
    out["slope"], out["intercept"] = slope, intercept
    return out


def _fit(x, y, method) -> tuple[float, float]:
    mx, my = float(x.mean()), float(y.mean())
    sx, sy = float(x.std()), float(y.std())
    if method == "rma":
        r = float(np.corrcoef(x, y)[0, 1])
        slope = math.copysign(sy / sx, r)
    else:
        slope = float(np.sum((x - mx) * (y - my)) / np.sum((x - mx) ** 2))
    return slope, my - slope * mx


# ============================================================================ layout


def _limits(obs, pred, limits):
    max_n = current_max_ticks() or 5
    if limits is not None:
        lo, hi = (float(v) for v in limits)
        if not hi > lo:
            raise ValueError(f"limits must be (low, high) with high > low (got {limits}).")
        from eofigs.styling import round_ticks

        return lo, hi, round_ticks(lo, hi, min(4, max_n), max_n)
    lo = float(min(obs.min(), pred.min()))
    hi = float(max(obs.max(), pred.max()))
    span = hi - lo
    top = math.floor(math.log10(span))
    steps = [m * 10.0**p for p in range(top - 3, top + 2) for m in TICK_STEPS[:-1]]
    # limits on ticks when that adds at most a tenth of the range on each side
    for step in steps:
        a, b = math.floor(lo / step + 1e-9), math.ceil(hi / step - 1e-9)
        if b - a + 1 <= max_n:
            if lo - a * step <= 0.1 * span and b * step - hi <= 0.1 * span:
                ticks = np.round(np.arange(a, b + 1) * step, 12)
                return float(ticks[0]), float(ticks[-1]), ticks
            break
    # otherwise round the limits to a fine step (about 1/20 of the range), ticks inside
    from eofigs.styling import round_ticks

    fine = next(s for s in steps if s >= span / 20)
    lo_l = round(math.floor(lo / fine + 1e-9) * fine, 12)
    hi_l = round(math.ceil(hi / fine - 1e-9) * fine, 12)
    return lo_l, hi_l, round_ticks(lo_l, hi_l, min(4, max_n), max_n)


def _axis_labels(var, observed_label, predicted_label) -> tuple[str, str]:
    if var is None:
        what = ""
    elif var.symbol.isupper() and len(var.symbol) > 1:
        what = f" {var.symbol}" + (f" ({var.units})" if var.units else "")
    else:
        long = var.long_name
        what = f" {long[0].lower()}{long[1:]}" + (f" ({var.units})" if var.units else "")
    obs = observed_label if observed_label is not None else f"Observed{what}"
    pred = predicted_label if predicted_label is not None else f"Predicted{what}"
    return obs, pred


def _handles(one_to_one, fit, has_groups, names):
    handles = []
    if has_groups:
        for i, name in enumerate(names):
            handles.append(
                Line2D(
                    [],
                    [],
                    linestyle="none",
                    marker=GROUP_MARKERS[i],
                    markersize=4.0,
                    markerfacecolor=GROUP_COLOURS[i],
                    markeredgecolor="white",
                    markeredgewidth=0.3,
                    label=str(name),
                )  # fmt: skip
            )
    if one_to_one:
        handles.append(Line2D([], [], color=SECONDARY_COLOUR, linewidth=0.8, label="1:1"))
    if fit is not None:
        text = "OLS fit" if fit == "ols" else "RMA fit"
        handles.append(Line2D([], [], color=TEXT_COLOUR, linewidth=1.0, linestyle=(0, (4, 2)),
                              label=text))  # fmt: skip
    return handles


def _legend_rows(handles, small, width_mm) -> tuple[int, int]:
    widths = [maps._text_mm(h.get_label(), small, "bold")[0] + 0.6 * small * 2.4 * maps._PT
              for h in handles]  # fmt: skip
    for ncols in range(len(handles), 0, -1):
        rows = math.ceil(len(handles) / ncols)
        cols = [max(widths[c::ncols]) for c in range(ncols)]
        if sum(cols) + 2.0 * (ncols - 1) <= width_mm:
            return ncols, rows
    return 1, len(handles)  # pragma: no cover (one column always fits)


def _axes(ax, width, height_mm, journal, ticks, use_density, handles, small, size, labels):
    if ax is not None:
        return ax.get_figure(root=True), ax
    preset = get_journal(journal or _STATE["journal"])
    fig_w = resolve_width(width, preset)
    tick_w = max(maps._text_mm(tick_label(t), small)[0] for t in ticks)
    lab_h = size * maps._PT
    small_h = small * maps._PT
    left = 1.0 + lab_h + 1.8 + tick_w + 1.0 + 1.1
    bottom = 1.0 + lab_h + 1.5 + small_h + 1.0 + 1.1
    right = 3.0
    if use_density:
        right = 1.5 + 2.5 + 1.1 + 1.0 + maps._text_mm("1000", small)[0] + 1.8 + lab_h + 1.0
    side = fig_w - left - right
    top = 3.0 if labels is None else lab_h + 3.0
    if handles:
        _, rows = _legend_rows(handles, small, side)
        top = max(top, rows * small_h * 1.7 + 3.0)
    fig_h = top + side + bottom
    if height_mm is not None:
        side = min(side, height_mm - top - bottom)
        fig_h = height_mm
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        fig, ax0 = new_figure(fig_w, height_mm=fig_h, journal=preset.key)
    fig.set_layout_engine("none")
    ax0.remove()
    x0 = left + (fig_w - left - right - side) / 2
    ax = fig.add_axes((x0 / fig_w, bottom / fig_h, side / fig_w, side / fig_h))
    return fig, ax


# ============================================================================ drawing


def _draw_points(ax, x, y, grp, names) -> None:
    if grp is None:
        ax.scatter(x, y, s=9.0, facecolors="none", edgecolors=TEXT_COLOUR, linewidths=0.5,
                   alpha=0.7, zorder=2)  # fmt: skip
        return
    for i, name in enumerate(names):
        sel = grp == name
        ax.scatter(x[sel], y[sel], s=12.0, marker=GROUP_MARKERS[i], color=GROUP_COLOURS[i],
                   edgecolors="white", linewidths=0.3, alpha=0.85, zorder=2)  # fmt: skip


def _draw_density(ax, x, y, lo, hi):
    edges = np.linspace(lo, hi, DENSITY_BINS + 1)
    counts, _, _ = np.histogram2d(x, y, bins=(edges, edges))
    ix = np.clip(np.searchsorted(edges, x, side="right") - 1, 0, DENSITY_BINS - 1)
    iy = np.clip(np.searchsorted(edges, y, side="right") - 1, 0, DENSITY_BINS - 1)
    c = counts[ix, iy]
    order = np.argsort(c, kind="stable")  # densest drawn last, on top
    max_count = int(c.max())
    image = ax.scatter(x[order], y[order], c=c[order], s=3.0, linewidths=0, cmap=DENSITY_CMAP,
                       norm=LogNorm(vmin=1, vmax=max(max_count, 2)), rasterized=True,
                       zorder=2)  # fmt: skip
    return image, max_count


def _colour_bar(ax, image, max_count, small, size) -> None:
    fig = ax.get_figure(root=True)
    width_mm = 2.5
    ax_w = ax.get_position().width * fig.get_figwidth() * 25.4
    cax = ax.inset_axes((1.0 + 1.5 / ax_w, 0.0, width_mm / ax_w, 1.0))
    bar = fig.colorbar(image, cax=cax)
    bar.outline.set_linewidth(0.6)
    bar.ax.yaxis.set_major_locator(LogLocator(base=10))
    bar.ax.yaxis.set_minor_locator(LogLocator(base=10, subs=(2, 5)))
    bar.ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}"))
    bar.ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    bar.ax.tick_params(labelsize=small)
    bar.set_label("Points per cell", size=size)
    _ = max_count


def _legend(ax, handles, small) -> None:
    fig = ax.get_figure(root=True)
    width_mm = ax.get_position().width * fig.get_figwidth() * 25.4
    ncols, _ = _legend_rows(handles, small, width_mm)
    leg = ax.legend(handles=handles, loc="lower right", bbox_to_anchor=(1.0, 1.0),
                    prop={"size": small, "weight": "bold"}, frameon=False, ncols=ncols,
                    borderaxespad=0.3, handlelength=2.4, columnspacing=1.2)  # fmt: skip
    leg.set_zorder(8)


def _decimals(value: float, digits: int = 3) -> int:
    if not np.isfinite(value) or value == 0:
        return 0
    return int(min(max(digits - 1 - math.floor(math.log10(abs(value))), 0), 6))


def _number(value: float, decimals: int) -> str:
    if not np.isfinite(value):
        return "n/a"
    text = f"{value:.{decimals}f}"
    if float(text) == 0:
        text = f"{0:.{decimals}f}"
    return text.replace("-", "−")


def _count(n: int) -> str:
    return f"{n:,}".replace(",", " ") if n >= 10_000 else str(n)


def stat_texts(values: dict[str, Any], shown: Sequence[str], units: str) -> list[str]:
    """Box lines such as "RMSE = 31.2 Mg ha⁻¹" for the statistics in ``shown``.

    Statistics with units share one number of decimals, set by the largest of them
    (three significant digits); R², r, NSE and the slope get two decimals and the
    percentages one.

    Examples
    --------
    >>> from eofigs.accuracy import stat_texts
    >>> stat_texts({"r2": 0.8123, "rmse": 31.24, "bias": -4.06, "n": 400},
    ...            ["r2", "rmse", "bias", "n"], "m")
    ['R² = 0.81', 'RMSE = 31.2 m', 'Bias = −4.1 m', 'n = 400']
    """
    scale = max((abs(values[k]) for k in _UNIT_STATS if k in values and k != "intercept"
                 and np.isfinite(values[k])), default=0.0)  # fmt: skip
    dec = _decimals(scale)
    suffix = f" {units}" if units else ""
    lines = []
    for key in [k for k in STATS if k in shown]:
        v = values[key]
        if key == "n":
            text = _count(int(v))
        elif key in _UNIT_STATS:
            text = _number(v, dec) + suffix
        elif key in _PERCENT_STATS:
            text = _number(v, 1) + " %"
        else:
            text = _number(v, 2)
        lines.append(f"{_NAMES[key]} = {text}")
    return lines


def _place_stats(ax, x, y, lo, hi, values, shown, var, small, stats_loc) -> str | None:
    if not shown:
        return None
    units = var.units if var is not None else ""
    lines = stat_texts(values, shown, units)
    fig = ax.get_figure(root=True)
    side_mm = ax.get_position().width * fig.get_figwidth() * 25.4
    w = max(maps._text_mm(_measurable(t), small)[0] for t in lines) + 3.0
    h = len(lines) * small * maps._PT * 1.35 + 2.0
    fw, fh = min(w / side_mm, 0.9), min(h / side_mm, 0.9)
    fx, fy = (x - lo) / (hi - lo), (y - lo) / (hi - lo)
    if stats_loc == "auto":
        boxes = {
            "upper left": (0.0, 1.0 - fh, fw, 1.0),
            "lower right": (1.0 - fw, 0.0, 1.0, fh),
            "upper right": (1.0 - fw, 1.0 - fh, 1.0, 1.0),
            "lower left": (0.0, 0.0, fw, fh),
        }
        counts = {c: int(((fx >= b[0]) & (fy >= b[1]) & (fx <= b[2]) & (fy <= b[3])).sum())
                  for c, b in boxes.items()}  # fmt: skip
        corner = min(_CORNERS, key=lambda c: counts[c])
    else:
        corner = stats_loc
    pad = 2.0 / side_mm
    vert, horiz = corner.split()
    px = pad if horiz == "left" else 1.0 - pad
    py = 1.0 - pad if vert == "upper" else pad
    ax.text(px, py, "\n".join(lines), transform=ax.transAxes, ha=horiz,
            va="top" if vert == "upper" else "bottom", size=small, linespacing=1.35, zorder=9,
            bbox={"boxstyle": "square,pad=0.25", "facecolor": "white", "alpha": 0.8,
                  "edgecolor": "none"})  # fmt: skip
    return corner


# ============================================================================ caption


def _caption(record, var, fit, one_to_one, has_groups, groups) -> str:
    units = _plain(var.units) if var is not None else ""
    suffix = f" {units}" if units else ""
    s = record["stats"]
    parts = []
    if record["orientation"] == "observed_y":
        parts.append(f"Observed against predicted values (n = {_count(s['n'])}).")
    else:
        parts.append(f"Predicted against observed values (n = {_count(s['n'])}).")
    if record["dropped"]:
        parts.append(f"{record['dropped']} pairs with a missing value were left out.")
    defs = [_DEFINITIONS[k] for k in record["shown"] if k in _DEFINITIONS]
    if defs:
        text = "; ".join(defs)
        parts.append(f"{text[0].upper()}{text[1:]}.")
    lines = []
    if one_to_one:
        lines.append("solid line: 1:1")
    if fit is not None:
        f = record["fit"]
        method = "ordinary least-squares regression" if fit == "ols" else "reduced major axis"
        dec = _decimals(max(abs(s["rmse"]), abs(s["bias"])))
        what = (
            f"{method} of {f['y']} on {f['x']}"
            if fit == "ols"
            else f"{method} line of {f['y']} against {f['x']}"
        )
        cite = " (Piñeiro et al. 2008)" if record["orientation"] == "observed_y" else ""
        lines.append(
            f"dashed line: {what}{cite}; slope {_number(f['slope'], 2)}, intercept "
            f"{_number(f['intercept'], dec)}{suffix}"
        )
    if lines:
        text = "; ".join(lines)
        parts.append(f"{text[0].upper()}{text[1:]}.")
    if record["density"] is not None:
        parts.append(
            f"Point colours: number of points in each cell of a {DENSITY_BINS} × "
            f"{DENSITY_BINS} grid over the axis range (log scale)."
        )
    if has_groups and record["groups"]:
        name = getattr(groups, "name", None)
        what = f" by {name}" if isinstance(name, str) and name else " by group"
        items = []
        for g, st in record["groups"].items():
            if "rmse" in st:
                dec = _decimals(max(abs(st["rmse"]), abs(st["bias"])))
                items.append(
                    f"{g}: R² {_number(st['r2'], 2)}, RMSE {_number(st['rmse'], dec)}{suffix} "
                    f"(n = {_count(st['n'])})"
                )
            else:
                items.append(f"{g}: n = {st['n']}")
        parts.append(f"Colours and markers{what}; " + "; ".join(items) + ".")
    return " ".join(parts)


def _measurable(text: str) -> str:
    """Text with mathtext units flattened ("ha$^{-1}$" -> "ha-1") for width estimates."""
    return text.replace("$^{", "").replace("}$", "").replace("$", "")
