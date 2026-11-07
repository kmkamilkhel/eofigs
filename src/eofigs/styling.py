"""Journal styles, figure sizes in mm and panel labels."""

from __future__ import annotations

import string
import warnings
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import cmcrameri.cm  # noqa: F401  (registers the "cmc.*" colour maps)
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from cycler import cycler
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.text import Text
from matplotlib.transforms import offset_copy

from eofigs._colour import GRID_COLOUR, OKABE_ITO, TEXT_COLOUR
from eofigs._presets import MM_PER_INCH, get_journal, resolve_width

#: Font fallback chains. TrueType fonts come first so that PDFs embed them as Type 42.
FONT_CHAINS: dict[str, tuple[str, ...]] = {
    "serif": ("Times New Roman", "Liberation Serif", "TeX Gyre Termes", "DejaVu Serif"),
    "sans-serif": ("Arial", "Liberation Sans", "Arimo", "DejaVu Sans"),
}
_FAMILY_ALIASES = {"serif": "serif", "sans": "sans-serif", "sans-serif": "sans-serif"}
LABEL_FORMATS = ("(a)", "a", "(A)", "A", "a)")
#: Default largest number of tick labels on an axis or colour bar.
MAX_TICKS = 5
#: Round steps for tick values (1, 2, 2.5 and 5 times a power of ten).
TICK_STEPS = (1, 2, 2.5, 5, 10)

_DEFAULT_STATE: dict[str, Any] = {
    "journal": "custom",
    "labels": "(a)",
    "label_bold": True,
    "font": None,
    "font_family": "sans-serif",
}
_STATE: dict[str, Any] = dict(_DEFAULT_STATE)
_ORIGINAL_RC: dict[str, Any] | None = None


def _installed_fonts() -> set[str]:
    return {f.name for f in font_manager.fontManager.ttflist}


def _resolve_font(font: str | None, default_family: str) -> tuple[str, str]:
    """Return (font name, family) for a requested font or family, warning on substitution."""
    installed = _installed_fonts()
    requested = font if font is not None else default_family
    family_key = _FAMILY_ALIASES.get(str(requested).lower())
    if family_key is not None:
        chain = FONT_CHAINS[family_key]
    else:
        family_key = "serif" if requested in FONT_CHAINS["serif"] else default_family
        family_key = _FAMILY_ALIASES.get(family_key, "sans-serif")
        chain = (requested, *FONT_CHAINS[family_key])
    for name in chain:
        if name in installed:
            if name != chain[0]:
                warnings.warn(
                    f"Font {chain[0]!r} is not installed; using {name!r} instead. "
                    "Install the font or pass font= with an installed font to silence this.",
                    UserWarning,
                    stacklevel=3,
                )
            return name, family_key
    return "DejaVu Sans", "sans-serif"  # always shipped with matplotlib


