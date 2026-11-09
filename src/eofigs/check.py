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
    TEXT_COLOUR,
    classify_cmap,
    cmap_lightness,
    delta_e2000,
    diverging_ok,
    is_monotonic,
    multi_sequential_ok,
    simulate_cvd,
    to_lab,
    to_srgb,
)
from eofigs._presets import MM_PER_INCH, Journal, check_art, get_journal
from eofigs.styling import current_journal, current_max_ticks

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
    fonts in use, colour-blind safety of categorical colours, colour maps, and, when a
    tick limit is set with ``set_style(max_ticks=...)``, the number of tick labels per
    axis. For
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
    fail. Overlays drawn in one colour (for example forest on a map) are compared with the
    colour maps drawn beneath them, as they appear on the page with their transparency,
    using the same thresholds; greyscale shading is not compared.

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
        max_ticks = getattr(fig_or_path, "_eofigs_max_ticks", None) or current_max_ticks()
        return CheckReport(
            preset.key, _check_live(fig_or_path, preset, dpi, check_art(art), max_ticks)
        )
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


def _check_live(
    fig: Figure, preset: Journal, dpi: float | None, art: str, max_ticks: int | None = None
) -> list[CheckResult]:
    fig.draw_without_rendering()
    width_mm = fig.get_figwidth() * MM_PER_INCH
    height_mm = fig.get_figheight() * MM_PER_INCH
    if dpi is None:
        dpi = preset.export_dpi_for(art)  # what save_figure writes by default
    texts = [t for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()]
    results = [
        _size_result(width_mm, height_mm, preset, "figure"),
        _dpi_result(float(dpi), preset, "figure", art),
        _font_size_result(texts, preset),
        _fonts_in_use_result(texts, preset),
        _categorical_result(fig),
        _cmap_result(fig),
    ]
    overlay = _overlay_result(fig)
    if overlay is not None:
        results.append(overlay)
    if max_ticks is not None:
        results.append(_tick_result(fig, max_ticks))
    return results


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


#: Free fonts with the same metrics as a commercial font: text keeps the same width and
#: line breaks, so journals' typesetting accepts them in its place.
METRIC_COMPATIBLE = {
    "Liberation Sans": "Arial",
    "Arimo": "Arial",
    "TeX Gyre Heros": "Helvetica",
    "Liberation Serif": "Times New Roman",
    "Tinos": "Times New Roman",
    "TeX Gyre Termes": "Times New Roman",
    "Liberation Mono": "Courier",
    "Cousine": "Courier",
}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def _accepted(name: str, accepted: tuple[str, ...]) -> bool:
    return any(_norm(a) in _norm(name) for a in accepted)


def _substitute_for(name: str, accepted: tuple[str, ...]) -> str | None:
    """Return the listed font that ``name`` is metric-compatible with, if any."""
    for free, commercial in METRIC_COMPATIBLE.items():
        if _norm(free) in _norm(name) and _accepted(commercial, accepted):
            return commercial
    return None


def _font_list_result(names: list[str], preset: Journal, target: str, embedded: bool):
    what = "Embedded fonts" if embedded else "Fonts in use"
    if not preset.fonts:
        return CheckResult("fonts", "pass", f"{what}: {', '.join(names)}.", target)
    found = any if embedded else all  # a PDF also embeds fonts for symbols and mathtext
    notes = []
    ok = []
    for name in names:
        if _accepted(name, preset.fonts):
            ok.append(True)
            continue
        commercial = _substitute_for(name, preset.fonts)
        ok.append(commercial is not None)
        if commercial is not None:
            notes.append(f"{name} is metric-compatible with {commercial}")
    if not found(ok):
        return CheckResult(
            "fonts",
            "warn",
            f"{what}: {', '.join(names)}; {preset.name} lists {', '.join(preset.fonts)}.",
            target,
        )
    note = f" ({'; '.join(sorted(set(notes)))})" if notes else ""
    return CheckResult("fonts", "pass", f"{what}: {', '.join(names)}{note}.", target)


def _fonts_in_use_result(texts: list[Text], preset: Journal) -> CheckResult:
    names = sorted({_font_name(t) for t in texts})
    if not names:
        return CheckResult("fonts", "pass", "No text in the figure.")
    return _font_list_result(names, preset, "figure", embedded=False)


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
            if not coll.get_visible() or _is_colour_mapped(coll) or _is_envelope(coll):
                continue
            faces = coll.get_facecolors()
            if 0 < len(faces) <= 20:
                for face in np.unique(np.round(faces, 4), axis=0):
                    add(tuple(face))
        for patch in ax.patches:
            if patch.get_visible() and patch.get_fill():
                add(patch.get_facecolor())
    return list(found)


