# Installation

The first release is not yet on PyPI. To install the development version:

```bash
pip install git+https://github.com/kmkamilkhel/eofigs.git
```

eofigs needs Python 3.11 or newer. It depends on matplotlib, cartopy, xarray, rioxarray and
geopandas. On Windows and macOS the simplest route to these libraries is conda-forge:

```bash
conda create -n eofigs -c conda-forge python=3.13 cartopy rioxarray geopandas cmcrameri matplotlib-scalebar
conda activate eofigs
pip install git+https://github.com/kmkamilkhel/eofigs.git
```

## Fonts

Journal presets use Times New Roman or Arial when installed. Otherwise eofigs falls back to
metric-compatible free fonts (TeX Gyre Termes, Liberation Serif, Liberation Sans) and tells you
which font was used.
