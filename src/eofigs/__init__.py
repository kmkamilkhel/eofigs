"""Analysis-aware, publication-ready figures for Earth observation research.

eofigs is under development towards its first release (v0.1). Available now: journal
styles, figure sizes in millimetres, panel labels, export and figure checks, the variable
library, print-size raster handling, trend statistics, manuscript figure sets, built-in
palettes and colour-blind previews.
"""

from eofigs import palettes
from eofigs.check import CheckReport, CheckResult, check_figure, cvd_preview
from eofigs.export import save_figure
from eofigs.figures import FigureSet, figure_set
from eofigs.raster import fit_raster
from eofigs.stats import trend
from eofigs.styling import label_panels, new_figure, set_style, style, tidy_axes
from eofigs.variables import Variable, register_variable, variable

__version__ = "0.1.0.dev0"

__all__ = [
    "CheckReport",
    "CheckResult",
    "FigureSet",
    "Variable",
    "__version__",
    "check_figure",
    "cvd_preview",
    "figure_set",
    "fit_raster",
    "label_panels",
    "new_figure",
    "palettes",
    "register_variable",
    "save_figure",
    "set_style",
    "style",
    "tidy_axes",
    "trend",
    "variable",
]