def set_style(
    journal: str | None = "elsevier",
    font: str | None = None,
    bold: bool = False,
    base_size: float | None = None,
    labels: str | None = "(a)",
    label_bold: bool = True,
) -> None:
    """Apply a journal style to matplotlib.

    This is the only eofigs function that changes global state (matplotlib's
    ``rcParams`` and the eofigs defaults for panel labels). Use :func:`style` to apply
    a style temporarily.

    Parameters
    ----------
    journal : str or None, default "elsevier"
        Journal preset: ``"elsevier"``, ``"springer"``, ``"mdpi"``, ``"wiley"``,
        ``"frontiers"``, ``"taylor_francis"`` or ``"custom"``. ``None`` restores the
        settings that were active before the first call.
    font : str, optional
        ``"serif"``, ``"sans-serif"`` or a font name such as ``"Times New Roman"``.
        Defaults to the journal's preferred family. Missing fonts fall back to
        metric-compatible free fonts (Liberation Serif, TeX Gyre Termes,
        Liberation Sans) with a warning.
    bold : bool, default False
        Bold text for labels, titles and tick labels.
    base_size : float, optional
        Base font size in points. Defaults to the journal preset; tick labels are one
        point smaller but never below the journal minimum.
    labels : str or None, default "(a)"
        Default panel-label format: ``"(a)"``, ``"a"``, ``"(A)"``, ``"A"``, ``"a)"`` or
        ``None`` for no labels.
    label_bold : bool, default True
        Bold panel labels.

    Raises
    ------
    ValueError
        For an unknown journal or label format.

    Examples
    --------
    >>> import eofigs
    >>> eofigs.set_style("elsevier", font="serif")  # doctest: +SKIP
    >>> eofigs.set_style(None)  # restore the previous matplotlib settings
    """
    global _ORIGINAL_RC
    if journal is None:
        if _ORIGINAL_RC is not None:
            mpl.rcParams.update(_ORIGINAL_RC)
        _STATE.clear()
        _STATE.update(_DEFAULT_STATE)
        return
    preset = get_journal(journal)
    if labels is not None and labels not in LABEL_FORMATS:
        raise ValueError(f"labels must be one of {LABEL_FORMATS} or None (got {labels!r}).")
    if _ORIGINAL_RC is None:
        _ORIGINAL_RC = {k: v for k, v in mpl.rcParams.items() if not k.startswith("backend")}

    name, family = _resolve_font(font, preset.font_family)
    size = float(base_size) if base_size is not None else preset.base_font_pt
    small = max(size - 1, preset.min_font_pt)
    weight = "bold" if bold else "normal"

    mpl.rcParams.update(
        {
            "font.family": [name],
            "font.size": size,
            "font.weight": weight,
            "axes.titlesize": size,
            "axes.titleweight": weight,
            "axes.labelsize": size,
            "axes.labelweight": weight,
            "figure.titlesize": size + 1,
            "figure.titleweight": weight,
            "xtick.labelsize": small,
            "ytick.labelsize": small,
            "legend.fontsize": small,
            "legend.title_fontsize": size,
            "legend.frameon": False,
            "mathtext.fontset": "stix" if family == "serif" else "dejavusans",
            "mathtext.default": "regular",
            "axes.unicode_minus": True,
            "axes.prop_cycle": cycler(color=list(OKABE_ITO)),
            "image.cmap": "cmc.batlow",
            "text.color": TEXT_COLOUR,
            "axes.edgecolor": TEXT_COLOUR,
            "axes.labelcolor": TEXT_COLOUR,
            "xtick.color": TEXT_COLOUR,
            "ytick.color": TEXT_COLOUR,
            "axes.linewidth": 0.6,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "xtick.minor.width": 0.4,
            "ytick.minor.width": 0.4,
            "xtick.major.size": 3.0,
            "ytick.major.size": 3.0,
            "lines.linewidth": 1.0,
            "lines.markersize": 4.0,
            "grid.color": GRID_COLOUR,
            "grid.linewidth": 0.5,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.dpi": preset.export_dpi,
            "savefig.bbox": "standard",
            "figure.constrained_layout.use": True,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "svg.hashsalt": "eofigs",
        }
    )
    _STATE.update(
        journal=preset.key, labels=labels, label_bold=label_bold, font=name, font_family=family
    )


@contextmanager
def style(journal: str = "elsevier", **kwargs: Any) -> Iterator[None]:
    """Apply a journal style inside a ``with`` block and restore all settings afterwards.

    Takes the same arguments as :func:`set_style`.

    Examples
    --------
    >>> import eofigs
    >>> with eofigs.style("frontiers", font="DejaVu Sans"):
    ...     fig, ax = eofigs.new_figure("single")
    """
    saved_state = dict(_STATE)
    with mpl.rc_context():
        set_style(journal, **kwargs)
        try:
            yield
        finally:
            _STATE.clear()
            _STATE.update(saved_state)


def current_journal() -> str:
    """Name of the journal preset set by :func:`set_style` (``"custom"`` if none)."""
    return str(_STATE["journal"])


