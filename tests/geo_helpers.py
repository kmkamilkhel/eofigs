"""Helpers for tests on geographic (EPSG:4326) grids and the hatched masked classes."""

import numpy as np
import pyproj
import rioxarray  # noqa: F401
import shapely
import xarray as xr
from shapely.geometry import box
from shapely.ops import unary_union

#: Approximate length of one degree of latitude (m).
DEGREE_M = 111_000


def geo_grid(values, name="slope"):
    """A grid in geographic coordinates (EPSG:4326) over Swat, north up."""
    rows, cols = values.shape
    lat = 35.9 - (np.arange(rows) + 0.5) * (1.3 / rows)
    lon = 72.0 + (np.arange(cols) + 0.5) * (1.0 / cols)
    da = xr.DataArray(values.astype("float64"), dims=("y", "x"), coords={"y": lat, "x": lon})
    da.name = name
    return da.rio.write_crs("EPSG:4326")


def hatched_area(ax, hatch):
    """Union of the hatched polygons of one masked class, in the map's coordinates."""
    geoms = [g for c in ax.collections if c.get_hatch() == hatch
             for g in c._feature.geometries()]  # fmt: skip
    return unary_union(geoms)


def patch_on_map(grid, rows, cols, crs):
    """The pixels ``grid[rows, cols]`` as a polygon in ``crs``, and the pixel size (m)."""
    dx = abs(float(grid.x[1] - grid.x[0])) / 2
    dy = abs(float(grid.y[1] - grid.y[0])) / 2
    xs, ys = grid.x.values[cols], grid.y.values[rows]
    patch = box(xs.min() - dx, ys.min() - dy, xs.max() + dx, ys.max() + dy).segmentize(0.01)
    to_map = pyproj.Transformer.from_crs(grid.rio.crs, crs, always_xy=True)

    def project(coords):
        return np.column_stack(to_map.transform(coords[:, 0], coords[:, 1]))

    return shapely.transform(patch, project), 2 * max(dx, dy) * DEGREE_M


def assert_hatching_on(ax, hatch, grid, rows, cols):
    """The class drawn with ``hatch`` covers the patch and nothing beyond a pixel of it."""
    area = hatched_area(ax, hatch)
    patch, pixel_m = patch_on_map(grid, rows, cols, pyproj.CRS(ax.projection.to_wkt()))
    assert not area.is_empty
    assert area.within(patch.buffer(1.5 * pixel_m))
    assert area.intersection(patch).area > 0.8 * patch.area
