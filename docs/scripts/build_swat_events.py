"""Build the Swat hot-dry event table and the monthly NDVI series in docs/data/swat/.

Run from the repository root:  python docs/scripts/build_swat_events.py [--workers 8] [--force]

Needs numcodecs (to decode TerraClimate's Blosc chunks); the eofigs package does not.

1. **Hot-dry events from TerraClimate** (Abatzoglou et al. 2018, CC0 1.0; the Zarr copy on
   the Microsoft Planetary Computer, monthly, 1/24 degree, 1958-2021).
   - Only the parts of each Blosc-compressed chunk that cover Swat are downloaded: the chunk
     header gives the offsets of its internal blocks, and each needed block is fetched with
     an HTTP range request and decompressed on its own.
   - Swat-mean monthly maximum temperature (tmax) and precipitation (ppt) 2001-2021 over the
     TerraClimate cells whose centres lie inside the outline. z-scores per calendar month
     against 2001-2021.
   - Event months: May-September months with tmax z >= +1 and ppt z <= -1. Consecutive event
     months form one event. With fewer than 3 events, both thresholds are relaxed to 0.75
     and the table says so.
   - Outputs: ``swat_terraclimate_monthly.csv`` (the Swat-mean series and z-scores) and
     ``swat_hot_dry_events.csv`` (one row per event).
2. **Monthly NDVI 2001-2021** from MODIS Terra MOD13A1 v6.1 (as in build_swat_ndvi.py):
   - each 16-day composite is assigned to the month it starts in; the monthly value is the
     median of its composites with pixel reliability 0 or 1, at 500 m;
   - reprojected (nearest) to the Swat 500 m grid, then averaged to 1 km (2 x 2 cells, at
     least 2 valid), and set to nodata farther than 2 km outside the outline (keeps the file
     small);
   - output ``swat_ndvi_monthly_1km.tif``: 252 bands named YYYY-MM, int16 scaled by 0.002
     (NDVI in steps of 0.002, keeping the file well under 2 MB), nodata -32768.

Downloads are cached in build/swat_events_cache/ and build/swat_ndvi_cache/ (ignored by
git), so the script resumes after an interruption.
"""

from __future__ import annotations

import argparse
import csv
import json
import struct
import sys
import urllib.request
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from rasterio.warp import reproject

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_swat_ndvi as ndvi  # noqa: E402  (shared MODIS reader)

ROOT = ndvi.ROOT
OUT = ROOT / "docs" / "data" / "swat"
CACHE = ROOT / "build" / "swat_events_cache"
YEARS = range(2001, 2022)  # TerraClimate on the Planetary Computer ends in December 2021
SEASON_MONTHS = (5, 6, 7, 8, 9)
THRESHOLD, RELAXED = 1.0, 0.75
MIN_EVENTS = 3
ZARR = "https://cpdataeuwest.blob.core.windows.net/cpdata/terraclimate.zarr"
ZARR_TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/cpdataeuwest/cpdata"
NDVI_MONTHLY = OUT / "swat_ndvi_monthly_1km.tif"
KEEP_BUFFER_M = 2000.0
_token: dict[str, str] = {}


def _get(path: str, start: int | None = None, end: int | None = None) -> bytes:
    if "value" not in _token:
        _token["value"] = ndvi._json(ZARR_TOKEN)["token"]
    request = urllib.request.Request(f"{ZARR}/{path}?{_token['value']}")
    if start is not None:
        request.add_header("Range", f"bytes={start}-{end}")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return response.read()
        except OSError:
            if attempt == 4:
                raise
    raise RuntimeError("unreachable")  # pragma: no cover


def _decompress(data: bytes) -> bytes:
    from numcodecs import blosc

    return blosc.decompress(data)


def outline_wgs84():
    """Return the Swat outline in WGS 84."""
    return gpd.read_file(ndvi.BOUNDARY).to_crs("EPSG:4326")


def terraclimate_window():
    """Rows and columns of the TerraClimate grid that cover Swat (with one cell to spare)."""
    lat = np.frombuffer(_decompress(_get("lat/0")), "<f8")
    lon = np.frombuffer(_decompress(_get("lon/0")), "<f8")
    west, south, east, north = outline_wgs84().total_bounds
    rows = np.nonzero((lat >= south - 0.05) & (lat <= north + 0.05))[0]
    cols = np.nonzero((lon >= west - 0.05) & (lon <= east + 0.05))[0]
    return lat, lon, rows, cols


