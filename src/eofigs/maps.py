"""Study area maps and map furniture: north arrow, scale bar and locator inset."""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import matplotlib as mpl
import numpy as np
from matplotlib import patheffects
from matplotlib.axes import Axes
from matplotlib.colors import LightSource, ListedColormap
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon
from matplotlib.text import Text

from eofigs._colour import GRID_COLOUR, NO_DATA_COLOUR, SECONDARY_COLOUR, TEXT_COLOUR
from eofigs._countries import countries as _load_countries
from eofigs._presets import MM_PER_INCH, get_journal, resolve_width
from eofigs.styling import _STATE, MAX_TICKS, new_figure, tidy_axes

__all__ = ["add_inset", "add_north_arrow", "add_scale_bar", "study_area_map"]

#: Overlay fill: Okabe-Ito bluish green, which stays distinguishable from batlow elevation colours.
OVERLAY_COLOUR = "#009E73"
OVERLAY_ALPHA = 0.85
ELEVATION_ALPHA = 0.45
AOI_COLOUR = TEXT_COLOUR
INSET_AOI_COLOUR = "#D55E00"  # Okabe-Ito vermillion
LAYOUTS = ("auto", "inside", "side")
#: An item inside the map needs this share of empty space under it.
MIN_EMPTY = 0.85
_PT = 25.4 / 72  # mm per point
_PAD_MM = 1.5


# ============================================================================ geometry input


def _as_gdf(obj: Any, what: str):
    import geopandas as gpd
    from shapely.geometry.base import BaseGeometry

    if isinstance(obj, str | Path):
        obj = gpd.read_file(obj)
    elif isinstance(obj, BaseGeometry):
        raise ValueError(
            f"{what} is a shapely geometry without a CRS. Wrap it with a CRS, for example "
            "geopandas.GeoSeries([geom], crs='EPSG:4326'); eofigs never assumes a CRS."
        )
    if isinstance(obj, gpd.GeoSeries):
        obj = gpd.GeoDataFrame(geometry=obj)
    if not isinstance(obj, gpd.GeoDataFrame):
        raise TypeError(
            f"{what} must be a GeoDataFrame, GeoSeries or vector file path "
            f"(got {type(obj).__name__})."
        )
    if obj.crs is None:
        raise ValueError(
            f"{what} has no CRS. Set it with .set_crs(...); eofigs never assumes a CRS."
        )
    return obj


def map_crs(aoi: Any):
    """CRS a study area map is drawn in: the AOI's CRS if projected, else its UTM zone.

    Parameters
    ----------
    aoi : GeoDataFrame, GeoSeries or path
        The area of interest, with a CRS.

    Returns
    -------
    pyproj.CRS
    """
    gdf = _as_gdf(aoi, "aoi")
    if gdf.crs.is_projected:
        return gdf.crs
    return gdf.estimate_utm_crs()


def _projection(crs):
    import cartopy.crs as ccrs

    return ccrs.Projection(crs)


# ============================================================================ north arrow


def north_angle(ax: Axes) -> float:
    """Clockwise angle in degrees from the map's up direction to true north at its centre."""
    import cartopy.crs as ccrs

    projection = getattr(ax, "projection", None)
    if projection is None:
        return 0.0
    x0, x1, y0, y1 = ax.get_extent()
    xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
    lon, lat = ccrs.PlateCarree().transform_point(xc, yc, projection)
    step = 0.01 if lat < 89.9 else -0.01
    xn, yn = projection.transform_point(lon, lat + step, ccrs.PlateCarree())
    angle = math.degrees(math.atan2(xn - xc, yn - yc))
    return angle if step > 0 else angle - 180.0


def add_north_arrow(
    ax: Axes,
    loc: str = "upper right",
    size_mm: float = 7.0,
    bbox_to_anchor: tuple[float, ...] | None = None,
) -> Any:
    """Add a north arrow that points to true north.

    On a cartopy map the arrow is rotated by the grid convergence at the map centre, so
    it points to true north rather than to grid north (in UTM the difference is a few
    degrees away from the central meridian). On ordinary axes it points up.

    Parameters
    ----------
    ax : Axes
        A cartopy GeoAxes (or ordinary axes).
    loc : str, default "upper right"
        Matplotlib location code, for example ``"upper left"`` or ``"lower right"``.
    size_mm : float, default 7
        Length of the arrow in mm (the bold "N" is added above it).
    bbox_to_anchor : tuple, optional
        Box in axes coordinates that ``loc`` refers to (default: the axes).

    Returns
    -------
    matplotlib.offsetbox.AnchoredOffsetbox
        The arrow artist; ``artist.angle`` holds the rotation in degrees.

    Examples
    --------
    >>> import cartopy.crs as ccrs
    >>> import eofigs
    >>> fig, ax = eofigs.new_figure("single", subplot_kw={"projection": ccrs.UTM(43)})
    >>> ax.set_extent([240_000, 300_000, 3_820_000, 3_960_000], crs=ccrs.UTM(43))  # Swat
    >>> arrow = eofigs.add_north_arrow(ax)
    >>> round(arrow.angle, 1)  # west of the central meridian: true north is clockwise of up
    1.5
    """
    from matplotlib.offsetbox import AnchoredOffsetbox, DrawingArea, TextArea, VPacker
    from matplotlib.transforms import Affine2D

    angle = north_angle(ax)
    length = size_mm / _PT  # points
    half = length * 0.32
    area = DrawingArea(length, length, 0, 0)
    centre = np.array([length / 2, length / 2])
    rotate = Affine2D().rotate_deg_around(*centre, -angle)
    tip, base = (length / 2, length), (length / 2, length * 0.22)
    left, right = (length / 2 - half, 0.0), (length / 2 + half, 0.0)
    for points, face in ((tip, base, left), "#1A1A1A"), ((tip, right, base), "white"):
        verts = rotate.transform(np.array(points))
        area.add_artist(
            Polygon(verts, closed=True, facecolor=face, edgecolor=TEXT_COLOUR, linewidth=0.6)
        )
    size = mpl.rcParams["font.size"]
    label = TextArea("N", textprops={"fontweight": "bold", "fontsize": size, "color": TEXT_COLOUR})
    box = VPacker(children=[label, area], align="center", pad=0, sep=1)
    artist = AnchoredOffsetbox(
        loc=loc,
        child=box,
        frameon=False,
        pad=0.2,
        borderpad=0.3,
        bbox_to_anchor=bbox_to_anchor,
        bbox_transform=ax.transAxes if bbox_to_anchor is not None else None,
    )
    artist.angle = angle
    artist.set_zorder(8)
    ax.add_artist(artist)
    return artist


