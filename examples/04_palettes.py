"""Built-in palettes.

The colour palettes built into eofigs (`eofigs.palettes`): Okabe–Ito for lines and
points, muted colours for filled areas, the slate sequential ramp and the
terracotta–slate diverging ramp, both also registered as colour maps
(`"eofigs.slate"`, `"eofigs.terra_slate"`), and the neutral colours for text, secondary
lines, grid lines and no-data areas.
"""

import matplotlib as mpl
import numpy as np

import eofigs
from eofigs import palettes

rows = {
    "okabe_ito": palettes.okabe_ito,
    "muted": palettes.muted,
    "slate": palettes.slate,
    "terra_slate": palettes.terra_slate,
    "neutrals": tuple(palettes.neutrals.values()),
}

eofigs.set_style("elsevier")
fig, axes = eofigs.new_figure("double", height_mm=95, nrows=len(rows) + 2)
for ax, (name, colours) in zip(axes, rows.items(), strict=False):
    rgb = np.array([mpl.colors.to_rgb(c) for c in colours])
    ax.imshow(rgb[None], aspect="auto", extent=(0, len(colours), 0, 1))
    for i, colour in enumerate(colours):
        dark = rgb[i] @ (0.299, 0.587, 0.114) < 0.5  # white text on dark colours
        ax.text(i + 0.5, 0.5, colour.upper(), ha="center", va="center",
                fontsize=7, color="white" if dark else "#1A1A1A")  # fmt: skip
    ax.set_ylabel(name, rotation=0, ha="right", va="center")
for ax, name in zip(axes[len(rows) :], ("eofigs.slate", "eofigs.terra_slate"), strict=True):
    ax.imshow(np.linspace(0, 1, 255)[None], aspect="auto", cmap=name, extent=(0, 1, 0, 1))
    ax.set_ylabel(f'"{name}"', rotation=0, ha="right", va="center")
for ax in axes:
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

if __name__ == "__main__":
    print(eofigs.save_figure(fig, "palettes"))
