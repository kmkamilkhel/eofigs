"""Build the country outlines bundled with eofigs for locator insets.

Run from the repository root:  python docs/scripts/build_countries.py

Source: Natural Earth 1:110m admin-0 countries, version 5.1.2 (public domain), in its
default (de facto) worldview. Only the ISO-style code and the English name are kept and
coordinates are rounded to 0.001 degrees (about 100 m, far below the 1:110m precision).
The download is cached in build/ (ignored by git).
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"
    "ne_110m_admin_0_countries.geojson"
)
CACHE = ROOT / "build" / "ne_110m_admin_0_countries.geojson"
OUT = ROOT / "src" / "eofigs" / "data" / "ne_110m_countries.geojson"


def _round(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 3), round(coords[1], 3)]
    return [_round(c) for c in coords]


def main() -> None:
    """Download (once), trim and write the bundled file."""
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL, CACHE)  # noqa: S310 (fixed https URL)
    source = json.loads(CACHE.read_text(encoding="utf-8"))
    features = []
    for feature in source["features"]:
        props = feature["properties"]
        features.append(
            {
                "type": "Feature",
                "properties": {"code": props["ADM0_A3"], "name": props["NAME_EN"]},
                "geometry": {
                    "type": feature["geometry"]["type"],
                    "coordinates": _round(feature["geometry"]["coordinates"]),
                },
            }
        )
    out = {
        "type": "FeatureCollection",
        "name": "ne_110m_countries",
        "source": (
            "Natural Earth 1:110m admin-0 countries v5.1.2 (public domain), de facto worldview"
        ),
        "features": features,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{OUT.name}: {len(features)} countries, {OUT.stat().st_size / 1e3:.0f} KB")


if __name__ == "__main__":
    main()
