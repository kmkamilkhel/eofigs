"""Colour science helpers: CIELAB, CIEDE2000, colour-vision simulation, colour-map classes."""

from __future__ import annotations

import numpy as np
from matplotlib.colors import Colormap

# Okabe & Ito (2008) categorical colours, black last.
OKABE_ITO = (
    "#E69F00",
    "#56B4E9",
    "#009E73",
    "#F0E442",
    "#0072B2",
    "#D55E00",
    "#CC79A7",
    "#000000",
)
TEXT_COLOUR = "#1A1A1A"
GRID_COLOUR = "#E0E0E0"

# Machado, Oliveira & Fernandes (2009), severity 1.0, applied to linear sRGB.
CVD_MATRICES = {
    "protan": np.array(
        [
            [0.152286, 1.052583, -0.204868],
            [0.114503, 0.786281, 0.099216],
            [-0.003882, -0.048116, 1.051998],
        ]
    ),
    "deutan": np.array(
        [
            [0.367322, 0.860646, -0.227968],
            [0.280085, 0.672501, 0.047413],
            [-0.011820, 0.042940, 0.968881],
        ]
    ),
    "tritan": np.array(
        [
            [1.255528, -0.076749, -0.178779],
            [-0.078411, 0.930809, 0.147602],
            [0.004733, 0.691367, 0.303900],
        ]
    ),
}

_SRGB_TO_XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ]
)
_D65 = np.array([0.95047, 1.0, 1.08883])

# Colour-map classes. Names are compared without a "cmc." prefix and without "_r".
CMAP_BANNED = frozenset(
    {
        "jet",
        "rainbow",
        "hsv",
        "nipy_spectral",
        "turbo",
        "gist_rainbow",
        "gist_ncar",
        "flag",
        "prism",
    }
)
CMAP_SEQUENTIAL = frozenset(
    {
        # cmcrameri
        "acton", "bamako", "batlow", "batlowK", "batlowW", "bilbao", "buda", "davos", "devon",
        "glasgow", "grayC", "hawaii", "imola", "lajolla", "lapaz", "lipari", "navia", "nuuk",
        "oslo", "tokyo", "turku",
        # matplotlib perceptually uniform and single-hue sequential
        "viridis", "plasma", "inferno", "magma", "cividis", "Greys", "Purples", "Blues",
        "Greens", "Oranges", "Reds", "YlOrBr", "YlOrRd", "OrRd", "PuRd", "RdPu", "BuPu", "GnBu",
        "PuBu", "YlGnBu", "PuBuGn", "BuGn", "YlGn", "gray", "binary", "bone",
    }
)  # fmt: skip
CMAP_DIVERGING = frozenset(
    {
        # cmcrameri
        "bam", "berlin", "broc", "cork", "lisbon", "managua", "roma", "tofino", "vanimo", "vik",
        # matplotlib
        "PiYG", "PRGn", "BrBG", "PuOr", "RdGy", "RdBu", "RdYlBu", "RdYlGn", "Spectral",
        "coolwarm", "bwr", "seismic",
    }
)  # fmt: skip
CMAP_MULTI_SEQUENTIAL = frozenset({"bukavu", "fes", "oleron"})
CMAP_CYCLIC = frozenset({"bamO", "brocO", "corkO", "romaO", "vikO", "twilight", "twilight_shifted"})
CMAP_CATEGORICAL = frozenset(
    {
        "tab10", "tab20", "tab20b", "tab20c", "Set1", "Set2", "Set3", "Paired", "Accent",
        "Dark2", "Pastel1", "Pastel2",
    }
)  # fmt: skip


def to_linear(rgb: np.ndarray) -> np.ndarray:
    """Convert sRGB values in [0, 1] to linear RGB."""
    rgb = np.asarray(rgb, dtype=float)
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def to_srgb(lin: np.ndarray) -> np.ndarray:
    """Convert linear RGB to sRGB values in [0, 1]."""
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)


def simulate_cvd(rgb: np.ndarray, kind: str) -> np.ndarray:
    """Simulate protan, deutan or tritan vision (Machado et al. 2009, full severity)."""
    return to_srgb(to_linear(rgb) @ CVD_MATRICES[kind].T)


