import numpy as np
import pytest
from PIL import Image

import eofigs


@pytest.fixture
def line_figure(sans_font):
    with eofigs.style("custom", font=sans_font):
        fig, ax = eofigs.new_figure("single", height_mm=60)
        x = np.linspace(0, 10, 50)
        ax.plot(x, np.sin(x), label="sin")
        ax.plot(x, np.cos(x), label="cos")
        ax.set_xlabel("Time (yr)")
        ax.legend()
        yield fig


def test_default_formats_come_from_preset(tmp_path, line_figure):
    report = eofigs.save_figure(line_figure, tmp_path / "fig1")
    assert (tmp_path / "fig1.pdf").exists()
    assert (tmp_path / "fig1.png").exists()
    assert report.passed, str(report)
    targets = {r.target for r in report.results}
    assert {"figure", "fig1.pdf", "fig1.png"} <= targets


def test_suffix_selects_single_format(tmp_path, line_figure):
    eofigs.save_figure(line_figure, tmp_path / "sub" / "fig2.png", check=False)
    assert sorted(p.name for p in (tmp_path / "sub").iterdir()) == ["fig2.png"]


def test_png_has_exact_size_and_dpi(tmp_path, line_figure):
    eofigs.save_figure(line_figure, tmp_path / "fig.png", dpi=600, check=False)
    with Image.open(tmp_path / "fig.png") as im:
        # matplotlib truncates: 90 mm at 600 dpi is 2125.98 px -> 2125 px
        assert im.size == (int(90 / 25.4 * 600), int(60 / 25.4 * 600))
        assert im.info["dpi"][0] == pytest.approx(600, abs=0.01)


def test_tiff_is_lzw_compressed(tmp_path, line_figure):
    eofigs.save_figure(line_figure, tmp_path / "fig", formats=("tiff",), check=False)
    with Image.open(tmp_path / "fig.tiff") as im:
        assert im.info["compression"] == "tiff_lzw"


def test_journal_default_formats(tmp_path, sans_font):
    with eofigs.style("springer", font=sans_font):
        fig, ax = eofigs.new_figure("single")
        ax.plot([0, 1], [0, 1])
        eofigs.save_figure(fig, tmp_path / "s", check=False)
    assert sorted(p.suffix for p in tmp_path.iterdir()) == [".eps", ".pdf", ".tiff"]


def test_size_px_sets_exact_pixels(tmp_path, line_figure):
    eofigs.save_figure(line_figure, tmp_path / "px.png", size_px=1800, check=False)
    with Image.open(tmp_path / "px.png") as im:
        assert im.size[0] == 1800
    height = int(60 / 90 * 1800)
    eofigs.save_figure(line_figure, tmp_path / "px2.png", size_px=(1800, height), check=False)
    with pytest.raises(ValueError, match="does not match the figure's aspect ratio"):
        eofigs.save_figure(line_figure, tmp_path / "px3.png", size_px=(1800, 1800))
    with pytest.raises(ValueError, match="positive"):
        eofigs.save_figure(line_figure, tmp_path / "px4.png", size_px=0)


def test_pdf_output_is_deterministic(tmp_path, line_figure):
    eofigs.save_figure(line_figure, tmp_path / "a.pdf", check=False)
    eofigs.save_figure(line_figure, tmp_path / "b.pdf", check=False)
    assert (tmp_path / "a.pdf").read_bytes() == (tmp_path / "b.pdf").read_bytes()


def test_svg_and_jpeg_formats(tmp_path, line_figure):
    eofigs.save_figure(line_figure, tmp_path / "v", formats=("svg", "jpg"), check=False)
    assert (tmp_path / "v.svg").exists()
    assert (tmp_path / "v.jpg").exists()


def test_unsupported_format(tmp_path, line_figure):
    with pytest.raises(ValueError, match="Unsupported format"):
        eofigs.save_figure(line_figure, tmp_path / "x", formats=("docx",))


def test_check_false_returns_none(tmp_path, line_figure):
    assert eofigs.save_figure(line_figure, tmp_path / "n.pdf", check=False) is None


def test_pdf_fonts_embedded_even_outside_style(tmp_path):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(90 / 25.4, 60 / 25.4))
    ax.set_xlabel("Time")
    eofigs.save_figure(fig, tmp_path / "plain.pdf", journal="custom", check=False)
    assert b"/Type3" not in (tmp_path / "plain.pdf").read_bytes()
