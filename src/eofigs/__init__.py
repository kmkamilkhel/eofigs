"""Analysis-aware, publication-ready figures for Earth observation research.

eofigs is under development towards its first release (v0.1). Available now: journal
styles, figure sizes in millimetres, panel labels, export and figure checks, the variable
library, print-size raster handling, trend statistics, manuscript figure sets, built-in
palettes, colour-blind previews, study area maps, trend maps, event composites and accuracy
scatters.
"""

from eofigs import palettes
from eofigs.accuracy import accuracy_scatter
from eofigs.check import CheckReport, CheckResult, check_figure, cvd_preview
from eofigs.events import event_composite
from eofigs.export import save_figure
from eofigs.figures import FigureSet, figure_set
from eofigs.maps import add_inset, add_north_arrow, add_scale_bar, study_area_map
from eofigs.raster import fit_raster
from eofigs.stats import trend
from eofigs.styling import label_panels, new_figure, set_style, style, tidy_axes
from eofigs.trends import trend_map
from eofigs.variables import Variable, register_variable, variable

__version__ = "0.2.0"

__all__ = [
    "CheckReport",
    "CheckResult",
    "FigureSet",
    "Variable",
    "__version__",
    "accuracy_scatter",
    "add_inset",
    "add_north_arrow",
    "add_scale_bar",
    "check_figure",
    "cvd_preview",
    "event_composite",
    "figure_set",
    "fit_raster",
    "label_panels",
    "new_figure",
    "palettes",
    "register_variable",
    "save_figure",
    "set_style",
    "study_area_map",
    "style",
    "tidy_axes",
    "trend",
    "trend_map",
    "variable",
]
