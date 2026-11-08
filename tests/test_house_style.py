import warnings

import matplotlib as mpl
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import pytest
from PIL import Image

import eofigs
from eofigs import palettes
from eofigs._colour import (
    classify_cmap,
    cmap_lightness,
    delta_e2000,
    diverging_ok,
    is_monotonic,
    simulate_cvd,
    to_lab,
)
from eofigs.check import DE_CVD, DE_NORMAL, _preview_columns
from eofigs.export import dense_artists


def _rgb(hexes):
    return np.array([mpl.colors.to_rgb(h) for h in hexes])


# ----------------------------------------------------------------------------- palettes


def test_palette_values_match_the_standard():
    assert palettes.okabe_ito == (
        "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#000000",
    )  # fmt: skip
    assert palettes.muted == ("#768EAE", "#A4B9A8", "#B58885", "#E2BE7B", "#BBA4C9", "#9A9A9A")
    assert palettes.slate == ("#EBEDF2", "#D3D7E0", "#B2BAC8", "#7F8E9D", "#5A6F7D", "#455B69")
    assert palettes.terra_slate == (
        "#965742", "#B88068", "#D5B2A0", "#F1EFEA", "#A8B7B6", "#83999A", "#546D73",
    )  # fmt: skip
    assert dict(palettes.neutrals) == {
        "text": "#1A1A1A",
        "secondary": "#4D4D4D",
        "grid": "#E0E0E0",
        "no_data": "#BDBDBD",
    }
    with pytest.raises(TypeError):
        palettes.neutrals["text"] = "#000000"


def test_ramps_have_monotonic_lightness():
    lightness = to_lab(_rgb(palettes.slate))[:, 0]
    assert np.all(np.diff(lightness) <= -5)  # light to dark, steps of at least 5 L*
    diverging = to_lab(_rgb(palettes.terra_slate))[:, 0]
    centre = int(np.argmax(diverging))
    assert centre == 3
    assert np.all(np.diff(diverging[: centre + 1]) > 0)
    assert np.all(np.diff(diverging[centre:]) < 0)


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("eofigs.slate", "sequential"),
        ("eofigs.slate_r", "sequential"),
        ("eofigs.terra_slate", "diverging"),
        ("eofigs.terra_slate_r", "diverging"),
    ],
)
def test_colour_maps_are_registered_and_pass_the_checks(name, kind):
    cmap = mpl.colormaps[name]
    assert classify_cmap(cmap) == kind
    lightness = cmap_lightness(cmap)
    assert is_monotonic(lightness) if kind == "sequential" else diverging_ok(lightness)
    assert mpl.colors.to_hex(cmap.get_bad()) == "#bdbdbd"


def test_diverging_map_is_centred():
    cmap = mpl.colormaps["eofigs.terra_slate"]
    assert mpl.colors.to_hex(cmap(0.5)).upper() == "#F1EFEA"
    assert mpl.colors.to_hex(cmap(0.0)).upper() == "#965742"


def test_registration_is_idempotent():
    palettes._register()
    assert "eofigs.slate_r" in mpl.colormaps


def test_muted_fills_meet_the_colour_blind_thresholds():
    rgb = _rgb(palettes.muted[:5])
    for view, threshold in (("normal", 10), ("protan", 6), ("deutan", 6), ("tritan", 6)):
        lab = to_lab(rgb if view == "normal" else simulate_cvd(rgb, view))
        worst = min(
            delta_e2000(lab[i], lab[j]) for i in range(len(rgb)) for j in range(i + 1, len(rgb))
        )
        assert worst >= threshold - 1.0, (view, worst)


def test_colour_blind_thresholds_are_pinned():
    assert (DE_NORMAL, DE_CVD) == (10.0, 6.0)


def test_muted_bars_pass_the_figure_check(sans_font):
    with eofigs.style("custom", font=sans_font):
        fig, ax = eofigs.new_figure("single", height_mm=60)
        ax.bar(range(5), [3, 4, 2, 5, 1], color=palettes.muted[:5])
        eofigs.tidy_axes(ax)
    report = eofigs.check_figure(fig)
    assert report.passed and report.warnings == [], str(report)


# ----------------------------------------------------------------------------- tidy_axes


