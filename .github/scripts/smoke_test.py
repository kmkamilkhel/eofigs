"""Smoke test of an installed eofigs: one small figure, its check and its export.

Run outside the source tree, so that the installed package is imported.
"""

import sys
import tempfile
from pathlib import Path

import numpy as np

import eofigs

eofigs.set_style("elsevier", font="DejaVu Sans")
rng = np.random.default_rng(0)
observed = rng.gamma(5, 30, 200)
fig = eofigs.accuracy_scatter(observed, observed + rng.normal(0, 15, 200), variable="agb")
report = eofigs.check_figure(fig)
print(report)
with tempfile.TemporaryDirectory() as tmp:
    saved = eofigs.save_figure(fig, Path(tmp) / "smoke")
    print(saved)
    written = sorted(p.suffix for p in Path(tmp).iterdir())
print("eofigs", eofigs.__version__, "from", Path(eofigs.__file__).parent, "wrote", written)
raster = {".png", ".tif", ".tiff"} & set(written)
sys.exit(0 if report.passed and ".pdf" in written and raster else 1)
