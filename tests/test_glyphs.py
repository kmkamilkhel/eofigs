"""Every unit string must render without missing glyphs in every installed fallback font."""

import warnings

import matplotlib.pyplot as plt
import pytest

import eofigs
from eofigs import styling as style_module

UNITS = [
    r"NDVI decade$^{-1}$",
    r"gC m$^{-2}$ yr$^{-1}$",
    r"Mg ha$^{-1}$",
    r"mm d$^{-1}$",
    r"m$^{3}$ m$^{-3}$",
    r"mW m$^{-2}$ nm$^{-1}$ sr$^{-1}$",
    r"$\degree$C",
    r"K yr$^{-1}$",
    r"R$^{2}$ = 0.81",
    r"$\mu$mol m$^{-2}$ s$^{-1}$",
]
FONTS = sorted({f for chain in style_module.FONT_CHAINS.values() for f in chain})


@pytest.mark.parametrize("font", FONTS)
@pytest.mark.parametrize("bold", [False, True])
def test_units_render_without_missing_glyphs(font, bold):
    if font not in style_module._installed_fonts():
        pytest.skip(f"{font} is not installed")
    with eofigs.style("custom", font=font, bold=bold):
        fig, ax = eofigs.new_figure("single")
        for i, unit in enumerate(UNITS):
            ax.text(0.05, 0.05 + i * 0.09, unit)
        with warnings.catch_warnings():
            warnings.filterwarnings("error", message=".*[Gg]lyph.*missing.*")
            fig.canvas.draw()
        plt.close(fig)