def _is_envelope(coll) -> bool:
    """Tell whether a collection is a fill_between band (a continuous envelope, not a class)."""
    return bool(getattr(coll, "_eofigs_envelope", False)) or (
        type(coll).__name__ == "FillBetweenPolyCollection"
    )


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


def _single_colour(image) -> tuple[float, float, float, float] | None:
    """Colour of an image drawn in one colour (a one-colour colour map), else None."""
    cmap = image.get_cmap()
    if cmap.N > 1 or image.get_array() is None:
        return None
    return tuple(float(v) for v in cmap(0.5))


def _alpha(image) -> float:
    alpha = image.get_alpha()
    return 1.0 if alpha is None or np.ndim(alpha) else float(alpha)


def overlay_contrast(
    colour, alpha: float, cmap, cmap_alpha: float, n: int = 64
) -> dict[str, float]:
    """Smallest CIEDE2000 difference between an overlay colour and a colour map's colours.

    Both are composited over white with their transparency, as they appear on the page,
    and compared in normal vision and under simulated protan, deutan and tritan vision.
    """
    overlay = np.array(_composite((*mpl.colors.to_rgb(colour), alpha)))
    samples = cmap(np.linspace(0, 1, n))[:, :3]
    base = samples * cmap_alpha + (1 - cmap_alpha)
    result = {}
    for view in ("normal", "protan", "deutan", "tritan"):
        a = overlay[None] if view == "normal" else simulate_cvd(overlay[None], view)
        b = base if view == "normal" else simulate_cvd(base, view)
        lab_a, lab_b = to_lab(a)[0], to_lab(b)
        result[view] = min(delta_e2000(lab_a, lab) for lab in lab_b)
    return result


def _is_grey(cmap) -> bool:
    lab = to_lab(cmap(np.linspace(0, 1, 32))[:, :3])
    return bool(np.hypot(lab[:, 1], lab[:, 2]).max() < 5)


