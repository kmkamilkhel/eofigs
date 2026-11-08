"""Compute the sha256 checksums of the Natural Earth worldview files that eofigs downloads.

Run from the repository root:  python docs/scripts/worldview_checksums.py

Downloads the 1:10m admin-0 country files of every worldview for the pinned Natural Earth
version into build/worldview_cache/ (ignored by git; reused when the script runs again) and
prints the table for ``WORLDVIEW_SHA256`` in src/eofigs/_countries.py.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eofigs._countries import WORLDVIEWS, worldview_url  # noqa: E402

CACHE = ROOT / "build" / "worldview_cache"


def fetch(code: str) -> tuple[str, str]:
    """Download one worldview file (once) and return its sha256."""
    target = CACHE / f"{code}.zip"
    if not target.exists():
        partial = target.with_suffix(".part")
        with urllib.request.urlopen(worldview_url(code)) as response, partial.open("wb") as fh:  # noqa: S310
            while chunk := response.read(1 << 20):
                fh.write(chunk)
        partial.replace(target)
    return code, hashlib.sha256(target.read_bytes()).hexdigest()


def main() -> None:
    """Print the checksum table."""
    from tqdm import tqdm

    CACHE.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = dict(tqdm(pool.map(fetch, WORLDVIEWS), total=len(WORLDVIEWS), desc="worldviews"))
    print("WORLDVIEW_SHA256 = {")
    for code in WORLDVIEWS:
        print(f'    "{code}": "{results[code]}",')
    print("}")


if __name__ == "__main__":
    main()
