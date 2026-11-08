import warnings

import matplotlib as mpl
import pytest

import eofigs
from eofigs import styling as style_module
from eofigs._colour import OKABE_ITO


def test_set_style_applies_journal_settings(sans_font):
    eofigs.set_style("springer", font=sans_font)
    rc = mpl.rcParams
    assert rc["font.family"] == [sans_font]
    assert rc["font.size"] == 8
    assert rc["xtick.labelsize"] == 8  # never below the journal minimum
    assert rc["pdf.fonttype"] == 42
    assert rc["savefig.dpi"] == 600
    assert rc["mathtext.fontset"] == "dejavusans"
    assert [c.upper() for c in rc["axes.prop_cycle"].by_key()["color"]] == list(OKABE_ITO)
    assert style_module.current_journal() == "springer"


def test_base_size_and_bold(sans_font):
    eofigs.set_style("elsevier", font=sans_font, base_size=9, bold=True)
    assert mpl.rcParams["font.size"] == 9
    assert mpl.rcParams["xtick.labelsize"] == 8
    assert mpl.rcParams["axes.labelweight"] == "bold"


def test_serif_uses_stix_mathtext():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # Times New Roman may be missing
        eofigs.set_style("elsevier", font="serif")
    assert mpl.rcParams["mathtext.fontset"] == "stix"
    assert style_module._STATE["font_family"] == "serif"


def test_set_style_none_restores_previous_settings(sans_font):
    before = mpl.rcParams["font.size"]
    eofigs.set_style("frontiers", font=sans_font, base_size=11)
    eofigs.set_style(None)
    assert mpl.rcParams["font.size"] == before
    assert style_module.current_journal() == "custom"


def test_style_context_restores_everything(sans_font):
    before = dict(mpl.rcParams)
    with eofigs.style("mdpi", font=sans_font, labels="A"):
        assert style_module.current_journal() == "mdpi"
        assert style_module._STATE["labels"] == "A"
    assert style_module.current_journal() == "custom"
    assert mpl.rcParams["font.size"] == before["font.size"]
    assert mpl.rcParams["pdf.fonttype"] == before["pdf.fonttype"]


def test_missing_font_falls_back_with_warning(monkeypatch):
    monkeypatch.setattr(
        style_module, "_installed_fonts", lambda: {"Liberation Serif", "DejaVu Sans"}
    )
    with pytest.warns(
        UserWarning, match="'Times New Roman' is not installed; using 'Liberation Serif'"
    ):
        eofigs.set_style("elsevier", font="serif")
    assert mpl.rcParams["font.family"] == ["Liberation Serif"]


def test_unknown_named_font_falls_back_to_family(monkeypatch):
    monkeypatch.setattr(style_module, "_installed_fonts", lambda: {"DejaVu Sans"})
    with pytest.warns(UserWarning, match="'Comic Neue' is not installed"):
        eofigs.set_style("custom", font="Comic Neue")
    assert mpl.rcParams["font.family"] == ["DejaVu Sans"]


def test_no_font_at_all_uses_dejavu(monkeypatch):
    monkeypatch.setattr(style_module, "_installed_fonts", set)
    eofigs.set_style("custom", font="serif")
    assert mpl.rcParams["font.family"] == ["DejaVu Sans"]


def test_invalid_labels_and_journal(sans_font):
    with pytest.raises(ValueError, match="labels must be one of"):
        eofigs.set_style("custom", font=sans_font, labels="i")
    with pytest.raises(ValueError, match="Unknown journal"):
        eofigs.set_style("unknown", font=sans_font)


@pytest.mark.parametrize(
    ("width", "expected_mm"), [("single", 90), ("onehalf", 140), ("double", 190), (100, 100)]
)
def test_new_figure_size_in_mm(width, expected_mm):
    fig, _ = eofigs.new_figure(width, height_mm=50, journal="elsevier")
    assert fig.get_figwidth() * 25.4 == pytest.approx(expected_mm)
    assert fig.get_figheight() * 25.4 == pytest.approx(50)


def test_new_figure_default_aspect_and_grid():
    fig, axes = eofigs.new_figure("double", nrows=2, ncols=3, journal="frontiers")
    assert axes.shape == (2, 3)
    assert fig.get_figheight() * 25.4 == pytest.approx(180 * 0.75 * 2 / 3)
    fig, _ = eofigs.new_figure("single", aspect=1.0, journal="frontiers")
    assert fig.get_figheight() == pytest.approx(fig.get_figwidth())


def test_new_figure_uses_current_journal(sans_font):
    with eofigs.style("springer", font=sans_font):
        fig, _ = eofigs.new_figure("double")
    assert fig.get_figwidth() * 25.4 == pytest.approx(174)
    assert fig._eofigs_journal == "springer"


def test_new_figure_height_limits():
    with pytest.raises(ValueError, match="exceeds Springer's maximum of 234 mm"):
        eofigs.new_figure("double", height_mm=250, journal="springer")
    with pytest.raises(ValueError, match="positive"):
        eofigs.new_figure("single", height_mm=-1, journal="custom")


def test_label_panels_formats():
    _, axes = eofigs.new_figure("double", nrows=2, ncols=2, journal="custom")
    texts = eofigs.label_panels(axes, "(a)")
    assert [t.get_text() for t in texts] == ["(a)", "(b)", "(c)", "(d)"]
    _, axes = eofigs.new_figure("double", ncols=3, journal="custom")
    assert [t.get_text() for t in eofigs.label_panels(axes, "A")] == ["A", "B", "C"]
    _, axes = eofigs.new_figure("double", ncols=2, journal="custom")
    texts = eofigs.label_panels(axes, "a)", loc="inside")
    assert [t.get_text() for t in texts] == ["a)", "b)"]


def test_label_panels_defaults_bold_and_off(sans_font):
    with eofigs.style("custom", font=sans_font, labels="(A)", label_bold=True):
        _, axes = eofigs.new_figure("double", ncols=2)
        texts = eofigs.label_panels(axes)
        assert [t.get_text() for t in texts] == ["(A)", "(B)"]
        assert all(t.get_fontweight() == "bold" for t in texts)
    with eofigs.style("custom", font=sans_font, labels=None):
        _, axes = eofigs.new_figure("double", ncols=2)
        assert eofigs.label_panels(axes) == []


def test_label_panels_explicit_list_and_errors():
    _, axes = eofigs.new_figure("double", ncols=2, journal="custom")
    texts = eofigs.label_panels(axes, ["Before", "After"], bold=False, fontsize=9)
    assert [t.get_text() for t in texts] == ["Before", "After"]
    assert texts[0].get_fontweight() == "normal"
    assert texts[0].get_fontsize() == 9
    with pytest.raises(ValueError, match="2 panels but only 1 labels"):
        eofigs.label_panels(axes, ["only one"])
    with pytest.raises(ValueError, match="labels must be one of"):
        eofigs.label_panels(axes, "i.")
    with pytest.raises(ValueError, match="loc must be"):
        eofigs.label_panels(axes, "(a)", loc="below")


def test_label_single_axes():
    _, ax = eofigs.new_figure("single", journal="custom")
    assert [t.get_text() for t in eofigs.label_panels(ax, "(a)")] == ["(a)"]


def test_panel_titles_setting(sans_font):
    assert style_module.current_panel_titles() is True
    with eofigs.style("custom", font=sans_font, panel_titles=False):
        assert style_module.current_panel_titles() is False
    assert style_module.current_panel_titles() is True
