"""Colour palettes and colour maps built into eofigs.

Each palette is a tuple of hex colours, chosen for one job:

| Palette | Use |
|---|---|
| ``okabe_ito`` | lines, points, error bars and small symbols (Okabe & Ito 2008; black last) |
| ``muted`` | filled areas: bars, stacked areas, class maps with up to five classes plus grey |
| ``slate`` | ordered magnitude in a few classes, light (low) to dark (high) |
| ``terra_slate`` | signed values around zero: terracotta (negative), off-white (zero), slate teal |

``slate`` and ``terra_slate`` are also registered as matplotlib colour maps
``"eofigs.slate"`` and ``"eofigs.terra_slate"`` (and their ``"_r"`` reversals), so they can
be passed as ``cmap=`` anywhere. ``neutrals`` holds the colours for text, secondary lines,
grid lines and no-data areas.

Examples
--------
>>> from eofigs import palettes
>>> palettes.muted[0]
'#768EAE'
>>> import matplotlib as mpl
>>> mpl.colormaps["eofigs.terra_slate"].N
255
"""

from __future__ import annotations

from types import MappingProxyType

import matplotlib as mpl
from matplotlib.colors import LinearSegmentedColormap

from eofigs._colour import (
    GRID_COLOUR,
    NO_DATA_COLOUR,
    OKABE_ITO,
    SECONDARY_COLOUR,
    TEXT_COLOUR,
)

__all__ = ["muted", "neutrals", "okabe_ito", "slate", "terra_slate"]

#: Okabe-Ito colours for lines, points and symbols, black last.
okabe_ito: tuple[str, ...] = OKABE_ITO

#: Muted colours for filled areas; the sixth (grey) is for "other" or a reference class.
muted: tuple[str, ...] = ("#768EAE", "#A4B9A8", "#B58885", "#E2BE7B", "#BBA4C9", "#9A9A9A")

#: Slate sequential ramp, light (low) to dark (high).
slate: tuple[str, ...] = ("#EBEDF2", "#D3D7E0", "#B2BAC8", "#7F8E9D", "#5A6F7D", "#455B69")

#: Terracotta-slate diverging ramp: negative, zero (off-white, centre), positive.
terra_slate: tuple[str, ...] = (
    "#965742",
    "#B88068",
    "#D5B2A0",
    "#F1EFEA",
    "#A8B7B6",
    "#83999A",
    "#546D73",
)

#: Neutral colours: text and axes, secondary lines, grid lines, no-data areas.
neutrals: MappingProxyType[str, str] = MappingProxyType(
    {
        "text": TEXT_COLOUR,
        "secondary": SECONDARY_COLOUR,
        "grid": GRID_COLOUR,
        "no_data": NO_DATA_COLOUR,
    }
)

_COLOUR_MAPS = {"eofigs.slate": slate, "eofigs.terra_slate": terra_slate}


def _register() -> None:
    """Register the eofigs colour maps with matplotlib (once per session)."""
    for name, colours in _COLOUR_MAPS.items():
        if name in mpl.colormaps:
            continue
        cmap = LinearSegmentedColormap.from_list(name, list(colours), N=255)  # odd: exact centre
        cmap = cmap.with_extremes(bad=NO_DATA_COLOUR)
        mpl.colormaps.register(cmap)
        reversed_cmap = cmap.reversed()
        reversed_cmap.name = f"{name}_r"
        mpl.colormaps.register(reversed_cmap)


_register()
