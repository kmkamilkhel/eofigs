# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

### Changed

- `check_figure` ignores single-colour contour lines when checking colour maps.
- Project structure, packaging, test and documentation workflows.
- Container image workflow for GitHub Container Registry (development `dev` tag); release tags build
  a multi-architecture image (amd64 and arm64).
- Code of conduct (Contributor Covenant 2.1), issue templates, pull request template.
- Citation file validation and coverage total in continuous integration.
