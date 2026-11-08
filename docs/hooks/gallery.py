"""MkDocs hook that builds the example gallery from examples/*.py.

Each example is a script whose module docstring holds the title (first line) and the
caption (the rest), and which leaves the finished figure in a variable named ``fig`` (or
several, shown side by side, in a dict ``figures = {label: fig}``).
During the docs build every example is run; for each one the hook adds to the site:

- ``gallery/<slug>.md``: figure, caption, downloads, the check report and the code;
- ``gallery/images/<slug>.png`` (web), ``gallery/thumbs/<slug>.png`` (card thumbnail);
- ``gallery/files/<slug>.py``, ``.pdf`` and ``_600dpi.png`` (downloads).

``gallery/index.md`` and the marker ``<!-- gallery-grid -->`` on the home page get a grid
of cards. An example that raises stops the build. The README must show every example's
thumbnail (checked here, so a missing entry fails ``mkdocs build --strict``).
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
        "code, the caption with the data sources, and downloads of the PDF and a 600 dpi PNG.\n\n"
        + _cards(examples, "")
    )


def _check_readme(examples: list[Example]) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for ex in examples:
        thumb = f"{SITE_URL}/gallery/thumbs/{ex.slug}.png"
        if thumb not in readme:
            log.warning("README.md has no gallery thumbnail for %r (%s).", ex.slug, thumb)


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
