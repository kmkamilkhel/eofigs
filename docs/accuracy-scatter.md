# Accuracy scatters

`accuracy_scatter` draws the standard validation figure: estimates against reference values
with the 1:1 line, a fitted line and a box of statistics, with labels and units from the
variable library.

```python
import eofigs

eofigs.set_style("elsevier")
fig = eofigs.accuracy_scatter(field_agb, predicted_agb, variable="agb")
print(fig.eofigs_layout["stats"])  # every statistic at full precision
print(fig.eofigs_layout["caption"])  # definitions, fitted line, density rule
```

![ICESat-2 terrain heights against the Copernicus DEM in the Swat valley](gallery/images/accuracy_scatter_icesat2.png)

ICESat-2 ATL08 terrain heights (2019–2024, strong beams, snow-free segments, terrain height
uncertainty at most 5 m), converted from the WGS 84 ellipsoid to EGM2008 heights, against
the Copernicus DEM GLO-90 at the segment centres in the Swat valley (pre-2026 district
boundary): the former Swat district (before January 2026), now Swat and Bar Swat. Full code
and downloads: [gallery](gallery/accuracy_scatter_icesat2.md).

## Orientation and fitted line

By default the **predicted** values go on the x axis and the **observed** values on the y
axis, and the fitted line is the ordinary least-squares regression of observed on
predicted. This follows Piñeiro et al. (2008): regressing observed on predicted gives a
slope and intercept that describe the model directly (a slope below 1 means the model
overestimates high values and underestimates low ones; the intercept shows a constant bias),
whereas the reverse regression mixes the model's error into the slope.
`orientation="observed_x"` swaps the axes (the fit then regresses predicted on observed),
`fit="rma"` draws the reduced major axis line, and `fit=None` leaves the line out.

Piñeiro, G., Perelman, S., Guerschman, J. P., & Paruelo, J. M. (2008). How to evaluate
models: Observed vs. predicted or predicted vs. observed? *Ecological Modelling*, 216(3–4),
316–322. <https://doi.org/10.1016/j.ecolmodel.2008.05.006>

## Statistics

With observed values *O*, predicted values *P*, their means *Ō* and *P̄*, and *n* pairs
(pairs with a missing value in either are left out and counted in the record):

| Key | Shown as | Formula |
|---|---|---|
| `r2` | R² | squared Pearson correlation of *O* and *P* |
| `r` | r | Pearson correlation |
| `nse` | NSE | Nash–Sutcliffe efficiency, 1 − Σ(*P* − *O*)² / Σ(*O* − *Ō*)² (it can be negative) |
| `rmse` | RMSE | √(Σ(*P* − *O*)² / *n*) |
| `rrmse` | rRMSE | 100 · RMSE / *Ō* (%) |
| `mae` | MAE | Σ\|*P* − *O*\| / *n* |
| `bias` | Bias | Σ(*P* − *O*) / *n* (positive: overestimation) |
| `rbias` | rBias | 100 · bias / *Ō* (%) |
| `slope`, `intercept` | Slope, Intercept | of the fitted line, in plot axes (y on x) |
| `n` | n | number of pairs |

R² is the squared correlation, as most remote sensing validation papers report it; the
agreement with the 1:1 line is carried by the RMSE and the bias. The coefficient of
determination against the 1:1 line is available as `nse`, so that a figure never shows a
value called R² that can be negative.

Numbers in the box carry three significant digits, the statistics with units share one
number of decimals, R², r, NSE and the slope get two decimals and the percentages one.
Every statistic is kept at full precision in `fig.eofigs_layout["stats"]` (and per group in
`["groups"]`), for tables.

## Points, groups and density

- Up to 1 000 pairs: open circles. With `groups=` (up to 6 categories), each group gets an
  Okabe-Ito colour and its own marker, and the caption lists R² and RMSE for each group.
- Above 1 000 pairs (`density="auto"`), each point is coloured by the number of points in
  its cell of a 60 × 60 grid over the axis range, on a log scale, with the densest points
  drawn on top. The points are rasterised inside vector PDFs, while the axes and text stay
  vector.
- Both axes share the same limits and ticks, and the plot is square. The statistics box
  goes in the corner with the fewest points (or `stats_loc=`).

## Several panels

Pass `ax=` to draw one panel of a larger figure, for example calibration and validation:

```python
fig, axes = eofigs.new_figure("double", ncols=2, height_mm=95)
eofigs.accuracy_scatter(obs_cal, pred_cal, variable="agb", ax=axes[0], labels=["(a)"])
eofigs.accuracy_scatter(obs_val, pred_val, variable="agb", ax=axes[1], labels=["(b)"])
```

![Calibration and validation plots](gallery/images/accuracy_scatter_synthetic.png)

## The Swat ICESat-2 pairs

`docs/scripts/build_swat_icesat2.py` builds `swat_icesat2_atl08_dem.csv` in
[`docs/data/swat/`](https://github.com/kmkamilkhel/eofigs/tree/main/docs/data/swat):

- ICESat-2 ATL08 version 7 land segments (100 m) from 2019 to 2024, cut to the Swat box on
  NASA's servers with Harmony (a free NASA Earthdata login is needed to run the script);
- strong beams only, valid best-fit terrain heights, terrain height uncertainty at most
  5 m, snow-free land, segment centres inside the Swat outline;
- **vertical datum:** ATL08 heights are above the WGS 84 ellipsoid and the Copernicus DEM
  is referenced to the EGM2008 geoid; the ATL08 heights are converted to EGM2008 heights
  with PROJ and NGA's EGM2008 grid before the comparison (the geoid undulation over Swat is
  about −27 to −39 m, so skipping this step would add a bias of that size);
- the DEM elevation and slope are interpolated bilinearly at each segment centre.

The 2 124 segments that pass the 5 m uncertainty limit lie mostly on gentle slopes (median
DEM slope 1°, against 26° over the whole valley), because the ATL08 terrain height
uncertainty grows with the slope within a segment. On these segments the DEM and ICESat-2
agree within a few metres (RMSE 4.2 m, bias +1.4 m); the differences grow with slope, from
an RMSE of 2.7 m below 10° to 13.4 m between 10° and 20° (99 segments).