# ============================================================================ scale bar


def _metres_per_unit(ax: Axes) -> tuple[float, float]:
    """Ground metres per data unit at the map centre, and the centre latitude."""
    import cartopy.crs as ccrs
    import pyproj

    projection = getattr(ax, "projection", None)
    if projection is None:
        raise ValueError("add_scale_bar needs a map (cartopy GeoAxes) to know distances.")
    x0, x1, y0, y1 = ax.get_extent()
    xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
    lon, lat = ccrs.PlateCarree().transform_point(xc, yc, projection)
    crs = pyproj.CRS.from_user_input(projection)
    if crs.is_geographic:
        geod = pyproj.Geod(ellps="WGS84")
        _, _, metres = geod.inv(lon - 0.5, lat, lon + 0.5, lat)
        return metres, lat
    unit = crs.axis_info[0].unit_conversion_factor if crs.axis_info else 1.0
    scale = pyproj.Proj(crs).get_factors(lon, lat).parallel_scale
    return unit / scale, lat


def nice_length(target: float) -> float:
    """Round a length to 1, 2, 2.5 or 5 times a power of ten (nearest on a log scale)."""
    if target <= 0:
        raise ValueError("target must be positive.")
    power = 10 ** math.floor(math.log10(target))
    options = [m * power for m in (1, 2, 2.5, 5, 10)]
    return min(options, key=lambda v: abs(math.log(v / target)))


def add_scale_bar(
    ax: Axes,
    loc: str = "lower left",
    length_km: float | None = None,
    fraction: float = 0.22,
    bbox_to_anchor: tuple[float, ...] | None = None,
) -> Any:
    """Add a scale bar that shows true ground distance at the map centre.

    The map's projection scale factor at its centre is taken into account, so the bar is
    correct in any projection near the centre (for UTM the correction is below 0.1 %).

    Parameters
    ----------
    ax : cartopy GeoAxes
        The map.
    loc : str, default "lower left"
        Matplotlib location code.
    length_km : float, optional
        Bar length in km. Defaults to a round length (1, 2, 2.5 or 5 x 10^n) near
        ``fraction`` of the map width.
    fraction : float, default 0.22
        Target share of the map width when the length is chosen automatically.
    bbox_to_anchor : tuple, optional
        Box in axes coordinates that ``loc`` refers to (default: the axes).

    Returns
    -------
    matplotlib_scalebar.scalebar.ScaleBar
        The scale bar; ``bar.length_km`` holds its length.

    Raises
    ------
    ValueError
        For axes that are not a map.

    Examples
    --------
    >>> import cartopy.crs as ccrs
    >>> import eofigs
    >>> fig, ax = eofigs.new_figure("single", subplot_kw={"projection": ccrs.UTM(43)})
    >>> ax.set_extent([240_000, 300_000, 3_820_000, 3_960_000], crs=ccrs.UTM(43))
    >>> eofigs.add_scale_bar(ax).length_km  # about 22 % of a 60 km wide map
    10
    """
    from matplotlib_scalebar.scalebar import ScaleBar

    metres_per_unit, _ = _metres_per_unit(ax)
    x0, x1, _, _ = ax.get_extent()
    width_km = abs(x1 - x0) * metres_per_unit / 1000
    km = length_km if length_km is not None else nice_length(fraction * width_km)
    km = int(km) if float(km).is_integer() else km
    units, value = ("km", km) if km >= 1 else ("m", round(km * 1000))
    size = mpl.rcParams["font.size"]
    bar = ScaleBar(
        dx=metres_per_unit,
        units="m",
        fixed_value=value,
        fixed_units=units,
        location=loc,
        scale_loc="top",
        length_fraction=None,
        width_fraction=0.012,
        color=TEXT_COLOUR,
        box_color="white",
        box_alpha=0.85,
        frameon=True,
        pad=0.3,
        border_pad=0.3,
        sep=2,
        font_properties={"weight": "bold", "size": size},
        bbox_to_anchor=bbox_to_anchor,
        bbox_transform=ax.transAxes if bbox_to_anchor is not None else None,
    )
    bar.length_km = km
    bar.set_zorder(8)
    ax.add_artist(bar)
    return bar


# ============================================================================ inset


def _focus_countries(world, aoi_wgs84):
    hits = world[world.intersects(aoi_wgs84.union_all())]
    if len(hits):
        return hits
    centre = aoi_wgs84.union_all().centroid
    local = f"+proj=aeqd +lat_0={centre.y} +lon_0={centre.x} +datum=WGS84 +units=m"
    projected = world.to_crs(local)
    distances = projected.distance(aoi_wgs84.to_crs(local).union_all().centroid)
    return world.loc[[distances.idxmin()]]


def _inset_view(focus, margin: float = 0.12):
    import cartopy.crs as ccrs

    lon0, lat0, lon1, lat1 = focus.total_bounds
    projection = ccrs.LambertAzimuthalEqualArea(
        central_longitude=(lon0 + lon1) / 2, central_latitude=(lat0 + lat1) / 2
    )
    projected = focus.to_crs(projection.proj4_init)
    x0, y0, x1, y1 = projected.total_bounds
    dx, dy = (x1 - x0) * margin, (y1 - y0) * margin
    return projection, (x0 - dx, x1 + dx, y0 - dy, y1 + dy)


def inset_aspect(aoi: Any, worldview: str | None = None, countries: Any = None) -> float:
    """Height-to-width ratio of the locator inset for an AOI."""
    world = _countries_for(worldview, countries)
    focus = _focus_countries(world, _as_gdf(aoi, "aoi").to_crs("EPSG:4326"))
    _, (x0, x1, y0, y1) = _inset_view(focus)
    return (y1 - y0) / (x1 - x0)


def _countries_for(worldview: str | None, countries: Any):
    if countries is not None:
        return _as_gdf(countries, "countries").to_crs("EPSG:4326")
    return _load_countries(worldview)


