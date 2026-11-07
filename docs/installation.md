# Installation

The first release is not yet on PyPI. To install the development version:

```bash
pip install git+https://github.com/kmkamilkhel/eofigs.git
```

eofigs needs Python 3.11 or newer. It depends on matplotlib, cartopy, xarray, rioxarray and
geopandas. On Windows and macOS the simplest route to these libraries is conda-forge:

```bash
conda create -n eofigs -c conda-forge python=3.13 cartopy rioxarray geopandas matplotlib-scalebar
conda activate eofigs
pip install cmcrameri git+https://github.com/kmkamilkhel/eofigs.git
```

### cmcrameri from conda-forge

The conda-forge build of cmcrameri 1.10 reports its version as `0.0.0`
([conda-forge/cmcrameri-feedstock#11](https://github.com/conda-forge/cmcrameri-feedstock/issues/11)),
so pip treats eofigs' requirement `cmcrameri>=1.9` as unmet and installs cmcrameri again from
PyPI. This is harmless. To keep a conda environment tidy, install cmcrameri from PyPI in the
first place:

```bash
conda create -n eofigs -c conda-forge python=3.13 cartopy rioxarray geopandas matplotlib-scalebar
conda activate eofigs
pip install cmcrameri git+https://github.com/kmkamilkhel/eofigs.git
```

## Fonts

Journal presets use Times New Roman or Arial when installed. Otherwise eofigs falls back to
metric-compatible free fonts (Liberation Serif, TeX Gyre Termes, Liberation Sans, Arimo) and
tells you which font was used. On Linux: `sudo apt install fonts-liberation fonts-texgyre`.

## Docker

A development image with eofigs and its geospatial stack is published on GitHub Container
Registry (`dev` tag until v0.1):

```bash
docker run --rm -v "$PWD":/work ghcr.io/kmkamilkhel/eofigs:dev python script.py
```
