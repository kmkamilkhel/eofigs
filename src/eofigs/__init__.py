"""Analysis-aware, publication-ready figures for Earth observation research.

eofigs is under development towards its first release (v0.1). Available now: journal
styles, figure sizes in millimetres, panel labels, export and figure checks.
"""

from eofigs.check import CheckReport, CheckResult, check_figure
from eofigs.export import save_figure
from eofigs.styling import label_panels, new_figure, set_style, style

__version__ = "0.1.0.dev0"

__all__ = [
    "CheckReport",
    "CheckResult",
    "__version__",
    "check_figure",
    "label_panels",
    "new_figure",
    "save_figure",
    "set_style",
    "style",
]