def add_inset(
    ax: Axes,
    aoi: Any,
    loc: str = "upper right",
    width_mm: float | None = None,
    rect: tuple[float, float, float, float] | None = None,
    worldview: str | None = None,
    countries: Any = None,
) -> Axes:
    """Add a locator inset: the country (or countries) around the AOI, with the AOI marked.

    Parameters
    ----------
    ax : Axes
        The main map; the inset is placed inside it unless ``rect`` is given.
    aoi : GeoDataFrame, GeoSeries or path
        The area of interest, with a CRS.
    loc : str, default "upper right"
        Corner of ``ax`` for the inset (``"upper left"``, ``"lower right"``, ...).
    width_mm : float, optional
        Inset width in mm; defaults to a third of the map width.
    rect : (left, bottom, width, height), optional
        Inset position in figure coordinates instead of ``loc`` (for example beside
        the map).
    worldview : str, optional
        ``None`` (default): the bundled Natural Earth 1:110m countries with de facto
        boundaries. A Natural Earth worldview code such as ``"PAK"`` or ``"IND"``
        shows that country's view of disputed boundaries; it is downloaded once (about
        5 MB) and cached.
    countries : GeoDataFrame, optional
        Your own country outlines (any CRS), instead of Natural Earth.

    Returns
    -------
    cartopy GeoAxes
        The inset axes; ``inset.focus`` lists the countries shown in grey.

    Notes
    -----
    Boundaries and names shown do not imply any opinion on the legal status of any
    country or territory. Choose the worldview that suits the journal and readership.
    """
    world = _countries_for(worldview, countries)
    aoi_gdf = _as_gdf(aoi, "aoi")
    aoi_wgs84 = aoi_gdf.to_crs("EPSG:4326")
    focus = _focus_countries(world, aoi_wgs84)
    projection, (x0, x1, y0, y1) = _inset_view(focus)
    fig = ax.figure
    if rect is None:
        pos = ax.get_position()
        fig_w, fig_h = (v * MM_PER_INCH for v in fig.get_size_inches())
        ax_w_mm = pos.width * fig_w
        w_mm = width_mm or max(20.0, ax_w_mm / 3)
        h_mm = w_mm * (y1 - y0) / (x1 - x0)
        pad_x, pad_y = _PAD_MM / fig_w, _PAD_MM / fig_h
        w, h = w_mm / fig_w, h_mm / fig_h
        left = pos.x0 + pad_x if "left" in loc else pos.x1 - pad_x - w
        bottom = pos.y0 + pad_y if "lower" in loc else pos.y1 - pad_y - h
        rect = (left, bottom, w, h)
    inset = fig.add_axes(rect, projection=projection)
    inset.set_extent((x0, x1, y0, y1), crs=projection)
    view = world.cx[-180:180, -90:90]
    others = view[~view.index.isin(focus.index)]
    crs = projection.proj4_init
    inset.add_geometries(
        others.to_crs(crs).geometry, crs=projection,
        facecolor="white", edgecolor=SECONDARY_COLOUR, linewidth=0.3,
    )  # fmt: skip
    inset.add_geometries(
        focus.to_crs(crs).geometry, crs=projection,
        facecolor=GRID_COLOUR, edgecolor=TEXT_COLOUR, linewidth=0.5,
    )  # fmt: skip
    marked = aoi_wgs84.to_crs(crs)
    inset.add_geometries(
        marked.geometry, crs=projection, facecolor=INSET_AOI_COLOUR,
        edgecolor=INSET_AOI_COLOUR, linewidth=0.6,
    )  # fmt: skip
    ax0, ay0, ax1, ay1 = marked.total_bounds
    min_size = 0.06 * (x1 - x0)  # keep a tiny AOI visible as a box
    cx, cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
    half_w, half_h = max(ax1 - ax0, min_size) / 2, max(ay1 - ay0, min_size) / 2
    inset.plot(
        [cx - half_w, cx + half_w, cx + half_w, cx - half_w, cx - half_w],
        [cy - half_h, cy - half_h, cy + half_h, cy + half_h, cy - half_h],
        color=INSET_AOI_COLOUR, linewidth=0.9, transform=projection,
    )  # fmt: skip
    inset.set_facecolor("white")
    for spine in inset.spines.values():
        spine.set_linewidth(0.6)
        spine.set_edgecolor(TEXT_COLOUR)
    inset.set_zorder(9)
    inset.focus = list(focus["name"])
    return inset


# ============================================================================ layout


_ANCHORS = {
    "upper left": (0.0, 1.0),
    "upper right": (1.0, 1.0),
    "lower left": (0.0, 0.0),
    "lower right": (1.0, 0.0),
    "upper center": (0.5, 1.0),
    "lower center": (0.5, 0.0),
    "center left": (0.0, 0.5),
    "center right": (1.0, 0.5),
}
_PREFERENCE = {
    "inset": ("upper right", "upper left", "lower right", "lower left"),
    "legend": ("lower left", "lower right", "upper left", "upper right"),
    "furniture": ("lower right", "lower left", "upper right", "upper left"),
}


def _box_at(loc: str, w: float, h: float, width: float, height: float, pad: float):
    """Box (x0, y0, x1, y1) in mm of a w x h item at ``loc`` inside a width x height map."""
    fx, fy = _ANCHORS[loc]
    x0 = pad if fx == 0 else width - pad - w if fx == 1 else (width - w) / 2
    y0 = pad if fy == 0 else height - pad - h if fy == 1 else (height - h) / 2
    return (x0, y0, x0 + w, y0 + h)


def _emptiness(box, occupied) -> float:
    from shapely.geometry import box as make_box

    area = make_box(*box)
    if occupied is None or occupied.is_empty:
        return 1.0
    return 1.0 - area.intersection(occupied).area / area.area


def place_items(
    sizes: dict[str, tuple[float, float]], occupied, width: float, height: float
) -> dict[str, tuple[str, tuple[float, float, float, float], float]]:
    """Put each item in the emptiest free position of a map (all sizes in mm).

    Items are placed in the order given, each in the position with the most empty space
    under it (corners and edge mid-points; ties go to the conventional corner), without
    overlapping items placed before. Returns ``{name: (loc, box, emptiness)}``.
    """
    from shapely.geometry import box as make_box

    placed: dict[str, tuple[str, tuple[float, float, float, float], float]] = {}
    for name, (w, h) in sizes.items():
        preference = _PREFERENCE.get(name, ())
        best = None
        for loc in _ANCHORS:
            box = _box_at(loc, w, h, width, height, _PAD_MM)
            if any(make_box(*box).intersects(make_box(*b)) for _, b, _ in placed.values()):
                continue
            empty = _emptiness(box, occupied)
            rank = preference.index(loc) if loc in preference else len(preference)
            score = (round(empty, 2), -rank)
            if best is None or score > best[0]:
                best = (score, loc, box, empty)
        if best is not None:
            placed[name] = (best[1], best[2], best[3])
    return placed


