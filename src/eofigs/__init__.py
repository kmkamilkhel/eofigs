"""Analysis-aware, publication-ready figures for Earth observation research.

eofigs is under development towards its first release (v0.1). Available now: journal
styles, figure sizes in millimetres, panel labels, export and figure checks, the variable
library and print-size raster handling.
"""

from eofigs.check import CheckReport, CheckResult, check_figure
from eofigs.export import save_figure
from eofigs.raster import fit_raster
from eofigs.styling import label_panels, new_figure, set_style, style
from eofigs.variables import Variable, register_variable, variable

__version__ = "0.1.0.dev0"

__all__ = [
    "CheckReport",
    "CheckResult",
    "Variable",
    "__version__",
    "check_figure",
    "fit_raster",
    "label_panels",
    "new_figure",
    "register_variable",
    "save_figure",
    "set_style",
    "style",
    "variable",
]
