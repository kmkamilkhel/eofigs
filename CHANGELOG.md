# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/).
Entries marked **Affects existing figures: re-render.** change figure output (what is drawn,
the statistics, the layout) or caption text: figures made with an earlier version should be
drawn again.

## [0.2.0] - 2026-11-11

Statistical tests behind the significance marks: false discovery rate control and the
seasonal Mann–Kendall test, plus two fixes that change existing trend maps.

### Added

- `fdr="bh"` in `trend_map` and `event_composite`: Benjamini–Hochberg false discovery rate
  control of the significance marks, at `fdr_q` (default 2 × `alpha`, Wilks 2016), over the
  valid pixels of the grid (in `event_composite` separately for each map). The record gives
  the method, q, the number of tests, the number significant and the equivalent p
  threshold; the legend and the caption say what was applied. Off by default.
- `eofigs.stats.fdr_mask`: the same correction for any array of p-values.
- `trend(..., seasonal="month")` (or season labels): seasonal Mann–Kendall test and seasonal
  Kendall slope (Hirsch et al. 1982) for monthly and other sub-annual data, with the
  Hirsch–Slack (1984) correction for correlation between seasons by default
  (`seasonal_correction`; at least 10 complete years). `trend_map` passes `seasonal` on,
  records it and names the test in the caption. Results match the R packages trend and rkt.
- `TrendWarning` for sub-annual data without `seasonal` (`seasonal="none"` keeps the plain
  test without the warning) and for records too short for the correction.
- Gallery: a synthetic field with a known trend, marked at p < 0.05 and with false
  discovery rate control; the trend map page compares both on the Swat NDVI series.
- Gallery: the seasonal trend of Swat monthly NDVI, May to September, with the shares of
  significant pixels with and without the Hirsch–Slack correction.

### Fixed

- `trend_map` with `data=`: pixels without any value lie outside the data. They are left
  white and not counted, as in `event_composite`; before, they were drawn as "no valid trend
  (too few observations)" and counted in the shares (in the Swat trend map, 0.8 % of the
  pixels were labelled so; none has too few observations).
  **Affects existing figures: re-render.**
- `trend_map` drawn into a subfigure leaves room above the map for a panel letter when panel
  labels are on, as `study_area_map` does; the letters were cut off at the top.
  **Affects existing figures: re-render.**

### Changed

- The README opens with a grid of six gallery figures, each linking to its gallery page.
  The docs build makes the cards from the gallery figures and fails when the README does
  not show and link every card.
- Roadmap: features are listed as released or planned, without version numbers for the
  planned ones.
- The citation page and the README give the version DOI of 0.1.1
  (10.5281/zenodo.24084780).
- Continuous integration: the install check on macOS still runs for every pull request but
  is no longer required to merge, because GitHub at times assigns no macOS runner to it;
  the macOS test jobs remain required.

## [0.1.1] - 2026-11-09

A reliability release: four fixes, captions that state the assumptions of the per-pixel
tests, and no new features.

> **Re-run `accuracy_scatter` if you passed two pandas Series.** eofigs 0.1.0 paired pandas
> inputs by position, not by index. If `observed` and `predicted` were Series whose indexes
> were in different orders (for example after a merge, a sort or a train/test split), the
> statistics, the fitted line and the caption from 0.1.0 are wrong, without an error or a
> warning. Plain arrays, and Series in the same order, were paired correctly.

### Fixed

- `accuracy_scatter` pairs two pandas inputs by their index labels and two xarray
  DataArrays by their coordinates (dimensions and labels put in the order of `observed`);
  `groups` given as a Series or DataArray follows the same alignment. Labels that are
  missing on one side or repeated raise a `ValueError` that counts them. Arrays, and one
  labelled input with one array, are still paired by position.
  `fig.eofigs_layout["pairing"]` records the rule used.
  **Affects existing figures: re-render.**
- Boolean masks in a CRS other than the map's (for example EPSG:4326 MODIS, TerraClimate or
  ERA5 grids with missing pixels) crashed `trend_map`, `event_composite` and
  `study_area_map` overlays with `KeyError: 'bool'`. Masks are now reprojected as 0/1
  bytes, keeping valid, not-vegetated and no-data pixels apart.
- The PDF font check passed files with fonts that are not embedded (for example the
  base-14 Helvetica written with `pdf.use14corefonts`). A font now passes only when its
  descriptor carries the font program (FontFile, FontFile2 or FontFile3); unembedded fonts
  fail, and a PDF whose fonts cannot be read gives a warning ("could not be verified")
  instead of a pass. The PDF is read with pypdf, tolerantly (small defects common in files
  from other tools are repaired), including compressed object streams.
