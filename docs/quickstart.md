# Quickstart

A journal preset, one recipe figure, its check and its export:

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

The figure is single-column width (90 mm for Elsevier), its axis labels and units come from
the variable library (`"agb"`), and the statistics box, fitted line and caption follow the
conventions described in [Accuracy scatters](accuracy-scatter.md).

## Your own figures

Recipes cover common analyses; for anything else, draw with matplotlib in a figure of the
printed size and let eofigs handle panels, ticks and export:

```python
eofigs.set_style("mdpi")
fig, axes = eofigs.new_figure("double", ncols=2, height_mm=70)
axes[0].plot(years, ndvi, color=eofigs.palettes.okabe_ito[4])
axes[1].bar(classes, area, color=eofigs.palettes.muted[:4])
eofigs.label_panels(axes)  # (a), (b) in the journal's style
eofigs.tidy_axes(*axes)  # a few ticks at round values
eofigs.save_figure(fig, "fig_trends")
```

## Recipes

| Recipe | Figure |
|---|---|
| [`study_area_map`](study-area.md) | Study area over a hillshade with an overlay, points, inset, graticule, north arrow and scale bar |
| [`trend_map`](trend-map.md) | Per-pixel Theil–Sen trends with Mann–Kendall significance and an optional latitude profile |
| [`event_composite`](event-composite.md) | Anomaly maps before, during and after events, with significance and a composite series |
| [`accuracy_scatter`](accuracy-scatter.md) | Observed against predicted values with the 1:1 line, a fitted line and statistics |

Every recipe returns a matplotlib figure, records what it computed in
`fig.eofigs_layout` (statistics, limits, a caption sentence) and accepts `ax=` or
`subfigure=` to become one panel of a larger figure. Worked examples with real data are in
the [Gallery](gallery/index.md).
