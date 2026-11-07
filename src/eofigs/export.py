"""Save figures in journal formats with a check report."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib as mpl
from matplotlib.figure import Figure

from eofigs._presets import get_journal
from eofigs.check import CheckReport, check_figure
from eofigs.styling import current_journal

SUPPORTED_FORMATS = ("pdf", "png", "tiff", "tif", "eps", "svg", "jpg", "jpeg")
_CHECKABLE = {"pdf", "png", "tiff", "tif", "jpg", "jpeg"}
# Always embed TrueType (Type 42) fonts and keep SVG text as text, whatever the global settings.
_EMBED_FONTS = {"pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none"}


def save_figure(
    fig: Figure,
    path: str | Path,
    formats: Sequence[str] | None = None,
    dpi: float | None = None,
    size_px: int | tuple[int, int] | None = None,
    check: bool = True,
    journal: str | None = None,
) -> CheckReport | None:
    """Save a figure in one or more formats at its exact printed size.

    The figure is never trimmed (no ``bbox_inches="tight"``), so the saved size is the
    size set with :func:`eofigs.new_figure`. PDFs embed TrueType fonts and carry no
    creation date, so the same figure always gives the same file.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to save.
    path : str or pathlib.Path
        Output path. With a suffix (``"fig1.png"``) and no ``formats``, only that format
        is written; without a suffix (``"figures/fig1"``) the journal's default formats
        are written next to each other.
    formats : sequence of str, optional
        Formats such as ``("pdf", "png", "tiff")``. Defaults to the journal preset
        (for example PDF + TIFF for Elsevier, PDF + PNG for ``"custom"``).
    dpi : float, optional
        Resolution of raster outputs; defaults to the preset's export resolution (600).
    size_px : int or (int, int), optional
        Exact pixel width (or width and height) of raster outputs; sets the dpi.
    check : bool, default True
        Run :func:`eofigs.check_figure` on the figure and on each written PDF, PNG,
        TIFF or JPEG file.
    journal : str, optional
        Journal preset; defaults to the one used to create the figure.

    Returns
    -------
    CheckReport or None
        The combined check report, or ``None`` when ``check=False``.

    Raises
    ------
    ValueError
        For an unsupported format, or a ``size_px`` height that does not match the
        figure's aspect ratio.

    Examples
    --------
    >>> import eofigs
    >>> fig, ax = eofigs.new_figure("single", journal="custom")
    >>> _ = ax.plot([0, 1], [0, 1])
    >>> report = eofigs.save_figure(fig, "fig1", formats=("pdf", "png"))  # doctest: +SKIP
    """
    key = journal or getattr(fig, "_eofigs_journal", None) or current_journal()
    preset = get_journal(key)
    path = Path(path)
    suffix = path.suffix.lower().lstrip(".")
    if suffix in SUPPORTED_FORMATS:
        base = path.with_suffix("")
        if formats is None:
            formats = (suffix,)
    else:
        base = path
    chosen = tuple(f.lower().lstrip(".") for f in (formats or preset.formats))
    unknown = [f for f in chosen if f not in SUPPORTED_FORMATS]
    if unknown:
        raise ValueError(f"Unsupported format(s) {unknown}; use {SUPPORTED_FORMATS}.")

    out_dpi = float(dpi) if dpi is not None else float(preset.export_dpi)
    if size_px is not None:
        out_dpi = _dpi_for_pixels(fig, size_px)

    base.parent.mkdir(parents=True, exist_ok=True)
    written = []
    with mpl.rc_context(_EMBED_FONTS):
        for fmt in chosen:
            out = base.parent / f"{base.name}.{fmt}"
            fig.savefig(out, format=_mpl_format(fmt), dpi=out_dpi, **_format_options(fmt))
            written.append(out)

    if not check:
        return None
    report = check_figure(fig, journal=preset.key, dpi=out_dpi)
    for out in written:
        if out.suffix.lower().lstrip(".") in _CHECKABLE:
            report.results.extend(check_figure(out, journal=preset.key).results)
    return report


def _mpl_format(fmt: str) -> str:
    return {"tif": "tiff", "jpeg": "jpg"}.get(fmt, fmt)


def _format_options(fmt: str) -> dict:
    if fmt == "pdf":
        return {"metadata": {"CreationDate": None}}
    if fmt in ("tif", "tiff"):
        return {"pil_kwargs": {"compression": "tiff_lzw"}}
    if fmt == "svg":
        return {"metadata": {"Date": None}}
    return {}


def _dpi_for_pixels(fig: Figure, size_px: int | tuple[int, int]) -> float:
    if isinstance(size_px, int):
        width_px, height_px = size_px, None
    else:
        width_px, height_px = (int(v) for v in size_px)
    if width_px <= 0:
        raise ValueError("size_px must be positive.")
    # matplotlib truncates the pixel size, so aim a hair above the requested width
    dpi = (width_px + 1e-6) / fig.get_figwidth()
    if height_px is not None:
        actual = int(fig.get_figheight() * dpi)
        if actual != height_px:
            raise ValueError(
                f"size_px height {height_px} does not match the figure's aspect ratio "
                f"({width_px} x {actual} px). Pass only the width, or create the figure with "
                f"height_mm = width_mm * {height_px / width_px:.4f}."
            )
    return dpi
