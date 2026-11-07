"""Check a figure or an exported file against journal requirements."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Literal

import matplotlib as mpl
import numpy as np
from matplotlib import font_manager
from matplotlib.cm import ScalarMappable
from matplotlib.collections import Collection
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure
from matplotlib.text import Text

from eofigs._colour import (
    classify_cmap,
    cmap_lightness,
    delta_e2000,
    diverging_ok,
    is_monotonic,
    multi_sequential_ok,
    simulate_cvd,
    to_lab,
)
from eofigs._presets import MM_PER_INCH, Journal, check_art, get_journal
from eofigs.styling import current_journal

Status = Literal["pass", "warn", "fail"]

#: CIEDE2000 thresholds for categorical colours (normal vision, colour-vision deficiency).
DE_NORMAL = 10.0
DE_CVD = 6.0
_RASTER_SUFFIXES = {".png", ".tif", ".tiff", ".jpg", ".jpeg"}
_WIDTH_TOL_MM = 0.5


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one check."""

    name: str
    status: Status
    message: str
    target: str = "figure"


@dataclass
class CheckReport:
    """All check results for a figure or file."""

    journal: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True when no check failed (warnings are allowed)."""
        return not self.failures

    @property
    def failures(self) -> list[CheckResult]:
        """Checks with status ``"fail"``."""
        return [r for r in self.results if r.status == "fail"]

    @property
    def warnings(self) -> list[CheckResult]:
        """Checks with status ``"warn"``."""
        return [r for r in self.results if r.status == "warn"]

    def to_dict(self) -> dict:
        """JSON-serialisable form of the report."""
        return {
            "journal": self.journal,
            "passed": self.passed,
            "results": [asdict(r) for r in self.results],
        }

    def __str__(self) -> str:
        """Readable multi-line report."""
        lines = [f"Figure check ({self.journal}): {'passed' if self.passed else 'FAILED'}"]
        for r in self.results:
            target = "" if r.target == "figure" else f" [{r.target}]"
            lines.append(f"  {r.status.upper():4s}  {r.name}{target}: {r.message}")
        return "\n".join(lines)


def check_figure(
    fig_or_path: Figure | str | Path,
    journal: str | None = None,
    dpi: float | None = None,
    art: str = "combination",
) -> CheckReport:
    """Check a figure, or an exported PDF/PNG/TIFF, against a journal preset.

    For a live figure the checks are: printed size, resolution, smallest font size,
    fonts in use, colour-blind safety of categorical colours, and colour maps. For
    files: size and resolution (raster files), size and embedded fonts (PDF).

    Parameters
    ----------
    fig_or_path : matplotlib.figure.Figure or path
        A figure, or a ``.pdf``, ``.png``, ``.tif``/``.tiff`` or ``.jpg`` file.
    journal : str, optional
        Journal preset; defaults to the one used to create the figure, or the one set by
        :func:`eofigs.set_style`.
    dpi : float, optional
        Export resolution to check for a live figure; defaults to the resolution
        :func:`eofigs.save_figure` writes by default for this journal and ``art``.
    art : {"combination", "line", "halftone"}, default "combination"
        Artwork type, which sets the resolution the journal requires: ``"line"`` for
        plots and drawings (for example 1000 dpi for Elsevier, 1200 dpi for Springer),
        ``"halftone"`` for photographs and images, ``"combination"`` for both.

    Returns
    -------
    CheckReport
        ``report.passed`` is True when no check failed; print the report for details.

    Raises
    ------
    ValueError
        For an unsupported file type.
    FileNotFoundError
        If the file does not exist.

    Notes
    -----
    Categorical colours (lines, markers, bars, filled areas) are compared pairwise with
    CIEDE2000 in normal vision (warning below 10) and under simulated protan, deutan and
    tritan vision (Machado et al. 2009, full severity; warning below 6). Close pairs are
    a warning, not a failure: they are safe when series also differ by marker, line style
    or direct labels. Colour maps are classified first; sequential maps need monotonic
    lightness, diverging maps monotonic lightness on each side of the centre, cyclic and
    categorical maps are exempt, and rainbow-type maps (jet, rainbow, hsv, turbo, ...)
    fail.

    Examples
    --------
    >>> import eofigs
    >>> fig, ax = eofigs.new_figure("single", journal="elsevier")
    >>> _ = ax.plot([0, 1], [0, 1])
    >>> eofigs.check_figure(fig, journal="elsevier").passed
    True
    """
    if isinstance(fig_or_path, Figure):
        key = journal or getattr(fig_or_path, "_eofigs_journal", None) or current_journal()
        preset = get_journal(key)
        return CheckReport(preset.key, _check_live(fig_or_path, preset, dpi, check_art(art)))
    check_art(art)
    path = Path(fig_or_path)
    preset = get_journal(journal or current_journal())
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        results = _check_pdf(path, preset)
    elif suffix in _RASTER_SUFFIXES:
        results = _check_raster(path, preset, art)
    else:
        raise ValueError(f"Cannot check {suffix!r} files; use PDF, PNG, TIFF or JPEG.")
    return CheckReport(preset.key, results)


# ----------------------------------------------------------------------------- size, dpi


def _size_result(width_mm: float, height_mm: float, preset: Journal, target: str) -> CheckResult:
    size = f"{width_mm:.1f} x {height_mm:.1f} mm"
    if width_mm > preset.max_width_mm + _WIDTH_TOL_MM:
        return CheckResult(
            "size",
            "fail",
            f"{size} is wider than the full width ({preset.max_width_mm:g} mm).",
            target,
        )
    if height_mm > preset.max_height_mm + _WIDTH_TOL_MM:
        return CheckResult(
            "size",
            "fail",
            f"{size} is taller than the maximum ({preset.max_height_mm:g} mm).",
            target,
        )
    for name, value in preset.widths_mm.items():
        if abs(width_mm - value) <= _WIDTH_TOL_MM and name != "minimum":
            return CheckResult("size", "pass", f"{size} ({name} width).", target)
    named = ", ".join(f"{k} {v:g}" for k, v in preset.widths_mm.items() if k != "minimum")
    return CheckResult(
        "size", "warn", f"{size} does not match a column width ({named} mm).", target
    )


_ART_WORDS = {
    "combination": "figures with text and images",
    "line": "line art",
    "halftone": "halftone images",
}


def _dpi_result(dpi: float, preset: Journal, target: str, art: str) -> CheckResult:
    need = preset.required_dpi(art)
    if dpi + 0.5 < need:
        return CheckResult(
            "resolution",
            "fail",
            f"{dpi:.0f} dpi is below the {need} dpi {preset.name} requires for {_ART_WORDS[art]}.",
            target,
        )
    return CheckResult(
        "resolution", "pass", f"{dpi:.0f} dpi (at least {need} for {_ART_WORDS[art]}).", target
    )


# ----------------------------------------------------------------------------- live figure


def _check_live(fig: Figure, preset: Journal, dpi: float | None, art: str) -> list[CheckResult]:
    fig.draw_without_rendering()
    width_mm = fig.get_figwidth() * MM_PER_INCH
    height_mm = fig.get_figheight() * MM_PER_INCH
    if dpi is None:
        dpi = preset.export_dpi_for(art)  # what save_figure writes by default
    texts = [t for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()]
    return [
        _size_result(width_mm, height_mm, preset, "figure"),
        _dpi_result(float(dpi), preset, "figure", art),
        _font_size_result(texts, preset),
        _fonts_in_use_result(texts, preset),
        _categorical_result(fig),
        _cmap_result(fig),
    ]


def _font_size_result(texts: list[Text], preset: Journal) -> CheckResult:
    if not texts:
        return CheckResult("font size", "pass", "No text in the figure.")
    smallest = min(t.get_fontsize() for t in texts)
    if smallest + 1e-6 < preset.min_font_pt:
        small = sorted({t.get_text()[:20] for t in texts if t.get_fontsize() == smallest})
        return CheckResult(
            "font size",
            "fail",
            f"Smallest text is {smallest:g} pt (minimum {preset.min_font_pt:g} pt): {small[:5]}.",
        )
    return CheckResult(
        "font size", "pass", f"Smallest text {smallest:g} pt (minimum {preset.min_font_pt:g} pt)."
    )


def _font_name(text: Text) -> str:
    path = font_manager.findfont(text.get_fontproperties(), fallback_to_default=True)
    return font_manager.get_font(path).family_name


def _accepted(name: str, accepted: tuple[str, ...]) -> bool:
    norm = re.sub(r"[^a-z]", "", name.lower())
    return any(re.sub(r"[^a-z]", "", a.lower()) in norm for a in accepted)


def _fonts_in_use_result(texts: list[Text], preset: Journal) -> CheckResult:
    names = sorted({_font_name(t) for t in texts})
    if not names:
        return CheckResult("fonts", "pass", "No text in the figure.")
    if preset.fonts and not all(_accepted(n, preset.fonts) for n in names):
        return CheckResult(
            "fonts",
            "warn",
            f"Fonts in use: {', '.join(names)}; {preset.name} lists {', '.join(preset.fonts)}.",
        )
    return CheckResult("fonts", "pass", f"Fonts in use: {', '.join(names)}.")


def _composite(rgba: tuple[float, float, float, float]) -> tuple[float, float, float]:
    r, g, b, a = rgba
    return (r * a + (1 - a), g * a + (1 - a), b * a + (1 - a))


def _categorical_colours(fig: Figure) -> list[str]:
    found: dict[str, None] = {}

    def add(colour) -> None:
        rgba = to_rgba(colour)
        if rgba[3] == 0:
            return
        rgb = _composite(rgba)
        if min(rgb) > 0.98:  # white background-like fills
            return
        found.setdefault(mpl.colors.to_hex(rgb), None)

    for ax in fig.axes:
        for line in ax.get_lines():
            if line.get_visible() and len(line.get_xdata()) > 0:
                add(line.get_color())
        for coll in ax.collections:
            if not coll.get_visible() or _is_colour_mapped(coll):
                continue
            faces = coll.get_facecolors()
            if 0 < len(faces) <= 20:
                for face in np.unique(np.round(faces, 4), axis=0):
                    add(tuple(face))
        for patch in ax.patches:
            if patch.get_visible() and patch.get_fill():
                add(patch.get_facecolor())
    return list(found)


def _is_colour_mapped(artist) -> bool:
    return isinstance(artist, ScalarMappable) and artist.get_array() is not None


def _categorical_result(fig: Figure) -> CheckResult:
    colours = _categorical_colours(fig)
    if len(colours) < 2:
        return CheckResult("colour-blind safety", "pass", "Fewer than two categorical colours.")
    rgb = np.array([mpl.colors.to_rgb(c) for c in colours])
    close: list[str] = []
    for view, threshold in (
        ("normal", DE_NORMAL),
        ("protan", DE_CVD),
        ("deutan", DE_CVD),
        ("tritan", DE_CVD),
    ):
        shown = rgb if view == "normal" else simulate_cvd(rgb, view)
        lab = to_lab(shown)
        for i, j in combinations(range(len(colours)), 2):
            d = delta_e2000(lab[i], lab[j])
            if d < threshold:
                close.append(f"{colours[i]}/{colours[j]} {view} {d:.1f}")
    if close:
        return CheckResult(
            "colour-blind safety",
            "warn",
            f"{len(close)} close colour pair(s): {'; '.join(close[:6])}. "
            "Distinguish these series by marker, line style or direct labels too.",
        )
    return CheckResult(
        "colour-blind safety", "pass", f"{len(colours)} categorical colours, all distinguishable."
    )


def _cmap_result(fig: Figure) -> CheckResult:
    problems, seen = [], {}
    for ax in fig.axes:
        artists = [*ax.images, *[c for c in ax.collections if isinstance(c, Collection)]]
        for artist in artists:
            if not _is_colour_mapped(artist):
                continue
            cmap = artist.get_cmap()
            if cmap.N <= 1:  # a single fixed colour (for example contour lines), not a colour map
                continue
            kind = getattr(artist, "_eofigs_cmap_kind", None) or classify_cmap(cmap)
            seen[cmap.name] = kind
            lightness = cmap_lightness(cmap)
            if kind == "banned":
                problems.append(f"{cmap.name} (rainbow-type, uneven lightness)")
            elif kind == "unknown":
                problems.append(f"{cmap.name} (lightness is not monotonic)")
            elif kind == "sequential" and not is_monotonic(lightness):
                problems.append(f"{cmap.name} (sequential map with non-monotonic lightness)")
            elif kind == "diverging" and not diverging_ok(lightness):
                problems.append(f"{cmap.name} (diverging map not monotonic on each side)")
            elif kind == "multi-sequential" and not multi_sequential_ok(lightness):
                problems.append(f"{cmap.name} (two-part map not monotonic in each part)")
    if problems:
        return CheckResult(
            "colour maps",
            "fail",
            f"Replace {', '.join(sorted(set(problems)))} with a perceptually uniform map "
            "(for example cmcrameri batlow, or vik for signed values).",
        )
    if not seen:
        return CheckResult("colour maps", "pass", "No colour-mapped data.")
    listed = ", ".join(f"{k} ({v})" for k, v in sorted(seen.items()))
    return CheckResult("colour maps", "pass", f"Colour maps: {listed}.")


# ----------------------------------------------------------------------------- files


def _check_raster(path: Path, preset: Journal, art: str) -> list[CheckResult]:
    from PIL import Image

    target = path.name
    with Image.open(path) as im:
        width_px, height_px = im.size
        info_dpi = im.info.get("dpi")
    if not info_dpi or not info_dpi[0]:
        return [
            CheckResult(
                "resolution",
                "fail",
                f"{width_px} x {height_px} px with no dpi stored in the file.",
                target,
            )
        ]
    dpi = float(info_dpi[0])
    width_mm = width_px / dpi * MM_PER_INCH
    height_mm = height_px / dpi * MM_PER_INCH
    return [
        _size_result(width_mm, height_mm, preset, target),
        _dpi_result(dpi, preset, target, art),
    ]


_MEDIABOX = re.compile(rb"/MediaBox\s*\[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]")
_FONT_SUBTYPE = re.compile(rb"/Subtype\s*/(Type3|Type1|TrueType|Type0|CIDFontType0|CIDFontType2)\b")
_BASEFONT = re.compile(rb"/BaseFont\s*/([^\s/<>\[\]()]+)")


def _check_pdf(path: Path, preset: Journal) -> list[CheckResult]:
    data = path.read_bytes()
    target = path.name
    results = []
    box = _MEDIABOX.search(data)
    if box:
        x0, y0, x1, y1 = (float(v) for v in box.groups())
        results.append(
            _size_result((x1 - x0) / 72 * MM_PER_INCH, (y1 - y0) / 72 * MM_PER_INCH, preset, target)
        )
    subtypes = {m.decode() for m in _FONT_SUBTYPE.findall(data)}
    names = sorted({re.sub(r"^[A-Z]{6}\+", "", m.decode()) for m in _BASEFONT.findall(data)})
    if not names:
        results.append(CheckResult("fonts", "pass", "No fonts embedded (no text).", target))
    elif "Type3" in subtypes:
        results.append(
            CheckResult(
                "fonts",
                "fail",
                f"Type 3 fonts embedded ({', '.join(names)}); journals need Type 42/TrueType. "
                "Use eofigs.set_style or set pdf.fonttype to 42.",
                target,
            )
        )
    elif preset.fonts and not any(_accepted(n, preset.fonts) for n in names):
        results.append(
            CheckResult(
                "fonts",
                "warn",
                f"Embedded fonts {', '.join(names)}; "
                f"{preset.name} lists {', '.join(preset.fonts)}.",
                target,
            )
        )
    else:
        results.append(CheckResult("fonts", "pass", f"Embedded fonts: {', '.join(names)}.", target))
    return results
