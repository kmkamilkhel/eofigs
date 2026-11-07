# Contributing

Bug reports, ideas and pull requests are welcome. Please open an issue first for larger changes.

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

## Guidelines

- Public functions have type hints and NumPy-style docstrings with a short runnable example.
- Tests use small synthetic data and make no network calls.
- Figures produced by recipes are covered by image-comparison tests (pytest-mpl).
- Coordinate reference systems are always handled explicitly.
- Commit messages are short, plain English and in the imperative ("Add scale bar options").
