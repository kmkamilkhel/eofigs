"""MkDocs hook that builds the example gallery from examples/*.py.

Each example is a script whose module docstring holds the title (first line) and the
caption (the rest), and which leaves the finished figure in a variable named ``fig``.
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
class Example:
    """One built gallery entry."""

    slug: str
    title: str
    caption: str
    code: str
    files: dict[str, bytes]
    report: str
    status: str


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


def _run(path: Path) -> Example:
    key = (str(path), path.stat().st_mtime_ns)
    if key in _CACHE:
        return _CACHE[key]
    from PIL import Image

    import eofigs
    from eofigs import styling

    source = path.read_text(encoding="utf-8")
    title, caption, code = _split_docstring(source)
    slug = _slug(path)
    saved_state = dict(styling._STATE)
    try:
        with mpl.rc_context(), warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=_FONT_WARNING, category=UserWarning)
            namespace = runpy.run_path(str(path), run_name="__gallery__")
            fig = namespace.get("fig")
            if not isinstance(fig, matplotlib.figure.Figure):
                raise PluginError(f"{path.name} must leave its figure in a variable named fig.")
            with tempfile.TemporaryDirectory() as tmp:
                report = eofigs.save_figure(fig, Path(tmp) / slug, formats=("pdf", "png"))
                files = {
                    f"files/{slug}.pdf": (Path(tmp) / f"{slug}.pdf").read_bytes(),
                    f"files/{slug}_600dpi.png": (Path(tmp) / f"{slug}.png").read_bytes(),
                }
            web = io.BytesIO()
            fig.savefig(web, format="png", dpi=WEB_DPI)
            files[f"images/{slug}.png"] = web.getvalue()
            with Image.open(io.BytesIO(web.getvalue())) as image:
                image = image.convert("RGB")
                image.thumbnail(THUMB_SIZE)
                card = Image.new("RGB", THUMB_SIZE, "white")
                card.paste(image, ((THUMB_SIZE[0] - image.width) // 2,
                                   (THUMB_SIZE[1] - image.height) // 2))  # fmt: skip
                thumb = io.BytesIO()
                card.save(thumb, format="PNG", optimize=True)
            files[f"thumbs/{slug}.png"] = thumb.getvalue()
            files[f"files/{slug}.py"] = source.encode("utf-8")
            checked = eofigs.check_figure(fig)
            figure_report = str(checked)
            status = "success"
            if not checked.passed:
                status = "failure"
            elif checked.warnings:
                status = "warning"
    except PluginError:
        raise
    except Exception as exc:  # a broken example fails the build
        raise PluginError(f"Gallery example {path.name} failed: {exc!r}") from exc
    finally:
        plt.close("all")
        styling._STATE.clear()
        styling._STATE.update(saved_state)
    del report  # the file checks are covered by the live-figure report shown on the page
    example = Example(slug, title, caption, code, files, figure_report, status)
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


def _page(ex: Example) -> str:
    return f"""# {ex.title}

![{ex.title}](images/{ex.slug}.png)

{ex.caption}

[:material-download: Script](files/{ex.slug}.py){{ .md-button }}
[:material-download: PDF](files/{ex.slug}.pdf){{ .md-button }}
[:material-download: PNG, 600 dpi](files/{ex.slug}_600dpi.png){{ .md-button }}

```python
{ex.code}
```

??? {ex.status} "Figure check"

    ```text
{_indent(ex.report, 4)}
    ```
"""


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
