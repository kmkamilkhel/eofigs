import cmcrameri.cm as cmc
import matplotlib as mpl
import numpy as np
import pytest

from eofigs import _colour as colour

# Sharma, Wu & Dalal (2005), CIEDE2000 test data, pairs 1, 2 and 7.
SHARMA = [
    ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
    ((50.0, 3.1571, -77.2803), (50.0, 0.0, -82.7485), 2.8615),
    ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((50.0, 2.5, 0.0), (50.0, 0.0, -2.5), 4.3065),
]


@pytest.mark.parametrize(("lab1", "lab2", "expected"), SHARMA)
def test_ciede2000_reference_values(lab1, lab2, expected):
    assert colour.delta_e2000(lab1, lab2) == pytest.approx(expected, abs=1e-4)


def test_ciede2000_grey_pair():
    assert colour.delta_e2000((50, 0, 0), (60, 0, 0)) > 0


def test_lab_of_white_and_black():
    lab = colour.to_lab(np.array([[1.0, 1.0, 1.0], [0.0, 0.0, 0.0]]))
    assert lab[0] == pytest.approx([100, 0, 0], abs=0.01)
    assert lab[1] == pytest.approx([0, 0, 0], abs=0.01)


def test_cvd_simulation_keeps_greys_and_merges_red_green():
    grey = np.array([0.5, 0.5, 0.5])
    for kind in ("protan", "deutan", "tritan"):
        assert colour.simulate_cvd(grey, kind) == pytest.approx(grey, abs=0.01)
    red, green = np.array([0.8, 0.2, 0.2]), np.array([0.3, 0.6, 0.2])
    normal = colour.delta_e2000(*colour.to_lab(np.array([red, green])))
    deutan = colour.delta_e2000(
        *colour.to_lab(colour.simulate_cvd(np.array([red, green]), "deutan"))
    )
    assert deutan < normal / 2


CMCRAMERI = [
    n
    for n in dir(cmc)
    if not n.startswith("_") and isinstance(getattr(cmc, n), mpl.colors.Colormap)
]


@pytest.mark.parametrize("name", CMCRAMERI)
def test_every_cmcrameri_map_passes_its_class(name):
    cmap = getattr(cmc, name)
    kind = colour.classify_cmap(cmap)
    assert kind in {"sequential", "diverging", "multi-sequential", "cyclic", "categorical"}
    lightness = colour.cmap_lightness(cmap)
    if kind == "sequential":
        assert colour.is_monotonic(lightness)
    elif kind == "diverging":
        assert colour.diverging_ok(lightness)
    elif kind == "multi-sequential":
        assert colour.multi_sequential_ok(lightness)


def test_classification_by_profile():
    ramp = mpl.colors.LinearSegmentedColormap.from_list("ramp_x", ["#000000", "#ffffff"])
    vee = mpl.colors.LinearSegmentedColormap.from_list("vee_x", ["#2b5f9e", "#ffffff", "#9e2b2b"])
    bumpy = mpl.colors.LinearSegmentedColormap.from_list("bumpy_x", ["k", "w", "k", "w"])
    assert colour.classify_cmap(ramp) == "sequential"
    assert colour.classify_cmap(vee) == "diverging"
    assert colour.classify_cmap(bumpy) == "unknown"
    assert colour.classify_cmap(mpl.colormaps["jet_r"]) == "banned"
    assert colour.base_cmap_name(cmc.vik_r) == "vik"
