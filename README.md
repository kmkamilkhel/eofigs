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

## Gallery

<table>
<tr>
<td width="33%"><a href="https://kmkamilkhel.github.io/eofigs/gallery/study_area_swat/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/thumbs/study_area_swat.png" alt="Study area map: Swat valley"></a><br><b>Study area map: Swat valley</b></td>
<td width="33%"><a href="https://kmkamilkhel.github.io/eofigs/gallery/study_area_single_column/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/thumbs/study_area_single_column.png" alt="Study area map: single column"></a><br><b>Study area map: single column</b></td>
<td width="33%"><a href="https://kmkamilkhel.github.io/eofigs/gallery/house_style/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/thumbs/house_style.png" alt="House style"></a><br><b>House style</b></td>
</tr>
<tr>
<td width="33%"><a href="https://kmkamilkhel.github.io/eofigs/gallery/style_export/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/thumbs/style_export.png" alt="Journal style and export"></a><br><b>Journal style and export</b></td>
<td width="33%"><a href="https://kmkamilkhel.github.io/eofigs/gallery/large_raster/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/thumbs/large_raster.png" alt="Large raster at print size"></a><br><b>Large raster at print size</b></td>
<td width="33%"><a href="https://kmkamilkhel.github.io/eofigs/gallery/trend_significance/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/thumbs/trend_significance.png" alt="Trend and significance"></a><br><b>Trend and significance</b></td>
</tr>
<tr>
<td width="33%"><a href="https://kmkamilkhel.github.io/eofigs/gallery/trend_map_swat/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/thumbs/trend_map_swat.png" alt="Trend map: Swat valley NDVI 2001–2024"></a><br><b>Trend map: Swat valley NDVI 2001–2024</b></td>
<td width="33%"><a href="https://kmkamilkhel.github.io/eofigs/gallery/trend_profile_swat/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/thumbs/trend_profile_swat.png" alt="Trend map with latitude profile"></a><br><b>Trend map with latitude profile</b></td>
<td width="33%"><a href="https://kmkamilkhel.github.io/eofigs/gallery/palettes/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/thumbs/palettes.png" alt="Built-in palettes"></a><br><b>Built-in palettes</b></td>
</tr>
<tr>
<td width="33%"><a href="https://kmkamilkhel.github.io/eofigs/gallery/event_composite_swat/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/thumbs/event_composite_swat.png" alt="Event composite: Swat hot-dry months"></a><br><b>Event composite: Swat hot-dry months</b></td>
<td width="33%"><a href="https://kmkamilkhel.github.io/eofigs/gallery/event_composite_synthetic/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/thumbs/event_composite_synthetic.png" alt="Event composite with significance"></a><br><b>Event composite with significance</b></td>
<td width="33%"><a href="https://kmkamilkhel.github.io/eofigs/gallery/accuracy_scatter_icesat2/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/thumbs/accuracy_scatter_icesat2.png" alt="Accuracy scatter: ICESat-2 against a DEM"></a><br><b>Accuracy scatter: ICESat-2 against a DEM</b></td>
</tr>
<tr>
<td width="33%"><a href="https://kmkamilkhel.github.io/eofigs/gallery/accuracy_scatter_synthetic/"><img src="https://kmkamilkhel.github.io/eofigs/gallery/thumbs/accuracy_scatter_synthetic.png" alt="Accuracy scatter: calibration and validation"></a><br><b>Accuracy scatter: calibration and validation</b></td>
<td width="33%"></td>
<td width="33%"></td>
</tr>
</table>

More in the [gallery](https://kmkamilkhel.github.io/eofigs/gallery/), with the code for
each figure.

## Installation

The first release is not yet on PyPI. To try the development version:

```bash
pip install git+https://github.com/kmkamilkhel/eofigs.git
```

## Run with Docker

A container image with eofigs and its geospatial stack (cartopy, rioxarray, geopandas, fonts)
is published on GitHub Container Registry. Until v0.1 it is a **development image** (`dev` tag),
rebuilt from the main branch:

```bash
docker run --rm -v "$PWD":/work ghcr.io/kmkamilkhel/eofigs:dev python script.py
```

## Roadmap

Available in the development version: `set_style`, `style`, `new_figure`, `label_panels`,
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
| `accuracy_scatter` | Observed against predicted values with the 1:1 line, a fitted line (Piñeiro et al. 2008), R², RMSE and bias, density colours or groups |

**v0.2**: burn severity, recovery and disturbance recipes, SHAP and partial dependence styling,
confusion matrix, Google Earth Engine input through Xee at print scale.

**v0.3**: R package with matching function names.

## Contributing

Questions and ideas are welcome in [Discussions](https://github.com/kmkamilkhel/eofigs/discussions);
bugs and feature requests in [Issues](https://github.com/kmkamilkhel/eofigs/issues).
See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).

## Citation

If you use eofigs, please cite it using the metadata in [CITATION.cff](CITATION.cff).

## License

MIT. See [LICENSE](LICENSE). Data files have their own licences, listed in
[DATA_LICENSES.md](DATA_LICENSES.md).
