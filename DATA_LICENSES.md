# Data licences

The eofigs **code** is released under the MIT licence (see [LICENSE](LICENSE)). The data
files listed here keep their own licences.

## Bundled with the package

| File | Source | Licence |
|---|---|---|
| `src/eofigs/data/ne_110m_countries.geojson` | [Natural Earth](https://www.naturalearthdata.com/) 1:110m admin-0 countries, version 5.1.2 (default, de facto boundaries); attributes reduced to code and name, coordinates rounded to 0.001° | Public domain. No permission is needed; "Made with Natural Earth" is appreciated. |

Worldview boundaries that eofigs downloads on request (`worldview=` in `add_inset` and
`study_area_map`) are Natural Earth 1:10m admin-0 point-of-view layers, version 5.1.2,
also public domain. They are stored in the user's cache folder, not in the package.

Boundaries and names shown do not imply any opinion on the legal status of any country or
territory.

## Documentation sample data (`docs/data/`)

These files are in the GitHub repository and used by the documentation and gallery. They
are **not** part of the installed package (wheel) or the source distribution.

### `docs/data/swat/swat_dem_90m.tif`: Copernicus DEM GLO-90

Derived from the Copernicus DEM GLO-90 (COP-DEM-GLO-90-F, DOI 10.5270/ESA-c5d3d65) under
the "Licence for COP-DEM-GLO-90-F Global 90m Full, Free & Open". The tiles were mosaicked,
reprojected and resampled (see `docs/data/swat/README.md`), so the notice for adapted data
applies:

> produced using Copernicus WorldDEM™-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space
> GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.

> The organisations in charge of the Copernicus programme by law or by delegation do not
> incur any liability for any use of the Copernicus WorldDEM™-90.

Anyone who redistributes this file, modified or not, is bound by the same obligations
(Article 6 of the licence): give the notice above, keep the no-liability sentence, do not
suggest endorsement by the Copernicus programme, and pass these obligations on.

### `docs/data/swat/swat_tree_cover_90m.tif`: ESA WorldCover 2021

Derived from ESA WorldCover 10 m 2021 v200 (Zanaga et al. 2022,
doi:10.5281/zenodo.7254221), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Changed: share of class 10
(tree cover) pixels in each 90 m cell.

> © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021)
> processed by ESA WorldCover consortium

### `docs/data/swat/swat_boundary.geojson`: geoBoundaries

Swat district outline from geoBoundaries gbOpen PAK ADM2 (boundary year 2019; Runfola et al.
2020, doi:10.1371/journal.pone.0231866), public domain. It shows the **former Swat district
(before January 2026), now Swat and Bar Swat**. Reprojected to UTM zone 43N and simplified
by 20 m.

### `docs/data/swat/swat_towns.geojson`: GeoNames

Six towns from [GeoNames](https://www.geonames.org/), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Changed: selected by name and
reprojected to UTM zone 43N.

### `docs/data/swat/swat_ndvi_growing_season_500m.tif`: MODIS MOD13A1

Derived from MODIS Terra Vegetation Indices 16-Day L3 Global 500 m, version 6.1 (MOD13A1;
Didan 2021, doi:10.5067/MODIS/MOD13A1.061), distributed by the NASA EOSDIS Land Processes
Distributed Active Archive Center (LP DAAC) and accessed through the Microsoft Planetary
Computer. NASA data have no restrictions on reuse, sale or redistribution; the citation
above is requested. Changed: May–September median NDVI per year of the composites with pixel
reliability 0 or 1 (at least three per year), reprojected to UTM zone 43N at 500 m.

### `docs/data/swat/swat_ndvi_monthly_1km.tif`: MODIS MOD13A1

From the same MODIS MOD13A1 v6.1 product (Didan 2021). Changed: monthly median NDVI
2001–2021 of the composites with pixel reliability 0 or 1, reprojected to UTM zone 43N,
averaged to 1 km and limited to the outline plus 2 km.

### `docs/data/swat/swat_terraclimate_monthly.csv` and `swat_hot_dry_events.csv`: TerraClimate

Derived from TerraClimate (Abatzoglou et al. 2018, doi:10.1038/sdata.2017.191), released
under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) and accessed through the
Microsoft Planetary Computer. Changed: Swat-mean monthly maximum temperature and
precipitation 2001–2021, their z-scores per calendar month, and the hot-dry event table.

### `docs/data/swat/swat_icesat2_atl08_dem.csv`: ICESat-2 ATL08 and Copernicus DEM

ICESat-2 terrain heights from ATLAS/ICESat-2 L3A Land and Vegetation Height, Version 7
(NASA National Snow and Ice Data Center DAAC, doi:10.5067/ATLAS/ATL08.007). NSIDC states that
these data are freely, openly and fully available to use without restrictions, provided
the data are cited. Changed: filtered land segments over Swat, heights converted from the
WGS 84 ellipsoid to EGM2008 heights. The DEM columns are interpolated from
`swat_dem_90m.tif`, so the Copernicus DEM notice above applies to them as well.

## References

- Abatzoglou, J. T., Dobrowski, S. Z., Parks, S. A., & Hegewisch, K. C. (2018). TerraClimate,
  a high-resolution global dataset of monthly climate and climatic water balance from
  1958–2015. *Scientific Data* 5: 170191. https://doi.org/10.1038/sdata.2017.191

- Didan, K. (2021). MODIS/Terra Vegetation Indices 16-Day L3 Global 500m SIN Grid V061.
  NASA EOSDIS Land Processes Distributed Active Archive Center.
  https://doi.org/10.5067/MODIS/MOD13A1.061

- NASA National Snow and Ice Data Center DAAC. ATLAS/ICESat-2 L3A Land and Vegetation
  Height, Version 7. https://doi.org/10.5067/ATLAS/ATL08.007
- Piñeiro, G., Perelman, S., Guerschman, J. P., & Paruelo, J. M. (2008). How to evaluate
  models: Observed vs. predicted or predicted vs. observed? *Ecological Modelling* 216:
  316–322. https://doi.org/10.1016/j.ecolmodel.2008.05.006
- Runfola, D., et al. (2020). geoBoundaries: A global database of political administrative
  boundaries. *PLoS ONE* 15(4): e0231866. https://doi.org/10.1371/journal.pone.0231866
- Zanaga, D., et al. (2022). ESA WorldCover 10 m 2021 v200. Zenodo.
  https://doi.org/10.5281/zenodo.7254221
- European Space Agency, Airbus (2022). Copernicus DEM. https://doi.org/10.5270/ESA-c5d3d65
