# Journal presets

Each preset is read from the publisher's author guidelines (link and date below). Values
marked with an asterisk are not stated by the publisher and use eofigs defaults; always
confirm against the journal's own guide, which can be stricter.

| Preset | Widths (mm) | Max height (mm) | Min font (pt) | Resolution (dpi): line / halftone / combination | Default formats | Source (checked) |
|---|---|---|---|---|---|---|
| `elsevier` | single 90, onehalf 140, double 190 | 240* | 7 | 1000 / 300 / 500 | PDF, TIFF | [Elsevier artwork sizing](https://www.elsevier.com/about/policies-and-standards/author/artwork-and-media-instructions/artwork-sizing) (2026-11-07) |
| `springer` | single 84, double 174, small_journal 119 | 234 | 8 | 1200 / 300 / 600 | PDF, EPS, TIFF | [Springer submission guidelines](https://link.springer.com/journal/10661/submission-guidelines) (2026-11-07) |
| `mdpi` | single 90*, onehalf 140*, double 190* | 240* | 7* | 600 / 600 / 600 | PDF, TIFF | [MDPI Remote Sensing instructions](https://www.mdpi.com/journal/remotesensing/instructions) (2026-11-07) |
| `wiley` | single 80, double 180 | 240* | 7* | 600 / 300 / 600 | PDF, TIFF | [Wiley figure preparation](https://authorservices.wiley.com/author-resources/Journal-Authors/Prepare/manuscript-preparation-guidelines.html/figure-preparation.html) (2026-11-07) |
| `frontiers` | single 85, double 180 | 240* | 8 | 300 / 300 / 300 | PDF, TIFF | [Frontiers author guidelines](https://www.frontiersin.org/guidelines/author-guidelines) (2026-11-07) |
| `taylor_francis` | single 90*, onehalf 140*, double 190* | 240* | 7* | 1200 / 300 / 600 | PDF, EPS, TIFF | [Taylor & Francis electronic artwork](https://authorservices.taylorandfrancis.com/publishing-your-research/making-your-submission/submit-electronic-artwork/) (2026-11-07) |
| `custom` | single 90, onehalf 140, double 190 | 240 | 7 | 600 / 600 / 600 | PDF, PNG | eofigs defaults |

Notes:

- **Springer**: 84 mm is one column of a two-column page and 174 mm the full text width;
  small-format journals use 119 mm and at most 195 mm height.
- **Wiley**: figures between 80 and 180 mm wide; individual Wiley journals set their own column widths.
- **MDPI** and **Taylor & Francis** state no figure widths; Taylor & Francis refers to each journal's page.
- eofigs exports raster files at 600 dpi for every preset, which meets or exceeds each
  publisher's requirement for figures that combine text and images. For line art
  (`art="line"`) it uses the publisher's line-art resolution when that is higher
  (1000 dpi for Elsevier, 1200 dpi for Springer and Taylor & Francis).
- `taylor_francis` also accepts `"tandf"` and `"t&f"`; `springer` accepts `"springer_nature"`.

The presets live in `eofigs/data/journals.json`, which the R version of eofigs will share.
