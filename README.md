# eofigs

[![Tests](https://github.com/kmkamilkhel/eofigs/actions/workflows/tests.yml/badge.svg)](https://github.com/kmkamilkhel/eofigs/actions/workflows/tests.yml)
[![Docs](https://github.com/kmkamilkhel/eofigs/actions/workflows/docs.yml/badge.svg)](https://kmkamilkhel.github.io/eofigs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/eofigs.svg)](https://pypi.org/project/eofigs/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24053760.svg)](https://doi.org/10.5281/zenodo.24053760)

Analysis-aware, publication-ready figures for Earth observation research.

<table>
<tr>
<td width="33%" align="center"><a href="https://kmkamilkhel.github.io/eofigs/gallery/study_area_swat/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/cards/study_area_swat.png" alt="Study area map: Swat valley"></a><br><b>Study area map</b></td>
<td width="33%" align="center"><a href="https://kmkamilkhel.github.io/eofigs/gallery/trend_map_swat/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/cards/trend_map_swat.png" alt="Trend map: Swat valley NDVI 2001–2024"></a><br><b>Trend map</b></td>
<td width="33%" align="center"><a href="https://kmkamilkhel.github.io/eofigs/gallery/event_composite_swat/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/cards/event_composite_swat.png" alt="Event composite: Swat hot-dry months"></a><br><b>Event composite</b></td>
</tr>
<tr>
<td width="33%" align="center"><a href="https://kmkamilkhel.github.io/eofigs/gallery/accuracy_scatter_icesat2/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/cards/accuracy_scatter_icesat2.png" alt="Accuracy scatter: ICESat-2 against a DEM"></a><br><b>DEM accuracy (ICESat-2)</b></td>
<td width="33%" align="center"><a href="https://kmkamilkhel.github.io/eofigs/gallery/fdr_synthetic/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/cards/fdr_synthetic.png" alt="Significance with false discovery rate control"></a><br><b>False discovery rate</b></td>
<td width="33%" align="center"><a href="https://kmkamilkhel.github.io/eofigs/gallery/house_style/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/cards/house_style.png" alt="House style"></a><br><b>House style</b></td>
</tr>
</table>

More examples in the [gallery](https://kmkamilkhel.github.io/eofigs/gallery/).

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

```bash
pip install eofigs
```

eofigs needs Python 3.11 or newer. On Windows and macOS, conda-forge is the simplest source
of its geospatial libraries; see the
[installation guide](https://kmkamilkhel.github.io/eofigs/installation/).

## Quick start

```python
import numpy as np
import eofigs

eofigs.set_style("elsevier")  # fonts, sizes and widths of the journal
rng = np.random.default_rng(1)
field = rng.gamma(5, 30, 300)  # observed aboveground biomass (Mg ha⁻¹)
model = 0.9 * field + rng.normal(10, 20, 300)  # predicted
fig = eofigs.accuracy_scatter(field, model, variable="agb")
print(fig.eofigs_layout["caption"])  # a ready caption sentence
print(eofigs.check_figure(fig))  # size, dpi, smallest font, fonts, colour-blind safety
eofigs.save_figure(fig, "fig_agb")  # vector PDF and a 600 dpi raster
```

More in the [quickstart](https://kmkamilkhel.github.io/eofigs/quickstart/) and the
[gallery](https://kmkamilkhel.github.io/eofigs/gallery/).

## Run with Docker

A container image with eofigs and its geospatial stack (cartopy, rioxarray, geopandas, fonts)
is published on GitHub Container Registry for each release (`0.1.1`, `latest`; `dev` follows
the main branch):

```bash
docker run --rm -v "$PWD":/work ghcr.io/kmkamilkhel/eofigs:0.1.1 python script.py
```

## Roadmap

Available in v0.1: `set_style`, `style`, `new_figure`, `label_panels`,
`save_figure`, `check_figure`, `cvd_preview`, `tidy_axes`, `palettes`, `variable`,
`register_variable`, `fit_raster`, `trend`, `figure_set`, `study_area_map`,
`add_north_arrow`, `add_scale_bar`, `add_inset`, `trend_map`, `event_composite` and
`accuracy_scatter`.


**v0.1**

| Function | Purpose |
|---|---|
| `set_style`, `new_figure`, `save_figure` | Journal presets (Elsevier, Springer, MDPI, Wiley, Frontiers, Taylor & Francis), widths in mm, one-call export |
| `check_figure`, `cvd_preview` | Size, dpi, smallest font, embedded fonts, colour-blind safety; preview as seen with colour-vision deficiencies |
| `palettes`, `tidy_axes` | Built-in palettes and colour maps; a few ticks at round values |
| `figure_set` | Manuscript figure set with automatic Fig/FigS numbering and a manifest |
| `variable`, `register_variable` | Variable library: colour map, symbol, unit, range |
| `fit_raster` | Reduce large rasters to the pixels the printed figure needs |
| `trend` | Theil–Sen slope with Mann–Kendall test on a time-series cube |
| `study_area_map` | DEM hillshade, overlay, labelled points, locator inset, graticule, north arrow to true north, scale bar, legend; automatic layout |
| `trend_map` | Trend map with zero-centred colours, significance dots, optional latitude profile |
| `event_composite` | Before/during/after anomaly maps with a composite time series |
| `accuracy_scatter` | Observed against predicted values with the 1:1 line, a fitted line (Piñeiro et al. 2008), R², RMSE, NMAD and bias, density colours or groups |

**v0.2**: burn severity, recovery and disturbance recipes, SHAP and partial dependence styling,
confusion matrix, Google Earth Engine input through Xee at print scale.

**v0.3**: R package with matching function names.

## Contributing

Questions and ideas are welcome in [Discussions](https://github.com/kmkamilkhel/eofigs/discussions);
bugs and feature requests in [Issues](https://github.com/kmkamilkhel/eofigs/issues).
See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).

## Citation

If you use eofigs, please cite it. The software is archived on Zenodo:
[doi:10.5281/zenodo.24053760](https://doi.org/10.5281/zenodo.24053760) covers all versions, and each release
has its own DOI (v0.1.1: [doi:10.5281/zenodo.24084780](https://doi.org/10.5281/zenodo.24084780)). The metadata are in
[CITATION.cff](CITATION.cff); the
[citation page](https://kmkamilkhel.github.io/eofigs/citation/) has APA and BibTeX entries.

## License

MIT. See [LICENSE](LICENSE). Data files have their own licences, listed in
[DATA_LICENSES.md](DATA_LICENSES.md).