@dataclass
class _Layout:
    """Positions in mm of the parts of a study area map."""

    mode: str
    fig_w: float
    fig_h: float
    map_box: tuple[float, float, float, float]  # left, bottom, width, height
    side_box: tuple[float, float, float, float] | None = None
    colourbar_box: tuple[float, float, float, float] | None = None
    items: dict[str, Any] = field(default_factory=dict)


def _text_mm(text: str, size: float, weight: str = "normal") -> tuple[float, float]:
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextToPath

    prop = FontProperties(size=size, weight=weight)
    w, h, _ = TextToPath().get_text_width_height_descent(text, prop, ismath=False)
    return w * _PT, h * _PT


def _small_font() -> float:
    from matplotlib.font_manager import FontProperties

    return FontProperties(size=mpl.rcParams["xtick.labelsize"]).get_size_in_points()


# ============================================================================ graticule


_DEGREE_STEPS = (
    1 / 60, 2 / 60, 5 / 60, 10 / 60, 15 / 60, 20 / 60, 30 / 60,
    1, 2, 5, 10, 15, 20, 30, 45, 90,
)  # fmt: skip


def graticule_step(low: float, high: float, max_lines: int = 4) -> float:
    """Smallest round degree step that gives 2 to ``max_lines`` lines between two values."""
    for step in _DEGREE_STEPS:
        n = math.floor(high / step + 1e-9) - math.ceil(low / step - 1e-9) + 1
        if n <= max_lines:
            return step
    return _DEGREE_STEPS[-1]


def _graticule_values(low: float, high: float, max_lines: int = 4) -> list[float]:
    step = graticule_step(low, high, max_lines)
    start = math.ceil(low / step - 1e-9)
    stop = math.floor(high / step + 1e-9)
    return [round(i * step, 10) for i in range(start, stop + 1)]


def _lonlat_bounds(projection, extent) -> tuple[float, float, float, float]:
    import cartopy.crs as ccrs

    x0, x1, y0, y1 = extent
    xs = np.r_[np.linspace(x0, x1, 21), np.full(21, x1), np.linspace(x1, x0, 21), np.full(21, x0)]
    ys = np.r_[np.full(21, y0), np.linspace(y0, y1, 21), np.full(21, y1), np.linspace(y1, y0, 21)]
    pts = ccrs.PlateCarree().transform_points(projection, xs, ys)
    return pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max()


def _add_graticule(ax, projection, extent, size: float) -> Any:
    import cartopy.crs as ccrs
    from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter
    from matplotlib.ticker import FixedLocator

    lon0, lon1, lat0, lat1 = _lonlat_bounds(projection, extent)
    lons = _graticule_values(lon0, lon1)
    lats = _graticule_values(lat0, lat1)
    dms = graticule_step(lon0, lon1) < 1 or graticule_step(lat0, lat1) < 1
    gl = ax.gridlines(
        crs=ccrs.PlateCarree(),
        draw_labels=True,
        x_inline=False,
        y_inline=False,
        linewidth=0.3,
        color=SECONDARY_COLOUR,
        alpha=0.6,
        linestyle=(0, (2, 2)),
    )
    gl.top_labels = False
    gl.right_labels = False
    gl.xlocator = FixedLocator(lons)
    gl.ylocator = FixedLocator(lats)
    gl.xformatter = LongitudeFormatter(dms=dms, auto_hide=False)
    gl.yformatter = LatitudeFormatter(dms=dms, auto_hide=False)
    gl.xlabel_style = {"size": size, "color": TEXT_COLOUR}
    gl.ylabel_style = {"size": size, "color": TEXT_COLOUR}
    gl.xpadding = gl.ypadding = 3
    return gl


# ============================================================================ rasters


def _prepare_raster(data: Any, crs, extent, width_mm, height_mm, dpi, kind=None):
    """Fit a raster to the print size, reproject it to the map CRS and clip to the extent."""
    from rasterio.enums import Resampling

    from eofigs.raster import fit_raster

    fitted = fit_raster(data, width_mm=width_mm, height_mm=height_mm, dpi=dpi, kind=kind)
    if fitted.rio.crs is None or fitted.rio.crs != crs:
        resampling = Resampling.nearest if kind in ("mask", "categorical") else Resampling.bilinear
        fitted = fitted.rio.reproject(crs, resampling=resampling, nodata=np.nan)
    x0, x1, y0, y1 = extent
    pad_x = abs(float(fitted.rio.resolution()[0])) * 2
    pad_y = abs(float(fitted.rio.resolution()[1])) * 2
    clipped = fitted.rio.clip_box(x0 - pad_x, y0 - pad_y, x1 + pad_x, y1 + pad_y)
    values = clipped.values.astype("float64")
    nodata = clipped.rio.nodata
    if nodata is not None and not np.isnan(nodata):
        values[values == nodata] = np.nan
    left, bottom, right, top = clipped.rio.bounds()
    return values, (left, right, bottom, top), clipped


def _hillshade(z: np.ndarray, cell: float) -> np.ndarray:
    filled = np.where(np.isnan(z), np.nanmean(z), z)
    exaggeration = 1.0 if cell <= 100 else math.sqrt(cell / 100)
    shade = LightSource(azdeg=315, altdeg=45).hillshade(
        filled, vert_exag=exaggeration, dx=cell, dy=cell
    )
    return np.where(np.isnan(z), np.nan, shade)


def _overlay_mask(values: np.ndarray, attrs: dict, threshold: float | None) -> np.ndarray:
    if threshold is None:
        percent = str(attrs.get("units", "")).strip() == "%" or np.nanmax(values) > 1.0
        threshold = 50.0 if percent else 0.5
    with np.errstate(invalid="ignore"):
        return values >= threshold


# ============================================================================ labels


_LABEL_OFFSETS = (  # (dx, dy) direction, ha, va
    ((1, 0), "left", "center"),
    ((-1, 0), "right", "center"),
    ((0, 1), "center", "bottom"),
    ((0, -1), "center", "top"),
    ((1, 1), "left", "bottom"),
    ((-1, 1), "right", "bottom"),
    ((1, -1), "left", "top"),
    ((-1, -1), "right", "top"),
)


