# Variables

The variable library fixes how each Earth observation variable is named, labelled and
coloured, so NDVI or land surface temperature look the same in every figure of a paper.

```python
import eofigs

ndvi = eofigs.variable("NDVI")  # by name, alias or CF standard name
ndvi.label  # 'Normalized Difference Vegetation Index'
ndvi.cmap  # 'cmc.bamako_r'

gpp = eofigs.variable("gpp")
gpp.short_label  # 'GPP (gC m$^{-2}$ d$^{-1}$)'
gpp.trend("year").units  # 'gC m$^{-2}$ d$^{-1}$ yr$^{-1}$'
gpp.anomaly().cmap  # 'cmc.vik_r', zero-centred

eofigs.variable(dataarray)  # recognised from standard_name, long_name or name
```

Anomalies and trends of any variable switch to a zero-centred diverging colour map.
For vegetation and water variables, negative values (browning, drying) are brown and
positive values blue (`cmc.vik_r`); for temperature, negative values are blue and positive
values red (`cmc.vik`).

## Units

Units are written in matplotlib mathtext (`gC m$^{-2}$ d$^{-1}$`), which every journal
font can typeset; Unicode superscripts such as "⁻¹" are missing from some fonts. The
library units are the units the data are expected in: eofigs never converts units. When a
DataArray has a `units` attribute that differs from the library, `variable()` uses the
data's units instead (CF strings such as `kg m-2 s-1` are written in mathtext).

## Your own variables

```python
eofigs.register_variable(
    "cci",
    long_name="Chlorophyll carotenoid index",
    symbol="CCI",
    cmap="cmc.bamako_r",
    vmin=-0.5,
    vmax=0.5,
)
```

Registered variables are found by `variable()` and every recipe for the rest of the
session. A `Variable` object can also be passed directly wherever a variable name is accepted.

## Bundled variables

Colour maps follow perceptually uniform cmcrameri maps: `bamako_r` for vegetation, `davos_r`
for water, `lajolla` for temperature (bright = hot) and `lajolla_r` for burn severity (dark = severe), `batlow` for terrain.

| Name | Long name | Symbol | Units | Colour map | Anomaly and trend map | Default range |
|---|---|---|---|---|---|---|
| `agb` | Aboveground biomass | AGB | Mg ha<sup>-1</sup> | `cmc.bamako_r` | `cmc.vik_r` | 0 to 400 |
| `air_temperature` | Air temperature | T<sub>a</sub> | °C | `cmc.lajolla` | `cmc.vik` | from data |
| `canopy_height` | Canopy height | h | m | `cmc.bamako_r` | `cmc.vik_r` | 0 to 50 |
| `dnbr` | Differenced Normalized Burn Ratio | dNBR | – | `cmc.lajolla_r` | `cmc.vik` | -0.25 to 1 |
| `elevation` | Elevation | z | m | `cmc.batlow` | `cmc.vik` | from data |
| `evapotranspiration` | Evapotranspiration | ET | mm d<sup>-1</sup> | `cmc.davos_r` | `cmc.vik_r` | 0 to data |
| `evi` | Enhanced Vegetation Index | EVI | – | `cmc.bamako_r` | `cmc.vik_r` | 0 to 1 |
| `fapar` | Fraction of absorbed photosynthetically active radiation | FAPAR | – | `cmc.bamako_r` | `cmc.vik_r` | 0 to 1 |
| `gpp` | Gross primary productivity | GPP | gC m<sup>-2</sup> d<sup>-1</sup> | `cmc.bamako_r` | `cmc.vik_r` | 0 to 15 |
| `kndvi` | Kernel NDVI | kNDVI | – | `cmc.bamako_r` | `cmc.vik_r` | 0 to 1 |
| `lai` | Leaf area index | LAI | m<sup>2</sup> m<sup>-2</sup> | `cmc.bamako_r` | `cmc.vik_r` | 0 to 7 |
| `lst` | Land surface temperature | LST | °C | `cmc.lajolla` | `cmc.vik` | from data |
| `ndvi` | Normalized Difference Vegetation Index | NDVI | – | `cmc.bamako_r` | `cmc.vik_r` | 0 to 1 |
| `nirv` | Near-infrared reflectance of vegetation | NIR<sub>v</sub> | – | `cmc.bamako_r` | `cmc.vik_r` | 0 to 0.5 |
| `npp` | Net primary productivity | NPP | gC m<sup>-2</sup> yr<sup>-1</sup> | `cmc.bamako_r` | `cmc.vik_r` | 0 to 1500 |
| `precipitation` | Precipitation | P | mm | `cmc.davos_r` | `cmc.vik_r` | 0 to data |
| `sif` | Solar-induced chlorophyll fluorescence | SIF | mW m<sup>-2</sup> nm<sup>-1</sup> sr<sup>-1</sup> | `cmc.bamako_r` | `cmc.vik_r` | 0 to 2 |
| `soil_moisture` | Soil moisture | SM | m<sup>3</sup> m<sup>-3</sup> | `cmc.davos_r` | `cmc.vik_r` | 0 to 0.5 |
| `spei` | Standardised Precipitation-Evapotranspiration Index | SPEI | – | `cmc.vik_r` | `cmc.vik_r` | -3 to 3 |
| `terrain_slope` | Terrain slope | Slope | ° | `cmc.batlow` | `cmc.vik` | 0 to 60 |
| `tree_cover` | Tree cover | TC | % | `cmc.bamako_r` | `cmc.vik_r` | 0 to 100 |
| `vod` | Vegetation optical depth | VOD | – | `cmc.bamako_r` | `cmc.vik_r` | 0 to 1.5 |

The table is generated from `eofigs/data/variables.json`, which the R version of eofigs
will share.
