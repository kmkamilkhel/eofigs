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

The README opens with a grid of the examples in ``README_CARDS``. Each of these examples
names, in a list ``readme_card``, the parts of its figure the card shows: artists (axes,
colour-bar axes, legends; their tight bounding box) or ``(artist, (x0, y0, x1, y1))`` for a
part of an axes frame (fractions, y upwards). A list of dicts ``{"items": [...], "label":
...}`` makes a card of several crops side by side, each labelled. The build renders that
region of the figure, made 4:3 (``gallery/cards/<slug>.png``), so a layout change in an
example moves the crop with it. The README must show and link every card, and every docs-site
image it uses must be one the build makes (checked here, so a missing or stale entry fails
``mkdocs build --strict``).
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
#: README card size (4:3), margin around the named parts (mm), gutter and label band (px).
CARD_SIZE = (800, 600)
CARD_MARGIN_MM = 0.5
CARD_GUTTER = 16
CARD_LABEL_H = 44
#: README grid, row by row: example slug, how a region that is not 4:3 is made 4:3
#: ("figure": take more of the figure, then white; "white": add white), whether panel letters
#: stay on the card, and the tile title. The parts shown are set in each example (readme_card).
README_CARDS = (
    ("study_area_swat", "white", False, "Study area map"),
    ("trend_map_swat", "figure", False, "Trend map"),
    ("event_composite_swat", "figure", False, "Event composite"),
    ("accuracy_scatter_icesat2", "white", False, "DEM accuracy (ICESat-2)"),
    ("fdr_synthetic", "figure", False, "False discovery rate"),
    ("house_style", "white", True, "House style"),  # the bold letters are part of the style
)
PANEL_LABEL_GID = "eofigs-panel-label"
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


def _region(fig, items) -> tuple[float, float, float, float]:
    """Union of the named parts, in inches from the figure's lower left (with a margin)."""
    from matplotlib.transforms import Bbox

    renderer = fig.canvas.get_renderer()
    boxes = []
    for item in items:
        if isinstance(item, tuple):
            artist, (fx0, fy0, fx1, fy1) = item
            b = artist.get_window_extent(renderer)
            x0, x1 = b.x0 + fx0 * b.width, b.x0 + fx1 * b.width
            y0, y1 = b.y0 + fy0 * b.height, b.y0 + fy1 * b.height
            boxes.append(Bbox.from_extents(x0, y0, x1, y1))
        else:
            boxes.append(item.get_tightbbox(renderer))
    union = Bbox.union(boxes)
    margin = CARD_MARGIN_MM / 25.4
    return (union.x0 / fig.dpi - margin, union.y0 / fig.dpi - margin,
            union.x1 / fig.dpi + margin, union.y1 / fig.dpi + margin)  # fmt: skip


