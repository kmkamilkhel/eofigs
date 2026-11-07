# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

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
- Project structure, packaging, test and documentation workflows.
- Container image workflow for GitHub Container Registry (development `dev` tag); release tags build
  a multi-architecture image (amd64 and arm64).
- Code of conduct (Contributor Covenant 2.1), issue templates, pull request template.
- Citation file validation and coverage total in continuous integration.