def to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert sRGB values in [0, 1] (last axis = channels) to CIELAB (D65)."""
    xyz = to_linear(rgb) @ _SRGB_TO_XYZ.T / _D65
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    lightness = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([lightness, a, b], axis=-1)


def delta_e2000(lab1: np.ndarray, lab2: np.ndarray) -> float:
    """CIEDE2000 colour difference between two CIELAB colours."""
    l1, a1, b1 = (float(v) for v in lab1)
    l2, a2, b2 = (float(v) for v in lab2)
    c1, c2 = np.hypot(a1, b1), np.hypot(a2, b2)
    c_mean = (c1 + c2) / 2
    g = 0.5 * (1 - np.sqrt(c_mean**7 / (c_mean**7 + 25**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dlp, dcp = l2 - l1, c2p - c1p
    if c1p * c2p == 0:
        dh = 0.0
    else:
        dh = h2p - h1p
        if dh > 180:
            dh -= 360
        elif dh < -180:
            dh += 360
    dhp = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dh / 2))
    lp_mean, cp_mean = (l1 + l2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        hp_mean = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hp_mean = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hp_mean = (h1p + h2p + 360) / 2
    else:
        hp_mean = (h1p + h2p - 360) / 2
    t = (
        1
        - 0.17 * np.cos(np.radians(hp_mean - 30))
        + 0.24 * np.cos(np.radians(2 * hp_mean))
        + 0.32 * np.cos(np.radians(3 * hp_mean + 6))
        - 0.20 * np.cos(np.radians(4 * hp_mean - 63))
    )
    d_theta = 30 * np.exp(-(((hp_mean - 275) / 25) ** 2))
    r_c = 2 * np.sqrt(cp_mean**7 / (cp_mean**7 + 25**7))
    s_l = 1 + 0.015 * (lp_mean - 50) ** 2 / np.sqrt(20 + (lp_mean - 50) ** 2)
    s_c = 1 + 0.045 * cp_mean
    s_h = 1 + 0.015 * cp_mean * t
    r_t = -np.sin(np.radians(2 * d_theta)) * r_c
    return float(
        np.sqrt(
            (dlp / s_l) ** 2 + (dcp / s_c) ** 2 + (dhp / s_h) ** 2 + r_t * (dcp / s_c) * (dhp / s_h)
        )
    )


def base_cmap_name(cmap: Colormap) -> str:
    """Return a colour map's name without a ``cmc.`` prefix or ``_r`` suffix."""
    name = cmap.name
    if name.startswith("cmc."):
        name = name[4:]
    if name.endswith("_r"):
        name = name[:-2]
    return name


def cmap_lightness(cmap: Colormap, n: int = 256) -> np.ndarray:
    """CIELAB lightness L* sampled evenly along a colour map."""
    rgb = cmap(np.linspace(0, 1, n))[:, :3]
    return to_lab(rgb)[:, 0]


def is_monotonic(values: np.ndarray, tol: float = 1.0) -> bool:
    """Test whether values only increase or only decrease.

    Small reversals are allowed: the values may fall back by at most ``tol`` below their
    running maximum (increasing) or rise by at most ``tol`` above their running minimum
    (decreasing), which absorbs rounding in sampled colour maps.
    """
    values = np.asarray(values, dtype=float)
    increasing = np.max(np.maximum.accumulate(values) - values) <= tol
    decreasing = np.max(values - np.minimum.accumulate(values)) <= tol
    return bool(increasing or decreasing)


def classify_cmap(cmap: Colormap) -> str:
    """Classify a colour map by how its lightness should behave.

    Returns ``"banned"``, ``"sequential"``, ``"diverging"``, ``"multi-sequential"``,
    ``"cyclic"``, ``"categorical"`` or ``"unknown"``. Known cmcrameri and matplotlib
    names are classified from fixed lists. Other maps are
    classified from their lightness profile; maps that fit no class are returned as
    ``"unknown"``.
    """
    name = base_cmap_name(cmap)
    if name in CMAP_BANNED:
        return "banned"
    for kind, names in (
        ("sequential", CMAP_SEQUENTIAL),
        ("diverging", CMAP_DIVERGING),
        ("multi-sequential", CMAP_MULTI_SEQUENTIAL),
        ("cyclic", CMAP_CYCLIC),
        ("categorical", CMAP_CATEGORICAL),
    ):
        if name in names:
            return kind
    if name.endswith("S") and name[:-1] in CMAP_SEQUENTIAL | {"batlowK", "batlowW"}:
        return "categorical"
    lightness = cmap_lightness(cmap)
    if is_monotonic(lightness):
        return "sequential"
    if diverging_ok(lightness):
        return "diverging"
    return "unknown"


def diverging_ok(lightness: np.ndarray, tol: float = 1.0) -> bool:
    """Test whether lightness is monotonic on each side of its extreme value near the centre."""
    n = lightness.size
    mid = slice(n // 4, 3 * n // 4)
    centre = lightness[mid]
    ends = (lightness[0] + lightness[-1]) / 2
    k = n // 4 + int(np.argmax(centre) if centre.mean() >= ends else np.argmin(centre))
    return is_monotonic(lightness[: k + 1], tol) and is_monotonic(lightness[k:], tol)


def multi_sequential_ok(lightness: np.ndarray, tol: float = 1.0) -> bool:
    """Test whether each half of a two-part colour map has monotonic lightness."""
    half = lightness.size // 2
    return is_monotonic(lightness[:half], tol) and is_monotonic(lightness[half:], tol)
