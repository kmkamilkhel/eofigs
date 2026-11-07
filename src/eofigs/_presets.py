"""Journal presets loaded from the bundled ``data/journals.json``."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

MM_PER_INCH = 25.4


@dataclass(frozen=True)
class Journal:
    """Figure requirements of one publisher, read from ``journals.json``."""

    key: str
    name: str
    widths_mm: dict[str, float]
    max_height_mm: float
    min_font_pt: float
    base_font_pt: float
    font_family: str
    fonts: tuple[str, ...]
    dpi: dict[str, int]
    export_dpi: int
    formats: tuple[str, ...]
    source_url: str
    checked: str
    eofigs_defaults: tuple[str, ...]
    notes: str

    @property
    def max_width_mm(self) -> float:
        """Largest named width (full page or text width)."""
        return max(self.widths_mm.values())

    def required_dpi(self, art: str = "combination") -> int:
        """Resolution the publisher asks for one artwork type.

        Parameters
        ----------
        art : {"combination", "line", "halftone"}
            ``"line"`` for line art (plots and drawings), ``"halftone"`` for photographs
            and continuous-tone images, ``"combination"`` for figures that mix both.
        """
        return int(self.dpi[check_art(art)])

    def export_dpi_for(self, art: str = "combination") -> int:
        """Default raster resolution: the export resolution or the requirement, if higher."""
        return max(self.export_dpi, self.required_dpi(art))


@lru_cache(maxsize=1)
def _load() -> dict:
    text = resources.files("eofigs").joinpath("data/journals.json").read_text(encoding="utf-8")
    return json.loads(text)


ART_TYPES = ("combination", "line", "halftone")


def check_art(art: str) -> str:
    """Validate an artwork type name.

    Raises
    ------
    ValueError
        If ``art`` is not ``"combination"``, ``"line"`` or ``"halftone"``.
    """
    if art not in ART_TYPES:
        raise ValueError(f"art must be one of {ART_TYPES} (got {art!r}).")
    return art


def journal_keys() -> list[str]:
    """Names of all bundled journal presets."""
    return sorted(_load()["journals"])


def get_journal(name: str | Journal) -> Journal:
    """Return the preset for ``name`` (case-insensitive; aliases such as ``"tandf"`` accepted).

    Raises
    ------
    ValueError
        If no preset has that name. The message lists the available presets.
    """
    if isinstance(name, Journal):
        return name
    data = _load()
    key = str(name).strip().lower()
    key = data["aliases"].get(key, key)
    if key not in data["journals"]:
        raise ValueError(
            f"Unknown journal {name!r}. Available presets: {', '.join(journal_keys())}. "
            "Use 'custom' for a generic preset."
        )
    entry = data["journals"][key]
    return Journal(
        key=key,
        name=entry["name"],
        widths_mm={k: float(v) for k, v in entry["widths_mm"].items()},
        max_height_mm=float(entry["max_height_mm"]),
        min_font_pt=float(entry["min_font_pt"]),
        base_font_pt=float(entry["base_font_pt"]),
        font_family=entry["font_family"],
        fonts=tuple(entry["fonts"]),
        dpi={k: int(v) for k, v in entry["dpi"].items()},
        export_dpi=int(entry["export_dpi"]),
        formats=tuple(entry["formats"]),
        source_url=entry["source_url"],
        checked=entry["checked"],
        eofigs_defaults=tuple(entry["eofigs_defaults"]),
        notes=entry["notes"],
    )


def resolve_width(width: str | float, journal: Journal) -> float:
    """Convert a named width (``"single"``, ``"double"``, ...) or a number in mm to mm.

    Raises
    ------
    ValueError
        For an unknown width name, a non-positive width, or a width larger than the
        journal's full text width.
    """
    if isinstance(width, str):
        if width not in journal.widths_mm:
            raise ValueError(
                f"Unknown width {width!r} for {journal.name}. "
                f"Use one of {sorted(journal.widths_mm)} or a number in mm."
            )
        return journal.widths_mm[width]
    width_mm = float(width)
    if width_mm <= 0:
        raise ValueError(f"width must be positive (got {width_mm} mm).")
    if width_mm > journal.max_width_mm + 0.5:
        raise ValueError(
            f"width {width_mm:g} mm is wider than {journal.name}'s full width "
            f"({journal.max_width_mm:g} mm). Use width='{_widest(journal)}' or a smaller number."
        )
    return width_mm


def _widest(journal: Journal) -> str:
    return max(journal.widths_mm, key=journal.widths_mm.get)
