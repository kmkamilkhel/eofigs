import cmcrameri.cm as cmc
import matplotlib as mpl
import numpy as np
import pytest
from PIL import Image

import eofigs
from eofigs.check import CheckReport, CheckResult


def _result(report, name):
    (result,) = [r for r in report.results if r.name == name and r.target == "figure"]
    return result


def _figure(sans_font, journal="custom", **kwargs):
    with eofigs.style(journal, font=sans_font):
        fig, ax = eofigs.new_figure("single", height_mm=60, **kwargs)
    return fig, ax


def test_clean_figure_passes(sans_font):
    fig, ax = _figure(sans_font)
    ax.plot([0, 1], [0, 1], color="#0072B2")
    ax.plot([0, 1], [1, 0], color="#E69F00")
    report = eofigs.check_figure(fig)
    assert report.passed, str(report)
    # matplotlib's default 0-1 axis has six ticks (0, 0.2, ..., 1): a warning only
    assert [r.name for r in report.warnings] == ["ticks"]
    eofigs.tidy_axes(ax)
    report = eofigs.check_figure(fig)
    assert report.warnings == [], str(report)
    assert "single width" in _result(report, "size").message


def test_small_font_fails(sans_font):
    fig, ax = _figure(sans_font)
    ax.text(0.5, 0.5, "tiny", fontsize=5)
    result = _result(eofigs.check_figure(fig), "font size")
    assert result.status == "fail"
    assert "5 pt" in result.message and "tiny" in result.message


def test_non_column_width_warns_and_too_wide_fails(sans_font):
    with eofigs.style("custom", font=sans_font):
        fig, _ = eofigs.new_figure(120, height_mm=60)
    assert _result(eofigs.check_figure(fig), "size").status == "warn"
    fig.set_size_inches(220 / 25.4, 60 / 25.4)
    assert _result(eofigs.check_figure(fig), "size").status == "fail"
    fig.set_size_inches(90 / 25.4, 260 / 25.4)
    assert "taller" in _result(eofigs.check_figure(fig), "size").message


def test_low_resolution_fails(sans_font):
    fig, _ = _figure(sans_font, journal="springer")
    result = _result(eofigs.check_figure(fig, dpi=300), "resolution")
    assert result.status == "fail" and "600 dpi" in result.message


def test_resolution_defaults_to_journal_export_dpi(sans_font):
    fig, _ = _figure(sans_font, journal="springer")
    result = _result(eofigs.check_figure(fig), "resolution")
    assert result.status == "pass" and result.message.startswith("600 dpi")


def test_fonts_outside_journal_list_warn(sans_font):
    fig, ax = _figure(sans_font, journal="springer")
    ax.set_xlabel("x")
    result = _result(eofigs.check_figure(fig), "fonts")
    assert result.status == "warn" and "DejaVu Sans" in result.message


def test_close_colours_warn_under_colour_blindness(sans_font):
    fig, ax = _figure(sans_font)
    ax.plot([0, 1], [0, 1], color="#D55E00")  # vermillion
    ax.plot([0, 1], [1, 0], color="#009E73")  # bluish green: fine in normal vision
    ax.plot([0, 1], [0.5, 0.5], color="#E05000")  # close to vermillion
    result = _result(eofigs.check_figure(fig), "colour-blind safety")
    assert result.status == "warn"
    assert "#d55e00/#e05000" in result.message


def test_bars_scatter_and_transparent_fills_are_collected(sans_font):
    fig, ax = _figure(sans_font)
    ax.bar([0, 1], [1, 2], color=["#768EAE", "#B58885"])
    ax.scatter([0, 1], [0, 1], color="#009E73")
    ax.fill_between([0, 1], [0, 0], [1, 1], color="#0072B2", alpha=0.3)
    ax.fill_between([0, 1], [0, 0], [1, 1], color="none")
    result = _result(eofigs.check_figure(fig), "colour-blind safety")
    # bar (#b58885) and scatter (#009e73) colours were both collected and compared
    assert result.status == "warn"
    assert "#009e73/#b58885 deutan" in result.message


def test_single_colour_passes(sans_font):
    fig, ax = _figure(sans_font)
    ax.plot([0, 1], [0, 1])
    assert _result(eofigs.check_figure(fig), "colour-blind safety").status == "pass"


@pytest.mark.parametrize("name", ["jet", "rainbow", "turbo", "hsv"])
def test_rainbow_colour_maps_fail(sans_font, name):
    fig, ax = _figure(sans_font)
    ax.imshow(np.random.default_rng(0).random((5, 5)), cmap=name)
    result = _result(eofigs.check_figure(fig), "colour maps")
    assert result.status == "fail" and name in result.message


@pytest.mark.parametrize(
    "cmap",
    [cmc.batlow, cmc.vik, cmc.roma, cmc.berlin, cmc.bamako_r, cmc.romaO, cmc.oleron, cmc.batlowS,
     "viridis", "RdBu_r", "twilight", "tab10"],
)  # fmt: skip
def test_good_colour_maps_pass(sans_font, cmap):
    fig, ax = _figure(sans_font)
    data = np.random.default_rng(1).random((5, 5))
    ax.imshow(data, cmap=cmap)
    ax.contourf(data, cmap=cmap)
    ax.scatter([0, 1], [0, 1], c=[0, 1], cmap=cmap)
    assert _result(eofigs.check_figure(fig), "colour maps").status == "pass"