def new_figure(
    width: str | float = "single",
    height_mm: float | None = None,
    aspect: float | None = None,
    nrows: int = 1,
    ncols: int = 1,
    journal: str | None = None,
    **kwargs: Any,
) -> tuple[Figure, Any]:
    """Create a figure with its printed size in millimetres.

    Parameters
    ----------
    width : str or float, default "single"
        A named width of the journal preset (``"single"``, ``"onehalf"``, ``"double"``;
        Springer also ``"small_journal"``) or a width in mm.
    height_mm : float, optional
        Height in mm. If omitted, the height is ``width * aspect``.
    aspect : float, optional
        Height-to-width ratio. Defaults to ``0.75 * nrows / ncols``.
    nrows, ncols : int, default 1
        Panel grid, passed to :func:`matplotlib.pyplot.subplots`.
    journal : str, optional
        Journal preset for the widths; defaults to the one set by :func:`set_style`.
    **kwargs
        Passed to :func:`matplotlib.pyplot.subplots` (for example ``sharex=True`` or
        ``subplot_kw={"projection": crs}``).

    Returns
    -------
    fig : matplotlib.figure.Figure
    axes : Axes or numpy.ndarray of Axes

    Raises
    ------
    ValueError
        If the width is unknown or too wide, or the height exceeds the journal's
        maximum figure height.

    Examples
    --------
    >>> import eofigs
    >>> fig, ax = eofigs.new_figure("single", height_mm=60)
    >>> float(round(fig.get_figwidth() * 25.4, 1))
    90.0
    """
    preset = get_journal(journal or _STATE["journal"])
    width_mm = resolve_width(width, preset)
    if height_mm is None:
        ratio = aspect if aspect is not None else 0.75 * nrows / ncols
        height_mm = width_mm * ratio
    if height_mm <= 0:
        raise ValueError(f"height_mm must be positive (got {height_mm}).")
    if height_mm > preset.max_height_mm + 0.5:
        raise ValueError(
            f"Figure height {height_mm:.1f} mm exceeds {preset.name}'s maximum of "
            f"{preset.max_height_mm:g} mm. Pass a smaller height_mm or aspect, or split the figure."
        )
    kwargs.setdefault("layout", "constrained")
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(width_mm / MM_PER_INCH, height_mm / MM_PER_INCH), **kwargs
    )
    fig._eofigs_journal = preset.key  # type: ignore[attr-defined]
    return fig, axes


def _label_text(index: int, fmt: str) -> str:
    letter = string.ascii_lowercase[index % 26]
    for i, char in enumerate(fmt):
        if char.isalpha():
            new = letter.upper() if char.isupper() else letter
            return fmt[:i] + new + fmt[i + 1 :]
    return fmt  # pragma: no cover (formats are validated)


def label_panels(
    axes: Axes | Sequence[Axes] | np.ndarray,
    labels: str | Sequence[str] | None = None,
    bold: bool | None = None,
    loc: str = "outside",
    fontsize: float | None = None,
) -> list[Text]:
    """Add panel labels such as (a), (b), (c) to axes, in row-major order.

    Parameters
    ----------
    axes : Axes or sequence of Axes
        The panels to label, for example the array returned by :func:`new_figure`.
    labels : str or sequence of str, optional
        A format (``"(a)"``, ``"a"``, ``"(A)"``, ``"A"``, ``"a)"``), an explicit list of
        labels, or ``None`` to use the default from :func:`set_style`. If the default is
        also ``None``, no labels are drawn.
    bold : bool, optional
        Bold labels; defaults to the :func:`set_style` setting.
    loc : {"outside", "inside"}, default "outside"
        Place labels just above the top-left corner of each panel, or inside it.
    fontsize : float, optional
        Label size in points; defaults to the base font size.

    Returns
    -------
    list of matplotlib.text.Text
        The label artists (empty when labelling is switched off).

    Raises
    ------
    ValueError
        For an unknown label format or location, or fewer explicit labels than panels.

    Examples
    --------
    >>> import eofigs
    >>> fig, axes = eofigs.new_figure("double", ncols=2)
    >>> [t.get_text() for t in eofigs.label_panels(axes, "(a)")]
    ['(a)', '(b)']
    """
    flat = list(np.ravel(np.asarray(axes, dtype=object)))
    spec = _STATE["labels"] if labels is None else labels
    if spec is None:
        return []
    if isinstance(spec, str):
        if spec not in LABEL_FORMATS:
            raise ValueError(f"labels must be one of {LABEL_FORMATS} or a list of strings.")
        texts = [_label_text(i, spec) for i in range(len(flat))]
    else:
        texts = list(spec)
        if len(texts) < len(flat):
            raise ValueError(f"{len(flat)} panels but only {len(texts)} labels were given.")
    if loc not in ("outside", "inside"):
        raise ValueError(f"loc must be 'outside' or 'inside' (got {loc!r}).")
    weight = "bold" if (_STATE["label_bold"] if bold is None else bold) else "normal"
    size = fontsize if fontsize is not None else mpl.rcParams["font.size"]
    artists = []
    for ax, text in zip(flat, texts, strict=False):
        if loc == "outside":
            transform = offset_copy(ax.transAxes, fig=ax.figure, x=0, y=2, units="points")
            artist = ax.text(0, 1, text, transform=transform, ha="left", va="bottom")
        else:
            transform = offset_copy(ax.transAxes, fig=ax.figure, x=3, y=-3, units="points")
            artist = ax.text(0, 1, text, transform=transform, ha="left", va="top")
        artist.set_fontweight(weight)
        artist.set_fontsize(size)
        artists.append(artist)
    return artists