def test_tidy_axes_limits_ticks_to_round_values(sans_font):
    with eofigs.style("custom", font=sans_font):
        fig, axes = eofigs.new_figure("double", ncols=2)
        for ax in axes:
            ax.plot([0, 0.93], [-3.3, 7.1])
        image = axes[1].imshow(np.linspace(-0.37, 0.81, 100).reshape(10, 10))
        bar = fig.colorbar(image, ax=axes[1])
        eofigs.tidy_axes(axes, bar)
        fig.draw_without_rendering()
    for ax in axes:
        for ticks in (ax.get_xticks(), ax.get_yticks()):
            inside = ticks[(ticks >= -3.3 - 1e-9) & (ticks <= 7.1 + 1e-9)]
            assert len(inside) <= 5
            steps = np.diff(ticks)
            assert np.allclose(steps, steps[0])
            mantissa = steps[0] / 10 ** np.floor(np.log10(steps[0]))
            assert any(np.isclose(mantissa, m) for m in (1, 2, 2.5, 5))
    assert len(bar.get_ticks()) <= 5


@pytest.mark.parametrize(
    ("low", "high", "expected"),
    [
        (640, 4870, [1000, 2000, 3000, 4000]),
        (500, 4500, [1000, 2000, 3000, 4000]),
        (0, 1, [0, 0.25, 0.5, 0.75, 1]),
        (-3.3, 7.1, [-2.5, 0, 2.5, 5]),
        (0, 0.93, [0, 0.25, 0.5, 0.75]),
        (2, 2, [2]),
    ],
)
def test_round_ticks(low, high, expected):
    from eofigs.styling import round_ticks

    assert round_ticks(low, high).tolist() == pytest.approx(expected)


def test_tidy_axes_gives_four_or_five_ticks_inside_the_view(sans_font):
    with eofigs.style("custom", font=sans_font):
        fig, ax = eofigs.new_figure("single")
        ax.barh([750, 4250], [10, 20], height=400)
        ax.set_ylim(500, 4500)
        eofigs.tidy_axes(ax)
    assert ax.get_yticks().tolist() == [1000, 2000, 3000, 4000]
    eofigs.tidy_axes(ax)  # tidying twice changes nothing
    assert ax.get_yticks().tolist() == [1000, 2000, 3000, 4000]


def test_tick_rule_is_a_style_setting(sans_font):
    def figure(**style):
        with eofigs.style("custom", font=sans_font, **style):
            fig, ax = eofigs.new_figure("single", height_mm=60)
            ax.plot([0, 1], [0, 1])  # matplotlib's default: six ticks, 0 to 1 by 0.2
        return fig, ax

    fig, ax = figure()
    assert "ticks" not in {r.name for r in eofigs.check_figure(fig).results}
    fig, ax = figure(max_ticks=5)
    report = eofigs.check_figure(fig)
    assert report.passed and [r.name for r in report.warnings] == ["ticks"]
    eofigs.tidy_axes(ax)
    assert eofigs.check_figure(fig).warnings == []
    fig, ax = figure(max_ticks=3)
    with eofigs.style("custom", font=sans_font, max_ticks=3):
        eofigs.tidy_axes(ax)  # uses the style's limit
    low, high = ax.get_ylim()
    assert len([t for t in ax.get_yticks() if low <= t <= high]) <= 3
    with pytest.raises(ValueError, match="max_ticks"):
        eofigs.set_style("custom", max_ticks=1)


