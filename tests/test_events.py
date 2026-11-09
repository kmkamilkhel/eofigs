"""event_composite: exact numbers on synthetic cubes, event handling, layout and checks."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rioxarray  # noqa: F401
import xarray as xr
from geo_helpers import assert_hatching_on, geo_grid
from scipy import stats

import eofigs
from eofigs import events as ev
from eofigs import trends

UTM = "EPSG:32643"
SWAT = Path(__file__).resolve().parents[1] / "docs" / "data" / "swat"
TIME = pd.date_range("2001-01-01", "2012-12-01", freq="MS")
STARTS = ["2002-06", "2004-07", "2006-05", "2008-08", "2010-06"]


@pytest.fixture
def custom_style(sans_font):
    with eofigs.style("custom", font=sans_font):
        yield


def _cube(values, time=TIME, name="ndvi"):
    ny, nx = values.shape[1:]
    y = 3_900_000 - (np.arange(ny) + 0.5) * 1000
    x = 500_000 + (np.arange(nx) + 0.5) * 1000
    da = xr.DataArray(values, dims=("time", "y", "x"), coords={"time": time, "y": y, "x": x})
    da.name = name
    da.attrs = {"long_name": "NDVI", "units": "1"}
    return da.rio.write_crs(UTM)


def _events(starts=STARTS, months=2):
    out = []
    for s in starts:
        start = pd.Timestamp(f"{s}-01")
        out.append((start, start + pd.offsets.MonthBegin(months - 1)))
    return out


def _injected(response=0.05, trend=0.0, season=0.1, starts=STARTS, ny=6, nx=8, noise=0.0):
    rng = np.random.default_rng(1)
    cycle = season * np.sin(2 * np.pi * (TIME.month.to_numpy() - 4) / 12)
    years = (TIME - TIME[0]).days.to_numpy() / 365.2425
    values = 0.5 + cycle[:, None, None] + trend * years[:, None, None]
    values = values + np.zeros((TIME.size, ny, nx)) + rng.normal(0, noise, (TIME.size, ny, nx))
    for s in starts:
        i = TIME.get_loc(pd.Timestamp(f"{s}-01"))
        values[i : i + 2] -= response  # during (2 months)
        values[i + 2 : i + 5] -= response / 2  # first 3 of the 6 months after
    return _cube(values)


def _layout(fig):
    return fig.eofigs_layout


# ----------------------------------------------------------------------------- numbers


def test_pure_seasonal_cycle_gives_zero_anomalies(custom_style):
    fig = eofigs.event_composite(_injected(response=0.0), _events(), detrend=None, test=None)
    series = _layout(fig)["series"]["mean"]
    assert np.allclose(series, 0.0, atol=1e-12)


def test_composite_recovers_the_injected_anomalies():
    values = _injected(response=0.05, season=0.1).transpose("time", ...).values
    times = pd.DatetimeIndex(TIME)
    used, _ = ev._events(_events(), times, (-3, 6))
    base = np.ones(times.size, bool)
    for e in used:
        base[e.first : e.last + 1] = False
    anomalies = ev._anomalies(values, times, base, True, "anomaly")
    grid = _injected().isel(time=0, drop=True)
    comp = ev._composite(anomalies, used, ev.PHASES, grid, np.zeros(grid.shape, bool), "ttest",
                         None)  # fmt: skip
    assert np.allclose(comp.phases["before"].values, 0.0, atol=1e-12)
    assert np.allclose(comp.phases["during"].values, -0.05)
    assert np.allclose(comp.phases["after"].values, -0.05 / 2 * 3 / 6)
    assert comp.series.shape == (5, 3 + 2 + 6)
    assert np.allclose(comp.series[:, 3:5], -0.05)


def test_linear_detrending_removes_a_greening_trend():
    values = _injected(response=0.05, trend=0.04, season=0.0).transpose("time", ...).values
    times = pd.DatetimeIndex(TIME)
    used, _ = ev._events(_events(), times, (-3, 6))
    base = np.ones(times.size, bool)
    for e in used:
        base[e.first : e.last + 1] = False
    grid = _injected().isel(time=0, drop=True)
    none = np.zeros(grid.shape, bool)
    detrended = ev._anomalies(ev._remove_trend(values, times, base), times, base, True, "anomaly")
    raw = ev._anomalies(values, times, base, True, "anomaly")
    good = ev._composite(detrended, used, ("during",), grid, none, None, None)
    biased = ev._composite(raw, used, ("during",), grid, none, None, None)
    assert np.allclose(good.phases["during"].values, -0.05, atol=1e-9)
    late, early = biased.series[-1, 3], biased.series[0, 3]
    assert late > early + 0.02  # without detrending, the late event looks better


def test_zscores_match_hand_computation():
    values = _injected(response=0.0, season=0.0, noise=0.01).transpose("time", ...).values
    times = pd.DatetimeIndex(TIME)
    base = np.ones(times.size, bool)
    z = ev._anomalies(values, times, base, True, "zscore")
    july = times.month == 7
    ref = values[july, 0, 0]
    expected = (ref - ref.mean()) / ref.std(ddof=1)
    assert np.allclose(z[july, 0, 0], expected)
    few = base.copy()
    few[np.nonzero(july)[0][4:]] = False  # only 4 baseline Julys: no z-score
    assert np.isnan(ev._anomalies(values, times, few, True, "zscore")[july]).all()


def test_pvalues_match_scipy():
    rng = np.random.default_rng(5)
    stack = rng.normal(-0.02, 0.03, (8, 3, 4))
    stack[:6, 0, 0] = np.nan  # only 2 valid events: no p-value
    p = ev.event_pvalues(stack, "ttest")
    expected = stats.ttest_1samp(stack[:, 1, 2], 0.0).pvalue
    assert p[1, 2] == pytest.approx(expected)
    assert np.isnan(p[0, 0])
    w = ev.event_pvalues(stack, "wilcoxon")
    assert w[1, 2] == pytest.approx(stats.wilcoxon(stack[:, 1, 2]).pvalue)
    assert ev.event_pvalues(stack[:2], "ttest") is None
    assert ev.event_pvalues(stack, None) is None


# ----------------------------------------------------------------------------- figure


def test_full_figure_with_marks_and_caption(custom_style):
    cube = _injected(response=0.05, trend=0.04, noise=0.01, ny=30, nx=40)
    fig = eofigs.event_composite(cube, _events(), event_rule="five synthetic hot-dry periods")
    layout = _layout(fig)
    assert [e["start"] for e in layout["events"]] == [f"{s}-01" for s in STARTS]
    assert layout["phase_steps"] == {"before": [3] * 5, "during": [2] * 5, "after": [6] * 5}
    assert layout["phases"]["during"]["significant_percent"] > 95
    assert layout["phases"]["during"]["marks"] > 0
    assert layout["test"] == "ttest" and layout["detrend"] == "linear"
    caption = layout["caption"]
    assert caption.startswith("5 events (2002-06 to 07; 2004-07 to 08;")
    assert "Events: five synthetic hot-dry periods." in caption
    assert "after removing a per-pixel linear trend fitted to those months" in caption
    assert "t-test across 5 events, p < 0.05" in caption
    assert "Series: map-mean anomaly for each event (grey)" in caption
    titles = [a.get_title() for a in fig.axes if a.get_title()]
    assert titles == ["Before (3 months)", "During", "After (6 months)"]
    report = eofigs.check_figure(fig)
    assert report.passed and not [r for r in report.warnings if r.name != "fonts"], str(report)


def test_two_events_have_no_test(custom_style):
    fig = eofigs.event_composite(_injected(), _events(STARTS[:2]))
    layout = _layout(fig)
    assert layout["test"] is None
    assert all(p["marks"] == 0 for p in layout["phases"].values())
    assert "No significance test: fewer than 3 events." in layout["caption"]
    assert layout["series"]["spread"] == "range"


def test_wilcoxon_and_no_test(custom_style):
    cube = _injected(noise=0.01, ny=10, nx=10)
    fig = eofigs.event_composite(cube, _events(), test="wilcoxon", stipple="hatch")
    assert "Wilcoxon signed-rank test across 5 events" in _layout(fig)["caption"]
    none = eofigs.event_composite(cube, _events(), test=None, series=False, maps=("during",))
    layout = _layout(none)
    assert layout["test"] is None and "series" not in layout
    assert "significance" not in layout["caption"]


def test_overlapping_and_edge_events_are_dropped(custom_style):
    pairs = [("2001-02-01", "2001-02-01"), *_events(), ("2004-09-01", "2004-09-01")]
    with pytest.warns(ev.EventWarning) as caught:
        fig = eofigs.event_composite(_injected(), pairs)
    messages = " ".join(str(w.message) for w in caught)
    assert "runs past the record" in messages and "overlaps event 2004-07" in messages
    assert len(_layout(fig)["events"]) == 5
    assert len(_layout(fig)["dropped"]) == 2


def test_boolean_events_match_date_pairs(custom_style):
    flags = xr.DataArray(np.zeros(TIME.size, bool), dims="time", coords={"time": TIME})
    for start, end in _events():
        flags.loc[start:end] = True
    a = _layout(eofigs.event_composite(_injected(), flags, test=None, legend=False))
    b = _layout(eofigs.event_composite(_injected(), _events(), test=None, legend=False))
    assert a["events"] == b["events"] and a["series"]["mean"] == b["series"]["mean"]
    series = pd.Series(flags.values, index=TIME)
    c = _layout(eofigs.event_composite(_injected(), series, test=None, legend=False))
    assert c["events"] == a["events"]


def test_resampling_daily_data(custom_style):
    days = pd.date_range("2001-01-01", "2012-12-31", freq="D")
    monthly = _injected(response=0.05).values
    index = days.to_period("M").to_timestamp()
    values = monthly[np.searchsorted(TIME, index)]
    daily = _cube(values, time=days)
    fig = eofigs.event_composite(daily, _events(), freq="MS", detrend=None, test=None)
    assert np.allclose(_layout(fig)["series"]["mean"][3:5], -0.05)


def test_annual_data_use_one_mean(custom_style):
    years = pd.date_range("1990-01-01", periods=30, freq="YS")
    values = np.full((30, 5, 5), 0.5)
    values[[10, 20]] -= 0.1
    cube = _cube(values, time=years)
    fig = eofigs.event_composite(cube, [("2000-01-01", "2000-01-01"), ("2010-01-01", "2010-01-01")],
                                 window=(-2, 2), test=None)  # fmt: skip
    layout = _layout(fig)
    assert layout["climatology"] == "mean"
    assert "Before (2 years)" in [a.get_title() for a in fig.axes]


def test_vegetation_exclusion_and_aoi_series(custom_style):
    import geopandas as gpd
    from shapely.geometry import box

    cube = _injected(ny=20, nx=20)
    cube[:, :5, :] = 0.05  # rock
    aoi = gpd.GeoDataFrame(geometry=[box(502_000, 3_882_000, 518_000, 3_898_000)], crs=UTM)
    fig = eofigs.event_composite(cube, _events(), aoi=aoi, aoi_label="Valley")
    layout = _layout(fig)
    assert layout["excluded_percent"] == 25.0
    assert "not vegetated; 25.0 % of pixels" in layout["caption"]
    assert "Series: study area-mean anomaly" in layout["caption"]
    labels = [t.get_text() for leg in fig.legends for t in leg.get_texts()]
    assert labels[0] == "Valley" and "Not vegetated" in labels


def test_subfigure(custom_style):
    fig, ax0 = eofigs.new_figure("double", height_mm=150, layout="none")
    ax0.remove()
    top, _ = fig.subfigures(2, 1)
    out = eofigs.event_composite(_injected(), _events(), subfigure=top, series=False)
    assert out is fig and top.eofigs_layout is fig.eofigs_layout


def test_zscore_labels(custom_style):
    fig = eofigs.event_composite(_injected(noise=0.01), _events(), kind="zscore", test=None)
    bar = [a for a in fig.axes if a.get_xlabel().startswith("NDVI z-score")]
    assert bar
    assert "Standardised anomalies (z-scores)" in _layout(fig)["caption"]


def test_errors(custom_style):
    cube = _injected()
    with pytest.raises(ValueError, match="subfigure="):
        eofigs.event_composite(cube, _events(), ax=object())
    for bad in ((-3,), (1, 6), (-3, -1), (-3.0, 6)):
        with pytest.raises(ValueError, match="window must be"):
            eofigs.event_composite(cube, _events(), window=bad)
    with pytest.raises(ValueError, match="kind must be"):
        eofigs.event_composite(cube, _events(), kind="ratio")
    with pytest.raises(ValueError, match="climatology must be"):
        eofigs.event_composite(cube, _events(), climatology="season")
    with pytest.raises(ValueError, match="detrend must be"):
        eofigs.event_composite(cube, _events(), detrend="quadratic")
    with pytest.raises(ValueError, match="test must be"):
        eofigs.event_composite(cube, _events(), test="mannwhitney")
    with pytest.raises(ValueError, match="maps must be"):
        eofigs.event_composite(cube, _events(), maps=("peak",))
    with pytest.raises(ValueError, match="no steps before"):
        eofigs.event_composite(cube, _events(), window=(0, 6))
    with pytest.raises(ValueError, match="no steps after"):
        eofigs.event_composite(cube, _events(), window=(-3, 0))
    with pytest.raises(ValueError, match="stipple must be"):
        eofigs.event_composite(cube, _events(), stipple="stars")
    with pytest.raises(ValueError, match="datetime 'time'"):
        eofigs.event_composite(cube.rename(time="step").assign_coords(step=range(TIME.size)),
                               _events())  # fmt: skip
    with pytest.raises(ValueError, match="No usable events"):
        with pytest.warns(ev.EventWarning):
            eofigs.event_composite(cube, [("2001-01-01", "2001-02-01")])
    with pytest.raises(ValueError, match="pair"):
        eofigs.event_composite(cube, [("2002-06-01",)])
    with pytest.raises(ValueError, match="before its start"):
        eofigs.event_composite(cube, [("2002-06-01", "2002-01-01")])
    with pytest.warns(ev.EventWarning, match="no time step"):
        with pytest.raises(ValueError, match="No usable events"):
            eofigs.event_composite(cube, [("1990-01-01", "1990-02-01")])
    flags = xr.DataArray(np.zeros(5, bool), dims="time", coords={"time": TIME[:5]})
    with pytest.raises(ValueError, match="cover every time step"):
        eofigs.event_composite(cube, flags)
    with pytest.raises(ValueError, match="fewer than 2 steps"):
        eofigs.event_composite(cube, _events(), baseline=("1990-01-01", "1990-02-01"))


def test_baseline_period_and_unknown_variable(custom_style):
    cube = _injected()
    cube.name = "mystery"
    cube.attrs = {"long_name": "Mystery index", "units": "1"}
    fig = eofigs.event_composite(cube, _events(), baseline=("2001-01-01", "2006-12-01"),
                                 test=None, exclude=None)  # fmt: skip
    assert "from 2001-01 to 2006-12 outside the event windows" in _layout(fig)["caption"]


# ----------------------------------------------------------------------------- Swat sample


@pytest.mark.skipif(
    not (SWAT / "swat_ndvi_monthly_1km.tif").exists(), reason="Swat data in the repository only"
)
def test_swat_event_composite(sans_font):
    table = pd.read_csv(SWAT / "swat_hot_dry_events.csv")
    raw = rioxarray.open_rasterio(SWAT / "swat_ndvi_monthly_1km.tif", mask_and_scale=True)
    months = pd.to_datetime([f"{m}-01" for m in raw.attrs["long_name"]])
    cube = raw.rename(band="time").assign_coords(time=months)
    cube.name = "ndvi"
    cube.attrs = {"long_name": "NDVI", "units": "1"}
    pairs = list(zip(table["start"] + "-01", table["end"] + "-01", strict=True))
    with eofigs.style("elsevier", font=sans_font):
        fig = eofigs.event_composite(cube, pairs, aoi=SWAT / "swat_boundary.geojson")
        report = eofigs.check_figure(fig)
    assert len(fig.eofigs_layout["events"]) >= 3
    assert report.passed and not [r for r in report.warnings if r.name != "fonts"], str(report)


# ----------------------------------------------------------------------------- review 13


def test_panel_titles_off_names_the_panels_in_the_caption(sans_font):
    with eofigs.style("custom", font=sans_font, panel_titles=False):
        fig = eofigs.event_composite(_injected(noise=0.01), _events())
        layout = _layout(fig)
        assert layout["panel_titles"] is False
        assert not [a.get_title() for a in fig.axes if a.get_title()]
        assert layout["caption"].startswith(
            "(a) before, 3 months; (b) during; (c) after, 6 months; (d) composite series. 5 events"
        )
        fig = eofigs.event_composite(
            _injected(noise=0.01), _events(), maps=("during",), series=False, labels=["A"]
        )
        assert _layout(fig)["caption"].startswith("A during. 5 events")
        assert "Maps show the mean over events." in _layout(fig)["caption"]
    with eofigs.style("custom", font=sans_font, labels=None, panel_titles=False):
        fig = eofigs.event_composite(_injected(noise=0.01), _events(), maps=("before", "after"))
        caption = _layout(fig)["caption"]
        assert caption.startswith(
            "Maps from left to right: before, 3 months; after, 6 months; below: composite series."
        )
        assert "Before: mean of the 3 months before each event; after: mean of the 6 " in caption


def test_event_period_shading_for_unequal_lengths(custom_style):
    events = [(a, b + pd.offsets.MonthBegin(i % 2)) for i, (a, b) in enumerate(_events())]
    fig = eofigs.event_composite(_injected(noise=0.01), events, maps=("after",))
    layout = _layout(fig)
    assert layout["series"]["event_steps"] == [2, 3]
    assert (
        "dark shading: all events ongoing (first 2 months); light shading: some events "
        "ongoing (up to 3 months)." in layout["caption"]
    )
    assert "After: mean of the 6 months after each event" in layout["caption"]
    series = fig.axes[-1]
    labels = [t.get_text() for t in series.get_legend().get_texts()]
    assert labels[-2:] == ["All events ongoing", "Some events ongoing"]
    spans = [p for p in series.patches if p.get_facecolor()[:3] != (1.0, 1.0, 1.0)]
    assert len(spans) == 2
    report = eofigs.check_figure(fig)
    assert report.passed and not [r for r in report.warnings if r.name != "fonts"], str(report)


def test_equal_lengths_draw_one_shade_and_low_power_note(custom_style):
    fig = eofigs.event_composite(_injected(noise=0.01), _events(STARTS[:3]))
    layout = _layout(fig)
    assert layout["series"]["event_steps"] == [2, 2]
    labels = [t.get_text() for t in fig.axes[-1].get_legend().get_texts()]
    assert labels[-1] == "Event period"
    assert "shading marks the event period." in layout["caption"]
    assert (
        "With only 3 events the test has low power; absence of dots does not indicate "
        "absence of an effect." in layout["caption"]
    )
    fig = eofigs.event_composite(_injected(noise=0.01), _events(), stipple="hatch")
    assert "low power" not in _layout(fig)["caption"]
    fig = eofigs.event_composite(_injected(noise=0.01), _events(STARTS[:4]), stipple="hatch")
    assert "absence of hatching does not indicate" in _layout(fig)["caption"]


# ----------------------------------------------------------------------------- 0.1.1 fixes


def test_geographic_cube_with_gaps_and_bare_ground(custom_style):
    cube = _injected(ny=30, nx=30, noise=0.01)
    grid = geo_grid(np.zeros((30, 30)))
    cube = cube.assign_coords(y=grid.y.values, x=grid.x.values).rio.write_crs("EPSG:4326")
    cube[:, 20:26, 3:9] = 0.05  # rock: not vegetated
    cube[1:, 4:9, 4:9] = np.nan  # one value only: inside the data, no anomalies
    fig = eofigs.event_composite(cube, _events())
    layout = _layout(fig)
    assert layout["excluded_percent"] > 0 and layout["no_data_percent"] > 0
    for ax in fig.axes[:3]:  # the before, during and after maps
        assert_hatching_on(ax, trends.NO_DATA_HATCH, grid, slice(4, 9), slice(4, 9))
        assert_hatching_on(ax, trends.EXCLUDED_HATCH, grid, slice(20, 26), slice(3, 9))


def test_caption_notes_multiple_comparisons(custom_style):
    fig = eofigs.event_composite(_injected(noise=0.01), _events())
    assert (
        "Per-pixel tests across events are not adjusted for multiple comparisons."
        in _layout(fig)["caption"]
    )
    untested = eofigs.event_composite(_injected(noise=0.01), _events(), test=None)
    assert "multiple comparisons" not in _layout(untested)["caption"]


def test_fdr_is_applied_to_each_map(custom_style):
    cube = _injected(noise=0.01)
    fig = eofigs.event_composite(cube, _events(), fdr="bh")
    layout = _layout(fig)
    for phase, record in layout["phases"].items():
        fdr = record["fdr"]
        assert fdr["method"] == "bh" and fdr["q"] == pytest.approx(0.10), phase
        assert fdr["n_tests"] == 48
        assert record["significant_percent"] == pytest.approx(
            100 * fdr["n_rejected"] / 48, abs=0.01
        )
    caption = layout["caption"]
    assert (
        "Benjamini–Hochberg false discovery rate control at q = 0.10, applied separately to "
        "each map" in caption
    )
    assert "not adjusted for multiple comparisons" not in caption
    labels = [t.get_text() for leg in fig.legends for t in leg.get_texts()]
    assert "FDR q = 0.10 in ≥ 50 % of pixels" in labels
    plain = _layout(eofigs.event_composite(cube, _events()))
    assert all(r["fdr"] is None for r in plain["phases"].values())