def place_labels(ax, xy: np.ndarray, names: list[str], obstacles=None, size: float | None = None):
    """Label points without overlapping each other, the points or the obstacles.

    Each label tries eight positions around its point (right, left, above, below, then
    the diagonals), first close to the point and then a little further out, and takes the
    first one that stays inside the map and clears earlier labels, all points and the
    ``obstacles`` (a shapely geometry in display pixels, for example the study area
    outline). If none is free, the position with the least overlap is used. Labels are
    bold with a white halo.

    Returns
    -------
    list of (Text, bool)
        Each label and whether it found a free position.
    """
    from matplotlib.transforms import offset_copy
    from shapely.geometry import Point
    from shapely.geometry import box as make_box

    size = size or mpl.rcParams["font.size"]
    fig = ax.figure
    renderer = fig.canvas.get_renderer()
    ax_box = ax.get_window_extent(renderer)
    frame = make_box(ax_box.x0, ax_box.y0, ax_box.x1, ax_box.y1)
    dpi_scale = fig.dpi / 72
    marker_px = 2.5 * dpi_scale
    display = ax.transData.transform(xy)
    markers = [Point(x, y).buffer(marker_px) for x, y in display]
    halo = 1.5
    taken: list = []
    results = []
    candidates = [(gap, *offset) for gap in (3.0, 7.0) for offset in _LABEL_OFFSETS]
    for i, ((x, y), name) in enumerate(zip(xy, names, strict=True)):
        best = None
        for gap, (dx, dy), ha, va in candidates:
            norm = math.hypot(dx, dy)
            transform = offset_copy(
                ax.transData, fig=fig, x=gap * dx / norm, y=gap * dy / norm, units="points"
            )
            text = Text(
                x, y, name, transform=transform, ha=ha, va=va, fontsize=size,
                fontweight="bold", color=TEXT_COLOUR,
            )  # fmt: skip
            text.set_figure(fig)
            bbox = text.get_window_extent(renderer).expanded(1.0, 1.0)
            shape = make_box(
                bbox.x0 - halo * dpi_scale, bbox.y0 - halo * dpi_scale,
                bbox.x1 + halo * dpi_scale, bbox.y1 + halo * dpi_scale,
            )  # fmt: skip
            others = [m for j, m in enumerate(markers) if j != i]
            clash = (
                shape.area
                - shape.intersection(frame).area
                + sum(shape.intersection(t).area for t in taken)
                + sum(shape.intersection(m).area for m in others)
                + (shape.intersection(obstacles).area * 4 if obstacles is not None else 0.0)
            )
            if best is None or clash < best[0] - 1e-9:
                best = (clash, gap, (dx, dy), ha, va, shape)
            if clash <= 1e-9:
                break
        clash, gap, (dx, dy), ha, va, shape = best
        norm = math.hypot(dx, dy)
        transform = offset_copy(
            ax.transData, fig=fig, x=gap * dx / norm, y=gap * dy / norm, units="points"
        )
        label = ax.text(
            x, y, name, transform=transform, ha=ha, va=va, fontsize=size,
            fontweight="bold", color=TEXT_COLOUR, zorder=7, clip_on=False,
        )  # fmt: skip
        label.set_path_effects([patheffects.withStroke(linewidth=2.0, foreground="white")])
        taken.append(shape)
        results.append((label, clash <= 1e-9))
    return results


def _outline_pixels(ax, geometries, width_px: float):
    """Study area outlines in display pixels, widened to ``width_px`` on each side."""
    import shapely
    from shapely.ops import unary_union

    lines = [shapely.transform(g.boundary, ax.transData.transform) for g in geometries]
    return unary_union(lines).buffer(width_px)


# ============================================================================ study area map