def read_year(variable: str, year: int, rows, cols, meta) -> Path:
    """Read the Swat part of one year of a TerraClimate variable (12 x rows x cols)."""
    target = CACHE / f"terraclimate_{variable}_{year}.npy"
    if target.exists():
        return target
    t_chunk, y_chunk, x_chunk = meta["chunks"]
    dtype = np.dtype(meta["dtype"])
    index = (year - 1958) * 12 // t_chunk
    if rows[0] // y_chunk != rows[-1] // y_chunk or cols[0] // x_chunk != cols[-1] // x_chunk:
        raise SystemExit("Swat spans two TerraClimate chunks; extend the reader.")
    key = f"{variable}/{index}.{rows[0] // y_chunk}.{cols[0] // x_chunk}"
    head = _get(key, 0, 15)
    version, version_lz, flags, typesize, nbytes, blocksize, cbytes = struct.unpack(
        "<BBBBIII", head
    )
    nblocks = -(-nbytes // blocksize)
    starts = np.frombuffer(_get(key, 16, 16 + 4 * nblocks - 1), "<i4")
    r0, r1 = rows[0] % y_chunk, rows[-1] % y_chunk
    row_bytes = x_chunk * dtype.itemsize
    flat = np.zeros(nbytes, "<u1")
    needed = set()
    for t in range(t_chunk):
        first = (t * y_chunk + r0) * row_bytes
        last = (t * y_chunk + r1 + 1) * row_bytes - 1
        needed.update(range(first // blocksize, last // blocksize + 1))
    for block in sorted(needed):
        start = int(starts[block])
        end = int(starts[block + 1]) - 1 if block + 1 < nblocks else cbytes - 1
        data = _get(key, start, end)
        size = min(blocksize, nbytes - block * blocksize)
        single = struct.pack("<BBBBIII", version, version_lz, flags, typesize, size, blocksize,
                             20 + len(data)) + struct.pack("<i", 20) + data  # fmt: skip
        values = np.frombuffer(_decompress(single), "<u1")
        flat[block * blocksize : block * blocksize + values.size] = values
    cube = flat.view(dtype).reshape(t_chunk, y_chunk, x_chunk)
    c0, c1 = cols[0] % x_chunk, cols[-1] % x_chunk
    part = cube[:, r0 : r1 + 1, c0 : c1 + 1].astype("float32")
    tmp = target.with_suffix(".part.npy")
    np.save(tmp, part)
    tmp.replace(target)
    return target


def swat_series(workers: int) -> list[dict]:
    """Swat-mean monthly tmax and ppt with z-scores per calendar month (2001-2021)."""
    from shapely.geometry import Point
    from tqdm import tqdm

    meta = json.loads(_get(".zmetadata"))["metadata"]
    lat, lon, rows, cols = terraclimate_window()
    outline = outline_wgs84().geometry.union_all()
    inside = np.array([[outline.contains(Point(lon[c], lat[r])) for c in cols] for r in rows])
    jobs = [(v, y) for v in ("tmax", "ppt") for y in YEARS]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(read_year, v, y, rows, cols, meta[f"{v}/.zarray"]) for v, y in jobs]
        for future in tqdm(as_completed(futures), total=len(futures), desc="TerraClimate",
                           unit="year"):  # fmt: skip
            future.result()
    series = {}
    for variable in ("tmax", "ppt"):
        years = [np.load(CACHE / f"terraclimate_{variable}_{y}.npy") for y in YEARS]
        cube = np.concatenate(years)  # month, row, col
        series[variable] = np.nanmean(np.where(inside, cube, np.nan), axis=(1, 2))
    records = []
    for i in range(len(YEARS) * 12):
        month = f"{YEARS[0] + i // 12}-{i % 12 + 1:02d}"
        tmax, ppt = float(series["tmax"][i]), float(series["ppt"][i])
        records.append({"month": month, "tmax_c": tmax, "ppt_mm": ppt})
    for variable in ("tmax", "ppt"):
        values = series[variable].reshape(len(YEARS), 12)
        z = (values - values.mean(axis=0)) / values.std(axis=0, ddof=1)
        for i, value in enumerate(z.ravel()):
            records[i][f"{variable}_z"] = float(value)
    return records


def find_events(records: list[dict], threshold: float) -> list[list[dict]]:
    """Group consecutive May-September months with tmax z >= t and ppt z <= -t into events."""
    events, current = [], []
    for record in records:
        month = int(record["month"][5:])
        hot_dry = (month in SEASON_MONTHS and record["tmax_z"] >= threshold
                   and record["ppt_z"] <= -threshold)  # fmt: skip
        if hot_dry:
            current.append(record)
        elif current:
            events.append(current)
            current = []
    if current:
        events.append(current)
    return events


def write_tables(records: list[dict]) -> None:
    """Write the monthly series and the event table."""
    with open(OUT / "swat_terraclimate_monthly.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["month", "tmax_c", "ppt_mm", "tmax_z", "ppt_z"])
        writer.writeheader()
        for r in records:
            writer.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
    threshold = THRESHOLD
    events = find_events(records, threshold)
    if len(events) < MIN_EVENTS:
        threshold = RELAXED
        events = find_events(records, threshold)
        print(f"Fewer than {MIN_EVENTS} events at |z| >= {THRESHOLD}: relaxed to {RELAXED}.")
    with open(OUT / "swat_hot_dry_events.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["event", "start", "end", "months", "tmax_z_mean", "ppt_z_mean",
                         "threshold"])  # fmt: skip
        for i, event in enumerate(events, 1):
            writer.writerow([
                i, event[0]["month"], event[-1]["month"], len(event),
                round(float(np.mean([r["tmax_z"] for r in event])), 2),
                round(float(np.mean([r["ppt_z"] for r in event])), 2), threshold,
            ])  # fmt: skip
    print(f"{len(events)} hot-dry events (|z| >= {threshold}):",
          ", ".join(f"{e[0]['month']}..{e[-1]['month']}" for e in events))  # fmt: skip


def monthly_ndvi(workers: int) -> None:
    """Monthly median NDVI 2001-2021 at 1 km around the Swat outline."""
    from tqdm import tqdm

    transform, width, height = ndvi.grid()
    by_year = {y: ndvi.items(y, ("01-01", "12-31")) for y in tqdm(YEARS, desc="search")}
    todo = [item for found in by_year.values() for item in found]
    ndvi.CACHE.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(ndvi.fetch, item, transform, width, height) for item in todo]
        for future in tqdm(as_completed(futures), total=len(futures), desc="MODIS", unit="file"):
            future.result()

    w1, h1 = width // 2, height // 2
    transform_1km = transform * Affine.scale(2)
    outline = gpd.read_file(ndvi.BOUNDARY).to_crs(ndvi.CRS).buffer(KEEP_BUFFER_M)
    keep = ~geometry_mask(outline.geometry, (h1, w1), transform_1km)
    bands, names = [], []
    for year in tqdm(YEARS, desc="monthly", unit="year"):
        for month in range(1, 13):
            paths = [ndvi.CACHE / f"{item['id']}.npz" for item in by_year[year]
                     if ndvi._start(item).month == month]  # fmt: skip
            out = np.full((height, width), np.nan, dtype="float32")
            if paths:
                # a month holds one or two composites: one good composite is enough
                median, src_transform, src_crs = ndvi.annual_median(paths, min_composites=1)
                reproject(
                    median, out, src_transform=rasterio.Affine(*src_transform), src_crs=src_crs,
                    src_nodata=np.nan, dst_transform=transform, dst_crs=ndvi.CRS,
                    dst_nodata=np.nan, resampling=Resampling.nearest,
                )  # fmt: skip
            blocks = out[: h1 * 2, : w1 * 2].reshape(h1, 2, w1, 2)
            count = np.isfinite(blocks).sum(axis=(1, 3))
            with np.errstate(all="ignore"):
                coarse = np.nanmean(blocks, axis=(1, 3))
            coarse[(count < 2) | ~keep] = np.nan
            bands.append(coarse)
            names.append(f"{year}-{month:02d}")
    stack = np.stack(bands)
    scaled = np.where(np.isfinite(stack), np.round(stack * 500), -32768).astype("int16")
    profile = {
        "driver": "GTiff", "dtype": "int16", "count": len(bands), "width": w1, "height": h1,
        "crs": ndvi.CRS, "transform": transform_1km, "nodata": -32768, "compress": "deflate",
        "predictor": 2, "zlevel": 9, "tiled": True, "blockxsize": 128, "blockysize": 128,
        "interleave": "band",
    }  # fmt: skip
    with rasterio.open(NDVI_MONTHLY, "w", **profile) as dst:
        dst.write(scaled)
        dst.scales = [2e-3] * len(bands)
        dst.offsets = [0.0] * len(bands)
        for i, name in enumerate(names, 1):
            dst.set_band_description(i, name)
        dst.update_tags(
            long_name="NDVI", units="1",
            period="monthly median of the 16-day composites starting in each month",
            source="MODIS Terra MOD13A1 v6.1 (500 m, 16-day), tile h23v05",
            quality="pixel reliability 0 (good) or 1 (marginal)",
            aggregation="mean of 2 x 2 500 m cells (at least 2 valid)",
            extent="outline plus 2 km; nodata outside",
        )  # fmt: skip
    size = NDVI_MONTHLY.stat().st_size / 1e6
    print(f"wrote {NDVI_MONTHLY.relative_to(ROOT)} ({w1} x {h1} x {len(bands)}, {size:.2f} MB)")


def main() -> None:
    """Build the event tables and the monthly NDVI series."""
    warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN pixels (snow, outside the outline)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--force", action="store_true", help="rewrite the outputs")
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    events = OUT / "swat_hot_dry_events.csv"
    if args.force or not events.exists():
        write_tables(swat_series(args.workers))
    if args.force or not NDVI_MONTHLY.exists():
        monthly_ndvi(args.workers)


if __name__ == "__main__":
    main()