def _render(fig, region, size, fill):
    """Render ``region`` (inches) of ``fig`` at the aspect of ``size``, as a PIL image.

    ``fill="figure"`` widens the region within the figure; ``fill="white"`` renders only the
    region and centres it on white.
    """
    from matplotlib.transforms import Bbox
    from PIL import Image

    x0, y0, x1, y1 = region
    fig_w, fig_h = fig.get_size_inches()
    aspect = size[0] / size[1]
    if fill == "figure":
        if (x1 - x0) / (y1 - y0) > aspect:  # too wide: more height
            grow = (x1 - x0) / aspect - (y1 - y0)
            y0, y1 = y0 - grow / 2, y1 + grow / 2
            shift = max(0.0, -y0) - max(0.0, y1 - fig_h)
            y0, y1 = y0 + shift, y1 + shift
        else:  # too tall: more width
            grow = (y1 - y0) * aspect - (x1 - x0)
            x0, x1 = x0 - grow / 2, x1 + grow / 2
            shift = max(0.0, -x0) - max(0.0, x1 - fig_w)
            x0, x1 = x0 + shift, x1 + shift
    scale = min(size[0] / (x1 - x0), size[1] / (y1 - y0))  # pixels per inch on the card
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=2 * scale, facecolor="white",
                bbox_inches=Bbox.from_extents(x0, y0, x1, y1))  # fmt: skip
    with Image.open(buf) as image:
        part = image.convert("RGB").resize(
            (min(size[0], round((x1 - x0) * scale)), min(size[1], round((y1 - y0) * scale))),
            Image.Resampling.LANCZOS,
        )
    slot = Image.new("RGB", size, "white")
    slot.paste(part, ((size[0] - part.width) // 2, (size[1] - part.height) // 2))
    return slot


def _card(spec, fill: str, keep_letters: bool) -> bytes:
    """Render an example's ``readme_card`` as a CARD_SIZE PNG."""
    from matplotlib import font_manager
    from matplotlib.text import Text
    from PIL import Image, ImageDraw, ImageFont

    groups = spec if spec and isinstance(spec[0], dict) else [{"items": spec, "label": None}]
    first = groups[0]["items"][0]
    fig = (first[0] if isinstance(first, tuple) else first).get_figure(root=True)
    hidden = []
    if not keep_letters:
        for text in fig.findobj(lambda a: isinstance(a, Text) and a.get_gid() == PANEL_LABEL_GID):
            if text.get_visible():
                text.set_visible(False)
                hidden.append(text)
    try:
        fig.canvas.draw()
        card = Image.new("RGB", CARD_SIZE, "white")
        n = len(groups)
        labelled = any(g.get("label") for g in groups)
        slot = ((CARD_SIZE[0] - CARD_GUTTER * (n - 1)) // n,
                CARD_SIZE[1] - (CARD_LABEL_H if labelled else 0))  # fmt: skip
        font_path = font_manager.findfont(font_manager.FontProperties(weight="bold"))
        font = ImageFont.truetype(font_path, 26)
        draw = ImageDraw.Draw(card)
        for i, group in enumerate(groups):
            x = i * (slot[0] + CARD_GUTTER)
            card.paste(_render(fig, _region(fig, group["items"]), slot, fill), (x, 0))
            if group.get("label"):
                width = draw.textlength(group["label"], font=font)
                draw.text((x + (slot[0] - width) / 2, slot[1] + 8), group["label"], font=font,
                          fill=(31, 35, 40))  # fmt: skip
    finally:
        for text in hidden:
            text.set_visible(True)
    out = io.BytesIO()
    card.save(out, format="PNG", optimize=True)
    return out.getvalue()


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
            for card_slug, fill, keep_letters, _ in README_CARDS:
                if card_slug == slug:
                    if "readme_card" not in namespace:
                        raise PluginError(f"{path.name} is a README card; it needs readme_card.")
                    files[f"cards/{slug}.png"] = _card(namespace["readme_card"], fill,
                                                       keep_letters)  # fmt: skip
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


def _check_readme(examples: list[Example]) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    slugs = {ex.slug for ex in examples}
    for slug, _, _, title in README_CARDS:
        if slug not in slugs:
            log.warning("README_CARDS names %r, which is not a gallery example.", slug)
        image = f"{SITE_URL}/gallery/cards/{slug}.png"
        page = f"{SITE_URL}/gallery/{slug}/"
        if image not in readme or page not in readme:
            log.warning("README.md is missing the %r card (%s linking to %s).", title, image, page)
    made = {f"{SITE_URL}/gallery/{name}" for ex in examples for name in ex.files}
    for url in re.findall(re.escape(SITE_URL) + r"/gallery/[^\s\"')<>]+\.png", readme):
        if url not in made:
            log.warning("README.md shows %s, which the docs build does not make.", url)


def on_files(files: Files, config) -> Files:
    """Run the examples and add the gallery pages, images and downloads."""
    examples = _examples()
    _check_readme(examples)
    files.append(File.generated(config, "gallery/index.md", content=_index(examples)))
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
