# Contributing

Bug reports, ideas and pull requests are welcome. Please open an issue first for larger changes.
Questions on how to use eofigs go to [Discussions (Q&A)](https://github.com/kmkamilkhel/eofigs/discussions/categories/q-a).

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By taking part you agree
to uphold it.

## Development setup

With conda (recommended, all geospatial libraries from conda-forge):

```bash
conda env create -f environment-dev.yml
conda activate eofigs-dev
pip install -e . --no-deps
pre-commit install
```

With pip:

```bash
pip install -e ".[dev]"
pre-commit install
```

## Checks

```bash
ruff check .
ruff format --check .
pytest
mkdocs build --strict
```

## Pull requests

- Work on a branch and open a pull request against `main`; fill in the pull request template.
- All checks (lint, citation, tests on Linux, Windows and macOS, docs build, container build) must pass
  before a pull request is merged.

## Guidelines

- Public functions have type hints and NumPy-style docstrings with a short runnable example.
- Tests use small synthetic data and make no network calls.
- Figures produced by recipes are covered by image-comparison tests (pytest-mpl).
- Coordinate reference systems are always handled explicitly.
- Commit messages are short, plain English and in the imperative ("Add scale bar options").
