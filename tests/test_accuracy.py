"""accuracy_scatter: exact statistics, formatting, layout, errors and checks."""

import numpy as np
import pandas as pd
import pytest
from scipy import stats as sps

import eofigs
from eofigs import accuracy as acc


@pytest.fixture
def custom_style(sans_font):
    with eofigs.style("custom", font=sans_font):
        yield


def _pairs(n=300, seed=1):
    rng = np.random.default_rng(seed)
    obs = rng.gamma(4, 40, n)
    pred = 15 + 0.85 * obs + rng.normal(0, 25, n)
    return obs, pred


def _clean(report):
    return report.passed and not [r for r in report.warnings if r.name != "fonts"]


# ----------------------------------------------------------------------------- statistics


def test_perfect_and_shifted_predictions(custom_style):
    obs = np.linspace(10, 100, 50)
    s = _layout(eofigs.accuracy_scatter(obs, obs))["stats"]
    assert s["rmse"] == 0 and s["bias"] == 0 and s["mae"] == 0
    assert s["r2"] == pytest.approx(1) and s["nse"] == pytest.approx(1)
    assert s["slope"] == pytest.approx(1) and s["intercept"] == pytest.approx(0, abs=1e-9)
    s = _layout(eofigs.accuracy_scatter(obs, obs + 2))["stats"]
    assert s["bias"] == pytest.approx(2) and s["rmse"] == pytest.approx(2)
    assert s["mae"] == pytest.approx(2) and s["r2"] == pytest.approx(1)
    assert s["rbias"] == pytest.approx(200 / obs.mean())
    assert s["nse"] == pytest.approx(1 - 4 * obs.size / np.sum((obs - obs.mean()) ** 2))


def _layout(fig):
    return fig.eofigs_layout


def test_statistics_match_scipy_and_formulas(custom_style):
    obs, pred = _pairs()
    layout = _layout(eofigs.accuracy_scatter(obs, pred))
    s = layout["stats"]
    r = sps.pearsonr(obs, pred).statistic
    assert s["r"] == pytest.approx(r) and s["r2"] == pytest.approx(r * r)
    assert s["rmse"] == pytest.approx(np.sqrt(np.mean((pred - obs) ** 2)))
    assert s["rrmse"] == pytest.approx(100 * s["rmse"] / obs.mean())
    assert s["bias"] == pytest.approx(np.mean(pred - obs))
    # Pineiro et al. (2008): observed (y) regressed on predicted (x)
    fit = sps.linregress(pred, obs)
    assert s["slope"] == pytest.approx(fit.slope) and s["intercept"] == pytest.approx(fit.intercept)
    assert layout["fit"]["y"] == "observed" and layout["fit"]["x"] == "predicted"
    flipped = _layout(eofigs.accuracy_scatter(obs, pred, orientation="observed_x"))
    fit = sps.linregress(obs, pred)
    assert flipped["stats"]["slope"] == pytest.approx(fit.slope)
    assert flipped["fit"]["y"] == "predicted"
    assert flipped["caption"].startswith("Predicted against observed values")


def test_reduced_major_axis(custom_style):
    obs, pred = _pairs()
    s = _layout(eofigs.accuracy_scatter(obs, pred, fit="rma"))["stats"]
    assert s["slope"] == pytest.approx(np.std(obs) / np.std(pred))
    assert s["intercept"] == pytest.approx(obs.mean() - s["slope"] * pred.mean())
    s = _layout(eofigs.accuracy_scatter(obs, -pred, fit="rma"))["stats"]
    assert s["slope"] < 0


def test_missing_pairs_are_dropped(custom_style):
    obs, pred = _pairs(50)
    obs[3], pred[7] = np.nan, np.nan
    layout = _layout(eofigs.accuracy_scatter(pd.Series(obs), pd.Series(pred)))
    assert layout["n"] == 48 and layout["dropped"] == 2
    assert "2 pairs with a missing value were left out." in layout["caption"]


# ----------------------------------------------------------------------------- formatting


