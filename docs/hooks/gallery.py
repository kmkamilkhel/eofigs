"""MkDocs hook that builds the example gallery from examples/*.py.

Each example is a script whose module docstring holds the title (first line) and the
caption (the rest), and which leaves the finished figure in a variable named ``fig`` (or
several, shown side by side, in a dict ``figures = {label: fig}``).
During the docs build every example is run; for each one the hook adds to the site:

- ``gallery/<slug>.md``: figure, caption, downloads, the check report and the code;
- ``gallery/images/<slug>.png`` (web), ``gallery/thumbs/<slug>.png`` (card thumbnail);
- ``gallery/files/<slug>.py``, ``.pdf`` and ``_600dpi.png`` (downloads).

``gallery/index.md`` and the marker ``<!-- gallery-grid -->`` on the home page get a grid
of cards. An example that raises stops the build.

The README opens with a grid of the examples in ``README_CARDS``. For each, the build writes
``gallery/cards/<slug>.png``: a 4:3 card cropped to the figure's most telling part. The README
must show and link every card, and every docs-site image it uses must be one the build makes
(checked here, so a missing or stale entry fails ``mkdocs build --strict``).
"""

from __future__ import annotations

import ast
import io
import logging
import re
import runpy
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib as mpl  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from mkdocs.exceptions import PluginError  # noqa: E402
from mkdocs.structure.files import File, Files  # noqa: E402

log = logging.getLogger("mkdocs.hooks.gallery")

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
SITE_URL = "https://kmkamilkhel.github.io/eofigs"
GRID_MARKER = "<!-- gallery-grid -->"
WEB_DPI = 200
THUMB_SIZE = (480, 360)
#: README card size (4:3).
CARD_SIZE = (800, 600)
#: README grid, row by row: example slug, figure (1-based, for examples with several), the
#: crop as fractions of the figure (left, top, right, bottom), how a crop that is not 4:3 is
#: made 4:3 ("figure": take more of the figure, then white; "white": add white), and the
#: tile title.
README_CARDS = (
    ("study_area_swat", 1, (0.075, 0.0, 1.0, 0.52), "figure", "Study area map"),
    ("trend_map_swat", 1, (0.19, 0.436, 0.80, 0.792), "figure", "Trend map"),
    ("event_composite_swat", 1, (0.08, 0.0, 0.96, 0.66), "figure", "Event composite"),
    ("accuracy_scatter_icesat2", 1, (0.555, 0.0, 1.0, 1.0), "white", "DEM accuracy (ICESat-2)"),
    ("fdr_synthetic", 1, (0.33, 0.0, 1.0, 0.92), "figure", "False discovery rate"),
    ("house_style", 2, (0.0, 0.0, 1.0, 0.75), "figure", "House style"),
)
_FONT_WARNING = r"Font .* is not installed"


@dataclass
class Panel:
    """One figure of a gallery entry."""

    label: str
    name: str
    report: str
    status: str


@dataclass
class Example:
    """One built gallery entry."""

    slug: str
    title: str
    caption: str
    code: str
    files: dict[str, bytes]
    panels: list[Panel]


_CACHE: dict[tuple[str, int], Example] = {}


def _slug(path: Path) -> str:
    return re.sub(r"^\d+_", "", path.stem)


def _split_docstring(source: str) -> tuple[str, str, str]:
    module = ast.parse(source)
    doc = ast.get_docstring(module, clean=True)
    if not doc:
        raise PluginError("Gallery examples need a module docstring (title, blank line, caption).")
    title, _, caption = doc.partition("\n")
    body = module.body[0]
    lines = source.splitlines()
    code = "\n".join(lines[body.end_lineno :]).strip("\n")
    return title.strip().rstrip("."), " ".join(caption.split()), code


def _figures(namespace: dict, path: Path) -> list[tuple[str, matplotlib.figure.Figure]]:
    """Return the example's figure (``fig``) or labelled figures (``figures``)."""
    figures = namespace.get("figures")
    if figures is None:
        fig = namespace.get("fig")
        if not isinstance(fig, matplotlib.figure.Figure):
            raise PluginError(
                f"{path.name} must leave its figure in a variable named fig "
                "(or several in a dict named figures)."
            )
        return [("", fig)]
    return list(figures.items())