def study_area_map(
    aoi: Any,
    dem: Any = None,
    overlay: Any = None,
    points: Any = None,
    *,
    labels: str | None = "name",
    aoi_label: str = "Study area",
    overlay_label: str | None = None,
    points_label: str = "Places",
    overlay_threshold: float | None = None,
    overlay_colour: str = OVERLAY_COLOUR,
    inset: str | Any | None = "country",
    worldview: str | None = None,
    graticule: bool = True,
    north_arrow: bool = True,
    scale_bar: bool = True,
    legend: bool = True,
    layout: str = "auto",
    width: str | float = "single",
    height_mm: float | None = None,
    journal: str | None = None,
    ax: Axes | None = None,
) -> Figure:
    """Draw a publication-ready study area map.

    The map shows the study area outline over a grey hillshade with semi-transparent
    elevation colours, an optional single-colour overlay (for example forest), labelled
    points, a graticule, a north arrow pointing to true north, a scale bar, a legend and a
    locator inset. Rasters are reduced to the printed resolution first (:func:`fit_raster`),
    so large DEMs are fine. The figure height follows the shape of the study area, within
    the journal's maximum height.

    Parameters
    ----------
    aoi : GeoDataFrame, GeoSeries or path
        Study area outline(s), with a CRS. The map uses the AOI's CRS if it is projected,
        otherwise the AOI's UTM zone.
    dem : path, URL or DataArray, optional
        Elevation in metres, with a CRS; drawn as hillshade plus elevation colours with a
        colour bar.
    overlay : path, URL or DataArray, optional
        A raster drawn in one colour where it is True, or where it reaches
        ``overlay_threshold`` (default 50 for percentages, 0.5 for fractions), for
        example tree cover.
    points : GeoDataFrame or path, optional
        Places to mark, with a CRS.
    labels : str or None, default "name"
        Column of ``points`` with the labels; ``None`` for no labels. Labels are bold with
        a white halo and placed so that they overlap neither each other nor the outline.
    aoi_label, overlay_label, points_label : str
        Legend entries. ``overlay_label`` defaults to the overlay's long name and threshold.
    overlay_threshold : float, optional
        Value from which the overlay is drawn.
    overlay_colour : str, default "#009E73" (Okabe-Ito bluish green)
        Overlay colour; check_figure tests that it stays distinguishable from the
        elevation colours.
    inset : "country", GeoDataFrame or None, default "country"
        Locator inset with the surrounding country (or the given outlines); ``None`` for
        no inset.
    worldview : str, optional
        Natural Earth worldview for the inset boundaries (see :func:`add_inset`);
        ``None`` uses the bundled default (de facto) boundaries.
    graticule, north_arrow, scale_bar, legend : bool, default True
        Map elements to draw. The graticule has at most four labelled lines per side.
    layout : {"auto", "inside", "side"}, default "auto"
        ``"inside"`` puts inset and legend in empty corners of the map, ``"side"`` puts
        them in a column beside it. ``"auto"`` uses ``"side"`` for tall study areas when
        the figure is at least 120 mm wide. An inset or legend is moved beside the map
        whenever no position inside it is at least 85 % empty.
    width : str or float, default "single"
        Named journal width or width in mm.
    height_mm : float, optional
        Figure height; by default it follows the study area's shape.
    journal : str, optional
        Journal preset (defaults to the one set by :func:`set_style`).
    ax : cartopy GeoAxes, optional
        Draw into existing map axes (inside layout, no automatic size).

    Returns
    -------
    matplotlib.figure.Figure
        The map. ``fig.eofigs_layout`` records the layout chosen and where each element
        went.

    Raises
    ------
    ValueError
        For inputs without a CRS, an unknown layout, or ``ax`` that is not a map.

    Notes
    -----
    Boundaries and names shown do not imply any opinion on the legal status of any
    country or territory.
    """
    import cartopy.crs as ccrs  # noqa: F401  (registers GeoAxes)
    from cartopy.mpl.geoaxes import GeoAxes

    if layout not in LAYOUTS:
        raise ValueError(f"layout must be one of {LAYOUTS} (got {layout!r}).")
    if ax is not None and not isinstance(ax, GeoAxes):
        raise ValueError("ax must be a cartopy GeoAxes; or leave ax=None to create the map.")
    aoi_gdf = _as_gdf(aoi, "aoi")
    crs = map_crs(aoi_gdf) if ax is None else _crs_of(ax)
    aoi_map = aoi_gdf.to_crs(crs)
    projection = _projection(crs) if ax is None else ax.projection
    point_gdf = _as_gdf(points, "points").to_crs(crs) if points is not None else None

    bx0, by0, bx1, by1 = aoi_map.total_bounds
    margin = 0.03 * max(bx1 - bx0, by1 - by0)
    extent = (bx0 - margin, bx1 + margin, by0 - margin, by1 + margin)
    ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])

    preset = get_journal(journal or _STATE["journal"])
    small = _small_font()
    size = mpl.rcParams["font.size"]
    handles = _legend_handles(
        aoi_label, overlay is not None, overlay_label, overlay, overlay_colour,
        point_gdf is not None, points_label,
    )  # fmt: skip
    legend_mm = _legend_size(handles, small) if legend and handles else None
    has_inset = inset is not None
    inset_ratio = (
        inset_aspect(aoi_gdf, worldview, None if isinstance(inset, str) else inset)
        if has_inset
        else 1.0
    )

    if ax is not None:
        fig = ax.figure
        lay = None
    else:
        lay = _choose_layout(
            layout, width, height_mm, preset, ratio, small, size, dem is not None,
            legend_mm, has_inset, inset_ratio, aoi_map, point_gdf, labels,
        )  # fmt: skip
        fig, ax = _make_axes(lay, preset, projection, width)
    ax.set_extent(extent, crs=projection)
    ax.set_facecolor("white")
    ax.spines["geo"].set_linewidth(0.6)
    ax.spines["geo"].set_edgecolor(TEXT_COLOUR)

    pos = ax.get_position()
    fig_w_mm, fig_h_mm = (v * MM_PER_INCH for v in fig.get_size_inches())
    map_w, map_h = pos.width * fig_w_mm, pos.height * fig_h_mm
    dpi = preset.export_dpi

    tint = None
    if dem is not None:
        tint = _draw_dem(ax, dem, crs, extent, map_w, map_h, dpi, projection)
    if overlay is not None:
        _draw_overlay(ax, overlay, crs, extent, map_w, map_h, dpi, projection,
                      overlay_threshold, overlay_colour)  # fmt: skip
    ax.add_geometries(
        aoi_map.geometry, crs=projection, facecolor="none", edgecolor=AOI_COLOUR,
        linewidth=1.0, zorder=5,
    )  # fmt: skip
    if graticule:
        _add_graticule(ax, projection, extent, small)

    record: dict[str, Any] = {"layout": lay.mode if lay else "inside", "crs": crs.to_string()}
    items = lay.items if lay else _inside_items(
        aoi_map, point_gdf, labels, extent, map_w, map_h, legend_mm, has_inset, inset_ratio,
        size, north_arrow or scale_bar,
    )  # fmt: skip
    record["items"] = {k: v[0] for k, v in items.items()}

    if point_gdf is not None:
        xy = np.column_stack([point_gdf.geometry.x, point_gdf.geometry.y])
        ax.scatter(
            xy[:, 0], xy[:, 1], s=14, marker="o", facecolor=TEXT_COLOUR, edgecolor="white",
            linewidth=0.7, zorder=6, transform=projection,
        )  # fmt: skip
        if labels is not None and labels in point_gdf.columns:
            fig.canvas.draw_idle()
            ax.apply_aspect()
            dpi_scale = fig.dpi / 72
            obstacles = _outline_pixels(ax, aoi_map.geometry, 1.0 * dpi_scale)
            obstacles = obstacles.union(_item_pixels(ax, items, map_w, map_h))
            placed = place_labels(
                ax, xy, [str(v) for v in point_gdf[labels]], obstacles=obstacles, size=size
            )
            record["labels_clear"] = all(ok for _, ok in placed)

    if north_arrow or scale_bar:
        _draw_furniture(ax, items.get("furniture"), map_w, map_h, north_arrow, scale_bar)
    if has_inset:
        _draw_inset(fig, ax, lay, items.get("inset"), aoi_gdf, inset, worldview, map_w, map_h)
    if legend and handles:
        _draw_legend(fig, ax, lay, items.get("legend"), handles, small, map_w, map_h)
    if tint is not None:
        _draw_colourbar(fig, ax, lay, tint)
    fig.eofigs_layout = record
    return fig


def _crs_of(ax):
    import pyproj

    return pyproj.CRS.from_user_input(ax.projection)


def _legend_handles(aoi_label, has_overlay, overlay_label, overlay, colour, has_points, p_label):
    handles = [Line2D([], [], color=AOI_COLOUR, linewidth=1.0, label=aoi_label)]
    if has_overlay:
        label = overlay_label
        if label is None:
            name = getattr(overlay, "attrs", {}).get("long_name") if overlay is not None else None
            label = name or "Overlay"
        handles.append(Patch(facecolor=colour, edgecolor="none", alpha=OVERLAY_ALPHA, label=label))
    if has_points:
        handles.append(
            Line2D([], [], marker="o", linestyle="none", markersize=4.2,
                   markerfacecolor=TEXT_COLOUR, markeredgecolor="white", label=p_label)
        )  # fmt: skip
    return handles


