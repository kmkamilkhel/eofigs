"""Manuscript figure sets: Fig/FigS numbering, export and a manifest."""

from __future__ import annotations

import csv
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from matplotlib.figure import Figure

from eofigs._presets import MM_PER_INCH, check_art, get_journal
from eofigs.export import save_figure
from eofigs.styling import current_journal

MANIFEST = "figures_manifest.csv"
COLUMNS = (
    "label",
    "name",
    "supplementary",
    "files",
    "width_mm",
    "height_mm",
    "dpi",
    "art",
    "check",
    "problems",
    "caption",
)
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class FigureSet:
    """The figures of one manuscript, numbered and saved in one folder.

    Create it with :func:`figure_set`. Main figures are saved as ``Fig01_<name>`` and
    supplementary figures as ``FigS01_<name>``, numbered in the order they are added
    (change it with :meth:`order`). Every change rewrites ``figures_manifest.csv``, so
    reopening the folder in a new session continues where the last one stopped.
    """

    def __init__(
        self,
        folder: str | Path,
        journal: str | None = None,
        formats: Sequence[str] | None = None,
        dpi: float | None = None,
        art: str = "combination",
    ) -> None:
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.journal = get_journal(journal or current_journal()).key
        self.formats = tuple(formats) if formats is not None else None
        self.dpi = dpi
        self.art = check_art(art)
        self._entries: list[dict[str, Any]] = self._read_manifest()

    # ------------------------------------------------------------------ public

    def add(
        self,
        name: str,
        fig: Figure,
        supplementary: bool = False,
        caption: str = "",
        art: str | None = None,
        check: bool = True,
    ) -> list[Path]:
        """Save a figure into the set and record it in the manifest.

        Adding a name that is already in the set replaces that figure (its number stays
        the same unless it moves between main and supplementary).

        Parameters
        ----------
        name : str
            Short name used in the file names: letters, digits, ``_`` and ``-``.
        fig : matplotlib.figure.Figure
            The figure to save.
        supplementary : bool, default False
            Number it as a supplementary figure (``FigS01``).
        caption : str, default ""
            Caption kept in the manifest.
        art : {"combination", "line", "halftone"}, optional
            Artwork type for this figure; defaults to the set's ``art``.
        check : bool, default True
            Run the figure check and record the result in the manifest.

        Returns
        -------
        list of pathlib.Path
            The files written.

        Raises
        ------
        ValueError
            For an invalid name.
        """
        if not _NAME.match(name):
            raise ValueError(
                f"Invalid figure name {name!r}: use letters, digits, '_' and '-', "
                "starting with a letter or digit."
            )
        existing = self._find(name)
        if existing is not None:
            self._delete_files(existing)
            if existing["supplementary"] != supplementary:
                self._entries.remove(existing)
                existing = None
        entry = existing or {"name": name, "supplementary": supplementary, "files": []}
        if existing is None:
            self._entries.append(entry)
        self._renumber()

        art = check_art(art or self.art)
        report = save_figure(
            fig,
            self.folder / self._stem(entry),
            formats=self.formats,
            dpi=self.dpi,
            check=check,
            journal=self.journal,
            art=art,
        )
        written = sorted(self.folder.glob(f"{self._stem(entry)}.*"))
        problems = [] if report is None else report.failures + report.warnings
        entry.update(
            label=self._label(entry),
            files=[p.name for p in written],
            width_mm=round(fig.get_figwidth() * MM_PER_INCH, 1),
            height_mm=round(fig.get_figheight() * MM_PER_INCH, 1),
            dpi=self.dpi or get_journal(self.journal).export_dpi_for(art),
            art=art,
            check="not run" if report is None else ("passed" if report.passed else "failed"),
            problems="; ".join(f"{r.status}: {r.name} [{r.target}]: {r.message}" for r in problems),
            caption=caption,
        )
        self._write_manifest()
        return [self.folder / f for f in entry["files"]]

    def order(self, names: Sequence[str], supplementary: bool = False) -> None:
        """Set the order of the main (or supplementary) figures and rename their files.

        Parameters
        ----------
        names : sequence of str
            All names of that group, in the new order.
        supplementary : bool, default False
            Reorder the supplementary figures instead of the main ones.

        Raises
        ------
        ValueError
            If ``names`` are not exactly the figures of that group.
        """
        group = [e for e in self._entries if e["supplementary"] == supplementary]
        if sorted(names) != sorted(e["name"] for e in group) or len(set(names)) != len(names):
            kind = "supplementary" if supplementary else "main"
            raise ValueError(
                f"order() needs every {kind} figure exactly once: {[e['name'] for e in group]}."
            )
        by_name = {e["name"]: e for e in group}
        others = [e for e in self._entries if e["supplementary"] != supplementary]
        self._entries = [by_name[n] for n in names] + others
        self._renumber()
        self._write_manifest()

    def exists(self, name: str) -> bool:
        """Check whether the figure is in the set and all its files are on disk.

        Use it to skip rebuilding expensive figures when a notebook is run again.
        """
        entry = self._find(name)
        return bool(entry and entry["files"]) and all(
            (self.folder / f).exists() for f in entry["files"]
        )

    @property
    def entries(self) -> list[dict[str, Any]]:
        """Manifest rows: main figures first, then supplementary figures."""
        return [dict(e) for e in self._ordered()]

    @property
    def manifest_path(self) -> Path:
        """Path of ``figures_manifest.csv``."""
        return self.folder / MANIFEST

    def __len__(self) -> int:
        """Return the number of figures in the set."""
        return len(self._entries)

    def __repr__(self) -> str:
        """Short description."""
        main = sum(not e["supplementary"] for e in self._entries)
        return (
            f"FigureSet({str(self.folder)!r}, journal={self.journal!r}, "
            f"{main} main, {len(self) - main} supplementary)"
        )

    # ------------------------------------------------------------------ internals

    def _find(self, name: str) -> dict[str, Any] | None:
        return next((e for e in self._entries if e["name"] == name), None)

    def _ordered(self) -> list[dict[str, Any]]:
        return [e for e in self._entries if not e["supplementary"]] + [
            e for e in self._entries if e["supplementary"]
        ]

    def _number(self, entry: dict[str, Any]) -> int:
        group = [e for e in self._entries if e["supplementary"] == entry["supplementary"]]
        return group.index(entry) + 1

    def _stem(self, entry: dict[str, Any]) -> str:
        prefix = "FigS" if entry["supplementary"] else "Fig"
        return f"{prefix}{self._number(entry):02d}_{entry['name']}"

    def _label(self, entry: dict[str, Any]) -> str:
        return f"Fig. {'S' if entry['supplementary'] else ''}{self._number(entry)}"

    def _delete_files(self, entry: dict[str, Any]) -> None:
        for name in entry.get("files", []):
            (self.folder / name).unlink(missing_ok=True)
        entry["files"] = []

    def _renumber(self) -> None:
        """Rename files whose number changed, in two steps so names never collide."""
        moves = []
        for entry in self._entries:
            stem = self._stem(entry)
            new_files = []
            for name in entry.get("files", []):
                suffix = name[name.index(".") :]
                target = f"{stem}{suffix}"
                if target != name:
                    moves.append((self.folder / name, self.folder / target))
                new_files.append(target)
            entry["files"] = new_files
            entry["label"] = self._label(entry)
        staged = []
        for i, (src, dst) in enumerate(moves):
            if src.exists():
                tmp = src.with_name(f".eofigs_tmp_{i}{dst.suffix}")
                src.rename(tmp)
                staged.append((tmp, dst))
        for tmp, dst in staged:
            tmp.replace(dst)

    def _write_manifest(self) -> None:
        with self.manifest_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMNS)
            writer.writeheader()
            for entry in self._ordered():
                row = {key: entry.get(key, "") for key in COLUMNS}
                row["supplementary"] = "yes" if entry["supplementary"] else "no"
                row["files"] = ";".join(entry.get("files", []))
                writer.writerow(row)

    def _read_manifest(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        with self.manifest_path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        entries = []
        for row in rows:
            entry: dict[str, Any] = dict(row)
            entry["supplementary"] = row["supplementary"] == "yes"
            entry["files"] = [f for f in row["files"].split(";") if f]
            entries.append(entry)
        return entries


def figure_set(
    folder: str | Path,
    journal: str | None = None,
    formats: Sequence[str] | None = None,
    dpi: float | None = None,
    art: str = "combination",
) -> FigureSet:
    """Open (or start) the figure set of a manuscript in a folder.

    Parameters
    ----------
    folder : str or pathlib.Path
        Output folder; created if needed. An existing ``figures_manifest.csv`` is read,
        so numbering continues across sessions.
    journal : str, optional
        Journal preset for formats, resolution and checks; defaults to the one set by
        :func:`eofigs.set_style`.
    formats : sequence of str, optional
        Output formats; default from the journal preset (for example PDF + TIFF).
    dpi : float, optional
        Raster resolution; default from the journal preset and artwork type.
    art : {"combination", "line", "halftone"}, default "combination"
        Default artwork type of the figures.

    Returns
    -------
    FigureSet

    Examples
    --------
    >>> import tempfile, eofigs
    >>> folder = tempfile.mkdtemp()
    >>> figs = eofigs.figure_set(folder, journal="custom", formats=("png",), dpi=100)
    >>> fig, ax = eofigs.new_figure("single", journal="custom")
    >>> [p.name for p in figs.add("study_area", fig, caption="Study area.")]
    ['Fig01_study_area.png']
    >>> [p.name for p in figs.add("accuracy", fig, supplementary=True)]
    ['FigS01_accuracy.png']
    """
    return FigureSet(folder, journal=journal, formats=formats, dpi=dpi, art=art)
