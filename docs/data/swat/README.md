# Swat valley sample data

Sample data for the eofigs documentation and gallery: the Swat valley, Khyber Pakhtunkhwa,
Pakistan. Built by `docs/scripts/build_swat_sample.py` on 2026-11-08. All files are in
WGS 84 / UTM zone 43N (EPSG:32643); the rasters cover the outline plus a 6 km buffer on a
90 m grid aligned to whole cells.

These files are not part of the installed package. Licences and the required notices are
in [DATA_LICENSES.md](../../../DATA_LICENSES.md).

| File | Source | Processing | Licence |
|---|---|---|---|
| `swat_boundary.geojson` | geoBoundaries gbOpen PAK ADM2, boundary year 2019 (build December 2023), feature "Swat" | reprojected, simplified by 20 m | public domain |
| `swat_dem_90m.tif` | Copernicus DEM GLO-90, tiles N34_00_E072_00 and N35_00_E072_00 (AWS open data) | mosaicked, bilinear resampling to 90 m, int16 metres, nodata -32768; deflate, predictor 2, 256 px tiles | Copernicus DEM GLO-90 licence (attribution and no-liability notice required) |
| `swat_tree_cover_90m.tif` | ESA WorldCover 10 m 2021 v200, tile N33E072 | share (%) of class 10 (tree cover) pixels per 90 m cell (area-weighted mean of a 0/100 mask), uint8, nodata 255 | CC BY 4.0 |
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
by ESA WorldCover consortium. Boundary: geoBoundaries. Towns: GeoNames (CC BY 4.0). Locator:
Natural Earth.
