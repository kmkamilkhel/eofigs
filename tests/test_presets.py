import re

import pytest

from eofigs._presets import get_journal, journal_keys, resolve_width

EXPECTED = {"elsevier", "springer", "mdpi", "wiley", "frontiers", "taylor_francis", "custom"}


def test_all_presets_present():
    assert set(journal_keys()) == EXPECTED


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_preset_fields_are_valid(key):
    j = get_journal(key)
    assert j.widths_mm and all(v > 0 for v in j.widths_mm.values())
    assert "single" in j.widths_mm and "double" in j.widths_mm
    assert j.widths_mm["single"] < j.widths_mm["double"]
    assert 100 < j.max_height_mm <= 300
    assert 5 <= j.min_font_pt <= j.base_font_pt <= 12
    assert j.font_family in {"serif", "sans-serif"}
    assert set(j.dpi) == {"line", "halftone", "combination"}
    assert j.export_dpi >= j.required_dpi("combination")
    assert j.export_dpi_for("line") >= j.required_dpi("line")
    assert "pdf" in j.formats
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", j.checked)
    if key != "custom":
        assert j.source_url.startswith("https://")


def test_published_values():
    assert get_journal("elsevier").widths_mm["double"] == 190
    assert get_journal("springer").widths_mm["single"] == 84
    assert get_journal("springer").max_height_mm == 234
    assert get_journal("frontiers").widths_mm["double"] == 180
    assert get_journal("frontiers").min_font_pt == 8


@pytest.mark.parametrize("alias", ["tandf", "T&F", "Taylor-Francis", " taylor_francis "])
def test_aliases(alias):
    assert get_journal(alias).key == "taylor_francis"


def test_unknown_journal_lists_choices():
    with pytest.raises(ValueError, match="Available presets: custom, elsevier"):
        get_journal("nature")


def test_resolve_width():
    j = get_journal("elsevier")
    assert resolve_width("onehalf", j) == 140
    assert resolve_width(120, j) == 120
    with pytest.raises(ValueError, match="Unknown width 'triple'"):
        resolve_width("triple", j)
    with pytest.raises(ValueError, match="wider than Elsevier's full width"):
        resolve_width(200, j)
    with pytest.raises(ValueError, match="positive"):
        resolve_width(0, j)


def test_required_dpi_by_artwork_type():
    assert get_journal("elsevier").required_dpi("line") == 1000
    assert get_journal("elsevier").required_dpi("halftone") == 300
    assert get_journal("springer").export_dpi_for("line") == 1200
    assert get_journal("elsevier").export_dpi_for("halftone") == 600
    with pytest.raises(ValueError, match="art must be one of"):
        get_journal("elsevier").required_dpi("photo")
