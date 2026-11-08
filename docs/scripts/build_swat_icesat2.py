"""Build the Swat ICESat-2 terrain heights paired with the Copernicus DEM in docs/data/swat/.

Run from the repository root:  python docs/scripts/build_swat_icesat2.py [--workers 4]

Needs h5py (to read the ICESat-2 files) and a NASA Earthdata login; the eofigs package needs
neither. The login is read from the user's netrc file (machine urs.earthdata.nasa.gov) or
from an Earthdata token in the environment variable EARTHDATA_TOKEN. Nothing about it is
written to the outputs or the log.

1. **ICESat-2 ATL08 v007** land and vegetation heights (NASA NSIDC DAAC), 2019-2024, over the
   bounding box of the Swat outline. NASA Harmony cuts each granule on the server to the
   box, so a few megabytes per granule are downloaded (the full granules total about 26 GB).
   Harmony cannot also select variables for this collection, which has no variable records
   in NASA's catalogue.
2. **Segments kept** (100 m land segments):
   - strong beams only (from the beam's ``atlas_beam_type``, else the spacecraft
     orientation);
   - a valid best-fit terrain height (``h_te_best_fit``);
   - terrain height uncertainty (``h_te_uncertainty``) of at most 5 m;
   - snow-free land (``segment_snowcover`` = 1);
   - segment centre inside the Swat outline, with valid DEM values around it.
3. **Vertical datum.** ATL08 heights are above the WGS 84 ellipsoid; the Copernicus DEM gives
   heights above the EGM2008 geoid. ATL08 heights are converted to EGM2008 orthometric heights
   with PROJ (WGS 84 to EGM2008 height, NGA's 2.5-minute EGM2008 grid ``us_nga_egm08_25``,
   read from the PROJ data network). The conversion is checked to be the grid-based one and
   not a ballpark transformation.
4. **DEM value** at each segment centre: bilinear interpolation of ``swat_dem_90m.tif``
   (Copernicus DEM GLO-90, EGM2008) and its slope (degrees, from the same grid).
5. **Output** ``swat_icesat2_atl08_dem.csv``: one row per segment with the date, beam,
   longitude, latitude, ICESat-2 terrain height (EGM2008), geoid undulation, DEM elevation
   and DEM slope.

Subsetted granules are cached in build/swat_icesat2_cache/ (ignored by git), and the Harmony
job id is kept there, so the script resumes after an interruption.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "data" / "swat"
CACHE = ROOT / "build" / "swat_icesat2_cache"
COLLECTION = "C3565574177-NSIDC_CPRD"  # ATL08 version 007, NSIDC cloud
HARMONY = "https://harmony.earthdata.nasa.gov"
START, END = "2019-01-01T00:00:00Z", "2024-12-31T23:59:59Z"
BEAMS = ("gt1l", "gt1r", "gt2l", "gt2r", "gt3l", "gt3r")
UNCERTAINTY_MAX_M = 5.0
SNOW_FREE_LAND = 1
FILL = 3.0e38


def outline():
    """Read the Swat outline in longitude and latitude."""
    return gpd.read_file(OUT / "swat_boundary.geojson").to_crs(4326)


def session() -> requests.Session:
    """Earthdata session: a token from EARTHDATA_TOKEN, else the netrc file."""
    s = requests.Session()
    token = os.environ.get("EARTHDATA_TOKEN")
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s  # without a token, requests reads the netrc file for urs.earthdata.nasa.gov


def submit(s: requests.Session) -> str:
    """Submit (or resume) the Harmony subsetting job and return its id."""
    job_file = CACHE / "job.json"
    if job_file.exists():
        return json.loads(job_file.read_text())["jobID"]
    w, so, e, n = outline().total_bounds
    url = f"{HARMONY}/{COLLECTION}/ogc-api-coverages/1.0.0/collections/all/coverage/rangeset"
    params = [
        ("subset", f"lat({so - 0.01:.4f}:{n + 0.01:.4f})"),
        ("subset", f"lon({w - 0.01:.4f}:{e + 0.01:.4f})"),
        ("subset", f'time("{START}":"{END}")'),
        ("forceAsync", "true"),
    ]
    r = s.get(url, params=params, timeout=300)
    if r.status_code in (401, 403):
        sys.exit("Earthdata login failed: check the netrc entry or EARTHDATA_TOKEN.")
    if not r.ok:
        sys.exit(f"Harmony refused the request ({r.status_code}): {r.text[:600]}")
    job = r.json()
    CACHE.mkdir(parents=True, exist_ok=True)
    job_file.write_text(json.dumps({"jobID": job["jobID"]}))
    return job["jobID"]


def wait(s: requests.Session, job_id: str) -> list[str]:
    """Wait for the job to finish and return the links of its output files."""
    from tqdm import tqdm

    bar = tqdm(total=100, desc="Harmony subsetting", unit="%")
    while True:
        job = s.get(f"{HARMONY}/jobs/{job_id}", params={"limit": 2000}, timeout=120).json()
        bar.n = int(job.get("progress", 0))
        bar.refresh()
        if job["status"] in ("successful", "complete_with_errors"):
            break
        if job["status"] in ("failed", "canceled"):
            bar.close()
            sys.exit(f"Harmony job {job_id} {job['status']}: {job.get('message', '')}")
        time.sleep(20)
    bar.close()
    if job["status"] == "complete_with_errors":
        print(f"Harmony: {job.get('message', 'some granules failed')}")
    links, page = [], job
    while True:
        links += [lk["href"] for lk in page.get("links", []) if lk.get("rel") == "data"]
        nxt = [lk["href"] for lk in page.get("links", []) if lk.get("rel") == "next"]
        if not nxt:
            break
        page = s.get(nxt[0], timeout=120).json()
    return [lk for lk in links if lk.startswith("https") and lk.endswith((".h5", ".hdf5"))]


def download(s: requests.Session, url: str) -> Path:
    """Download one subsetted granule into the cache (skipped if already there)."""
    path = CACHE / "granules" / url.rsplit("/", 1)[-1]
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(".part")
    with s.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(part, "wb") as fh:
            for chunk in r.iter_content(1 << 16):
                fh.write(chunk)
    part.replace(path)
    return path


def strong_beams(f) -> list[str]:
    """Names of the strong beams in an open ATL08 file."""
    beams = [b for b in BEAMS if b in f]
    typed = {b: f[b].attrs.get("atlas_beam_type") for b in beams}
    if all(v is not None for v in typed.values()) and beams:
        return [
            b for b, v in typed.items() if (v.decode() if isinstance(v, bytes) else v) == "strong"
        ]
    orient = int(np.ravel(f["orbit_info/sc_orient"][()])[0])
    if orient == 0:  # backward: left beams are strong
        return [b for b in beams if b.endswith("l")]
    if orient == 1:  # forward: right beams are strong
        return [b for b in beams if b.endswith("r")]
    return []  # transition: beam strength unknown


def read_segments(path: Path) -> list[dict]:
    """Land segments of one granule that pass the beam, height, uncertainty and snow filters."""
    import h5py

    date = re.search(r"ATL08_(\d{4})(\d{2})(\d{2})", path.name)
    rows = []
    with h5py.File(path, "r") as f:
        for beam in strong_beams(f):
            seg = f[f"{beam}/land_segments"]
            if "latitude" not in seg:
                continue
            lat, lon = seg["latitude"][()], seg["longitude"][()]
            snow = seg["segment_snowcover"][()]
            h = seg["terrain/h_te_best_fit"][()].astype("float64")
            unc = seg["terrain/h_te_uncertainty"][()].astype("float64")
            ok = (np.abs(h) < FILL) & (unc <= UNCERTAINTY_MAX_M) & (snow == SNOW_FREE_LAND)
            day = f"{date[1]}-{date[2]}-{date[3]}"
            for i in np.flatnonzero(ok):
                rows.append(
                    {"date": day, "beam": beam, "lon": float(lon[i]), "lat": float(lat[i]),
                     "h": float(h[i])}
                )  # fmt: skip
    return rows


def to_egm2008(lon, lat, h):
    """Ellipsoidal (WGS 84) to EGM2008 orthometric heights with NGA's grid via PROJ."""
    import pyproj

    pyproj.network.set_network_enabled(True)
    t = pyproj.Transformer.from_crs("EPSG:4979", "EPSG:9518", always_xy=True, only_best=True)
    _, _, height = t.transform(lon, lat, h)
    used = t.get_last_used_operation().description
    if "EGM2008 height" not in used or "ballpark" in used:
        sys.exit(f"The EGM2008 grid is not available to PROJ (used: {used}).")
    print(f"vertical datum: {used}")
    height = np.asarray(height)
    if not np.all(np.isfinite(height)) or np.allclose(height, h):
        sys.exit("The EGM2008 conversion did not change the heights; stopping.")
    return height