def test_tidy_axes_keeps_explicit_and_log_ticks(sans_font):
    with eofigs.style("custom", font=sans_font):
        fig, ax = eofigs.new_figure("single")
        ax.plot([1, 1000], [0, 1])
        ax.set_xscale("log")
        ax.set_yticks([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        eofigs.tidy_axes(ax)
    assert len(ax.get_yticks()) == 7  # explicit ticks are respected
    assert ax.xaxis.get_scale() == "log"
    with pytest.raises(ValueError, match="at least 2"):
        eofigs.tidy_axes(ax, max_ticks=1)


def test_tidy_axes_on_dates(sans_font):
    with eofigs.style("custom", font=sans_font):
        fig, ax = eofigs.new_figure("double")
        dates = pd.date_range("2001-01-01", "2024-12-31", freq="MS")
        ax.plot(dates, np.arange(dates.size))
        eofigs.tidy_axes(ax)
        fig.draw_without_rendering()
    assert isinstance(ax.xaxis.get_major_locator(), mdates.AutoDateLocator)
    assert isinstance(ax.xaxis.get_major_formatter(), mdates.ConciseDateFormatter)
    low, high = ax.get_xlim()
    ticks = [t for t in ax.get_xticks() if low <= t <= high]
    assert len(ticks) <= 6


def test_tidy_axes_skips_map_axes():
    import cartopy.crs as ccrs

    fig, ax = eofigs.new_figure("single", subplot_kw={"projection": ccrs.PlateCarree()})
    before = ax.xaxis.get_major_locator()
    eofigs.tidy_axes(ax)
    assert ax.xaxis.get_major_locator() is before


def test_true_minus_sign(sans_font):
    with eofigs.style("custom", font=sans_font):
        assert mpl.rcParams["axes.unicode_minus"] is True
        fig, ax = eofigs.new_figure("single")
        ax.plot([-2, 2], [-2, 2])
        eofigs.tidy_axes(ax)
        fig.draw_without_rendering()
        labels = [t.get_text() for t in ax.get_xticklabels()]
    assert any(label.startswith("\N{MINUS SIGN}") for label in labels), labels


def test_crowded_ticks_warn(sans_font):
    with eofigs.style("custom", font=sans_font, max_ticks=5):
        fig, ax = eofigs.new_figure("double")
        ax.plot(np.arange(12), np.arange(12))
        ax.set_xticks(np.arange(12))
    result = [r for r in eofigs.check_figure(fig).results if r.name == "ticks"][0]
    assert result.status == "warn"
    assert "axes 1 x (12)" in result.message


def test_hidden_tick_labels_are_not_counted(sans_font):
    with eofigs.style("custom", font=sans_font, max_ticks=5):
        fig, ax = eofigs.new_figure("double")
        ax.plot(np.arange(12), np.arange(12))
        ax.set_xticks(np.arange(12))
        ax.tick_params(labelbottom=False)
        ax.set_yticks(np.arange(12))
        ax.set_yscale("log")
    result = [r for r in eofigs.check_figure(fig).results if r.name == "ticks"][0]
    assert result.status == "pass"


# ----------------------------------------------------------------------------- author style


def test_author_style_in_one_call():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # Arial may fall back to Liberation Sans
        with eofigs.style(journal="custom", font="Arial", bold=True, labels="A", max_ticks=5):
            assert mpl.rcParams["font.weight"] == "bold"
            assert mpl.rcParams["axes.labelweight"] == "bold"
            assert mpl.rcParams["font.family"][0] in ("Arial", "Liberation Sans", "Arimo",
                                                      "DejaVu Sans")  # fmt: skip
            fig, axes = eofigs.new_figure("double", ncols=2)
            texts = eofigs.label_panels(axes)
    assert [t.get_text() for t in texts] == ["A", "B"]
    assert fig._eofigs_max_ticks == 5
    for text, ax in zip(texts, axes, strict=True):
        assert text.get_fontweight() == "bold"
        assert text.get_position() == (0, 1)  # top-left corner of the panel
        assert text.get_va() == "bottom" and text.get_ha() == "left"  # outside, above
        assert text.axes is ax


# ----------------------------------------------------------------------------- export


def test_dense_layers_are_rasterised_only_while_saving_vectors(tmp_path, sans_font):
    rng = np.random.default_rng(1)
    with eofigs.style("custom", font=sans_font):
        fig, (ax1, ax2) = eofigs.new_figure("double", ncols=2)
        dense = ax1.scatter(rng.random(5000), rng.random(5000), s=1)
        sparse = ax1.scatter([0.5], [0.5], s=20, color="#D55E00")
        mesh = ax2.pcolormesh(rng.random((20, 20)))
    assert dense_artists(fig) == [dense, mesh]
    seen = {}
    original = fig.savefig

    def spy(path, **kwargs):
        seen[kwargs["format"]] = (dense.get_rasterized(), sparse.get_rasterized())
        return original(path, **kwargs)

    fig.savefig = spy
    eofigs.save_figure(fig, tmp_path / "dense", formats=("pdf", "png", "svg"), check=False)
    assert seen == {"pdf": (True, False), "png": (False, False), "svg": (True, False)}
    assert not dense.get_rasterized() and not mesh.get_rasterized()
    seen.clear()
    eofigs.save_figure(fig, tmp_path / "vector", formats=("pdf",), check=False,
                       rasterize_dense=False)  # fmt: skip
    assert seen == {"pdf": (False, False)}


def test_rasterised_pdf_is_smaller(tmp_path, sans_font):
    rng = np.random.default_rng(2)
    with eofigs.style("custom", font=sans_font):
        fig, ax = eofigs.new_figure("single")
        ax.scatter(rng.random(20000), rng.random(20000), s=1)
    eofigs.save_figure(fig, tmp_path / "r.pdf", check=False)
    eofigs.save_figure(fig, tmp_path / "v.pdf", check=False, rasterize_dense=False)
    assert (tmp_path / "r.pdf").stat().st_size < (tmp_path / "v.pdf").stat().st_size


# ----------------------------------------------------------------------------- cvd_preview


def test_cvd_preview_from_figure(tmp_path, sans_font):
    with eofigs.style("custom", font=sans_font):
        fig, ax = eofigs.new_figure("single", height_mm=60)
        ax.plot([0, 1], [0, 1], color="#D55E00", lw=4)
        ax.plot([0, 1], [1, 0], color="#009E73", lw=4)
    out = eofigs.cvd_preview(fig, tmp_path / "preview.png", dpi=100)
    assert out == tmp_path / "preview.png"
    with Image.open(out) as im:
        width, height = im.size
        pixels = np.asarray(im.convert("RGB"), dtype=float) / 255
    panel_w, panel_h = round(90 / 25.4 * 100), round(60 / 25.4 * 100)
    # a 3:2 figure is laid out in three columns and two rows, close to 16:9 overall
    assert _preview_columns(panel_w, panel_h) == 3
    assert 3 * panel_w <= width < 3.3 * panel_w and 2 * panel_h < height < 2.6 * panel_h
    # the fifth panel (second row, middle) is greyscale and shows the lines
    grey = pixels[height // 2 + 40 :, width // 3 + 10 : 2 * width // 3 - 10]
    assert np.allclose(grey[..., 0], grey[..., 1], atol=0.02)
    assert np.allclose(grey[..., 1], grey[..., 2], atol=0.02)
    assert grey.min() < 0.6
    # the normal-vision panel (top left) keeps the colours
    normal = pixels[: height // 2, : width // 3]
    assert np.abs(normal[..., 0] - normal[..., 2]).max() > 0.5


@pytest.mark.parametrize(
    ("size", "ncols"), [((1000, 1000), 3), ((3000, 1000), 2), ((300, 1200), 5)]
)
def test_preview_layout_is_close_to_16_by_9(size, ncols):
    assert _preview_columns(*size) == ncols


def test_cvd_preview_from_file(tmp_path):
    colours = np.zeros((10, 20, 4), dtype=np.uint8)
    colours[..., 0] = 213
    colours[..., 1] = 94
    colours[..., 3] = 255
    colours[:, 10:, 3] = 0  # transparent half is shown as white
    Image.fromarray(colours, "RGBA").save(tmp_path / "fig.png")
    out = eofigs.cvd_preview(tmp_path / "fig.png")
    assert out == tmp_path / "fig_cvd.png" and out.exists()


def test_lightness_to_grey_round_trip():
    from eofigs.check import _lightness_to_grey

    lightness = np.array([0.0, 5.0, 25.0, 50.0, 75.0, 100.0])
    grey = _lightness_to_grey(lightness)
    back = to_lab(np.repeat(grey[:, None], 3, axis=1))[:, 0]
    assert np.allclose(back, lightness, atol=0.05)


def test_cvd_preview_errors(tmp_path, sans_font):
    fig, ax = eofigs.new_figure("single")
    with pytest.raises(ValueError, match="Pass out="):
        eofigs.cvd_preview(fig)
    with pytest.raises(ValueError, match="Cannot preview"):
        eofigs.cvd_preview(tmp_path / "figure.pdf")
    with pytest.raises(FileNotFoundError):
        eofigs.cvd_preview(tmp_path / "missing.png")


# ----------------------------------------------------------------------------- font substitutes


@pytest.mark.parametrize(
    ("free", "commercial"),
    [
        ("Liberation Sans", "Arial"),
        ("Arimo", "Arial"),
        ("TeX Gyre Heros", "Helvetica"),
        ("Liberation Serif", "Times New Roman"),
        ("TeX Gyre Termes", "Times New Roman"),
    ],
)
def test_metric_compatible_fonts_pass_with_a_note(free, commercial):
    from eofigs._presets import get_journal
    from eofigs.check import _font_list_result

    preset = get_journal("elsevier")  # lists Arial, Helvetica, Times New Roman, ...
    result = _font_list_result([free], preset, "figure", embedded=False)
    assert result.status == "pass"
    assert f"{free} is metric-compatible with {commercial}" in result.message
    pdf = _font_list_result([free.replace(" ", "") + "-Bold", "DejaVuSans"], preset, "f.pdf", True)
    assert pdf.status == "pass" and "metric-compatible" in pdf.message


def test_other_fonts_still_warn():
    from eofigs._presets import get_journal
    from eofigs.check import _font_list_result

    preset = get_journal("springer")  # lists Helvetica and Arial only
    assert _font_list_result(["Liberation Serif"], preset, "figure", False).status == "warn"
    assert _font_list_result(["Comic Neue"], preset, "figure", False).status == "warn"
    assert _font_list_result(["Liberation Sans"], preset, "figure", False).status == "pass"
    custom = get_journal("mdpi")  # no font list
    assert _font_list_result(["Comic Neue"], custom, "figure", False).status == "pass"
