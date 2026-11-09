# Trend maps

`trend_map` draws per-pixel trends with zero-centred colours and significance marks at a
size the printed page can show.

```python
import eofigs

eofigs.set_style("elsevier")
fig = eofigs.trend_map(
    ndvi_cube,  # time, y, x with a CRS
    aoi="swat_boundary.geojson",
    aoi_label="Swat valley\n(pre-2026 district boundary)",
)
print(fig.eofigs_layout["caption"])  # the caption sentences on limits, dots and grey
eofigs.save_figure(fig, "figures/fig2")
```

![Trend of growing-season NDVI around the Swat valley, 2001–2024](gallery/images/trend_map_swat.png)

Theil–Sen trend of growing-season NDVI (MODIS MOD13A1, 500 m, May–September median),
2001–2024, around the Swat valley (pre-2026 district boundary): the former Swat district
(before January 2026), now Swat and Bar Swat. Colours are limited to ±0.08 decade⁻¹ (98th
percentile of |slope|); 1.9 % of pixels exceed this. Dots: at least 50 % of 500 m pixels
significant (Mann–Kendall, p < 0.05). Per-pixel Mann–Kendall tests assume serial
independence and are not adjusted for multiple comparisons. Grey with diagonal hatching:
mean NDVI below 0.1 over the record (not vegetated; 14.8 % of pixels). Grey with cross-hatching: no valid trend (too
few observations; 0.8 % of pixels). Boundaries and names shown do not imply any opinion on the
legal status of any country or territory. Full code and downloads:
[gallery](gallery/trend_map_swat.md).

## How it works

1. **The trend is computed at full resolution** with [`trend`](trends.md) (Theil–Sen
   slope, Mann–Kendall test), or taken from `slope=` and `pvalue=` grids.
2. **Then it is reduced to print size**: slopes are averaged to the printed pixels;
   p-values are never averaged.
3. **Significance at print size.** The map is divided into cells of about 1.6 mm
   (`dot_spacing_mm`). A cell gets a dot (or hatching with `stipple="hatch"`) when at least
   half (`sig_fraction`) of its valid full-resolution pixels are significant. Dots are
   0.35 mm, dark with a thin white edge, so they read on both ends of the colour map.
4. **Colours** come from the variable library and are centred exactly on zero. Vegetation
   variables (indices, productivity and structure) use terracotta (browning, loss) to slate
   teal (greening, gain); other
   variables use `vik` in the physically sensible direction (see
   [Variables](variables.md)). The limits are symmetric, at the 98th percentile of
   |slope| rounded up (`limits=`), with arrows on the colour bar when values are clipped.
5. **Two masked classes in grey #BDBDBD, told apart by hatching** (plain grey would be too
   close to weak greening for colour-blind readers):
   - **not vegetated** (diagonal hatching): for vegetation indices, pixels whose mean over
     the record is below 0.1 (rock, snow, ice) are left out (`exclude=`);
   - **no valid trend** (cross-hatching): too few valid observations.

   Each class has its own legend entry and caption clause with its share of pixels, and is
   left out when it has none.

## The caption sentence

Journals expect the caption to say when colours are clipped. `trend_map` writes it with
the exact numbers:

```python
fig.eofigs_layout["caption"]
# 'Colours are limited to ±0.08 decade⁻¹ (98th percentile of |slope|); 1.9 % of pixels
#  exceed this. Dots: at least 50 % of 500 m pixels significant (Mann–Kendall, p < 0.05).
#  Per-pixel Mann–Kendall tests assume serial independence and are not adjusted for
#  multiple comparisons. Grey with diagonal hatching: mean NDVI below 0.1 over the record (not vegetated; 14.8 %
#  of pixels). Grey with cross-hatching: no valid trend (too few observations; 0.8 % of
#  pixels).'
```

`fig.eofigs_layout` also records the limits, the clipped share, the share of significant
pixels, the shares of not-vegetated and no-data pixels, the number of marks and the cell
size.

## What the dots mean

Each pixel is tested on its own. The Mann–Kendall test assumes that the values of a pixel
are serially independent; positive autocorrelation (common in vegetation and climate
series) makes it reject too often. And with thousands of pixels tested at p < 0.05, about
5 % of the pixels without any trend are marked by chance. Requiring half of the pixels in a
cell to be significant thins out isolated false positives, but it is not a correction for
multiple testing: neighbouring pixels are correlated, so false positives come in patches.
The caption says both. Wilks (2016) explains why maps of per-pixel significance overstate
results and recommends controlling the false discovery rate instead; that option is planned
for eofigs 0.2. Until then, read the dots as a guide to where trends are consistent, not as
a field significance test.

Wilks, D. S. (2016). "The stippling shows statistically significant grid points": how
research results are routinely overstated and overinterpreted, and what to do about it.
*Bulletin of the American Meteorological Society*, 97(12), 2263–2273.
[doi:10.1175/BAMS-D-15-00267.1](https://doi.org/10.1175/BAMS-D-15-00267.1)

## Latitude profile

`latitude_profile=True` adds a panel with the median and interquartile range of the
full-resolution slope in latitude bands about 2 mm tall, from valid pixels only; bands with
fewer than 20 pixels are skipped. The bands line up with the map.

![Trend map with latitude profile](gallery/images/trend_profile_swat.png)

## Inputs

| Argument | Use |
|---|---|
| `data` | a time-series cube (`time`, `y`, `x`) with a CRS; `trend` is run on it |
| `slope`, `pvalue` | precomputed grids on the same grid and CRS (dimension order may differ); without `pvalue` there are no marks |
| `alpha`, `sig_fraction`, `dot_spacing_mm`, `stipple` | the significance rule and its marks |
| `limits` | `"p98"` (default), a number, or `None` for the largest absolute slope |
| `exclude` | `"auto"`, a threshold on the record mean, a boolean grid, or `None` |
| `aoi` | study area outline; the map then shows the study area with a margin |
| `ax`, `subfigure` | draw into existing map axes or into one panel of a larger figure |

The Swat NDVI series is in
[`docs/data/swat/`](https://github.com/kmkamilkhel/eofigs/tree/main/docs/data/swat), built
by `docs/scripts/build_swat_ndvi.py` from MODIS MOD13A1 v6.1 (NASA LP DAAC, through the
Microsoft Planetary Computer); it is not part of the installed package.
