# Installation

```bash
pip install eofigs
```

eofigs needs Python 3.11 or newer. It depends on matplotlib, cartopy, xarray, rioxarray,
geopandas and pypdf (which reads exported PDFs for the font check). On Windows and macOS the
simplest route to these libraries is conda-forge:

```bash
conda create -n eofigs -c conda-forge python=3.13 cartopy rioxarray geopandas matplotlib-scalebar pypdf cmcrameri
conda activate eofigs
pip install eofigs
```

Environments created before 16 November 2026 may hold the first conda-forge build of
cmcrameri 1.10, which reports its version as `0.0.0`; pip then installs cmcrameri again from
PyPI. Run `conda update -c conda-forge cmcrameri` to get the corrected build.

### Development version

The main branch, with the changes listed under "Unreleased" in the
[changelog](changelog.md):

```bash
pip install git+https://github.com/kmkamilkhel/eofigs.git
```

## Fonts

Journal presets use Times New Roman or Arial when installed. Otherwise eofigs falls back to
metric-compatible free fonts (Liberation Serif, TeX Gyre Termes, Liberation Sans, Arimo) and
tells you which font was used. On Linux: `sudo apt install fonts-liberation fonts-texgyre`.

## Docker

An image with eofigs and its geospatial stack is published on GitHub Container Registry for
Linux on amd64 and arm64. Each release has its own tag (`0.2.1`), `latest` is the newest
release and `dev` follows the main branch:

```bash
docker run --rm -v "$PWD":/work ghcr.io/kmkamilkhel/eofigs:0.2.1 python script.py
```
