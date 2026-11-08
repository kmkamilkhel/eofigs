"""Build the Swat valley sample data in docs/data/swat/ from open sources.

Run from the repository root:  python docs/scripts/build_swat_sample.py

Downloads go to build/swat_cache/ (ignored by git) and are reused when the script runs
again; each output file is skipped when it exists (pass --force to rebuild). Sources and
licences are listed in docs/data/swat/README.md and DATA_LICENSES.md.
"""

from __future__ import annotations

import argparse
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import reproject
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "data" / "swat"
CACHE = ROOT / "build" / "swat_cache"
CRS = "EPSG:32643"  # WGS 84 / UTM zone 43N
CELL = 90.0
BUFFER_M = 6000.0

GEOBOUNDARIES = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/PAK/ADM2/"
    "geoBoundaries-PAK-ADM2.geojson"
)
COP_DEM = (
    "https://copernicus-dem-90m.s3.amazonaws.com/Copernicus_DSM_COG_30_{tile}_DEM/"
    "Copernicus_DSM_COG_30_{tile}_DEM.tif"
)
COP_TILES = ("N34_00_E072_00", "N35_00_E072_00")
WORLDCOVER = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_N33E072_Map.tif"
)
GEONAMES = "https://download.geonames.org/export/dump/PK.zip"
# Towns shown on the sample map, looked up by name among GeoNames populated places
# (feature class P) inside the Swat boundary; the most populous match is used.
TOWNS = ("Mingora", "Saidu Sharif", "Matta", "Khwazakhela", "Bahrain", "Kalam")


def download(url: str, name: str) -> Path:
    """Download a file once into the cache, with a progress bar."""
    from tqdm import tqdm

    target = CACHE / name
    if target.exists():
        return target
    CACHE.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url) as response:  # noqa: S310 (fixed https URLs)
        total = int(response.headers.get("Content-Length") or 0) or None
        with (
            partial.open("wb") as fh,
            tqdm(total=total, unit="B", unit_scale=True, desc=name) as bar,
        ):
            while chunk := response.read(1 << 20):
                fh.write(chunk)
                bar.update(len(chunk))
    partial.replace(target)
    return target


def boundary(force: bool) -> gpd.GeoDataFrame:
    """Swat outline from geoBoundaries ADM2 (2019), reprojected to UTM 43N."""
    out = OUT / "swat_boundary.geojson"
    if out.exists() and not force:
        return gpd.read_file(out)
    adm2 = gpd.read_file(download(GEOBOUNDARIES, "geoBoundaries-PAK-ADM2.geojson"))
    swat = adm2[adm2["shapeName"] == "Swat"].to_crs(CRS)
    if len(swat) != 1:
        raise RuntimeError(f"Expected one 'Swat' feature, found {len(swat)}.")
    swat = gpd.GeoDataFrame(
        {
            "name": ["Swat"],
            "note": ["Former Swat district (before January 2026), now Swat and Bar Swat"],
            "source": ["geoBoundaries gbOpen PAK ADM2, boundary year 2019"],
        },
        geometry=[swat.geometry.iloc[0]],
        crs=CRS,
    )
    swat["geometry"] = swat.geometry.simplify(20)  # 20 m: invisible at print size
    swat.to_file(out, driver="GeoJSON", COORDINATE_PRECISION=1)
    return swat


def grid(aoi: gpd.GeoDataFrame) -> tuple[rasterio.Affine, int, int]:
    """90 m grid aligned to whole cells, covering the AOI plus the buffer."""
    x0, y0, x1, y1 = aoi.total_bounds
    x0 = np.floor((x0 - BUFFER_M) / CELL) * CELL
    y0 = np.floor((y0 - BUFFER_M) / CELL) * CELL
    x1 = np.ceil((x1 + BUFFER_M) / CELL) * CELL
    y1 = np.ceil((y1 + BUFFER_M) / CELL) * CELL
    width, height = int((x1 - x0) / CELL), int((y1 - y0) / CELL)
    return from_origin(x0, y1, CELL, CELL), width, height


def write(path: Path, array: np.ndarray, transform, nodata, description: str, units: str) -> None:
    """Write a tiled, deflate-compressed single-band GeoTIFF."""
    profile = {
        "driver": "GTiff",
        "height": array.shape[0],
        "width": array.shape[1],
        "count": 1,
        "dtype": array.dtype,
        "crs": CRS,
        "transform": transform,
        "nodata": nodata,
        "compress": "deflate",
        "predictor": 2,
        "zlevel": 9,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array, 1)
        dst.set_band_description(1, description)
        dst.set_band_unit(1, units)