def tidy_axes(*items: Any, max_ticks: int = MAX_TICKS) -> None:
    """Limit axes and colour bars to a few ticks at round values.

    Every eofigs recipe calls this; call it on your own plots for the same look. Only
    automatically placed ticks are changed: ticks set explicitly (``ax.set_xticks``),
    log axes and map axes (cartopy GeoAxes, which use graticules) are left as they are.

    Parameters
    ----------
    *items : Axes, Colorbar or sequence of them
        Axes (or an array of axes from :func:`new_figure`) and colour bars.
    max_ticks : int, default 5
        Largest number of tick labels per axis.

    Raises
    ------
    ValueError
        If ``max_ticks`` is smaller than 2.

    Examples
    --------
    >>> import eofigs
    >>> fig, ax = eofigs.new_figure("single")
    >>> _ = ax.plot([0, 0.95], [-3.3, 7.1])
    >>> eofigs.tidy_axes(ax)
    >>> len(ax.get_yticks()) <= 5
    True
    """
    from matplotlib.colorbar import Colorbar

    if max_ticks < 2:
        raise ValueError(f"max_ticks must be at least 2 (got {max_ticks}).")
    for item in items:
        if isinstance(item, Colorbar):
            if _is_auto_locator(item.locator):
                item.locator = _round_locator(max_ticks)
                item.update_ticks()
        elif isinstance(item, Axes):
            if _is_map_axes(item):
                continue
            for axis in (item.xaxis, item.yaxis):
                _tidy_axis(axis, max_ticks)
        else:
            tidy_axes(*np.ravel(np.asarray(item, dtype=object)), max_ticks=max_ticks)


def _round_locator(max_ticks: int):
    from matplotlib.ticker import MaxNLocator

    return MaxNLocator(nbins=max_ticks - 1, steps=list(TICK_STEPS), min_n_ticks=2)


def _is_auto_locator(locator) -> bool:
    from matplotlib.ticker import AutoLocator, MaxNLocator

    return type(locator) in (AutoLocator, MaxNLocator)


def _is_map_axes(ax: Axes) -> bool:
    return type(ax).__name__ == "GeoAxes" or hasattr(ax, "projection")


def _tidy_axis(axis, max_ticks: int) -> None:
    import matplotlib.dates as mdates

    if axis.get_scale() != "linear":
        return
    locator = axis.get_major_locator()
    if isinstance(locator, mdates.AutoDateLocator):
        new = mdates.AutoDateLocator(maxticks=max_ticks, minticks=2)
        axis.set_major_locator(new)
        if isinstance(axis.get_major_formatter(), mdates.AutoDateFormatter):
            axis.set_major_formatter(mdates.ConciseDateFormatter(new))
    elif _is_auto_locator(locator):
        axis.set_major_locator(_round_locator(max_ticks))