- `trend_map` accepts a p-value grid whose dimensions are in another order than the
  slope's (it is transposed), and refuses a p-value grid in another CRS with a clear error.
  **Affects existing figures: re-render.**

### Changed

- Captions state the assumptions of the per-pixel tests behind the significance marks:
  `trend_map` "Per-pixel Mann–Kendall tests assume serial independence and are not
  adjusted for multiple comparisons." and `event_composite` "Per-pixel tests across events
  are not adjusted for multiple comparisons." With p-values passed to `trend_map`, the
  caption says "Significance from the supplied p-values (alpha = 0.05); eofigs applied no
  adjustment for multiple comparisons." The trend map and event composite pages explain
  both, with Wilks (2016).
  **Affects existing figures: re-render.**
- New dependency: pypdf (BSD licence), for the PDF font check.
- The README opens with four figures from the Swat valley data; the gallery introduction
  points to the ICESat-2 DEM validation as a real accuracy assessment.
- The Zenodo DOI is in CITATION.cff, the README and a "How to cite" section of the
  documentation; the installation page installs from PyPI.

## [0.1.0] - 2026-11-08

First release: journal styles and one-call export, the figure check, figure sets, the
variable library, print-size raster handling and trend statistics, with four recipe
figures: study area map, trend map, event composite and accuracy scatter.

### Added

- `study_area_map`: study area outline over a grey hillshade with semi-transparent
  elevation colours (light `lapaz` under an overlay, `batlow` otherwise), a single-colour
  overlay (for example tree cover) that lets the hillshade show through, labelled points,
  graticule (at most four labels per side), north arrow to true north above or beside the
  scale bar, legend and locator inset. The figure height follows the study area's shape up
  to 75 % of the journal maximum; inset, legend and furniture go to the emptiest part of
  the map, clear of the outline, points and labels, or below or beside the map; point
  labels avoid each other and the outline. `subfigure=` draws the map as one panel of a
  larger figure.
- `add_north_arrow` (rotated by the grid convergence), `add_scale_bar` (true distance at
  the map centre, round lengths) and `add_inset` (Natural Earth countries, default de facto
  boundaries bundled; Natural Earth worldviews downloaded on request with a pinned version
  and checksum, and cached).
- `trend_map`: per-pixel trends (Theil–Sen, Mann–Kendall, computed at full resolution and
  then reduced to print size; p-values are never averaged) with zero-centred colours,
  symmetric limits at the rounded 98th percentile, significance dots or hatching where at
  least half of the pixels in each 1.6 mm cell are significant, hatched grey for
  non-vegetated and no-data pixels, an optional latitude profile from the full-resolution
  slope, and a ready caption sentence with the colour limits, the clipped share and the
  significance rule (`fig.eofigs_layout["caption"]`).
- `event_composite`: anomaly maps before, during and after a set of events (date pairs or a
  boolean series), averaged over the events, with a composite series. Events whose window
  runs past the record or overlaps another are dropped with a warning; a per-pixel linear
  trend is removed first; anomalies are taken from a monthly climatology of the non-event
  steps at full resolution (or z-scores); significance by a t-test (or Wilcoxon test) across
  events, marked as in `trend_map`; shared colour limits and a ready caption sentence,
  which notes the low power of a test with fewer than 5 events. The series shades the event
  period, darker while all events are ongoing and lighter while only some are.
- `accuracy_scatter`: observed against predicted values (predicted on the x axis and the
  least-squares line of observed on predicted by default, after Piñeiro et al. 2008; or
  the reverse, or a reduced major axis line) with the 1:1 line, a statistics box (R² as the
  squared Pearson correlation, RMSE, rRMSE, NMAD after Höhle and Höhle 2009, MAE, bias,
  rBias, NSE, slope, intercept, n)
  with units from the variable library, square axes with shared ticks, groups in Okabe-Ito
  colours with distinct markers, density colours above 1 000 pairs (rasterised in vector
  files), `ax=` for multi-panel figures and a ready caption sentence.
- Swat ICESat-2 ATL08 terrain heights 2019–2024 (a slope-independent quality rule and a
  random sample of 25 000 segments), converted to EGM2008 heights and paired with the
  Copernicus DEM (built by `docs/scripts/build_swat_icesat2.py`); gallery entries for the
  ICESat-2 comparison, with the DEM error by slope class, and for synthetic calibration and
  validation plots.
- Swat hot-dry events 2001–2021 from TerraClimate (built by `docs/scripts/build_swat_events.py`)
  and a monthly 1 km NDVI series from MODIS MOD13A1 in `docs/data/swat/`; gallery entries
  for the Swat event composite and a synthetic composite with eight events.
