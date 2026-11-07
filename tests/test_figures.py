import csv

import pytest

import eofigs
from eofigs.figures import MANIFEST


@pytest.fixture
def make_fig(sans_font):
    def _make(fontsize=8):
        with eofigs.style("custom", font=sans_font):
            fig, ax = eofigs.new_figure("single", height_mm=60)
            ax.plot([0, 1], [0, 1])
            ax.set_xlabel("x", fontsize=fontsize)
        return fig

    return _make


def _manifest(folder):
    with (folder / MANIFEST).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_numbering_and_manifest(tmp_path, make_fig):
    figs = eofigs.figure_set(tmp_path, journal="custom", formats=("pdf", "png"))
    figs.add("study_area", make_fig(), caption="Study area in the Swat valley.")
    figs.add("trend", make_fig())
    figs.add("accuracy", make_fig(), supplementary=True)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == [
        "Fig01_study_area.pdf", "Fig01_study_area.png", "Fig02_trend.pdf", "Fig02_trend.png",
        "FigS01_accuracy.pdf", "FigS01_accuracy.png", MANIFEST,
    ]  # fmt: skip
    rows = _manifest(tmp_path)
    assert [r["label"] for r in rows] == ["Fig. 1", "Fig. 2", "Fig. S1"]
    assert rows[0]["caption"] == "Study area in the Swat valley."
    assert rows[0]["files"] == "Fig01_study_area.pdf;Fig01_study_area.png"
    assert rows[0]["width_mm"] == "90.0" and rows[0]["height_mm"] == "60.0"
    assert rows[0]["dpi"] == "600" and rows[0]["check"] == "passed"
    assert rows[2]["supplementary"] == "yes"
    assert len(figs) == 3
    assert "2 main, 1 supplementary" in repr(figs)


def test_failed_check_is_recorded(tmp_path, make_fig):
    figs = eofigs.figure_set(tmp_path, journal="custom", formats=("png",))
    figs.add("tiny", make_fig(fontsize=4))
    row = _manifest(tmp_path)[0]
    assert row["check"] == "failed"
    assert "fail: font size [figure]" in row["problems"]


def test_check_can_be_skipped(tmp_path, make_fig):
    figs = eofigs.figure_set(tmp_path, journal="custom", formats=("png",))
    figs.add("quick", make_fig(), check=False)
    assert _manifest(tmp_path)[0]["check"] == "not run"


def test_replace_keeps_number_and_removes_old_files(tmp_path, make_fig):
    figs = eofigs.figure_set(tmp_path, journal="custom", formats=("pdf", "png"))
    figs.add("a", make_fig())
    figs.add("b", make_fig())
    figs.formats = ("png",)
    figs.add("a", make_fig(), caption="new")
    assert not (tmp_path / "Fig01_a.pdf").exists()
    assert (tmp_path / "Fig01_a.png").exists()
    assert [e["label"] for e in figs.entries] == ["Fig. 1", "Fig. 2"]
    assert figs.entries[0]["caption"] == "new"


def test_moving_to_supplementary_renumbers(tmp_path, make_fig):
    figs = eofigs.figure_set(tmp_path, journal="custom", formats=("png",))
    for name in ("a", "b", "c"):
        figs.add(name, make_fig())
    figs.add("a", make_fig(), supplementary=True)
    assert sorted(p.name for p in tmp_path.glob("*.png")) == [
        "Fig01_b.png", "Fig02_c.png", "FigS01_a.png",
    ]  # fmt: skip


def test_order_renames_files(tmp_path, make_fig):
    figs = eofigs.figure_set(tmp_path, journal="custom", formats=("png",))
    for name in ("a", "b", "c"):
        figs.add(name, make_fig())
    figs.order(["c", "a", "b"])
    assert sorted(p.name for p in tmp_path.glob("*.png")) == [
        "Fig01_c.png", "Fig02_a.png", "Fig03_b.png",
    ]  # fmt: skip
    assert [r["name"] for r in _manifest(tmp_path)] == ["c", "a", "b"]
    assert [r["label"] for r in _manifest(tmp_path)] == ["Fig. 1", "Fig. 2", "Fig. 3"]
    with pytest.raises(ValueError, match="needs every main figure exactly once"):
        figs.order(["a", "b"])
    with pytest.raises(ValueError, match="exactly once"):
        figs.order(["a", "a", "b"])


def test_resume_from_manifest(tmp_path, make_fig):
    first = eofigs.figure_set(tmp_path, journal="custom", formats=("png",))
    first.add("a", make_fig())
    first.add("s", make_fig(), supplementary=True)
    again = eofigs.figure_set(tmp_path, journal="custom", formats=("png",))
    assert again.exists("a") and again.exists("s") and not again.exists("b")
    again.add("b", make_fig())
    assert [e["label"] for e in again.entries] == ["Fig. 1", "Fig. 2", "Fig. S1"]
    (tmp_path / "Fig01_a.png").unlink()
    assert not again.exists("a")


def test_line_art_and_journal_defaults(tmp_path, sans_font):
    with eofigs.style("springer", font=sans_font):
        fig, ax = eofigs.new_figure("single", height_mm=60)
        ax.plot([0, 1], [0, 1])
        figs = eofigs.figure_set(tmp_path, art="line")
        files = figs.add("chart", fig)
    assert figs.journal == "springer"
    assert sorted(p.suffix for p in files) == [".eps", ".pdf", ".tiff"]
    assert figs.entries[0]["dpi"] == 1200 and figs.entries[0]["art"] == "line"


def test_invalid_names_and_art(tmp_path, make_fig):
    figs = eofigs.figure_set(tmp_path, journal="custom", formats=("png",))
    for bad in ("", "has space", "../escape", "_hidden"):
        with pytest.raises(ValueError, match="Invalid figure name"):
            figs.add(bad, make_fig())
    with pytest.raises(ValueError, match="art must be one of"):
        eofigs.figure_set(tmp_path, art="photo")
