"""Trend maps: per-pixel trends with zero-centred colours and print-size significance marks."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

import matplotlib as mpl
import numpy as np
import xarray as xr
from matplotlib.axes import Axes
from matplotlib.colors import Normalize
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

from eofigs import maps
from eofigs._colour import NO_DATA_COLOUR, SECONDARY_COLOUR, TEXT_COLOUR
from eofigs._presets import get_journal, resolve_width
from eofigs.stats import fdr_mask
from eofigs.styling import _STATE, label_panels, round_ticks
from eofigs.variables import Variable
from eofigs.variables import variable as lookup_variable

__all__ = ["trend_map"]

#: Variables whose pixels with a low record mean are greyed out as "not vegetated".
VEGETATION_INDICES = ("ndvi", "evi", "kndvi", "nirv", "lai", "fapar", "gpp", "npp", "sif")
#: Record mean below which a vegetation-index pixel counts as not vegetated (rock, snow, ice).
EXCLUDE_THRESHOLD = 0.1
STIPPLES = ("dots", "hatch")
DOT_COLOUR = TEXT_COLOUR
#: Hatching on the grey of excluded ("not vegetated") and of no-data pixels.
EXCLUDED_HATCH = "///"
NO_DATA_HATCH = "xxx"
#: False discovery rate methods for ``fdr=`` (Benjamini–Hochberg).
FDR_METHODS = ("bh", None)
#: Caption sentence on the per-pixel tests behind the significance marks (Wilks 2016).
ASSUMPTIONS = (
    "Per-pixel Mann–Kendall tests assume serial independence and are not adjusted for "
    "multiple comparisons."
)
DOT_SIZE_MM = 0.35
#: Interquartile band of the profile: the light teal of terra_slate (drawn at 50 %).
ENVELOPE_COLOUR = "#A8B7B6"
#: Latitude bands of the profile are about this tall on the page (mm).
PROFILE_BAND_MM = 2.0
#: A profile band needs at least this many valid full-resolution pixels.
PROFILE_MIN_PIXELS = 20
#: Round values for colour limits; each gives 4-5 round ticks (1.5 would need 0.75 steps).
_MANTISSAS = (1, 1.2, 2, 2.5, 3, 4, 5, 6, 8, 10)
_SUPERSCRIPT = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def trend_map(
    data: xr.DataArray | None = None,
    *,
    slope: xr.DataArray | None = None,
    pvalue: xr.DataArray | None = None,
    alpha: float = 0.05,
    fdr: str | None = None,
    fdr_q: float | None = None,
    dim: str = "time",
    per: str = "decade",
    variable: str | Variable | None = None,
    limits: str | float | None = "p98",
    stipple: str | None = "dots",
    sig_fraction: float = 0.5,
    dot_spacing_mm: float = 1.6,
    exclude: str | float | xr.DataArray | None = "auto",
    exclude_label: str = "Not vegetated",
    aoi: Any = None,
    aoi_label: str = "Study area",
    latitude_profile: bool = False,
    graticule: bool = True,
    north_arrow: bool = True,
    scale_bar: bool = True,
    legend: bool = True,
    labels: str | list[str] | None = None,
    width: str | float = "onehalf",
    height_mm: float | None = None,
    journal: str | None = None,
    ax: Axes | None = None,
    subfigure: Any = None,
) -> Figure:
    """Map per-pixel trends with zero-centred colours and significance marks.

    The trend is computed at the data's full resolution (Theil–Sen slope, Mann–Kendall
    test, :func:`eofigs.trend`) and only then reduced to the printed size: slopes are
    averaged, p-values never are. Significance is shown at print size: a dot (or hatching)
    marks each cell of about ``dot_spacing_mm`` where at least ``sig_fraction`` of the
    valid full-resolution pixels are significant.

    Parameters
    ----------
    data : xarray.DataArray, optional
        Time-series cube with a datetime dimension ``dim`` and a CRS; :func:`trend` is run
        on it. Give either ``data`` or ``slope``.
    slope, pvalue : xarray.DataArray, optional
        A precomputed slope grid (with a CRS) and, optionally, its p-values on the same
        grid (same coordinates; dimensions in another order are transposed to the slope's,
        and a p-value grid with a different CRS is refused). Without p-values no
        significance marks are drawn.
    alpha : float, default 0.05
        Significance level of each pixel's test.
    fdr : {"bh"} or None, default None
        ``"bh"``: Benjamini–Hochberg false discovery rate control over the map's valid
        pixels (finite slope and p-value, not excluded) before the marks are drawn, with
        :func:`eofigs.stats.fdr_mask`. The family of tests is the grid passed in: to make
        the study area the family, clip the data to it first.
    fdr_q : float, optional
        False discovery rate for ``fdr="bh"``; default ``2 * alpha`` (Wilks 2016, BAMS 97:
        2263–2273, for spatially correlated fields).
    dim : str, default "time"
        Time dimension of ``data``.
    per : {"decade", "year"}, default "decade"
        Unit of the slope computed from ``data``.
    variable : str or Variable, optional
        The variable (for example ``"ndvi"``) or its trend; sets the colours and the
        colour-bar label. By default it is recognised from the data.
    limits : "p98", float or None, default "p98"
        Symmetric colour limits: the 98th percentile of the absolute slope rounded up to
        a round value, a number, or ``None`` for the largest absolute slope. Clipped
        values get arrows on the colour bar, and the caption states their share.
    stipple : {"dots", "hatch"} or None, default "dots"
        How significance is marked.
    sig_fraction : float, default 0.5
        Share of significant pixels a cell needs for a mark.
    dot_spacing_mm : float, default 1.6
        Size of the significance cells on the page.
    exclude : "auto", float, DataArray or None, default "auto"
        Pixels drawn in grey and left out of the colours, marks and profile. ``"auto"``
        greys out vegetation-index pixels whose mean over the record is below 0.1 (rock,
        snow, ice; only with ``data``); a number sets that threshold; a boolean grid
        (True = excluded) is used as given.
    exclude_label : str, default "Not vegetated"
        Legend entry for the excluded pixels.
    aoi : GeoDataFrame, GeoSeries or path, optional
        Study area outline drawn on top; the map then shows the study area with a margin.
    aoi_label : str, default "Study area"
        Legend entry for the outline.
    latitude_profile : bool, default False
        Add a panel beside the map with the median and interquartile range of the
        full-resolution slope in latitude bands (valid pixels only; bands with fewer than
        20 pixels are skipped).
    graticule, north_arrow, scale_bar, legend : bool, default True
        Map elements to draw.
    labels : str or list of str, optional
        Panel labels for the map and profile (style default when omitted).
    width : str or float, default "onehalf"
        Named journal width or width in mm.
    height_mm : float, optional
        Figure height; by default it follows the map's shape, up to 75 % of the
        journal's maximum height.
    journal : str, optional
        Journal preset (defaults to the one set by :func:`set_style`).
    ax : cartopy GeoAxes, optional
        Draw into existing map axes (no profile, no automatic size).
    subfigure : matplotlib SubFigure, optional
        Draw within a subfigure, for example one panel of ``fig.subfigures(1, 2)``.

    Returns
    -------
    matplotlib.figure.Figure
        The figure. ``fig.eofigs_layout`` records the colour limits, the clipped and
        significant shares, the number of marks and a ready caption sentence
        (``fig.eofigs_layout["caption"]``).

    Raises
    ------
    ValueError
        For missing or conflicting inputs, grids without a CRS, mismatched grids, an
        unknown ``stipple``, ``sig_fraction`` outside (0, 1], or a profile with ``ax``.

    Examples
    --------
    >>> import numpy as np, pandas as pd, xarray as xr, rioxarray
    >>> import eofigs
    >>> time = pd.date_range("2001-01-01", periods=12, freq="YS")
    >>> y, x = np.arange(3_900_000, 3_880_000, -500.0), np.arange(500_000, 520_000, 500.0)
    >>> values = 0.5 + 0.01 * np.arange(12)[:, None, None] * np.ones((12, y.size, x.size))
    >>> cube = xr.DataArray(values, dims=("time", "y", "x"),
    ...                     coords={"time": time, "y": y, "x": x}, name="ndvi")
    >>> fig = eofigs.trend_map(cube.rio.write_crs("EPSG:32643"))
    >>> fig.eofigs_layout["significant_percent"]
    100.0
    """
    import pyproj
    from cartopy.mpl.geoaxes import GeoAxes

    _check_arguments(data, slope, pvalue, stipple, sig_fraction, ax, subfigure, latitude_profile)
    q = check_fdr(fdr, fdr_q, alpha)
    if ax is not None and not isinstance(ax, GeoAxes):
        raise ValueError("ax must be a cartopy GeoAxes; or leave ax=None to create the map.")
    grids = _grids(data, slope, pvalue, alpha, dim, per)
    var = _trend_variable(variable, grids.slope, per)
    excluded, threshold = _excluded(exclude, data, dim, var, grids.slope)
    valid = np.isfinite(grids.slope.values) & ~excluded
    fdr_record = None
    if q is not None and grids.pvalues is not None:
        result = fdr_mask(grids.pvalues, q=q, valid=valid)
        grids.significant = result.mask
        fdr_record = fdr_entry(result, q)
    shown = grids.slope.where(valid)
    limit, rule = _limits(shown.values, limits)
    stats = _shares(shown.values, grids.significant, valid, limit)

    src_crs = grids.slope.rio.crs
    aoi_map = None
    if aoi is not None:
        aoi_gdf = maps._as_gdf(aoi, "aoi")
        crs = maps.map_crs(aoi_gdf) if not src_crs.is_projected else src_crs
        aoi_map = aoi_gdf.to_crs(crs)
        extent = maps._extent_from(aoi_map)
    else:
        crs = src_crs if src_crs.is_projected else _utm_of(grids.slope)
        extent = _bounds_in(grids.slope, crs)
    if ax is not None:
        crs = maps._crs_of(ax)
    crs = pyproj.CRS.from_user_input(crs)
    projection = maps._projection(crs) if ax is None else ax.projection
    ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])

    preset = get_journal(journal or _STATE["journal"])
    small = maps._small_font()
    size = mpl.rcParams["font.size"]
    outline_label = aoi_label if aoi is not None else None
    handles = _legend_handles(outline_label, grids, stipple, alpha, q, sig_fraction, excluded,
                              grids.slope, exclude_label)  # fmt: skip
    legend_mm = maps._legend_size(handles, small) if legend and handles else None
    spec = None
    if north_arrow or scale_bar:
        metres_per_unit, _ = maps._ground_scale(projection, extent)
        spec = maps._FurnitureSpec(north_arrow, scale_bar, metres_per_unit, extent[1] - extent[0])

    holder = subfigure
    prof_ax = None
    if ax is not None:
        fig, lay = ax.figure, None
        holder = ax.figure
        pos = ax.get_position()
        box_w, box_h = maps._size_mm(holder)
        map_w, map_h = pos.width * box_w, pos.height * box_h
    else:
        if subfigure is not None:
            width, height_mm = maps._size_mm(subfigure)
        has_labels = (latitude_profile or subfigure is not None) and (
            labels is not None or _STATE.get("labels") is not None
        )  # room for panel letters: with the profile, or as one panel of a larger figure
        lay = _layout(width, height_mm, preset, ratio, small, size, legend_mm, latitude_profile,
                      has_labels)  # fmt: skip
        fig, ax = maps._make_axes(lay, preset, projection, holder)
        holder = holder if holder is not None else fig
        map_w, map_h = lay.map_box[2:]
    ax.set_extent(extent, crs=projection)
    ax.set_facecolor("white")
    ax.spines["geo"].set_linewidth(0.6)
    ax.spines["geo"].set_edgecolor(TEXT_COLOUR)

    dpi = preset.export_dpi
    image = _draw_slope(ax, shown, var, limit, crs, extent, map_w, map_h, dpi, projection)
    no_data = ~np.isfinite(grids.slope.values) & ~excluded
    for mask, hatch in ((excluded, EXCLUDED_HATCH), (no_data, NO_DATA_HATCH)):
        grey = xr.DataArray(mask, coords=grids.slope.coords, dims=grids.slope.dims)
        _draw_grey(ax, grey.rio.write_crs(src_crs), hatch, crs, extent, map_w, map_h, dpi,
                   projection)  # fmt: skip
    marks, cell_mm = 0, None
    if grids.significant is not None and stipple is not None:
        marks, cell_mm = _draw_marks(ax, grids.significant, valid, grids.slope, stipple,
                                     sig_fraction, dot_spacing_mm, crs, extent, map_w)  # fmt: skip
    if aoi_map is not None:
        ax.add_geometries(aoi_map.geometry, crs=projection, facecolor="none",
                          edgecolor=maps.AOI_COLOUR, linewidth=1.0, zorder=5)  # fmt: skip
    if graticule:
        maps._add_graticule(ax, projection, extent, small)

    items, furniture = {}, None
    if spec is not None:
        parts = maps._Parts(None, False, 1.0, spec, aoi_map if aoi_map is not None else _empty(),
                            None, None, extent)  # fmt: skip
        occupied, clear = maps._occupied(parts, map_w, map_h, size)
        variants = maps._furniture_variants(spec, map_w, map_h)
        found = maps._place_furniture(variants, occupied, clear, map_w, map_h, [])
        if found is None:  # no place clear of the outline: the preferred corner, over the data
            found = maps._place_furniture(variants, None, None, map_w, map_h, [])
        if found is not None:
            items["furniture"], furniture = found
        maps._draw_furniture(ax, items.get("furniture"), furniture, map_w, map_h, north_arrow,
                             scale_bar)  # fmt: skip

    extend = _extend(shown.values, limit)
    _draw_colourbar(holder, ax, lay, image, var, extend)
    if legend_mm is not None:
        _draw_legend(holder, ax, lay, handles, small)
    profile = None
    if latitude_profile:
        prof_ax, profile = _draw_profile(holder, ax, lay, shown, crs, extent, limit, var, small)
        label_panels([ax, prof_ax], labels)

    record: dict[str, Any] = {
        "layout": "profile" if latitude_profile else "map",
        "crs": crs.to_string(),
        "limits": limit,
        "limits_rule": rule,
        "extend": extend,
        **stats,
        "fdr": fdr_record,
        "excluded_percent": round(100.0 * float(excluded.mean()), 2),
        "no_data_percent": round(100.0 * float(no_data.mean()), 2),
        "marks": marks,
        "mark_cell_mm": cell_mm,
        "items": {k: v[0] for k, v in items.items()},
    }
    if profile is not None:
        record["profile_bands"] = profile
    record["caption"] = _caption(record, var, grids, stipple, sig_fraction, alpha, threshold,
                                 latitude_profile, excluded, shown)  # fmt: skip
    fig.eofigs_layout = record
    if holder is not fig:
        holder.eofigs_layout = record
    return fig


# ============================================================================ inputs


@dataclass
class _Grids:
    slope: xr.DataArray
    significant: np.ndarray | None  # full-resolution bool, or None without p-values
    from_test: bool  # True when the p-values come from trend() (Mann–Kendall)
    pvalues: np.ndarray | None = None  # full-resolution p-values, or None


def check_fdr(fdr, fdr_q, alpha) -> float | None:
    """Validate ``fdr`` and ``fdr_q``; return the false discovery rate q, or None."""
    if fdr not in FDR_METHODS:
        raise ValueError(f"fdr must be one of {FDR_METHODS} (got {fdr!r}).")
    if fdr is None:
        if fdr_q is not None:
            raise ValueError("fdr_q needs fdr='bh'.")
        return None
    q = 2.0 * alpha if fdr_q is None else float(fdr_q)
    if not 0 < q < 1:
        raise ValueError(f"fdr_q must be between 0 and 1 (got {q:g}).")
    return q


def fdr_entry(result, q: float) -> dict[str, Any]:
    """Describe a false discovery rate correction for ``fig.eofigs_layout``."""
    return {"method": "bh", "q": q, "n_tests": result.n_tests,
            "n_rejected": result.n_rejected, "p_threshold": result.p_threshold}  # fmt: skip


def _check_arguments(data, slope, pvalue, stipple, sig_fraction, ax, subfigure, profile):
    if data is None and slope is None:
        raise ValueError("Give data= (a time-series cube) or slope= (a precomputed slope grid).")
    if data is not None and (slope is not None or pvalue is not None):
        raise ValueError("Give either data= or slope= (with pvalue=), not both.")
    if stipple is not None and stipple not in STIPPLES:
        raise ValueError(f"stipple must be one of {STIPPLES} or None (got {stipple!r}).")
    if not 0 < sig_fraction <= 1:
        raise ValueError(f"sig_fraction must be in (0, 1] (got {sig_fraction}).")
    if ax is not None and subfigure is not None:
        raise ValueError("Pass either ax or subfigure, not both.")
    if ax is not None and profile:
        raise ValueError(
            "latitude_profile needs its own layout; leave ax=None (or use subfigure=)."
        )


def _with_crs(da: Any, what: str) -> xr.DataArray:
    import rioxarray  # noqa: F401  (adds the .rio accessor)

    if not isinstance(da, xr.DataArray):
        raise TypeError(f"{what} must be an xarray DataArray (got {type(da).__name__}).")
    if da.rio.crs is None:
        raise ValueError(
            f"{what} has no CRS. Set it with .rio.write_crs(...); eofigs never assumes a CRS."
        )
    return da


def _grids(data, slope, pvalue, alpha, dim, per) -> _Grids:
    from eofigs.stats import trend

    if data is not None:
        data = _with_crs(data, "data")
        result = trend(data, dim=dim, per=per, alpha=alpha)
        sl = result.slope.rio.write_crs(data.rio.crs)
        significant = (result.pvalue.values < alpha) & np.isfinite(sl.values)
        return _Grids(sl, significant, True, result.pvalue.values)
    sl = _with_crs(slope, "slope")
    if sl.ndim != 2:
        raise ValueError(f"slope must be a 2-D grid (got dimensions {sl.dims}).")
    if pvalue is None:
        return _Grids(sl, None, False)
    if not isinstance(pvalue, xr.DataArray):
        raise TypeError(f"pvalue must be an xarray DataArray (got {type(pvalue).__name__}).")
    if pvalue.rio.crs is not None and pvalue.rio.crs != sl.rio.crs:
        raise ValueError(
            f"slope and pvalue have different CRS ({sl.rio.crs} and {pvalue.rio.crs}); "
            "compute both with eofigs.trend or reproject one onto the other."
        )
    if set(pvalue.dims) == set(sl.dims) and pvalue.dims != sl.dims:
        pvalue = pvalue.transpose(*sl.dims)
    same = pvalue.shape == sl.shape and all(
        d in pvalue.coords and np.allclose(pvalue[d].values, sl[d].values) for d in sl.dims
    )
    if not same:
        raise ValueError(
            "slope and pvalue must be on the same grid (same shape and coordinates); "
            "compute both with eofigs.trend or reproject one onto the other."
        )
    significant = (pvalue.values < alpha) & np.isfinite(sl.values)
    return _Grids(sl, significant, False, pvalue.values)


def _trend_variable(variable, slope, per) -> Variable:
    if variable is not None:
        var = lookup_variable(variable)
        return var if var.name.endswith("_trend") else var.trend(per)
    try:
        var = lookup_variable(slope)
    except ValueError:
        units = str(slope.attrs.get("units", ""))
        name = str(slope.attrs.get("long_name") or "Trend")
        return Variable(name="trend", long_name=name, symbol=name, units=units,
                        cmap="cmc.vik", anomaly_cmap="cmc.vik", kind="diverging")  # fmt: skip
    return var if var.kind == "diverging" else var.trend(per)


def _base_name(var: Variable) -> str:
    return var.name.removesuffix("_trend")


def _excluded(exclude, data, dim, var, slope) -> tuple[np.ndarray, float | None]:
    none = np.zeros(slope.shape, dtype=bool)
    if exclude is None:
        return none, None
    if isinstance(exclude, str):
        if exclude != "auto":
            raise ValueError(f"exclude must be 'auto', a number, a grid or None (got {exclude!r}).")
        if data is None or _base_name(var) not in VEGETATION_INDICES:
            return none, None
        threshold = EXCLUDE_THRESHOLD
    elif isinstance(exclude, int | float) and not isinstance(exclude, bool):
        if data is None:
            raise ValueError("exclude=<number> is applied to the mean over time: it needs data=.")
        threshold = float(exclude)
    elif isinstance(exclude, xr.DataArray):
        if exclude.shape != slope.shape:
            raise ValueError("exclude must be on the slope's grid (same shape).")
        return exclude.values.astype(bool), None
    else:
        raise TypeError(f"exclude must be 'auto', a number, a grid or None (got {exclude!r}).")
    mean = data.mean(dim=dim, skipna=True).values
    with np.errstate(invalid="ignore"):
        return mean < threshold, threshold


def _round_up(value: float) -> float:
    if not value > 0:
        return 1.0
    power = 10 ** math.floor(math.log10(value))
    for m in _MANTISSAS:
        if m * power >= value * (1 - 1e-9):
            return float(f"{m * power:.6g}")
    return 10 * power  # pragma: no cover


def _limits(values: np.ndarray, limits) -> tuple[float, str]:
    magnitude = np.abs(values[np.isfinite(values)])
    if limits == "p98":
        top = float(np.percentile(magnitude, 98)) if magnitude.size else 1.0
        return _round_up(top), "p98"
    if limits is None:
        return _round_up(float(magnitude.max()) if magnitude.size else 1.0), "max"
    if isinstance(limits, str):
        raise ValueError(f"limits must be 'p98', a number or None (got {limits!r}).")
    if not float(limits) > 0:
        raise ValueError(f"limits must be positive (got {limits}).")
    return float(limits), "fixed"


def _shares(values, significant, valid, limit) -> dict[str, float | None]:
    finite = np.isfinite(values)
    n = int(finite.sum())
    clipped = 100.0 * float((np.abs(values[finite]) > limit).sum()) / n if n else 0.0
    out: dict[str, float | None] = {"clipped_percent": round(clipped, 2)}
    if significant is None:
        out["significant_percent"] = None
    else:
        count = int(valid.sum())
        out["significant_percent"] = (
            round(100.0 * float((significant & valid).sum()) / count, 2) if count else 0.0
        )
    return out


def _extend(values, limit) -> str:
    low = bool(np.nanmin(values) < -limit) if np.isfinite(values).any() else False
    high = bool(np.nanmax(values) > limit) if np.isfinite(values).any() else False
    return {(True, True): "both", (True, False): "min", (False, True): "max"}.get(
        (low, high), "neither"
    )


def _utm_of(da):
    import geopandas as gpd
    from shapely.geometry import box

    bounds = da.rio.bounds()
    return gpd.GeoDataFrame(geometry=[box(*bounds)], crs=da.rio.crs).estimate_utm_crs()


def _bounds_in(da, crs) -> tuple[float, float, float, float]:
    from rasterio.warp import transform_bounds

    left, bottom, right, top = transform_bounds(da.rio.crs, crs, *da.rio.bounds())
    return (left, right, bottom, top)


def _empty():
    import geopandas as gpd

    return gpd.GeoDataFrame(geometry=[])


# ============================================================================ layout


def _layout(width, height_mm, preset, ratio, small, size, legend_mm, profile, has_labels):
    fig_w = resolve_width(width, preset)
    max_h = height_mm if height_mm is not None else maps.HEIGHT_SHARE * preset.max_height_mm
    lat_w, _ = maps._text_mm("35°30′N", small)
    lab_h = small * maps._PT
    left, right = lat_w + 3.0, 4.0
    top = size * maps._PT + 3.0 if has_labels else 2.0
    bottom = lab_h + 4.0
    cbar_block = 2.5 + 2 * (small * maps._PT + 1.5) + 3.0
    prof_w = max(28.0, 0.24 * fig_w) if profile else 0.0
    gap = 9.0 if profile else 0.0  # room for the last longitude and the first slope label
    prof_right = lat_w + 3.0 if profile else 0.0  # the profile's latitude labels
    lw, lh = legend_mm if legend_mm is not None else (0.0, 0.0)

    def sizes(map_w):
        beside = legend_mm is None or map_w - lw - 6.0 >= 30.0
        block = max(cbar_block, lh + 3.0) if beside else cbar_block + lh + 3.0
        return beside, block

    map_w = fig_w - left - right - gap - prof_w - prof_right
    beside, block = sizes(map_w)
    map_h = map_w * ratio
    if top + map_h + bottom + block > max_h:
        map_h = max_h - top - bottom - block
        map_w = map_h / ratio
        beside, block = sizes(map_w)
        map_h = min(map_h, max_h - top - bottom - block)
        map_w = map_h / ratio
    fig_h = height_mm if height_mm is not None else top + map_h + bottom + block
    used = left + map_w + gap + prof_w + prof_right + right
    x = left + (fig_w - used) / 2
    y = fig_h - top - map_h
    lay = maps._Layout("inside", fig_w, fig_h, (x, y, map_w, map_h))
    below = y - bottom - 1.0
    if legend_mm is None:
        cb_w = 0.6 * map_w
        lay.colourbar_box = (x + (map_w - cb_w) / 2, below - 2.5, cb_w, 2.5)
    elif beside:
        cb_w = min(0.55 * map_w, map_w - lw - 6.0)
        lay.colourbar_box = (x, below - 2.5, cb_w, 2.5)
        lay.legend_anchor = (x + cb_w + 6.0, below + 1.0)
    else:
        cb_w = 0.6 * map_w
        lay.colourbar_box = (x + (map_w - cb_w) / 2, below - 2.5, cb_w, 2.5)
        lay.legend_anchor = (x, below - cbar_block)
    if profile:
        lay.side_box = (x + map_w + gap, y, prof_w, map_h)
    return lay


# ============================================================================ drawing


def _draw_slope(ax, shown, var, limit, crs, extent, map_w, map_h, dpi, projection):
    values, img_extent, _ = maps._prepare_raster(shown, crs, extent, map_w, map_h, dpi,
                                                 "continuous")  # fmt: skip
    cmap = mpl.colormaps[var.cmap].with_extremes(bad=(0, 0, 0, 0))  # gaps: hatched classes
    image = ax.imshow(
        np.ma.masked_invalid(values), cmap=cmap, norm=Normalize(-limit, limit),
        extent=img_extent, transform=projection, origin="upper", zorder=1,
        interpolation="nearest",
    )  # fmt: skip
    return image


def _draw_grey(ax, grey, hatch, crs, extent, map_w, map_h, dpi, projection):
    """Masked pixels: grey #BDBDBD with white hatching, pixel-exact.

    The hatching keeps them apart from the light middle of the trend colours (plain grey
    is too close to weak greening in protan and deutan simulation): diagonal for excluded
    pixels, crossed for pixels without data.
    """
    from rasterio import features
    from rasterio.transform import from_bounds
    from shapely.geometry import shape

    if not bool(grey.values.any()):
        return None
    values, (left, right, bottom, top), _ = maps._prepare_raster(
        grey, crs, extent, map_w, map_h, dpi, "mask"
    )
    with np.errstate(invalid="ignore"):
        mask = (values >= 0.5).astype("uint8")
    transform = from_bounds(left, bottom, right, top, mask.shape[1], mask.shape[0])
    polygons = [shape(geom) for geom, _ in features.shapes(mask, mask=mask == 1,
                                                           transform=transform)]  # fmt: skip
    if not polygons:
        return None
    return ax.add_geometries(
        polygons, crs=projection, facecolor=NO_DATA_COLOUR, edgecolor="white",
        linewidth=0.0, hatch=hatch, zorder=2,
    )  # fmt: skip


def _cell_factor(slope, crs, extent, map_w, spacing_mm) -> tuple[int, float]:
    """Source pixels per significance cell (k x k) and the cell size on the page (mm)."""
    left, right, _, _ = _bounds_in(slope, crs)
    pixel_mm = (right - left) / slope.rio.width * map_w / (extent[1] - extent[0])
    k = max(1, round(spacing_mm / pixel_mm))
    return k, k * pixel_mm


def significance_cells(significant, valid, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Share of significant pixels per k x k cell, and the share of valid pixels.

    Cells are built from the top-left corner; a partial last row or column is dropped.
    The share counts valid pixels only (excluded and no-data pixels do not count).

    Examples
    --------
    >>> import numpy as np
    >>> from eofigs.trends import significance_cells
    >>> sig = np.zeros((4, 4), bool); sig[:, :2] = True
    >>> share, valid = significance_cells(sig, np.ones((4, 4), bool), 2)
    >>> share.tolist()
    [[1.0, 0.0], [1.0, 0.0]]
    """
    rows, cols = (significant.shape[0] // k) * k, (significant.shape[1] // k) * k
    sig = (significant & valid)[:rows, :cols].astype(float)
    ok = valid[:rows, :cols].astype(float)
    shape = (rows // k, k, cols // k, k)
    count = ok.reshape(shape).sum(axis=(1, 3))
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(count > 0, sig.reshape(shape).sum(axis=(1, 3)) / count, np.nan)
    return share, count / (k * k)


def _draw_marks(ax, significant, valid, slope, stipple, sig_fraction, spacing_mm, crs, extent,
                map_w):  # fmt: skip
    import pyproj

    k, cell_mm = _cell_factor(slope, crs, extent, map_w, spacing_mm)
    share, valid_share = significance_cells(significant, valid, k)
    x = slope[slope.rio.x_dim].values
    y = slope[slope.rio.y_dim].values
    cx = x[: share.shape[1] * k].reshape(-1, k).mean(axis=1)
    cy = y[: share.shape[0] * k].reshape(-1, k).mean(axis=1)
    xx, yy = np.meshgrid(cx, cy)
    usable = valid_share >= 0.5
    projection = maps._projection(pyproj.CRS.from_user_input(slope.rio.crs))
    if stipple == "dots":
        with np.errstate(invalid="ignore"):
            hit = usable & (share >= sig_fraction - 1e-9)
        px, py = xx[hit], yy[hit]
        if pyproj.CRS(slope.rio.crs) != pyproj.CRS(crs):
            to_map = pyproj.Transformer.from_crs(slope.rio.crs, crs, always_xy=True)
            px, py = to_map.transform(px, py)
        inside = (px >= extent[0]) & (px <= extent[1]) & (py >= extent[2]) & (py <= extent[3])
        px, py = px[inside], py[inside]
        diameter = DOT_SIZE_MM / maps._PT  # points
        ax.scatter(
            px, py, s=diameter**2, marker="o", facecolor=DOT_COLOUR, edgecolor="white",
            linewidth=0.15, zorder=4, transform=maps._projection(crs),
        )  # fmt: skip
        return int(px.size), round(float(cell_mm), 3)
    field = np.ma.masked_where(~usable, share)
    cs = ax.contourf(
        xx, yy, field, levels=[sig_fraction - 1e-9, 1.0 + 1e-9], colors="none",
        hatches=["...."], transform=projection, zorder=4,
    )  # fmt: skip
    cs.set_edgecolor(TEXT_COLOUR)
    cs.set_linewidth(0.0)
    with np.errstate(invalid="ignore"):
        return int((usable & (share >= sig_fraction - 1e-9)).sum()), round(float(cell_mm), 3)


def mark_label(alpha: float, q: float | None, sig_fraction: float) -> str:
    """Legend text of the significance marks."""
    rule = f"p < {alpha:g}" if q is None else f"FDR q = {q:g}"
    return f"{rule} in ≥ {sig_fraction * 100:g} % of pixels"


def _legend_handles(aoi_label, grids, stipple, alpha, q, sig_fraction, excluded, slope, label):
    handles = []
    if aoi_label is not None:
        handles.append(Line2D([], [], color=maps.AOI_COLOUR, linewidth=1.0, label=aoi_label))
    if grids.significant is not None and stipple is not None:
        text = mark_label(alpha, q, sig_fraction)
        if stipple == "dots":
            handles.append(Line2D([], [], marker="o", linestyle="none", markersize=2.0,
                                  markerfacecolor=DOT_COLOUR, markeredgecolor="white",
                                  markeredgewidth=0.15, label=text))  # fmt: skip
        else:
            handles.append(Patch(facecolor="none", edgecolor=TEXT_COLOUR, hatch="....",
                                 linewidth=0.0, label=text))  # fmt: skip
    if excluded.any():
        handles.append(Patch(facecolor=NO_DATA_COLOUR, edgecolor="white", hatch=EXCLUDED_HATCH,
                             linewidth=0.0, label=label))  # fmt: skip
    if (~np.isfinite(slope.values) & ~excluded).any():
        handles.append(Patch(facecolor=NO_DATA_COLOUR, edgecolor="white", hatch=NO_DATA_HATCH,
                             linewidth=0.0, label=_no_data_label(grids)))  # fmt: skip
    return handles


def _no_data_label(grids) -> str:
    return "No valid trend (too few observations)" if grids.from_test else "No data"


def _draw_colourbar(holder, ax, lay, image, var, extend):
    small = maps._small_font()
    if lay is None:
        bar = holder.colorbar(image, ax=ax, orientation="horizontal", shrink=0.6, pad=0.06,
                              extend=extend)  # fmt: skip
    else:
        x, y, w, h = lay.colourbar_box
        rect = (x / lay.fig_w, y / lay.fig_h, w / lay.fig_w, h / lay.fig_h)
        bar = holder.colorbar(image, cax=holder.add_axes(rect), orientation="horizontal",
                              extend=extend)  # fmt: skip
    bar.set_label(var.short_label, size=mpl.rcParams["font.size"])
    bar.ax.tick_params(labelsize=small, width=0.6, length=2.5)
    bar.outline.set_linewidth(0.6)
    bar.set_ticks(diverging_ticks(image.norm.vmax, _STATE.get("max_ticks") or 5))
    bar.formatter = FuncFormatter(lambda value, _: tick_label(value))
    bar.update_ticks()
    return bar


def tick_label(value: float) -> str:
    """Shortest exact label for a tick value, "0" for zero and a true minus sign.

    Examples
    --------
    >>> from eofigs.trends import tick_label
    >>> [tick_label(v) for v in (-0.05, -0.025, 0.0, 0.025, 0.05)]
    ['−0.05', '−0.025', '0', '0.025', '0.05']
    """
    if abs(value) < 1e-12:
        return "0"
    text = f"{value:.10g}"
    return text.replace("-", "−")


def diverging_ticks(limit: float, max_ticks: int = 5) -> np.ndarray:
    """Ticks for a colour bar from -limit to +limit: round steps, else quarters of the range.

    Examples
    --------
    >>> from eofigs.trends import diverging_ticks
    >>> diverging_ticks(0.1).tolist(), diverging_ticks(0.08).tolist()
    ([-0.1, -0.05, 0.0, 0.05, 0.1], [-0.08, -0.04, 0.0, 0.04, 0.08])
    """
    ticks = round_ticks(-limit, limit, min(4, max_ticks), max_ticks)
    if min(4, max_ticks) <= len(ticks) <= max_ticks or max_ticks < 5:
        return ticks
    return np.round(np.linspace(-limit, limit, 5), 12)


def _draw_legend(holder, ax, lay, handles, size):
    props = {"size": size, "weight": "bold"}
    if lay is None or lay.legend_anchor is None:
        leg = ax.legend(handles=handles, loc="lower left", prop=props, frameon=True,
                        framealpha=0.85, facecolor="white", edgecolor="none")  # fmt: skip
        leg.set_zorder(8)
        return leg
    x, top = lay.legend_anchor
    return holder.legend(
        handles=handles, loc="upper left", bbox_to_anchor=(x / lay.fig_w, top / lay.fig_h),
        bbox_transform=holder.transSubfigure, prop=props, frameon=False, borderpad=0.0,
        borderaxespad=0.0, handlelength=1.6,
    )  # fmt: skip


def _row_latitudes(da) -> np.ndarray:
    import pyproj

    y = da[da.rio.y_dim].values
    src = pyproj.CRS(da.rio.crs)
    if src.is_geographic:
        return y.astype(float)
    x = da[da.rio.x_dim].values
    xc = np.full_like(y, (x[0] + x[-1]) / 2, dtype=float)
    _, lat = pyproj.Transformer.from_crs(src, 4326, always_xy=True).transform(xc, y)
    return np.asarray(lat)


def latitude_bands(shown: xr.DataArray, step: float, low: float, high: float):
    """Median and interquartile range of a grid's values in latitude bands.

    Each row's latitude is taken at the grid's centre column. Bands with fewer than
    :data:`PROFILE_MIN_PIXELS` valid values are skipped.

    Returns
    -------
    tuple of numpy.ndarray
        Band centres (degrees), medians, 25th and 75th percentiles, and pixel counts.
    """
    lat = _row_latitudes(shown)
    values = shown.values
    edges = np.arange(low, high + step, step)
    centres, med, q25, q75, counts = [], [], [], [], []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        rows = (lat >= lo) & (lat < hi)
        band = values[rows]
        band = band[np.isfinite(band)]
        if band.size < PROFILE_MIN_PIXELS:
            continue
        centres.append((lo + hi) / 2)
        a, b, c = np.percentile(band, [25, 50, 75])
        q25.append(a)
        med.append(b)
        q75.append(c)
        counts.append(band.size)
    return tuple(np.asarray(v, dtype=float) for v in (centres, med, q25, q75, counts))


def _draw_profile(holder, ax, lay, shown, crs, extent, limit, var, small):
    import cartopy.crs as ccrs
    from cartopy.mpl.ticker import LatitudeFormatter
    from matplotlib.ticker import FixedLocator

    x, y, w, h = lay.side_box
    prof = holder.add_axes((x / lay.fig_w, y / lay.fig_h, w / lay.fig_w, h / lay.fig_h))
    xc = (extent[0] + extent[1]) / 2
    geo = ccrs.PlateCarree()
    projection = maps._projection(crs)
    _, lat_low = geo.transform_point(xc, extent[2], projection)
    _, lat_high = geo.transform_point(xc, extent[3], projection)
    step = (lat_high - lat_low) * PROFILE_BAND_MM / h
    centres, med, q25, q75, counts = latitude_bands(shown, step, lat_low, lat_high)
    band = prof.fill_betweenx(centres, q25, q75, color=ENVELOPE_COLOUR, alpha=0.5, linewidth=0,
                              zorder=1, label="Interquartile range")  # fmt: skip
    band._eofigs_envelope = True  # a continuous band, not a categorical class
    prof.plot(med, centres, color=TEXT_COLOUR, linewidth=1.0, zorder=3, label="Median")
    prof.axvline(0, color=SECONDARY_COLOUR, linewidth=0.6, linestyle=(0, (3, 2)), zorder=2)
    prof.set_xlim(-limit, limit)
    prof.set_ylim(lat_low, lat_high)
    lats = maps._graticule_values(lat_low, lat_high)
    dms = maps.graticule_step(lat_low, lat_high) < 1
    prof.yaxis.set_major_locator(FixedLocator(lats))
    prof.yaxis.set_major_formatter(LatitudeFormatter(dms=dms, auto_hide=False))
    prof.yaxis.tick_right()
    prof.tick_params(labelsize=small, width=0.6, length=2.5)
    prof.grid(axis="y", color=SECONDARY_COLOUR, linewidth=0.3, alpha=0.6, linestyle=(0, (2, 2)))
    prof.set_xlabel(f"Median {var.short_label}", size=mpl.rcParams["font.size"])
    for spine in prof.spines.values():
        spine.set_linewidth(0.6)
    prof.set_xticks(diverging_ticks(limit, _STATE.get("max_ticks") or 5))
    prof.xaxis.set_major_formatter(FuncFormatter(lambda value, _: tick_label(value)))
    return prof, {"step_deg": round(float(step), 4), "bands": int(len(centres)),
                  "min_pixels": PROFILE_MIN_PIXELS}  # fmt: skip


# ============================================================================ caption


def percent(value: float) -> str:
    """Share for a caption: one decimal, or "<0.1" for small non-zero shares.

    Examples
    --------
    >>> from eofigs.trends import percent
    >>> percent(14.77), percent(0.03), percent(0.0)
    ('14.8', '<0.1', '0.0')
    """
    return "<0.1" if 0 < value < 0.05 else f"{value:.1f}"


def count(n: int) -> str:
    """Format a count for a caption, with thin-space thousands from 10 000 ("41 233")."""
    return f"{n:,}".replace(",", " ") if n >= 10_000 else str(n)


def p_text(p: float) -> str:
    """Format a p-value threshold with two significant digits ("0.012", "3.4 × 10⁻⁵").

    Examples
    --------
    >>> from eofigs.trends import p_text
    >>> p_text(0.01234), p_text(0.06), p_text(3.4e-05)
    ('0.012', '0.06', '3.4 × 10⁻⁵')
    """
    text = f"{p:.2g}"
    if "e" in text:
        mantissa, exponent = text.split("e")
        return f"{mantissa} × 10{str(int(exponent)).translate(_SUPERSCRIPT)}"
    return text


def _plain(units: str) -> str:
    """Mathtext units as plain text with Unicode superscripts ("decade$^{-1}$" -> "decade⁻¹")."""
    text = re.sub(r"\$\^\{([-0-9]+)\}\$", lambda m: m.group(1).translate(_SUPERSCRIPT), units)
    return text.replace("$", "")


def _caption(record, var, grids, stipple, sig_fraction, alpha, threshold, profile, excluded,
             shown) -> str:  # fmt: skip
    units = _plain(var.units)
    limit = f"±{record['limits']:g}{' ' + units if units else ''}"
    clipped = record["clipped_percent"]
    if record["limits_rule"] == "p98":
        parts = [f"Colours are limited to {limit} (98th percentile of |slope|); "
                 f"{percent(clipped)} % of pixels exceed this."]  # fmt: skip
    elif record["limits_rule"] == "fixed":
        parts = [f"Colours are limited to {limit}; {percent(clipped)} % of pixels exceed this."]
    else:
        parts = [f"Colours span the full range ({limit})."]
    if record["marks"] or (grids.significant is not None and stipple is not None):
        res = abs(float(grids.slope.rio.resolution()[0]))
        size = f"{res:g} m" if grids.slope.rio.crs.is_projected else f"{res:g}°"
        test = "Mann–Kendall, " if grids.from_test else ""
        what = "Dots" if stipple == "dots" else "Hatching"
        fdr = record["fdr"]
        if fdr is None:
            parts.append(f"{what}: at least {sig_fraction * 100:g} % of {size} pixels "
                         f"significant ({test}p < {alpha:g}).")  # fmt: skip
            if grids.from_test:
                parts.append(ASSUMPTIONS)
            else:
                parts.append(f"Significance from the supplied p-values (alpha = {alpha:g}); "
                             "eofigs applied no adjustment for multiple comparisons.")  # fmt: skip
        else:
            source = "Mann–Kendall" if grids.from_test else "supplied p-values"
            rule = (f"Benjamini–Hochberg false discovery rate control at q = {fdr['q']:g} over "
                    f"{count(fdr['n_tests'])} pixels")  # fmt: skip
            if fdr["n_rejected"] == 0:
                parts.append(f"No pixel is significant after {rule} ({source}; Wilks 2016).")
            else:
                parts.append(f"{what}: at least {sig_fraction * 100:g} % of {size} pixels "
                             f"significant ({source}, {rule}, equivalent to "
                             f"p ≤ {p_text(fdr['p_threshold'])}; Wilks 2016).")  # fmt: skip
            if grids.from_test:
                parts.append("Per-pixel Mann–Kendall tests assume serial independence.")
    share = record["excluded_percent"]
    if excluded.any():
        name = var.symbol.removesuffix(" trend")
        what = (f"mean {name} below {threshold:g} over the record (not vegetated"
                if threshold is not None else "excluded pixels (")  # fmt: skip
        sep = "; " if threshold is not None else ""
        parts.append(f"Grey with diagonal hatching: {what}{sep}{percent(share)} % of pixels).")
    if record["no_data_percent"] > 0:
        what = ("no valid trend (too few observations" if grids.from_test
                else "no data (")  # fmt: skip
        sep = "; " if grids.from_test else ""
        parts.append(f"Grey with cross-hatching: {what}{sep}"
                     f"{percent(record['no_data_percent'])} % of pixels).")  # fmt: skip
    if profile:
        step = record["profile_bands"]["step_deg"]
        parts.append(f"Profile: median and interquartile range of the full-resolution slope in "
                     f"{step:.2f}° latitude bands (bands with at least "
                     f"{PROFILE_MIN_PIXELS} valid pixels).")  # fmt: skip
    return " ".join(parts)