def test_unknown_non_monotonic_map_fails(sans_font):
    fig, ax = _figure(sans_font)
    bumpy = mpl.colors.LinearSegmentedColormap.from_list(
        "bumpy", ["black", "white", "black", "white"]
    )
    ax.imshow(np.random.default_rng(2).random((5, 5)), cmap=bumpy)
    assert _result(eofigs.check_figure(fig), "colour maps").status == "fail"


def test_kind_override_from_artist(sans_font):
    fig, ax = _figure(sans_font)
    bad_sequential = mpl.colors.LinearSegmentedColormap.from_list(
        "vee", ["white", "black", "white"]
    )
    image = ax.imshow(np.random.default_rng(3).random((5, 5)), cmap=bad_sequential)
    image._eofigs_cmap_kind = "sequential"
    assert "non-monotonic" in _result(eofigs.check_figure(fig), "colour maps").message
    image._eofigs_cmap_kind = "diverging"
    assert _result(eofigs.check_figure(fig), "colour maps").status == "pass"
    image._eofigs_cmap_kind = "multi-sequential"
    two_part = mpl.colors.LinearSegmentedColormap.from_list(
        "w", ["white", "black", "white", "black"]
    )
    image.set_cmap(two_part)
    assert _result(eofigs.check_figure(fig), "colour maps").status == "fail"
    image._eofigs_cmap_kind = "diverging"
    assert _result(eofigs.check_figure(fig), "colour maps").status == "fail"


def test_empty_figure(sans_font):
    fig, ax = _figure(sans_font)
    ax.set_axis_off()
    report = eofigs.check_figure(fig)
    assert _result(report, "font size").message == "No text in the figure."
    assert _result(report, "fonts").message == "No text in the figure."


def test_pdf_fonts_type42_pass_and_type3_fail(tmp_path, sans_font):
    fig, ax = _figure(sans_font)
    ax.set_xlabel("Time (yr)")
    eofigs.save_figure(fig, tmp_path / "ok.pdf", check=False)
    (font_result,) = [
        r for r in eofigs.check_figure(tmp_path / "ok.pdf").results if r.name == "fonts"
    ]
    assert font_result.status == "pass" and "DejaVuSans" in font_result.message
    with mpl.rc_context({"pdf.fonttype": 3}):
        fig.savefig(tmp_path / "t3.pdf")
    (font_result,) = [
        r for r in eofigs.check_figure(tmp_path / "t3.pdf").results if r.name == "fonts"
    ]
    assert font_result.status == "fail" and "Type 3" in font_result.message


def test_pdf_font_list_and_size(tmp_path, sans_font):
    fig, ax = _figure(sans_font)
    ax.set_xlabel("x")
    eofigs.save_figure(fig, tmp_path / "s.pdf", check=False)
    report = eofigs.check_figure(tmp_path / "s.pdf", journal="elsevier")
    by_name = {r.name: r for r in report.results}
    assert by_name["size"].status == "pass"
    assert by_name["fonts"].status == "warn"  # DejaVu is not on Elsevier's list


def test_pdf_without_text(tmp_path, sans_font):
    fig, ax = _figure(sans_font)
    ax.set_axis_off()
    fig.savefig(tmp_path / "blank.pdf")
    results = eofigs.check_figure(tmp_path / "blank.pdf").results
    assert any(r.message.startswith("No fonts embedded") for r in results)


def test_raster_file_checks(tmp_path, sans_font):
    fig, ax = _figure(sans_font)
    ax.plot([0, 1])
    eofigs.save_figure(fig, tmp_path / "r.png", dpi=600, check=False)
    report = eofigs.check_figure(tmp_path / "r.png")
    assert report.passed, str(report)
    Image.new("RGB", (100, 100)).save(tmp_path / "nodpi.png")
    (res,) = eofigs.check_figure(tmp_path / "nodpi.png").results
    assert res.status == "fail" and "no dpi" in res.message


def test_file_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        eofigs.check_figure(tmp_path / "missing.pdf")
    (tmp_path / "f.txt").write_text("x")
    with pytest.raises(ValueError, match="Cannot check '.txt' files"):
        eofigs.check_figure(tmp_path / "f.txt")


def test_report_output():
    report = CheckReport(
        "custom",
        [CheckResult("size", "pass", "ok"), CheckResult("fonts", "fail", "Type 3", "a.pdf")],
    )
    assert not report.passed
    assert len(report.failures) == 1 and report.warnings == []
    text = str(report)
    assert "FAILED" in text and "[a.pdf]" in text
    assert report.to_dict()["results"][1]["status"] == "fail"


def test_single_colour_contours_are_not_colour_maps(sans_font):
    fig, ax = _figure(sans_font)
    data = np.random.default_rng(4).random((5, 5))
    ax.contour(data, levels=[0.5], colors="#1A1A1A")
    assert _result(eofigs.check_figure(fig), "colour maps").message == "No colour-mapped data."
