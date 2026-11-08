"""Build the Swat growing-season NDVI cube in docs/data/swat/ from MODIS MOD13A1 v6.1.

Run from the repository root:  python docs/scripts/build_swat_ndvi.py [--workers 8] [--force]

Source: MODIS Terra MOD13A1 version 6.1, 500 m 16-day vegetation indices (NDVI and pixel
reliability), read as cloud-optimised GeoTIFFs from the Microsoft Planetary Computer STAC
(collection ``modis-13A1-061``, tile h23v05). Only the Swat window of each file is read.

Processing, per year 2001-2024 (the 2025 season is incomplete on the Planetary Computer):
1. keep pixels with reliability 0 (good) or 1 (marginal) in the 16-day composites that
   start between 1 May and 30 September;
2. take the median NDVI where at least ``MIN_COMPOSITES`` composites are good, else NaN;
3. reproject (nearest neighbour) to the Swat grid in EPSG:32643 at 500 m, which covers
   the Swat outline plus a 6 km buffer.

Output: ``swat_ndvi_growing_season_500m.tif``, one band per year (band descriptions are the
years), int16 scaled by 0.001 (NDVI to three decimals), nodata -32768. Downloaded windows
are cached in build/swat_ndvi_cache/ (ignored by git), so the script resumes after an
interruption.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window, from_bounds

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "data" / "swat" / "swat_ndvi_growing_season_500m.tif"
BOUNDARY = ROOT / "docs" / "data" / "swat" / "swat_boundary.geojson"
CACHE = ROOT / "build" / "swat_ndvi_cache"
CRS = "EPSG:32643"
CELL = 500.0
BUFFER_M = 6000.0
YEARS = range(2001, 2025)
SEASON = ("05-01", "09-30")
MIN_COMPOSITES = 3
COLLECTION = "modis-13A1-061"
TILE = ".h23v05."
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/{account}/{container}"
NDVI_ASSET = "500m_16_days_NDVI"
RELIABILITY_ASSET = "500m_16_days_pixel_reliability"

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "6")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "5")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")

_tokens: dict[tuple[str, str], tuple[str, float]] = {}
_token_lock = threading.Lock()


def _json(url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except OSError:
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")  # pragma: no cover


def sign(href: str) -> str:
    """Append a Planetary Computer read token for the file's storage container.

    Tokens are anonymous, cached per container and refreshed before they expire.
    """
    parts = urllib.parse.urlsplit(href)
    key = (parts.netloc.split(".")[0], parts.path.split("/")[1])
    with _token_lock:
        token, expires = _tokens.get(key, ("", 0.0))
        if time.time() > expires - 300:
            token = _json(TOKEN.format(account=key[0], container=key[1]))["token"]
            _tokens[key] = (token, time.time() + 45 * 60)
        return f"{href}?{token}"


def grid() -> tuple[rasterio.Affine, int, int]:
    """500 m grid aligned to whole cells, covering the Swat outline plus the buffer."""
    x0, y0, x1, y1 = gpd.read_file(BOUNDARY).to_crs(CRS).total_bounds
    x0 = np.floor((x0 - BUFFER_M) / CELL) * CELL
    y0 = np.floor((y0 - BUFFER_M) / CELL) * CELL
    x1 = np.ceil((x1 + BUFFER_M) / CELL) * CELL
    y1 = np.ceil((y1 + BUFFER_M) / CELL) * CELL
    width, height = int((x1 - x0) / CELL), int((y1 - y0) / CELL)
    return from_origin(x0, y1, CELL, CELL), width, height


def items(year: int) -> list[dict]:
    """Terra composites of tile h23v05 starting in the growing season of ``year``."""
    transform, width, height = grid()
    bounds = rasterio.transform.array_bounds(height, width, transform)
    west, south, east, north = transform_bounds(CRS, "EPSG:4326", *bounds)
    body = {
        "collections": [COLLECTION],
        "bbox": [west, south, east, north],
        "datetime": f"{year}-04-01T00:00:00Z/{year}-10-31T23:59:59Z",
        "limit": 100,
    }
    found = _json(STAC, body)["features"]
    first, last = (date.fromisoformat(f"{year}-{day}") for day in SEASON)
    keep = [
        f for f in found
        if f["id"].startswith("MOD13A1.") and TILE in f["id"] and first <= _start(f) <= last
    ]  # fmt: skip
    latest = {}  # a composite reprocessed later appears twice: keep the latest version
    for item in sorted(keep, key=lambda f: f["id"]):
        latest[item["id"].split(".")[1]] = item
    return [latest[key] for key in sorted(latest)]


def _start(item: dict) -> date:
    """First day of a composite, from its id (MOD13A1.AYYYYDDD....)."""
    stamp = item["id"].split(".")[1]  # AYYYYDDD
    return date(int(stamp[1:5]), 1, 1) + timedelta(days=int(stamp[5:8]) - 1)


def fetch(item: dict, transform, width, height) -> Path:
    """Read the Swat window of one composite (NDVI and reliability) into the cache."""
    target = CACHE / f"{item['id']}.npz"
    if target.exists():
        return target
    bounds = rasterio.transform.array_bounds(height, width, transform)
    arrays = {}
    with rasterio.Env():
        for key, asset in (("ndvi", NDVI_ASSET), ("reliability", RELIABILITY_ASSET)):
            with rasterio.open(sign(item["assets"][asset]["href"])) as src:
                if "window" not in arrays:
                    left, bottom, right, top = transform_bounds(
                        CRS, src.crs, *bounds, densify_pts=21
                    )
                    window = from_bounds(left, bottom, right, top, src.transform)
                    window = Window(
                        int(window.col_off) - 2, int(window.row_off) - 2,
                        int(window.width) + 5, int(window.height) + 5,
                    ).intersection(Window(0, 0, src.width, src.height))  # fmt: skip
                    arrays["window"] = window
                    arrays["transform"] = np.array(src.window_transform(window))[:6]
                    arrays["crs"] = np.array(src.crs.to_wkt())
                arrays[key] = src.read(1, window=arrays["window"])
    window = arrays.pop("window")
    tmp = target.with_suffix(".part.npz")
    np.savez_compressed(tmp, window=np.array([window.col_off, window.row_off]), **arrays)
    tmp.replace(target)
    return target


def annual_median(paths: list[Path]) -> tuple[np.ndarray, np.ndarray, str]:
    """Median NDVI of the good composites, NaN where fewer than MIN_COMPOSITES are good."""
    stack, transform, crs = [], None, None
    for path in paths:
        with np.load(path) as f:
            ndvi = f["ndvi"].astype("float32")
            good = np.isin(f["reliability"], (0, 1)) & (ndvi >= -2000) & (ndvi <= 10000)
            stack.append(np.where(good, ndvi / 10000.0, np.nan))
            transform, crs = f["transform"], str(f["crs"])
    cube = np.stack(stack)
    count = np.isfinite(cube).sum(axis=0)
    with np.errstate(all="ignore"):
        median = np.nanmedian(cube, axis=0) if len(stack) else cube[0]
    median[count < MIN_COMPOSITES] = np.nan
    return median, transform, crs


def main() -> None:
    """Download the composites, build the annual medians and write the GeoTIFF."""
    from tqdm import tqdm

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--force", action="store_true", help="rewrite the output file")
    args = parser.parse_args()
    if OUT.exists() and not args.force:
        print(f"{OUT.relative_to(ROOT)} exists (pass --force to rebuild).")
        return
    CACHE.mkdir(parents=True, exist_ok=True)
    transform, width, height = grid()
    by_year = {year: items(year) for year in tqdm(YEARS, desc="search", unit="year")}
    for year, found in by_year.items():
        if len(found) < 8:
            raise SystemExit(f"{year}: only {len(found)} composites found; is the season complete?")
    todo = [item for found in by_year.values() for item in found]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch, item, transform, width, height) for item in todo]
        for future in tqdm(as_completed(futures), total=len(futures), desc="download", unit="file"):
            future.result()

    bands = np.full((len(YEARS), height, width), np.nan, dtype="float32")
    counts = []
    for i, year in enumerate(tqdm(YEARS, desc="composite", unit="year")):
        paths = [CACHE / f"{item['id']}.npz" for item in by_year[year]]
        median, src_transform, src_crs = annual_median(paths)
        counts.append(len(paths))
        reproject(
            median, bands[i], src_transform=rasterio.Affine(*src_transform), src_crs=src_crs,
            src_nodata=np.nan, dst_transform=transform, dst_crs=CRS, dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )  # fmt: skip
    scaled = np.where(np.isfinite(bands), np.round(bands * 1000), -32768).astype("int16")
    profile = {
        "driver": "GTiff", "dtype": "int16", "count": len(YEARS), "width": width,
        "height": height, "crs": CRS, "transform": transform, "nodata": -32768,
        "compress": "deflate", "predictor": 2, "zlevel": 9, "tiled": True,
        "blockxsize": 256, "blockysize": 256,
    }  # fmt: skip
    with rasterio.open(OUT, "w", **profile) as dst:
        dst.write(scaled)
        dst.scales = [1e-3] * len(YEARS)
        dst.offsets = [0.0] * len(YEARS)
        for i, year in enumerate(YEARS, 1):
            dst.set_band_description(i, str(year))
        dst.update_tags(
            long_name="NDVI",
            units="1",
            period="May-September median of 16-day composites",
            source="MODIS Terra MOD13A1 v6.1 (500 m, 16-day), tile h23v05",
            quality="pixel reliability 0 (good) or 1 (marginal)",
            min_composites=str(MIN_COMPOSITES),
            composites_per_year=",".join(str(c) for c in counts),
        )
    size = OUT.stat().st_size / 1e6
    print(f"wrote {OUT.relative_to(ROOT)} ({width} x {height} x {len(YEARS)}, {size:.2f} MB)")


if __name__ == "__main__":
    main()