def _overlay_result(fig: Figure) -> CheckResult | None:
    """Single-colour overlays must stay distinguishable from the colour maps beneath them."""
    pairs, close = 0, []
    worst: dict[str, float] = {}
    for ax in fig.axes:
        images = ax.get_images()
        for top in images:
            colour = _single_colour(top)
            if colour is None or not top.get_visible():
                continue
            for base in images:
                if (
                    base is top
                    or base.get_zorder() >= top.get_zorder()
                    or not _is_colour_mapped(base)
                    or base.get_cmap().N <= 1
                    or _is_grey(base.get_cmap())
                ):
                    continue
                pairs += 1
                diff = overlay_contrast(colour[:3], _alpha(top), base.get_cmap(), _alpha(base))
                for view, value in diff.items():
                    worst[view] = min(worst.get(view, np.inf), value)
                    threshold = DE_NORMAL if view == "normal" else DE_CVD
                    if value < threshold:
                        close.append(f"{mpl.colors.to_hex(colour)} on {base.get_cmap().name} "
                                     f"{view} {value:.1f}")  # fmt: skip
    if not pairs:
        return None
    summary = ", ".join(f"{k} {v:.1f}" for k, v in worst.items())
    if close:
        return CheckResult(
            "overlay contrast",
            "warn",
            "An overlay colour is close to colours of the map beneath it "
            f"({'; '.join(close[:4])}). Choose an overlay colour or a colour map that differ more.",
        )
    return CheckResult(
        "overlay contrast",
        "pass",
        f"Overlay distinguishable from the colour map (min dE00 {summary}).",
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


def _tick_count(axis) -> int:
    """Count the non-empty major tick labels shown inside the view interval."""
    if not axis.get_visible():  # for example map axes, labelled by their graticule
        return 0
    params = axis.get_tick_params(which="major")
    sides = ("labelbottom", "labeltop") if axis.axis_name == "x" else ("labelleft", "labelright")
    if not any(params.get(side, side in ("labelbottom", "labelleft")) for side in sides):
        return 0
    low, high = sorted(axis.get_view_interval())
    span = (high - low) * 1e-9
    locs = [v for v in axis.get_majorticklocs() if low - span <= v <= high + span]
    if not locs:
        return 0
    labels = axis.get_major_formatter().format_ticks(locs)
    return sum(1 for label in labels if str(label).strip())


def _tick_result(fig: Figure, max_ticks: int) -> CheckResult:
    crowded = []
    for i, ax in enumerate(fig.axes, 1):
        if not ax.get_visible() or not ax.axison:
            continue
        for axis in (ax.xaxis, ax.yaxis):
            if axis.get_scale() != "linear":
                continue
            n = _tick_count(axis)
            if n > max_ticks:
                crowded.append(f"axes {i} {axis.axis_name} ({n})")
    if crowded:
        return CheckResult(
            "ticks",
            "warn",
            f"More than {max_ticks} tick labels: {', '.join(crowded[:6])}. "
            "eofigs.tidy_axes limits ticks to round values.",
        )
    return CheckResult("ticks", "pass", f"At most {max_ticks} tick labels per axis.")


# ----------------------------------------------------------------------------- preview


_PREVIEW_VIEWS = ("Normal", "Protan", "Deutan", "Tritan", "Greyscale")


def cvd_preview(
    fig_or_path: Figure | str | Path, out: str | Path | None = None, dpi: float = 150
) -> Path:
    """Write one image showing a figure as seen with colour-vision deficiencies.

    The image has five panels: normal vision, protan, deutan and tritan simulations
    (Machado et al. 2009, full severity, the same as :func:`check_figure`) and greyscale
    (CIELAB lightness). Use it to confirm that every series, class and colour-map step
    is still distinguishable, and that sequential data keep their order in greyscale.

    Parameters
    ----------
    fig_or_path : matplotlib.figure.Figure or path
        A figure, or a PNG, TIFF or JPEG file.
    out : str or pathlib.Path, optional
        Output PNG. Defaults to ``<name>_cvd.png`` next to an input file; required for a
        figure.
    dpi : float, default 150
        Resolution at which a figure is rendered for the preview.

    Returns
    -------
    pathlib.Path
        The written PNG.

    Raises
    ------
    ValueError
        For a figure without ``out``, or an unsupported file type (render PDFs to PNG
        first).
    FileNotFoundError
        If the input file does not exist.

    Examples
    --------
    >>> import eofigs
    >>> fig, ax = eofigs.new_figure("single")
    >>> _ = ax.plot([0, 1], [0, 1])
    >>> eofigs.cvd_preview(fig, "fig1_cvd.png")  # doctest: +SKIP
    """
    if out is None and isinstance(fig_or_path, Figure):
        raise ValueError("Pass out= (the PNG to write) when previewing a figure.")
    rgb = _preview_input(fig_or_path, dpi)
    if out is None:
        source = Path(fig_or_path)
        out = source.with_name(f"{source.stem}_cvd.png")
    out = Path(out)
    views = [rgb, *(simulate_cvd(rgb, kind) for kind in ("protan", "deutan", "tritan"))]
    grey = _lightness_to_grey(to_lab(rgb)[..., 0])
    views.append(np.repeat(grey[..., None], 3, axis=-1))
    _write_preview(views, out)
    return out


def _preview_input(fig_or_path: Figure | str | Path, dpi: float) -> np.ndarray:
    from io import BytesIO

    from PIL import Image

    if isinstance(fig_or_path, Figure):
        buffer = BytesIO()
        fig_or_path.savefig(buffer, format="png", dpi=dpi, facecolor="white")
        buffer.seek(0)
        image = Image.open(buffer)
    else:
        path = Path(fig_or_path)
        if path.suffix.lower() not in _RASTER_SUFFIXES:
            raise ValueError(
                f"Cannot preview {path.suffix!r} files; use PNG, TIFF or JPEG "
                "(export a PNG with eofigs.save_figure first)."
            )
        if not path.exists():
            raise FileNotFoundError(path)
        image = Image.open(path)
    with image:
        rgba = np.asarray(image.convert("RGBA"), dtype=float) / 255
    alpha = rgba[..., 3:]
    return rgba[..., :3] * alpha + (1 - alpha)  # flatten transparency onto white


def _lightness_to_grey(lightness: np.ndarray) -> np.ndarray:
    """Return the sRGB grey value that has the given CIELAB lightness."""
    f = (lightness + 16) / 116
    luminance = np.where(lightness > 8, f**3, lightness / (24389 / 27))
    return to_srgb(luminance)


def _preview_columns(width: int, height: int, n: int = len(_PREVIEW_VIEWS)) -> int:
    """Choose the number of columns that brings the whole preview closest to 16:9."""

    def distance(ncols: int) -> float:
        nrows = -(-n // ncols)
        empty = nrows * ncols - n  # empty cells waste space
        return abs(np.log(ncols * width / (nrows * height) / (16 / 9))) + 0.2 * empty

    return min(range(1, n + 1), key=distance)


def _write_preview(views: list[np.ndarray], out: Path) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    height, width = views[0].shape[:2]
    ncols = _preview_columns(width, height)
    nrows = -(-len(views) // ncols)
    gap = max(8, min(width, height) // 40)
    header = max(30, round(0.06 * max(width, height) / max(ncols, 2)))
    cell_w, cell_h = width + gap, height + header + gap
    total_w, total_h = ncols * cell_w - gap, nrows * cell_h - gap
    preview = Figure(figsize=(total_w / 100, total_h / 100), dpi=100, facecolor="white")
    FigureCanvasAgg(preview)
    for i, (view, title) in enumerate(zip(views, _PREVIEW_VIEWS, strict=True)):
        row, col = divmod(i, ncols)
        left = col * cell_w / total_w
        top = 1 - row * cell_h / total_h
        bottom = top - (header + height) / total_h
        ax = preview.add_axes((left, bottom, width / total_w, height / total_h))
        ax.imshow(np.clip(view, 0, 1), interpolation="nearest")
        ax.set_axis_off()
        preview.text(
            left + width / total_w / 2,
            top - header / total_h / 2,
            title,
            ha="center",
            va="center",
            fontsize=header * 0.55 * 72 / 100,
            fontweight="bold",
            color=TEXT_COLOUR,
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    preview.savefig(out, dpi=100, facecolor="white")


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
_FONT_FILES = ("/FontFile", "/FontFile2", "/FontFile3")


def _font_entries(path: Path) -> tuple[dict[str, str], tuple[float, ...] | None]:
    """Fonts used on the pages of a PDF, each "embedded", "type3" or "not embedded".

    Reads the PDF structure (cross-reference tables and object streams) with pypdf and
    follows every page's resources, including form XObjects and Type 3 glyph resources.
    A font counts as embedded only when its descriptor carries the font program
    (FontFile, FontFile2 or FontFile3). Returns the fonts and the first page's MediaBox.
    Raises ValueError when the file cannot be read reliably.
    """
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    fonts: dict[str, str] = {}
    seen: set[int] = set()
    rank = {"embedded": 0, "not embedded": 1, "type3": 2}

    def resolve(obj):
        return obj.get_object() if obj is not None else None

    def visit(resources) -> None:
        res = resolve(resources)
        if not res or id(res) in seen:
            return
        seen.add(id(res))
        for key, ref in (resolve(res.get("/Font")) or {}).items():
            font = resolve(ref)
            subtype = font.get("/Subtype")
            name = str(font.get("/BaseFont") or font.get("/Name") or key).lstrip("/")
            name = re.sub(r"^[A-Z]{6}\+", "", name)
            if subtype == "/Type3":
                status = "type3"
                visit(font.get("/Resources"))
            else:
                described = resolve(font["/DescendantFonts"])[0] if subtype == "/Type0" else font
                descriptor = resolve(resolve(described).get("/FontDescriptor"))
                embedded = descriptor is not None and any(k in descriptor for k in _FONT_FILES)
                status = "embedded" if embedded else "not embedded"
            if rank[status] >= rank.get(fonts.get(name, "embedded"), 0):
                fonts[name] = status
        for ref in (resolve(res.get("/XObject")) or {}).values():
            xobject = resolve(ref)
            if xobject.get("/Subtype") == "/Form":
                visit(xobject.get("/Resources"))

    try:
        reader = PdfReader(path, strict=True)
        box = None
        for i, page in enumerate(reader.pages):
            if i == 0:
                box = tuple(float(v) for v in page.mediabox)
            visit(page.get("/Resources"))
    except (PyPdfError, KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError(f"{type(exc).__name__}: {exc}") from exc
    return fonts, box


def _check_pdf(path: Path, preset: Journal) -> list[CheckResult]:
    target = path.name
    results = []
    try:
        fonts, box = _font_entries(path)
    except ValueError as exc:
        fonts, box = None, None
        reason = str(exc)
    if box is None:
        found = _MEDIABOX.search(path.read_bytes())
        box = tuple(float(v) for v in found.groups()) if found else None
    if box:
        x0, y0, x1, y1 = box
        results.append(
            _size_result((x1 - x0) / 72 * MM_PER_INCH, (y1 - y0) / 72 * MM_PER_INCH, preset, target)
        )
    if fonts is None:
        results.append(
            CheckResult(
                "fonts",
                "warn",
                f"Font embedding could not be verified: the PDF structure could not be read "
                f"({reason}). Check the fonts in a PDF viewer (document properties).",
                target,
            )
        )
        return results
    type3 = sorted(n for n, s in fonts.items() if s == "type3")
    missing = sorted(n for n, s in fonts.items() if s == "not embedded")
    if not fonts:
        results.append(CheckResult("fonts", "pass", "No fonts embedded (no text).", target))
    elif type3 or missing:
        problems = []
        if missing:
            problems.append(
                f"Fonts not embedded ({', '.join(missing)}); journals need every font "
                "embedded. Turn pdf.use14corefonts off."
            )
        if type3:
            problems.append(
                f"Type 3 fonts embedded ({', '.join(type3)}); journals need Type 42/TrueType."
            )
        problems.append("Use eofigs.set_style or set pdf.fonttype to 42.")
        results.append(CheckResult("fonts", "fail", " ".join(problems), target))
    else:
        results.append(_font_list_result(sorted(fonts), preset, target, embedded=True))
    return results
