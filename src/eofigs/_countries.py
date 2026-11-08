"""Country outlines for locator insets: bundled default and optional Natural Earth worldviews."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import urllib.error
import urllib.request
from importlib import resources
from pathlib import Path

NE_VERSION = "5.1.2"

#: Natural Earth worldviews (point-of-view country layers), by lower-case code. ``iso`` and
#: ``tlc`` are Natural Earth's ISO-based and "Top Level Country" variants.
WORLDVIEWS = (
    "arg", "bdg", "bra", "chn", "deu", "egy", "esp", "fra", "gbr", "grc", "idn", "ind",
    "iso", "isr", "ita", "jpn", "kor", "mar", "nep", "nld", "pak", "pol", "prt", "pse",
    "rus", "sau", "swe", "tlc", "tur", "twn", "ukr", "usa", "vnm",
)  # fmt: skip

#: sha256 of each worldview file at NE_VERSION (docs/scripts/worldview_checksums.py).
WORLDVIEW_SHA256: dict[str, str] = {
    "arg": "357fbb518e4288d32734087c91ac9f27d630068f7f60552d225ff64a6c04ed12",
    "bdg": "38dc28eea054c58cd828ca846cd08bd31007451b5c3591df0d73483d24380ed7",
    "bra": "131c5102ecf8f87f8462bb2bb50d114e3d80c3076ad61bc29122ace3fb97186d",
    "chn": "16e7589083527d01208b9f645fc8643c767170258e9d13b59d37bc5a1f6a8758",
    "deu": "125fc4b1f425926b8bd22dce23af6f9f873543c2fe330915ccbe0aa7fa21ff82",
    "egy": "11a59f8d01367bfe49e1e65a04349dc670a4341ba9465683b10e70f34576f5ef",
    "esp": "cc953fbb5ee827ca39d49940491fe48b3979a7ca4b10649c36d66948ad3ea7a0",
    "fra": "e5537c00e42ef027db1be55f3cadaf97441a8edea7435c3731c742175267d48c",
    "gbr": "23e586f7225a4a83b20178b78b8b8209b14bc6c385b09add44e3a2e50ac6dac3",
    "grc": "dfb2253a2ee995a4f2a4ea9ae90c6b915080d85144be7a37971be33ca7096592",
    "idn": "358d61ae12a92f9d42bb2193877030b4bff1193ff967ce0f0d9edb51b60acfea",
    "ind": "36a54ee97a509325e98eb44fd91bc7e53b0c5139cf10039918042bbd64102192",
    "iso": "9a097f5c5fe0cd2e0f1f120a507f9f8e421c6ff7e20a2e4c8621311081b55453",
    "isr": "36c2af239f9a04d2d104e893ce82ca52fea7dafbceac91a09be5b9c0569ecf68",
    "ita": "76f28332474ffdd7717fc67dcd8f0b2086eb8405c71fa47bf857ff42642a9615",
    "jpn": "d9dde4daa1b51fef2ee76b7e7ab86eb0f5deffc6bacb64dd9cacdd6cec6e880c",
    "kor": "4d7d99017cc81e5825295e781c21361c3f3b86b702d515302770924cf0c4cbf8",
    "mar": "9956aa888e35c4ca8d8d10a918469b3695316cfc6528d41d48bbfbeff19f3d4b",
    "nep": "4755295da115a74668886f37db1b8a6b631a28e5c30a5cf7e47d799565a6d365",
    "nld": "19f257724022f2c694e80f52c7e3263da75ec0f0f0c7a39ae22bd5672a492375",
    "pak": "cb6730734f7ffd64a087ec8cd801291ddf4507611c9902bd800362f2813a653b",
    "pol": "eef38fb79a91f9d26e1645f761dfafe9550ec217c73ac443f824581d42f5f197",
    "prt": "b1ca5db9522ba7d249b62fec5bab48afed74b42fbbcc79743a9722b7d8dcc35b",
    "pse": "8a69cbfe9402ac5bbd6e24e81cce6950137e0d7524023df9f5cfbd467bfdc976",
    "rus": "8309218a2d9b0b2a7f218a03fa05825a7757390ccec4d793e6e8e6a6015dd04d",
    "sau": "36191159ec58c7beaca1e2508cef84155b9dccba143d621ee336b60b81e786c0",
    "swe": "6ff518e3d0079108fc12996a72352d30c86b251431ec506b6573a1eebd9d6bc6",
    "tlc": "07b9ea4ffe9daa6b5280dc3c3343d176db5c05c77e4975918501356ca2080ce4",
    "tur": "2019fd24f5ac8dc68b90a2f26e236e5e1f5bd97b75e7e88520c3f20ac22e7fde",
    "twn": "5a3a14498c8fed258452de9e207d5e226b6fd279a43ff191897674708c219e9b",
    "ukr": "6fcdaed26c8d551018fbd3b97185df863a4f15f489e602fceae1dee90d6a5ae8",
    "usa": "4dd67d07246421372a3ea069d0b58b8ae28fe42c6a787a18411025b68f614d03",
    "vnm": "09e8e8d4fa210d8d8b5d8d0c988bf3e2ff37beda138ac97af2b044b7859ef7a2",
}

#: Simplification tolerance in degrees for downloaded worldviews (inset scale).
SIMPLIFY_DEG = 0.02


def worldview_url(code: str) -> str:
    """URL of one worldview file (1:10m admin-0 countries) at the pinned version."""
    return (
        f"https://naciscdn.org/naturalearth/{NE_VERSION}/10m/cultural/"
        f"ne_10m_admin_0_countries_{code}.zip"
    )


def cache_dir() -> Path:
    """Folder for downloaded data (``EOFIGS_CACHE`` overrides the platform default)."""
    if os.environ.get("EOFIGS_CACHE"):
        return Path(os.environ["EOFIGS_CACHE"])
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "eofigs" / "Cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "eofigs"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "eofigs"


def _normalise(worldview: str) -> str:
    code = str(worldview).strip().lower()
    if code not in WORLDVIEWS:
        raise ValueError(
            f"Unknown worldview {worldview!r}. Natural Earth provides: "
            f"{', '.join(c.upper() for c in WORLDVIEWS)}; or pass worldview=None for the "
            "default (de facto) boundaries."
        )
    return code


def countries(worldview: str | None = None):
    """Country outlines (EPSG:4326) with ``code`` and ``name`` columns.

    ``None`` returns the bundled Natural Earth 1:110m layer (de facto boundaries). A
    worldview code such as ``"PAK"`` or ``"IND"`` returns that country's point of view,
    downloaded once from Natural Earth (version pinned, checksum verified), simplified
    to inset scale and cached.
    """
    import geopandas as gpd

    if worldview is None:
        path = resources.files("eofigs").joinpath("data/ne_110m_countries.geojson")
        with resources.as_file(path) as local:
            return gpd.read_file(local)
    code = _normalise(worldview)
    cached = cache_dir() / f"ne_{NE_VERSION}_countries_{code}.geojson"
    if not cached.exists():
        _build_worldview(code, cached)
    return gpd.read_file(cached)


def _download(url: str, target: Path) -> None:
    try:
        with urllib.request.urlopen(url, timeout=60) as response, target.open("wb") as fh:  # noqa: S310
            while chunk := response.read(1 << 20):
                fh.write(chunk)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"Could not download the Natural Earth worldview file {url} ({exc}). eofigs "
            "needs the internet once for each worldview; after that it is cached in "
            f"{cache_dir()}. Offline, use worldview=None (bundled default boundaries) or "
            "pass your own boundaries as a GeoDataFrame (countries=...)."
        ) from exc


def _build_worldview(code: str, cached: Path) -> None:
    import geopandas as gpd

    expected = WORLDVIEW_SHA256.get(code)
    if expected is None:
        raise RuntimeError(f"No checksum is recorded for worldview {code.upper()!r}.")
    cached.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / f"{code}.zip"
        _download(worldview_url(code), archive)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != expected:
            raise RuntimeError(
                f"The downloaded worldview file for {code.upper()} does not match its "
                f"checksum (got {digest[:12]}..., expected {expected[:12]}...); it was not "
                "used. Try again later."
            )
        data = gpd.read_file(f"zip://{archive.as_posix()}")
    data = data.to_crs("EPSG:4326")
    out = gpd.GeoDataFrame(
        {"code": data["ADM0_A3"], "name": data["NAME_EN"]},
        geometry=data.geometry.simplify(SIMPLIFY_DEG, preserve_topology=True),
        crs="EPSG:4326",
    )
    partial = cached.with_suffix(".part")
    out.to_file(partial, driver="GeoJSON")
    partial.replace(cached)
