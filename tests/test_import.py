import re

import eofigs


def test_version_is_pep440_string():
    assert re.fullmatch(r"\d+\.\d+\.\d+(\.dev\d+|rc\d+)?", eofigs.__version__)


def test_public_api():
    assert set(eofigs.__all__) == {
        "CheckReport",
        "CheckResult",
        "FigureSet",
        "Variable",
        "__version__",
        "add_inset",
        "add_north_arrow",
        "add_scale_bar",
        "check_figure",
        "cvd_preview",
        "event_composite",
        "figure_set",
        "fit_raster",
        "label_panels",
        "new_figure",
        "palettes",
        "register_variable",
        "save_figure",
        "set_style",
        "study_area_map",
        "style",
        "tidy_axes",
        "trend",
        "trend_map",
        "variable",
    }
    for name in eofigs.__all__:
        assert hasattr(eofigs, name)