def sample_dem(lon, lat):
    """Bilinear DEM elevation and slope (degrees) at the given points; NaN near nodata."""
    from pyproj import Transformer

    with rasterio.open(OUT / "swat_dem_90m.tif") as src:
        z = src.read(1).astype("float64")
        z[z == src.nodata] = np.nan
        inv = ~src.transform
        x, y = Transformer.from_crs(4326, src.crs, always_xy=True).transform(lon, lat)
        res = src.res[0]
    gy, gx = np.gradient(z, res)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    col, row = inv * (np.asarray(x), np.asarray(y))
    col, row = col - 0.5, row - 0.5  # pixel centres
    c0, r0 = np.floor(col).astype(int), np.floor(row).astype(int)
    fc, fr = col - c0, row - r0
    out = []
    for grid in (z, slope):
        vals = np.full(col.shape, np.nan)
        inside = (c0 >= 0) & (r0 >= 0) & (c0 + 1 < grid.shape[1]) & (r0 + 1 < grid.shape[0])
        c, r, a, b = c0[inside], r0[inside], fc[inside], fr[inside]
        vals[inside] = (grid[r, c] * (1 - a) * (1 - b) + grid[r, c + 1] * a * (1 - b)
                        + grid[r + 1, c] * (1 - a) * b + grid[r + 1, c + 1] * a * b)  # fmt: skip
        out.append(vals)
    return out