def _legend_size(handles, size: float) -> tuple[float, float]:
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    probe = Figure(figsize=(4, 4), dpi=100)
    FigureCanvasAgg(probe)
    leg = probe.legend(handles=handles, prop={"size": size, "weight": "bold"}, frameon=True,
                       borderpad=0.4, handlelength=1.6)  # fmt: skip
    bbox = leg.get_window_extent(probe.canvas.get_renderer())
    return bbox.width / probe.dpi * MM_PER_INCH, bbox.height / probe.dpi * MM_PER_INCH


def _furniture_size(map_w: float, size: float) -> tuple[float, float]:
    arrow_h = 7.0 + size * _PT + 1
    bar_h = size * _PT + 4
    return max(0.3 * map_w, 12.0), arrow_h + bar_h + 1.5


def _occupied(aoi_map, point_gdf, labels, extent, map_w, map_h, size):
    """AOI, points and rough label areas in mm map coordinates."""
    from shapely.affinity import affine_transform
    from shapely.geometry import box as make_box
    from shapely.ops import unary_union

    x0, x1, y0, y1 = extent
    sx, sy = map_w / (x1 - x0), map_h / (y1 - y0)
    matrix = [sx, 0, 0, sy, -x0 * sx, -y0 * sy]
    shapes = [affine_transform(g, matrix).buffer(1.0) for g in aoi_map.geometry]
    if point_gdf is not None:
        for _, row in point_gdf.iterrows():
            px, py = affine_transform(row.geometry, matrix).coords[0]
            name = str(row[labels]) if labels and labels in point_gdf.columns else ""
            tw, th = _text_mm(name, size, "bold") if name else (0.0, 0.0)
            shapes.append(make_box(px - tw - 3, py - th, px + tw + 3, py + th))
    return unary_union(shapes)


def _inside_items(aoi_map, point_gdf, labels, extent, map_w, map_h, legend_mm, has_inset,
                  inset_ratio, size, furniture):  # fmt: skip
    occupied = _occupied(aoi_map, point_gdf, labels, extent, map_w, map_h, size)
    sizes: dict[str, tuple[float, float]] = {}
    if has_inset:
        w = min(max(20.0, map_w / 3), 45.0)
        h = w * inset_ratio
        if h > 0.4 * map_h:
            h = 0.4 * map_h
            w = h / inset_ratio
        sizes["inset"] = (w, h)
    if legend_mm is not None:
        sizes["legend"] = legend_mm
    if furniture:
        sizes["furniture"] = _furniture_size(map_w, size)
    return place_items(sizes, occupied, map_w, map_h)


def _choose_layout(layout, width, height_mm, preset, ratio, small, size, has_dem, legend_mm,
                   has_inset, inset_ratio, aoi_map, point_gdf, labels):  # fmt: skip
    fig_w = resolve_width(width, preset)
    max_h = height_mm if height_mm is not None else preset.max_height_mm
    lat_w, _ = _text_mm("35°30′N", small)
    lab_h = small * _PT
    left, right, top = lat_w + 3.0, 4.0, 2.0
    bottom = lab_h + 4.0
    cbar_block = (2.5 + 2 * (small * _PT + 1.5) + 3.0) if has_dem else 0.0
    extent_of = _extent_from(aoi_map)

    def inside():
        map_w = fig_w - left - right
        map_h = map_w * ratio
        total = top + map_h + bottom + cbar_block
        if total > max_h:
            map_h = max_h - top - bottom - cbar_block
            map_w = map_h / ratio
        fig_h = height_mm if height_mm is not None else top + map_h + bottom + cbar_block
        x = left + (fig_w - left - right - map_w) / 2
        y = fig_h - top - map_h
        lay = _Layout("inside", fig_w, fig_h, (x, y, map_w, map_h))
        if has_dem:
            cb_w = 0.6 * map_w
            lay.colourbar_box = (x + (map_w - cb_w) / 2, y - bottom - 2.5 - 1.0, cb_w, 2.5)
        lay.items = _inside_items(
            aoi_map, point_gdf, labels, extent_of, map_w, map_h, legend_mm, has_inset,
            inset_ratio, size, True,
        )  # fmt: skip
        return lay

    def side():
        col = min(max(0.3 * fig_w, 32.0), 55.0)
        map_w = fig_w - left - right - col
        map_h = map_w * ratio
        if top + map_h + bottom > max_h:
            map_h = max_h - top - bottom
            map_w = map_h / ratio
        fig_h = height_mm if height_mm is not None else top + map_h + bottom
        y = fig_h - top - map_h
        lay = _Layout("side", fig_w, fig_h, (left, y, map_w, map_h))
        lay.side_box = (left + map_w + right, y, fig_w - (left + map_w + right) - 1.0, map_h)
        occupied = _occupied(aoi_map, point_gdf, labels, extent_of, map_w, map_h, size)
        lay.items = place_items({"furniture": _furniture_size(map_w, size)}, occupied, map_w, map_h)
        return lay

    if layout == "side":
        return side()
    if layout == "auto" and ratio > 1.25 and fig_w >= 120:
        return side()
    lay = inside()
    crowded = [
        name for name in ("inset", "legend")
        if name in lay.items and lay.items[name][2] < MIN_EMPTY
    ]  # fmt: skip
    if crowded or (has_inset and "inset" not in lay.items):
        return side()
    return lay


def _extent_from(aoi_map):
    bx0, by0, bx1, by1 = aoi_map.total_bounds
    margin = 0.03 * max(bx1 - bx0, by1 - by0)
    return (bx0 - margin, bx1 + margin, by0 - margin, by1 + margin)


def _make_axes(lay: _Layout, preset, projection, width):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        fig, ax0 = new_figure(lay.fig_w, height_mm=lay.fig_h, journal=preset.key)
    fig.set_layout_engine("none")
    ax0.remove()
    x, y, w, h = lay.map_box
    rect = (x / lay.fig_w, y / lay.fig_h, w / lay.fig_w, h / lay.fig_h)
    ax = fig.add_axes(rect, projection=projection)
    fig._eofigs_layout = lay
    return fig, ax