- Swat growing-season NDVI 2001–2024 (MODIS MOD13A1, 500 m) in `docs/data/swat/`, built by
  `docs/scripts/build_swat_ndvi.py`; gallery entries for the Swat trend map with and
  without the latitude profile.
- `check_figure` checks that single-colour overlays stay distinguishable from the colour
  maps beneath them.
- `fit_raster` reads http(s) and s3 URLs.
- Swat valley sample data in `docs/data/swat/` (not in the package) with
  `DATA_LICENSES.md`; gallery entries for the Swat study area map and a house style.
- `eofigs.palettes`: Okabe-Ito, muted, slate and terracotta-slate palettes and neutral
  colours; colour maps `"eofigs.slate"` and `"eofigs.terra_slate"` (and `_r`).
- `cvd_preview`: one image showing a figure in normal vision, protan, deutan and tritan
  simulation and greyscale.
- `tidy_axes`: four or five ticks at round values on axes and colour bars.
  `set_style(max_ticks=5)` sets a house tick limit, which `check_figure` then checks.
- `set_style(panel_titles=False)`: recipes leave out panel titles and name the panels in
  their caption sentence instead.
- `check_figure` accepts metric-compatible free fonts (Liberation Sans, Arimo, TeX Gyre
  Heros, Liberation Serif, Tinos, TeX Gyre Termes) in place of the journal's fonts, with a
  note.
- `save_figure` rasterises dense layers (mesh plots, collections with more than 2 000
  elements) inside vector files; `rasterize_dense=False` keeps them vector.
- Styles use a true minus sign.
- Example gallery built from `examples/*.py` when the documentation is built, with the
  check report and downloads for each figure.

- `set_style` and the `style` context manager: journal presets for Elsevier, Springer,
  MDPI, Wiley, Frontiers and Taylor & Francis (plus `custom`), font fallback to
  metric-compatible free fonts with a warning, mathtext matched to the text font,
  Okabe-Ito colour cycle, TrueType font embedding.
- `new_figure`: figures sized in millimetres from named column widths.
- `label_panels`: bold (a), (b), ... panel labels in several formats.
- `save_figure`: one call writes the journal's formats (vector PDF plus TIFF/PNG/EPS) at
  600 dpi or an exact pixel width, without trimming, with reproducible PDFs.
- `check_figure`: size, resolution, smallest font, fonts in use or embedded, colour-blind
  safety of categorical colours (CIEDE2000 with simulated colour-vision deficiency) and
  colour-map lightness, for live figures and exported files.
- Journal presets in `journals.json` with source links and check dates; documentation pages
  for style and export, and for the presets.
- `art=` option ("combination", "line", "halftone") for `save_figure` and `check_figure`:
  line art is written and checked at the publisher's line-art resolution (for example
  1000 dpi for Elsevier, 1200 dpi for Springer).
- Variable library (`variable`, `register_variable`, `Variable`): 22 Earth observation
  variables in `variables.json` with long names, symbols, mathtext units, cmcrameri colour
  maps, default ranges and zero-centred anomaly and trend maps (terracotta–slate for all
  vegetation variables: indices, productivity and structure; `vik` with the physically
  sensible direction for water, temperature, terrain and burn severity); recognises xarray variables
  from CF attributes and writes CF units in mathtext.
- `fit_raster`: reduces GeoTIFFs, COGs and xarray rasters to the printed resolution (mean,
  mode or mask fraction), ignores nodata, sets sparse pixels to NaN (`min_valid`), keeps the
  CRS, stays lazy with dask, and reads files at the output size (integer files are averaged
  exactly by eofigs).
- `trend`: Theil–Sen slope and Mann–Kendall test (tie- and continuity-corrected) per pixel,
  against real dates, with `min_valid`, a memory budget for any series length, and dask
  support; compared with `scipy.stats.theilslopes` in the tests. The slope is labelled as a
  trend of the input variable, and the intercept records its `reference_time`.
- `figure_set` and `FigureSet`: manuscript figures saved as `Fig01_<name>` / `FigS01_<name>`
  in the journal's formats, reordering with file renaming, and `figures_manifest.csv` with
  sizes, resolution, check results and captions; resumes from the manifest.
- `check_figure` treats single-colour contour lines as lines, not as colour maps.
- Project structure, packaging, test and documentation workflows, with a check of the
  built wheel and source distribution and an install test on Linux, Windows and macOS.
- Container image workflow for GitHub Container Registry (development `dev` tag); release tags build
  a multi-architecture image (amd64 and arm64).
- Code of conduct (Contributor Covenant 2.1), issue templates, pull request template.
- Citation file validation and coverage total in continuous integration.

[0.2.0]: https://github.com/kmkamilkhel/eofigs/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/kmkamilkhel/eofigs/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/kmkamilkhel/eofigs/releases/tag/v0.1.0