def test_stat_texts_format():
    values = dict(r2=0.8123, r=-0.9, nse=0.7, rmse=31.24, rrmse=12.34, mae=20.0, bias=-4.06)
    values.update(rbias=-0.004, slope=0.93, intercept=8.1, n=12345)
    lines = acc.stat_texts(values, list(acc.STATS), "m")
    assert lines == [
        "R² = 0.81",
        "r = −0.90",
        "NSE = 0.70",
        "RMSE = 31.2 m",
        "rRMSE = 12.3 %",
        "MAE = 20.0 m",
        "Bias = −4.1 m",
        "rBias = 0.0 %",
        "Slope = 0.93",
        "Intercept = 8.1 m",
        "n = 12 345",
    ]
    small = acc.stat_texts({"rmse": 0.05234, "bias": -0.00001}, ["rmse", "bias"], "")
    assert small == ["RMSE = 0.0523", "Bias = 0.0000"]
    assert acc._number(float("nan"), 2) == "n/a"


def test_limits_and_ticks():
    lo, hi, ticks = acc._limits(np.array([12.0, 48]), np.array([15.0, 40]), None)
    assert (lo, hi) == (10, 50) and ticks.tolist() == [10, 20, 30, 40, 50]
    lo, hi, ticks = acc._limits(np.array([-5.0, 535]), np.array([0.0, 500]), None)
    assert (lo, hi) == (-50, 550) and ticks.tolist() == [0, 250, 500]
    lo, hi, ticks = acc._limits(np.array([0.1]), np.array([0.2]), (0, 1))
    assert (lo, hi) == (0, 1) and ticks[0] == 0 and ticks[-1] == 1


# ----------------------------------------------------------------------------- layout


def test_default_figure_labels_and_check(custom_style):
    obs, pred = _pairs()
    fig = eofigs.accuracy_scatter(obs, pred, variable="agb")
    ax = fig.axes[0]
    assert ax.get_xlabel() == "Predicted AGB (Mg ha$^{-1}$)"
    assert ax.get_ylabel() == "Observed AGB (Mg ha$^{-1}$)"
    assert ax.get_xlim() == ax.get_ylim()
    assert list(ax.get_xticks()) == list(ax.get_yticks())
    layout = _layout(fig)
    assert layout["density"] is None and layout["stats_loc"] in acc._CORNERS
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["1:1", "OLS fit"]
    caption = layout["caption"]
    assert caption.startswith("Observed against predicted values (n = 300). R²: squared Pearson")
    assert (
        "ordinary least-squares regression of observed on predicted (Piñeiro et al. 2008)"
        in caption
    )
    assert "Mg ha⁻¹" in caption
    assert _clean(eofigs.check_figure(fig)), str(eofigs.check_figure(fig))


def test_variable_from_name_and_plain_labels(custom_style):
    obs, pred = _pairs()
    fig = eofigs.accuracy_scatter(pd.Series(obs, name="canopy_height"), pred)
    assert fig.axes[0].get_ylabel() == "Observed canopy height (m)"
    fig = eofigs.accuracy_scatter(pd.Series(obs, name="field"), pred, fit=None, one_to_one=False,
                                  legend=False, stats=())  # fmt: skip
    ax = fig.axes[0]
    assert ax.get_ylabel() == "Observed" and ax.get_legend() is None
    assert _layout(fig)["fit"] is None and _layout(fig)["stats_loc"] is None
    fig = eofigs.accuracy_scatter(obs, pred, observed_label="Field AGB", predicted_label="Model")
    assert fig.axes[0].get_xlabel() == "Model"


def test_density_above_threshold(custom_style):
    rng = np.random.default_rng(2)
    h = rng.gamma(6, 400, 5000) + 600
    dem = h + rng.normal(0, 15, h.size)
    fig = eofigs.accuracy_scatter(h, dem, variable="elevation")
    layout = _layout(fig)
    assert layout["density"]["bins"] == acc.DENSITY_BINS and layout["density"]["max_count"] > 10
    assert "Point colours: number of points in each cell of a 60 × 60 grid" in layout["caption"]
    assert any(a.get_ylabel() == "Points per cell" for a in fig.axes[0].child_axes)
    points = [c for c in fig.axes[0].collections if c.get_array() is not None][0]
    counts = np.asarray(points.get_array())
    assert np.all(np.diff(counts) >= 0)  # densest drawn last
    assert points.get_rasterized()
    assert _clean(eofigs.check_figure(fig)), str(eofigs.check_figure(fig))
    small = _layout(eofigs.accuracy_scatter(h[:500], dem[:500]))
    assert small["density"] is None
    forced = _layout(eofigs.accuracy_scatter(h[:500], dem[:500], density=True))
    assert forced["density"] is not None


