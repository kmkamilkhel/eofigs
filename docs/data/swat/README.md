# Swat valley sample data

Sample data for the eofigs documentation and gallery: the Swat valley, Khyber Pakhtunkhwa,
Pakistan. Built by `docs/scripts/build_swat_sample.py` and `docs/scripts/build_swat_ndvi.py`
on 2026-11-08. All files are in WGS 84 / UTM zone 43N (EPSG:32643); the rasters cover the
outline plus a 6 km buffer on grids aligned to whole cells (90 m; NDVI 500 m). The 2025
season is not complete on the Planetary Computer (no composites from July to mid-November
2025), so the NDVI series ends in 2024.

These files are not part of the installed package. Licences and the required notices are
in [DATA_LICENSES.md](../../../DATA_LICENSES.md).

| File | Source | Processing | Licence |
|---|---|---|---|
| `swat_boundary.geojson` | geoBoundaries gbOpen PAK ADM2, boundary year 2019 (build December 2023), feature "Swat" | reprojected, simplified by 20 m | public domain |
| `swat_dem_90m.tif` | Copernicus DEM GLO-90, tiles N34_00_E072_00 and N35_00_E072_00 (AWS open data) | mosaicked, bilinear resampling to 90 m, int16 metres, nodata -32768; deflate, predictor 2, 256 px tiles | Copernicus DEM GLO-90 licence (attribution and no-liability notice required) |
| `swat_tree_cover_90m.tif` | ESA WorldCover 10 m 2021 v200, tile N33E072 | share (%) of class 10 (tree cover) pixels per 90 m cell (area-weighted mean of a 0/100 mask), uint8, nodata 255 | CC BY 4.0 |
| `swat_ndvi_growing_season_500m.tif` | MODIS Terra MOD13A1 v6.1, 500 m 16-day NDVI and pixel reliability, tile h23v05, through the Microsoft Planetary Computer STAC (built by `docs/scripts/build_swat_ndvi.py`) | per year 2001–2024: median of the composites starting 1 May to 30 September with reliability 0 or 1, NaN where fewer than 3 are good; nearest-neighbour reprojection to a 500 m grid (outline plus 6 km); 24 bands named by year, int16 scaled by 0.001, nodata -32768 | NASA, no restrictions (cite Didan 2021) |
| `swat_ndvi_monthly_1km.tif` | MODIS Terra MOD13A1 v6.1 as above (built by `docs/scripts/build_swat_events.py`) | per month 2001–2021: median of the 16-day composites starting in that month with reliability 0 or 1; nearest-neighbour reprojection to the 500 m grid, then the mean of 2 x 2 cells (at least 2 valid) on a 1 km grid; nodata farther than 2 km outside the outline; 252 bands named YYYY-MM, int16 scaled by 0.002, nodata -32768 | NASA, no restrictions (cite Didan 2021) |
| `swat_terraclimate_monthly.csv` | TerraClimate monthly tmax and ppt, Planetary Computer Zarr (1958–2021) | Swat-mean of the cells whose centres lie inside the outline, 2001–2021; z-scores per calendar month (2001–2021) | CC0 1.0 |
| `swat_hot_dry_events.csv` | from `swat_terraclimate_monthly.csv` | May–September months with tmax z ≥ +1 and ppt z ≤ −1; consecutive months merged; thresholds relaxed to 0.75 only if fewer than 3 events (not needed: 3 events) | CC0 1.0 |
| `swat_icesat2_atl08_dem.csv` | ICESat-2 ATL08 v007 land segments 2019–2024 (NASA NSIDC DAAC, doi:10.5067/ATLAS/ATL08.007), cut to the Swat box with NASA Harmony (built by `docs/scripts/build_swat_icesat2.py`, needs an Earthdata login) | slope-independent rule: strong beams, valid `h_te_best_fit`, snow-free land (`segment_snowcover` = 1), no cloud or blowing-snow layer (`msw_flag` = 0), at least 10 terrain photons (`n_te_photons`), centre inside the outline (27 619 segments); blunders with \|DEM − ICESat-2\| > 150 m dropped (none); random subsample of 25 000 (seed 2019); heights converted from the WGS 84 ellipsoid to EGM2008 with PROJ and NGA's 2.5-minute EGM2008 grid (`us_nga_egm08_25`; geoid undulation −27 to −39 m over Swat; ITRF2014 and WGS 84 differ by centimetres, ignored); DEM elevation and slope interpolated bilinearly from `swat_dem_90m.tif`; 25 000 rows | NASA, no restrictions (cite the dataset); DEM columns: Copernicus DEM licence |
| `swat_towns.geojson` | GeoNames (PK dump) | Mingora, Saidu Sharif, Matta, Khwazakhela, Bahrain, Kalam: populated places inside the outline, most populous match per name; `geonameid` kept | CC BY 4.0 |

**Boundary status.** The outline is the **former Swat district (before January 2026), now
Swat and Bar Swat**. The Khyber Pakhtunkhwa government divided the district by
notification of 27 January 2026 into Swat (headquarters Gulkada; Babuzai, Kabal, Charbagh
and Barikot tehsils) and Bar Swat (headquarters Matta; Matta, Bahrain and Khwazakhela
tehsils) (Dawn, 28 January 2026, https://www.dawn.com/news/1969386).

**Attribution for figures made with these files:**

Produced using Copernicus WorldDEM™-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space
GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed
by ESA WorldCover consortium. NDVI: MODIS MOD13A1 v6.1 (NASA LP DAAC). Climate: TerraClimate
(CC0 1.0). ICESat-2: ATL08 v007 (NASA NSIDC DAAC). Boundary: geoBoundaries. Towns: GeoNames (CC BY 4.0). Locator:
Natural Earth.