def _draw_dem(ax, dem, crs, extent, map_w, map_h, dpi, projection):
    from eofigs.variables import variable

    z, img_extent, data = _prepare_raster(dem, crs, extent, map_w, map_h, dpi, "continuous")
    cell = abs(float(data.rio.resolution()[0]))
    shade = _hillshade(z, cell)
    grey = mpl.colormaps["gray"].with_extremes(bad=NO_DATA_COLOUR)
    ax.imshow(
        np.ma.masked_invalid(shade), cmap=grey, vmin=-0.5, vmax=1.05, extent=img_extent,
        transform=projection, origin="upper", zorder=1, interpolation="nearest",
    )  # fmt: skip
    elevation = variable("elevation")
    low, high = np.nanpercentile(z, [1, 99])
    tint = ax.imshow(
        np.ma.masked_invalid(z), cmap=elevation.cmap, vmin=low, vmax=high, alpha=ELEVATION_ALPHA,
        extent=img_extent, transform=projection, origin="upper", zorder=2,
        interpolation="nearest",
    )  # fmt: skip
    tint.eofigs_label = elevation.label
    return tint


def _draw_overlay(ax, overlay, crs, extent, map_w, map_h, dpi, projection, threshold, colour):
    values, img_extent, data = _prepare_raster(overlay, crs, extent, map_w, map_h, dpi)
    if data.dtype == bool:
        mask = values.astype(bool)
    else:
        mask = _overlay_mask(values, data.attrs, threshold)
    shown = np.ma.masked_where(~mask, np.ones_like(values))
    ax.imshow(
        shown, cmap=ListedColormap([colour]), vmin=0, vmax=1, alpha=OVERLAY_ALPHA,
        extent=img_extent, transform=projection, origin="upper", zorder=3,
        interpolation="nearest",
    )  # fmt: skip


def _axes_fraction(box, map_w, map_h):
    x0, y0, x1, y1 = box
    return (x0 / map_w, y0 / map_h, (x1 - x0) / map_w, (y1 - y0) / map_h)


def _item_pixels(ax, items, map_w, map_h):
    from shapely.geometry import box as make_box
    from shapely.ops import unary_union

    shapes = []
    for _, box, _ in items.values():
        fx, fy, fw, fh = _axes_fraction(box, map_w, map_h)
        (px0, py0), (px1, py1) = ax.transAxes.transform([(fx, fy), (fx + fw, fy + fh)])
        shapes.append(make_box(px0, py0, px1, py1))
    return unary_union(shapes) if shapes else make_box(0, 0, 0, 0)


def _draw_furniture(ax, item, map_w, map_h, arrow, bar):
    if item is None:
        if arrow:
            add_north_arrow(ax)
        if bar:
            add_scale_bar(ax)
        return
    loc, box, _ = item
    anchor = _axes_fraction(box, map_w, map_h)
    side = "left" if "left" in loc else "right" if "right" in loc else "center"
    if arrow:
        add_north_arrow(ax, loc=f"upper {side}", bbox_to_anchor=anchor)
    if bar:
        add_scale_bar(ax, loc=f"lower {side}", bbox_to_anchor=anchor)


def _draw_inset(fig, ax, lay, item, aoi, inset, worldview, map_w, map_h):
    countries = None if isinstance(inset, str) else inset
    if lay is not None and lay.mode == "side":
        x, y, w, h = lay.side_box
        ratio = inset_aspect(aoi, worldview, countries)
        iw = w
        ih = min(iw * ratio, 0.45 * h)
        iw = ih / ratio
        rect = (x / lay.fig_w, (y + h - ih) / lay.fig_h, iw / lay.fig_w, ih / lay.fig_h)
        lay.inset_bottom = y + h - ih
        return add_inset(ax, aoi, rect=rect, worldview=worldview, countries=countries)
    if item is None:
        return add_inset(ax, aoi, worldview=worldview, countries=countries)
    loc, box, _ = item
    pos = ax.get_position()
    fig_w, fig_h = (v * MM_PER_INCH for v in fig.get_size_inches())
    x0, y0, x1, y1 = box
    rect = (pos.x0 + x0 / fig_w, pos.y0 + y0 / fig_h, (x1 - x0) / fig_w, (y1 - y0) / fig_h)
    return add_inset(ax, aoi, rect=rect, worldview=worldview, countries=countries)


def _draw_legend(fig, ax, lay, item, handles, size, map_w, map_h):
    props = {"size": size, "weight": "bold"}
    if lay is not None and lay.mode == "side":
        x, y, w, h = lay.side_box
        top = getattr(lay, "inset_bottom", y + h) - 3.0
        leg = fig.legend(
            handles=handles, loc="upper left", bbox_to_anchor=(x / lay.fig_w, top / lay.fig_h),
            bbox_transform=fig.transFigure, prop=props, frameon=False, borderpad=0.0,
            borderaxespad=0.0, handlelength=1.6,
        )  # fmt: skip
        return leg
    loc, box, _ = item if item is not None else ("lower left", None, 1.0)
    anchor = _axes_fraction(box, map_w, map_h) if box is not None else None
    leg = ax.legend(
        handles=handles, loc=loc, bbox_to_anchor=anchor, prop=props, frameon=True,
        framealpha=0.85, facecolor="white", edgecolor="none", borderpad=0.4,
        borderaxespad=0.0, handlelength=1.6,
    )  # fmt: skip
    leg.set_zorder(8)
    return leg


def _draw_colourbar(fig, ax, lay, tint):
    small = _small_font()
    if lay is None:
        bar = fig.colorbar(tint, ax=ax, orientation="horizontal", shrink=0.6, pad=0.08)
    elif lay.mode == "side":
        x, y, w, h = lay.side_box
        cb_w = 0.8 * w
        rect = (x / lay.fig_w, (y + 9.0) / lay.fig_h, cb_w / lay.fig_w, 2.5 / lay.fig_h)
        bar = fig.colorbar(tint, cax=fig.add_axes(rect), orientation="horizontal")
    else:
        x, y, w, h = lay.colourbar_box
        rect = (x / lay.fig_w, y / lay.fig_h, w / lay.fig_w, h / lay.fig_h)
        bar = fig.colorbar(tint, cax=fig.add_axes(rect), orientation="horizontal")
    bar.set_label(getattr(tint, "eofigs_label", ""), size=mpl.rcParams["font.size"])
    bar.ax.tick_params(labelsize=small, width=0.6, length=2.5)
    bar.outline.set_linewidth(0.6)
    tidy_axes(bar, max_ticks=_STATE.get("max_ticks") or MAX_TICKS)
    return bar