def dem(aoi: gpd.GeoDataFrame, force: bool) -> None:
    """Copernicus GLO-90 DEM, mosaicked and resampled (bilinear) to the 90 m grid."""
    out = OUT / "swat_dem_90m.tif"
    if out.exists() and not force:
        return
    tiles = [download(COP_DEM.format(tile=t), f"{t}.tif") for t in COP_TILES]
    sources = [rasterio.open(t) for t in tiles]
    mosaic, mosaic_transform = merge(sources)
    src_crs = sources[0].crs
    for s in sources:
        s.close()
    transform, width, height = grid(aoi)
    target = np.full((height, width), np.nan, dtype="float32")
    reproject(
        mosaic[0].astype("float32"),
        target,
        src_transform=mosaic_transform,
        src_crs=src_crs,
        dst_transform=transform,
        dst_crs=CRS,
        resampling=Resampling.bilinear,
        src_nodata=np.nan,
        dst_nodata=np.nan,
    )
    array = np.where(np.isnan(target), -32768, np.round(target)).astype("int16")
    write(out, array, transform, -32768, "Elevation", "m")


def tree_cover(aoi: gpd.GeoDataFrame, force: bool) -> None:
    """Percentage of ESA WorldCover 2021 tree-cover pixels (class 10) in each 90 m cell."""
    out = OUT / "swat_tree_cover_90m.tif"
    if out.exists() and not force:
        return
    transform, width, height = grid(aoi)
    lon0, lat0, lon1, lat1 = (
        gpd.GeoSeries.from_xy(
            [transform.c, transform.c + width * CELL],
            [transform.f - height * CELL, transform.f],
            crs=CRS,
        )
        .to_crs("EPSG:4326")
        .total_bounds
    )
    with rasterio.open(WORLDCOVER) as src:  # read only the window needed (cloud-optimised GeoTIFF)
        window = (
            rasterio.windows.from_bounds(
                lon0 - 0.02, lat0 - 0.02, lon1 + 0.02, lat1 + 0.02, src.transform
            )
            .round_offsets()
            .round_lengths()
        )
        classes = src.read(1, window=window)
        src_transform = src.window_transform(window)
        src_crs = src.crs
    trees = (classes == 10).astype("float32") * 100  # class 10 = tree cover
    trees[classes == 0] = np.nan  # no data
    target = np.full((height, width), np.nan, dtype="float32")
    reproject(
        trees,
        target,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=transform,
        dst_crs=CRS,
        resampling=Resampling.average,  # area-weighted mean = percent of tree-cover pixels
        src_nodata=np.nan,
        dst_nodata=np.nan,
    )
    array = np.where(np.isnan(target), 255, np.round(target)).astype("uint8")
    write(out, array, transform, 255, "Tree cover", "%")


def towns(aoi: gpd.GeoDataFrame, force: bool) -> None:
    """Six towns from GeoNames (populated places inside the Swat outline)."""
    out = OUT / "swat_towns.geojson"
    if out.exists() and not force:
        return
    archive = zipfile.ZipFile(download(GEONAMES, "geonames_PK.zip"))
    area = aoi.to_crs("EPSG:4326").geometry.iloc[0]
    found: dict[str, tuple] = {}
    with archive.open("PK.txt") as fh:
        for line in io.TextIOWrapper(fh, encoding="utf-8"):
            f = line.rstrip("\n").split("\t")
            if f[6] != "P" or (f[1] not in TOWNS and f[2] not in TOWNS):
                continue
            name = f[1] if f[1] in TOWNS else f[2]
            lat, lon, pop = float(f[4]), float(f[5]), int(f[14] or 0)
            if not area.contains(Point(lon, lat)):
                continue
            if name not in found or pop > found[name][3]:
                found[name] = (int(f[0]), lat, lon, pop)
    missing = [t for t in TOWNS if t not in found]
    if missing:
        raise RuntimeError(f"Not found in GeoNames inside Swat: {missing}")
    gdf = gpd.GeoDataFrame(
        {
            "name": list(TOWNS),
            "geonameid": [found[t][0] for t in TOWNS],
            "population": [found[t][3] for t in TOWNS],
        },
        geometry=[Point(found[t][2], found[t][1]) for t in TOWNS],
        crs="EPSG:4326",
    ).to_crs(CRS)
    gdf.to_file(out, driver="GeoJSON", COORDINATE_PRECISION=0)
    print(gdf.drop(columns="geometry").to_string(index=False))


def main() -> None:
    """Build all sample files."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="rebuild existing output files")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    aoi = boundary(args.force)
    dem(aoi, args.force)
    tree_cover(aoi, args.force)
    towns(aoi, args.force)
    for path in sorted(OUT.glob("swat_*")):
        print(f"{path.name:28s} {path.stat().st_size / 1e6:6.2f} MB")
    print(json.dumps({"crs": CRS, "cell_m": CELL, "buffer_m": BUFFER_M}))


if __name__ == "__main__":
    main()
