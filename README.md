# eofigs

[![Tests](https://github.com/kmkamilkhel/eofigs/actions/workflows/tests.yml/badge.svg)](https://github.com/kmkamilkhel/eofigs/actions/workflows/tests.yml)
[![Docs](https://github.com/kmkamilkhel/eofigs/actions/workflows/docs.yml/badge.svg)](https://kmkamilkhel.github.io/eofigs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Analysis-aware, publication-ready figures for Earth observation research.

> **Under development. First release: v0.1.**

eofigs turns Earth observation analysis outputs (rasters, time series, validation pairs) into
journal-ready figures that know the analysis, the variable and the printed size:

- **Recipe figures** for common analyses: trend with significance, event composites, and later
  recovery, burn severity, disturbance and divergence.
- **A variable library** with fixed colour maps, symbols and units, so NDVI, LST or GPP look the
  same in every figure, and their anomalies and trends get zero-centred diverging colours.
- **Print-size rendering**: rasters are read and reduced to the pixels the printed figure needs,
  from its width in mm and its dpi, keeping memory use and PDF size small.
- **Journal presets and one-call export** to vector PDF plus 600 dpi PNG or TIFF, with a check
  of size, resolution, smallest font, font embedding and colour-blind safety.

## Installation

The first release is not yet on PyPI. To try the development version:

```bash
pip install git+https://github.com/kmkamilkhel/eofigs.git
```

## Roadmap

**v0.1**

| Function | Purpose |
|---|---|
| `set_style`, `new_figure`, `save_figure` | Journal presets (Elsevier, Springer, MDPI, Wiley, Frontiers, Taylor & Francis), widths in mm, one-call export |
| `check_figure` | Size, dpi, smallest font, embedded fonts, colour-blind safety |
| `figure_set` | Manuscript figure set with automatic Fig/FigS numbering and a manifest |
| `variable`, `register_variable` | Variable library: colour map, symbol, unit, range |
| `fit_raster` | Reduce large rasters to the pixels the printed figure needs |
| `trend` | Theil–Sen slope with Mann–Kendall test on a time-series cube |
| `study_area_map` | DEM hillshade, locator inset, graticule, north arrow, scale bar, points, legend |
| `trend_map` | Trend map with zero-centred colours, significance dots, optional latitude profile |
| `event_composite` | Before/during/after anomaly maps with a composite time series |
| `accuracy_scatter` | Density scatter with 1:1 line, R², RMSE and bias |

**v0.2**: burn severity, recovery and disturbance recipes, SHAP and partial dependence styling,
confusion matrix, Google Earth Engine input through Xee at print scale.

**v0.3**: R package with matching function names.

## Citation

If you use eofigs, please cite it using the metadata in [CITATION.cff](CITATION.cff).

## License

MIT. See [LICENSE](LICENSE).
