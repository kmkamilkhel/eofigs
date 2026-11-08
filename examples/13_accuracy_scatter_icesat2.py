"""Accuracy scatter: ICESat-2 against a DEM.

Terrain heights from ICESat-2 ATL08 version 7 land segments (100 m, 2019–2024; strong beams,
snow-free segments, terrain height uncertainty at most 5 m) against the Copernicus DEM
GLO-90 at the segment centres (bilinear interpolation), in the Swat valley (pre-2026
district boundary): the former Swat district (before January 2026), now Swat and Bar Swat
(geoBoundaries). ATL08 heights, given above the WGS 84 ellipsoid, are converted to EGM2008
heights, the datum of the Copernicus DEM, with PROJ and NGA's EGM2008 grid. With thousands
of segments the points are coloured by density, and the bias is the mean of DEM minus
ICESat-2. The pairs are `docs/data/swat/swat_icesat2_atl08_dem.csv`, built by
`docs/scripts/build_swat_icesat2.py`. ICESat-2: ATLAS/ICESat-2 L3A Land and Vegetation
Height, Version 7 (NASA NSIDC DAAC, doi:10.5067/ATLAS/ATL08.007). Produced using Copernicus
WorldDEM™-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided
under COPERNICUS by the European Union and ESA; all rights reserved.
"""

from pathlib import Path

import pandas as pd

import eofigs

DATA = Path(__file__).resolve().parents[1] / "docs" / "data" / "swat"

pairs = pd.read_csv(DATA / "swat_icesat2_atl08_dem.csv")

eofigs.set_style("elsevier")
fig = eofigs.accuracy_scatter(
    pairs["icesat2_height_egm2008_m"],
    pairs["dem_elevation_m"],
    variable="elevation",
    stats=("r2", "rmse", "mae", "bias", "n"),
    observed_label="ICESat-2 terrain height (m)",
    predicted_label="Copernicus DEM elevation (m)",
)

if __name__ == "__main__":
    print(fig.eofigs_layout["caption"])
    print(eofigs.save_figure(fig, "accuracy_scatter_icesat2"))