def _thumbnail(images: list[bytes]) -> bytes:
    from PIL import Image

    card = Image.new("RGB", THUMB_SIZE, "white")
    slot_w = THUMB_SIZE[0] // len(images)
    for i, data in enumerate(images):
        with Image.open(io.BytesIO(data)) as image:
            image = image.convert("RGB")
            image.thumbnail((slot_w - 6, THUMB_SIZE[1]))
            card.paste(image, (i * slot_w + (slot_w - image.width) // 2,
                               (THUMB_SIZE[1] - image.height) // 2))  # fmt: skip
    out = io.BytesIO()
    card.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _card(png: bytes, box: tuple[float, float, float, float], fill: str = "figure") -> bytes:
    """Crop a figure to ``box`` (fractions), made 4:3 (see README_CARDS), as a CARD_SIZE PNG."""
    from PIL import Image

    with Image.open(io.BytesIO(png)) as image:
        image = image.convert("RGB")
        w, h = image.size
        x0, y0, x1, y1 = box[0] * w, box[1] * h, box[2] * w, box[3] * h
        aspect = CARD_SIZE[0] / CARD_SIZE[1]
        if (x1 - x0) / (y1 - y0) > aspect:  # too wide: take more height
            grow = (x1 - x0) / aspect - (y1 - y0)
            y0, y1 = y0 - grow / 2, y1 + grow / 2
            if fill == "figure":
                shift = max(0.0, -y0) - max(0.0, y1 - h)
                y0, y1 = y0 + shift, y1 + shift
        else:  # too tall: take more width
            grow = (y1 - y0) * aspect - (x1 - x0)
            x0, x1 = x0 - grow / 2, x1 + grow / 2
            if fill == "figure":
                shift = max(0.0, -x0) - max(0.0, x1 - w)
                x0, x1 = x0 + shift, x1 + shift
        canvas = Image.new("RGB", (round(x1 - x0), round(y1 - y0)), "white")
        bx0, by0, bx1, by1 = box[0] * w, box[1] * h, box[2] * w, box[3] * h
        if fill == "white":  # only the box itself, the rest white
            inner = (round(bx0), round(by0), round(bx1), round(by1))
        else:
            inner = (max(0, round(x0)), max(0, round(y0)), min(w, round(x1)), min(h, round(y1)))
        canvas.paste(image.crop(inner), (inner[0] - round(x0), inner[1] - round(y0)))
        canvas = canvas.resize(CARD_SIZE, Image.Resampling.LANCZOS)
    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _readme_cards(examples: list[Example]) -> dict[str, bytes]:
    """Make the README cards, keyed by file name under gallery/."""
    by_slug = {ex.slug: ex for ex in examples}
    cards = {}
    for slug, figure, box, fill, _ in README_CARDS:
        if slug not in by_slug:
            raise PluginError(f"README_CARDS names {slug!r}, which is not a gallery example.")
        ex = by_slug[slug]
        name = slug if len(ex.panels) == 1 else f"{slug}_{figure}"
        cards[f"cards/{slug}.png"] = _card(ex.files[f"files/{name}_600dpi.png"], box, fill)
    return cards


def _run(path: Path) -> Example:
    key = (str(path), path.stat().st_mtime_ns)
    if key in _CACHE:
        return _CACHE[key]
    import eofigs
    from eofigs import styling

    source = path.read_text(encoding="utf-8")
    title, caption, code = _split_docstring(source)
    slug = _slug(path)
    saved_state = dict(styling._STATE)
    files: dict[str, bytes] = {f"files/{slug}.py": source.encode("utf-8")}
    panels: list[Panel] = []
    web_images: list[bytes] = []
    try:
        with mpl.rc_context(), warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=_FONT_WARNING, category=UserWarning)
            namespace = runpy.run_path(str(path), run_name="__gallery__")
            figures = _figures(namespace, path)
            for i, (label, fig) in enumerate(figures, 1):
                name = slug if len(figures) == 1 else f"{slug}_{i}"
                with tempfile.TemporaryDirectory() as tmp:
                    eofigs.save_figure(fig, Path(tmp) / name, formats=("pdf", "png"), check=False)
                    files[f"files/{name}.pdf"] = (Path(tmp) / f"{name}.pdf").read_bytes()
                    files[f"files/{name}_600dpi.png"] = (Path(tmp) / f"{name}.png").read_bytes()
                web = io.BytesIO()
                fig.savefig(web, format="png", dpi=WEB_DPI)
                files[f"images/{name}.png"] = web.getvalue()
                web_images.append(web.getvalue())
                checked = eofigs.check_figure(fig)
                status = "success"
                if not checked.passed:
                    status = "failure"
                elif checked.warnings:
                    status = "warning"
                panels.append(Panel(label, name, str(checked), status))
            files[f"thumbs/{slug}.png"] = _thumbnail(web_images)
    except PluginError:
        raise
    except Exception as exc:  # a broken example fails the build
        raise PluginError(f"Gallery example {path.name} failed: {exc!r}") from exc
    finally:
        plt.close("all")
        styling._STATE.clear()
        styling._STATE.update(saved_state)
    example = Example(slug, title, caption, code, files, panels)
    _CACHE[key] = example
    return example


def _examples() -> list[Example]:
    return [_run(path) for path in sorted(EXAMPLES.glob("[0-9]*.py"))]


def _cards(examples: list[Example], prefix: str) -> str:
    items = []
    for ex in examples:
        items.append(
            f"-   [![{ex.title}]({prefix}thumbs/{ex.slug}.png)]({prefix}{ex.slug}.md)\n\n"
            f"    **[{ex.title}]({prefix}{ex.slug}.md)**"
        )
    return '<div class="grid cards" markdown>\n\n' + "\n\n".join(items) + "\n\n</div>\n"


def _downloads(name: str, label: str) -> str:
    suffix = f" ({label})" if label else ""
    return (
        f"[:material-download: PDF{suffix}](files/{name}.pdf){{ .md-button }}\n"
        f"[:material-download: PNG, 600 dpi{suffix}](files/{name}_600dpi.png){{ .md-button }}\n"
    )


def _page(ex: Example) -> str:
    if len(ex.panels) == 1:
        figures = f"![{ex.title}](images/{ex.panels[0].name}.png)\n"
    else:
        cells = "\n\n".join(
            f"-   **{p.label}**\n\n    ![{p.label}](images/{p.name}.png)" for p in ex.panels
        )
        figures = f'<div class="grid" markdown>\n\n{cells}\n\n</div>\n'
    downloads = "".join(_downloads(p.name, p.label) for p in ex.panels)
    checks = "\n".join(
        f'??? {p.status} "Figure check{f" ({p.label})" if p.label else ""}"\n\n'
        f"    ```text\n{_indent(p.report, 4)}\n    ```\n"
        for p in ex.panels
    )
    return f"""# {ex.title}

{figures}
{ex.caption}

[:material-download: Script](files/{ex.slug}.py){{ .md-button }}
{downloads}
```python
{ex.code}
```

{checks}"""


def _indent(text: str, n: int) -> str:
    return "\n".join(" " * n + line for line in text.splitlines())


def _index(examples: list[Example]) -> str:
    return (
        "# Gallery\n\nEvery figure below is built from a script in the "
        "[examples folder](https://github.com/kmkamilkhel/eofigs/tree/main/examples) "
        "when this site is built, and checked with `eofigs.check_figure`. Each page has the "
        "code, the caption with the data sources, and downloads of the PDF and a 600 dpi PNG. "
        "For a real accuracy assessment, see "
        "[Accuracy scatter: ICESat-2 against a DEM](accuracy_scatter_icesat2.md): 25 000 "
        "ICESat-2 terrain heights against the Copernicus DEM in the Swat valley, with the "
        "error by slope class.\n\n" + _cards(examples, "")
    )


def _check_readme(examples: list[Example], cards: dict[str, bytes]) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for slug, _, _, _, title in README_CARDS:
        image = f"{SITE_URL}/gallery/cards/{slug}.png"
        page = f"{SITE_URL}/gallery/{slug}/"
        if image not in readme or page not in readme:
            log.warning("README.md is missing the %r card (%s linking to %s).", title, image, page)
    made = {f"{SITE_URL}/gallery/{name}" for ex in examples for name in ex.files}
    made |= {f"{SITE_URL}/gallery/{name}" for name in cards}
    for url in re.findall(re.escape(SITE_URL) + r"/gallery/[^\s\"')<>]+\.png", readme):
        if url not in made:
            log.warning("README.md shows %s, which the docs build does not make.", url)


def on_files(files: Files, config) -> Files:
    """Run the examples and add the gallery pages, images and downloads."""
    examples = _examples()
    cards = _readme_cards(examples)
    _check_readme(examples, cards)
    files.append(File.generated(config, "gallery/index.md", content=_index(examples)))
    for name, data in cards.items():
        files.append(File.generated(config, f"gallery/{name}", content=data))
    for ex in examples:
        files.append(File.generated(config, f"gallery/{ex.slug}.md", content=_page(ex)))
        for name, data in ex.files.items():
            files.append(File.generated(config, f"gallery/{name}", content=data))
    return files


def on_page_markdown(markdown: str, page, config, files) -> str:
    """Put the gallery grid on the home page."""
    if GRID_MARKER in markdown:
        return markdown.replace(GRID_MARKER, _cards(_examples(), "gallery/"))
    return markdown