def main() -> None:
    """Subset, download, filter, convert, sample and write the table."""
    from shapely import contains_xy
    from tqdm import tqdm

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    s = session()
    job_id = submit(s)
    links = wait(s, job_id)
    print(f"{len(links)} subsetted granules")
    paths = []
    with ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(download, s, url) for url in links]
        for future in tqdm(as_completed(futures), total=len(futures), desc="download", unit="file"):
            paths.append(future.result())

    rows = []
    for path in tqdm(sorted(paths), desc="read", unit="file"):
        rows += read_segments(path)
    print(f"{len(rows)} segments pass the beam, height, uncertainty and snow filters")
    lon = np.array([r["lon"] for r in rows])
    lat = np.array([r["lat"] for r in rows])
    h = np.array([r["h"] for r in rows])
    shape = outline().geometry.union_all()
    inside = contains_xy(shape, lon, lat)
    height = to_egm2008(lon, lat, h)
    dem, slope = sample_dem(lon, lat)
    keep = inside & np.isfinite(dem) & np.isfinite(slope)
    print(f"{int(keep.sum())} segments inside the outline with DEM values")

    order = np.lexsort((lat[keep], np.array([r["date"] for r in rows])[keep]))
    idx = np.flatnonzero(keep)[order]
    target = OUT / "swat_icesat2_atl08_dem.csv"
    with open(target, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "beam", "longitude", "latitude", "icesat2_height_egm2008_m",
                    "geoid_undulation_m", "dem_elevation_m", "dem_slope_deg"])  # fmt: skip
        for i in idx:
            r = rows[i]
            w.writerow([r["date"], r["beam"], f"{lon[i]:.5f}", f"{lat[i]:.5f}", f"{height[i]:.2f}",
                        f"{h[i] - height[i]:.2f}", f"{dem[i]:.1f}", f"{slope[i]:.1f}"])  # fmt: skip
    print(
        f"wrote {target.relative_to(ROOT)} ({target.stat().st_size / 1e6:.2f} MB, {len(idx)} rows)"
    )


if __name__ == "__main__":
    main()
