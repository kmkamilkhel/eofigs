import matplotlib as mpl
import numpy as np
import pytest
import xarray as xr

import eofigs
from eofigs import variables as variables_module
from eofigs._colour import classify_cmap
from eofigs.variables import Variable, cf_units_to_mathtext, variable_names


@pytest.fixture(autouse=True)
def _clean_registry():
    saved = dict(variables_module._REGISTERED)
    yield
    variables_module._REGISTERED.clear()
    variables_module._REGISTERED.update(saved)


@pytest.mark.parametrize("name", variable_names())
def test_every_bundled_variable_is_consistent(name):
    var = eofigs.variable(name)
    assert var.name == name
    assert var.long_name and var.symbol
    assert "⁻" not in var.units and "²" not in var.units  # mathtext, not Unicode superscripts
    expected = {"continuous": "sequential", "diverging": "diverging"}[var.kind]
    assert classify_cmap(var.get_cmap()) == expected
    assert classify_cmap(mpl.colormaps[var.anomaly_cmap]) == "diverging"


def test_library_size_and_examples():
    assert len(variable_names()) >= 20
    assert eofigs.variable("ndvi").cmap == "cmc.bamako_r"
    assert eofigs.variable("lst").cmap == "cmc.lajolla"
    assert eofigs.variable("precipitation").cmap == "cmc.davos_r"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("NDVI", "ndvi"),
        ("Leaf area index", "lai"),
        ("leaf_area_index", "lai"),
        ("gross primary production", "gpp"),
        ("rainfall", "precipitation"),
        ("DEM", "elevation"),
        ("surface_altitude", "elevation"),
    ],
)
def test_lookup_by_name_alias_and_standard_name(query, expected):
    assert eofigs.variable(query).name == expected


def test_unknown_variable_suggests_close_names():
    with pytest.raises(ValueError, match="Did you mean .*ndvi"):
        eofigs.variable("ndiv")
    with pytest.raises(ValueError, match="Unknown variable 'zzz'. Available:"):
        eofigs.variable("zzz")


def test_variable_object_passes_through():
    var = eofigs.variable("gpp")
    assert eofigs.variable(var) is var


def test_labels():
    assert eofigs.variable("gpp").label == "Gross primary productivity (gC m$^{-2}$ d$^{-1}$)"
    assert eofigs.variable("gpp").short_label == "GPP (gC m$^{-2}$ d$^{-1}$)"
    assert eofigs.variable("ndvi").label == "Normalized Difference Vegetation Index"
    assert eofigs.variable("ndvi").short_label == "NDVI"


def test_anomaly_and_trend():
    anomaly = eofigs.variable("ndvi").anomaly()
    assert anomaly.kind == "diverging" and anomaly.cmap == "cmc.vik_r"
    assert anomaly.vmin is None and anomaly.units == ""
    trend = eofigs.variable("gpp").trend("year")
    assert trend.units == "gC m$^{-2}$ d$^{-1}$ yr$^{-1}$"
    assert trend.long_name == "Gross primary productivity trend"
    assert eofigs.variable("ndvi").trend().units == "decade$^{-1}$"
    assert eofigs.variable("lst").trend().cmap == "cmc.vik"
    with pytest.raises(ValueError, match="per must be one of"):
        eofigs.variable("ndvi").trend("month")


def _da(name=None, **attrs):
    return xr.DataArray(np.zeros((2, 2)), dims=("y", "x"), name=name, attrs=attrs)


def test_recognise_dataarray():
    assert eofigs.variable(_da("NDVI")).name == "ndvi"
    assert eofigs.variable(_da("band1", standard_name="leaf_area_index")).name == "lai"
    assert eofigs.variable(_da("x", long_name="Soil moisture")).name == "soil_moisture"


def test_dataarray_units_override_library_units():
    var = eofigs.variable(_da("lst", units="K"))
    assert var.units == "K"
    var = eofigs.variable(_da("gpp", units="kg m-2 s-1"))
    assert var.units == "kg m$^{-2}$ s$^{-1}$"
    var = eofigs.variable(_da("gpp", units="gC m-2 d-1"))
    assert var.units == "gC m$^{-2}$ d$^{-1}$"


def test_unrecognised_dataarray():
    with pytest.raises(ValueError, match="Could not recognise the variable from \\['band_7'\\]"):
        eofigs.variable(_da("band_7"))
    with pytest.raises(ValueError, match="an unnamed DataArray"):
        eofigs.variable(_da())


@pytest.mark.parametrize(
    ("cf", "mathtext"),
    [
        ("kg m-2 s-1", "kg m$^{-2}$ s$^{-1}$"),
        ("m^3 m^-3", "m$^{3}$ m$^{-3}$"),
        ("degC", "$\\degree$C"),
        ("1", ""),
        ("m", "m"),
        ("m1", "m"),
        ("gC m**-2", "gC m$^{-2}$"),
        ("W m$^{-2}$", "W m$^{-2}$"),
    ],
)
def test_cf_units_to_mathtext(cf, mathtext):
    assert cf_units_to_mathtext(cf) == mathtext


def test_register_variable():
    var = eofigs.register_variable(
        "Chlorophyll index", long_name="Chlorophyll index", symbol="CI", aliases=["ci"]
    )
    assert var.name == "chlorophyll_index"
    assert eofigs.variable("ci") is var
    assert "chlorophyll_index" in variable_names()
    with pytest.raises(ValueError, match="already exists"):
        eofigs.register_variable("chlorophyll_index", long_name="x")
    with pytest.raises(ValueError, match="already exists"):
        eofigs.register_variable("ndvi", long_name="x")
    replaced = eofigs.register_variable("ndvi", long_name="My NDVI", overwrite=True)
    assert eofigs.variable("ndvi") is replaced
    with pytest.raises(ValueError, match="needs long_name"):
        eofigs.register_variable("other")


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"kind": "ordinal"}, "kind must be one of"),
        ({"cmap": "not_a_map"}, "is not a registered colour map"),
        ({"vmin": 1.0, "vmax": 0.0}, "must be smaller than vmax"),
    ],
)
def test_invalid_fields(fields, message):
    with pytest.raises(ValueError, match=message):
        Variable(name="x", long_name="X", symbol="X", **fields)