def test_groups(custom_style):
    obs, pred = _pairs()
    grp = pd.Series(np.where(np.arange(300) % 3 == 0, "Conifer", "Broadleaf"), name="forest type")
    fig = eofigs.accuracy_scatter(obs, pred, variable="agb", groups=grp)
    layout = _layout(fig)
    assert set(layout["groups"]) == {"Broadleaf", "Conifer"}
    sel = grp.to_numpy() == "Conifer"
    assert layout["groups"]["Conifer"]["n"] == 100
    assert layout["groups"]["Conifer"]["rmse"] == pytest.approx(
        np.sqrt(np.mean((pred[sel] - obs[sel]) ** 2))
    )
    assert "Colours and markers by forest type; Broadleaf: R²" in layout["caption"]
    texts = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
    assert texts == ["Broadleaf", "Conifer", "1:1", "OLS fit"]
    assert _clean(eofigs.check_figure(fig)), str(eofigs.check_figure(fig))
    cat = pd.Categorical(np.where(np.arange(300) < 298, "B", "A"), categories=["B", "A"])
    layout = _layout(eofigs.accuracy_scatter(obs, pred, groups=cat))
    assert list(layout["groups"]) == ["B", "A"] and layout["groups"]["A"] == {"n": 2}
    big = _layout(eofigs.accuracy_scatter(np.tile(obs, 4), np.tile(pred, 4),
                                          groups=np.repeat(["x", "y"], 600)))  # fmt: skip
    assert big["density"] is None  # auto density is off with groups


def test_panels_with_ax_and_labels(custom_style):
    obs, pred = _pairs()
    fig, axes = eofigs.new_figure("double", ncols=2, height_mm=80)
    out = eofigs.accuracy_scatter(obs, pred, ax=axes[0], labels=["(a)"])
    eofigs.accuracy_scatter(obs[:100], pred[:100], ax=axes[1], stats_loc="lower right")
    assert out is fig
    assert axes[0].eofigs_layout["n"] == 300 and axes[1].eofigs_layout["n"] == 100
    assert axes[1].eofigs_layout["stats_loc"] == "lower right"
    assert any(t.get_text() == "(a)" for t in axes[0].texts)


def test_height_and_max_ticks(sans_font):
    obs, pred = _pairs()
    with eofigs.style("custom", font=sans_font, max_ticks=4):
        fig = eofigs.accuracy_scatter(obs, pred, height_mm=70)
        assert round(fig.get_figheight() * 25.4, 1) == 70
        assert len(fig.axes[0].get_xticks()) <= 4


def test_errors(custom_style):
    obs, pred = _pairs(20)
    with pytest.raises(ValueError, match="different shapes"):
        eofigs.accuracy_scatter(obs, pred[:10])
    with pytest.raises(ValueError, match="At least 3 valid pairs"):
        eofigs.accuracy_scatter([1, np.nan, 3], [1, 2, np.nan])
    with pytest.raises(ValueError, match="all equal"):
        eofigs.accuracy_scatter(np.ones(5), np.arange(5.0))
    with pytest.raises(ValueError, match="Unknown statistic"):
        eofigs.accuracy_scatter(obs, pred, stats=("r2", "kge"))
    with pytest.raises(ValueError, match="fit must be"):
        eofigs.accuracy_scatter(obs, pred, fit="theil")
    with pytest.raises(ValueError, match="orientation must be"):
        eofigs.accuracy_scatter(obs, pred, orientation="up")
    with pytest.raises(ValueError, match="density must be"):
        eofigs.accuracy_scatter(obs, pred, density="hexbin")
    with pytest.raises(ValueError, match="stats_loc must be"):
        eofigs.accuracy_scatter(obs, pred, stats_loc="centre")
    with pytest.raises(ValueError, match="at most 6 can be told apart"):
        eofigs.accuracy_scatter(obs, pred, groups=np.arange(20) % 7)
    with pytest.raises(ValueError, match="groups has 3 values"):
        eofigs.accuracy_scatter(obs, pred, groups=["a", "b", "c"])
    with pytest.raises(ValueError, match="density=True cannot be combined"):
        eofigs.accuracy_scatter(obs, pred, groups=np.arange(20) % 2, density=True)
    with pytest.raises(ValueError, match="high > low"):
        eofigs.accuracy_scatter(obs, pred, limits=(5, 1))
