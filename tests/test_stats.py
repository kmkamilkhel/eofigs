import numpy as np
import pandas as pd
import pytest
import rioxarray  # noqa: F401
import xarray as xr
from scipy import stats as sps

import eofigs
from eofigs import trend

YEARS = pd.date_range("2001-01-01", periods=20, freq="YS")


def _years(time):
    return (time - time[0]) / np.timedelta64(1, "D") / 365.2425


def _mk_reference(y):
    """Straightforward Mann-Kendall (tie- and continuity-corrected) for one series."""
    y = y[~np.isnan(y)]
    n = len(y)
    s = sum(np.sign(y[j] - y[i]) for i in range(n) for j in range(i + 1, n))
    _, counts = np.unique(y, return_counts=True)
    var = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in counts)) / 18
    z = (s - np.sign(s)) / np.sqrt(var) if s != 0 else 0.0
    return 2 * sps.norm.sf(abs(z))


def _cube(values, time=YEARS):
    ny, nx = values.shape[1:]
    da = xr.DataArray(
        values,
        dims=("time", "y", "x"),
        coords={"time": time, "y": np.arange(ny, 0, -1) * 30.0, "x": np.arange(nx) * 30.0},
        name="ndvi",
        attrs={"units": "1"},
    )
    return da.rio.write_crs("EPSG:32643")


def test_matches_scipy_theilslopes_and_reference_mk():
    rng = np.random.default_rng(0)
    values = rng.normal(0, 1, (20, 3, 4)) + 0.05 * np.arange(20)[:, None, None]
    values = np.round(values, 1)  # create ties
    result = trend(_cube(values), per="year")
    t = _years(YEARS.values)
    for r in range(3):
        for c in range(4):
            y = values[:, r, c]
            ref = sps.theilslopes(y, t, method="joint")
            assert result.slope.values[r, c] == pytest.approx(ref.slope, rel=1e-12)
            assert result.intercept.values[r, c] == pytest.approx(ref.intercept, rel=1e-12)
            assert result.pvalue.values[r, c] == pytest.approx(_mk_reference(y), rel=1e-10)


def test_exact_linear_trend_per_decade_and_significance():
    t = _years(YEARS.values)
    values = (0.3 + 0.01 * t)[:, None, None] * np.ones((1, 2, 2))
    result = trend(_cube(values), per="decade")
    np.testing.assert_allclose(result.slope.values, 0.1)
    np.testing.assert_allclose(result.intercept.values, 0.3)
    assert result.significant.all()
    assert (result.n_valid == 20).all()
    assert result.slope.attrs["units"] == "decade$^{-1}$"
    assert result.attrs["autocorrelation"] == "not corrected"


def test_gaps_and_irregular_time_use_real_dates():
    time = pd.to_datetime(["2000-01-01", "2001-01-01", "2005-01-01", "2006-07-01", "2010-01-01",
                           "2011-01-01", "2015-01-01", "2016-01-01", "2020-01-01"])  # fmt: skip
    t = _years(time.values)
    values = (2.0 * t)[:, None, None] * np.ones((1, 1, 1))
    values[3, 0, 0] = np.nan
    result = trend(_cube(values, time=time), per="year")
    assert result.slope.item() == pytest.approx(2.0)
    assert result.n_valid.item() == 8


def test_flat_series_is_not_significant():
    result = trend(_cube(np.ones((20, 1, 1))))
    assert result.slope.item() == 0.0
    assert result.pvalue.item() == 1.0
    assert not result.significant.item()


def test_min_valid_and_nan_handling():
    rng = np.random.default_rng(1)
    values = rng.random((20, 2, 2))
    values[:15, 0, 0] = np.nan  # 5 valid
    values[:10, 0, 1] = np.nan  # 10 valid
    result = trend(_cube(values), min_valid=8)
    assert np.isnan(result.slope.values[0, 0]) and int(result.n_valid.values[0, 0]) == 5
    assert not np.isnan(result.slope.values[0, 1])
    y = values[:, 0, 1]
    ok = ~np.isnan(y)
    ref = sps.theilslopes(y[ok], _years(YEARS.values)[ok], method="joint")
    assert result.slope.values[0, 1] == pytest.approx(ref.slope * 10)
    assert result.pvalue.values[0, 1] == pytest.approx(_mk_reference(y))


def test_unsorted_time_is_sorted():
    rng = np.random.default_rng(2)
    values = rng.random((20, 1, 1))
    order = rng.permutation(20)
    shuffled = _cube(values[order], time=YEARS[order])
    np.testing.assert_allclose(trend(shuffled).slope, trend(_cube(values)).slope)


def test_small_memory_budget_gives_identical_results():
    rng = np.random.default_rng(3)
    values = rng.random((30, 6, 7))
    values[rng.random(values.shape) < 0.1] = np.nan
    time = pd.date_range("1991-01-01", periods=30, freq="YS")
    a = trend(_cube(values, time=time), memory_mb=0.001)  # one pixel per block
    b = trend(_cube(values, time=time), memory_mb=512)
    for name in ("slope", "intercept", "pvalue", "n_valid"):
        np.testing.assert_allclose(a[name], b[name])


def test_dask_input_matches_numpy():
    pytest.importorskip("dask")
    rng = np.random.default_rng(4)
    values = rng.random((20, 8, 10))
    eager = trend(_cube(values))
    lazy = trend(_cube(values).chunk({"time": 5, "y": 4, "x": 5}))
    assert lazy.slope.chunks is not None
    np.testing.assert_allclose(lazy.slope.values, eager.slope.values)
    np.testing.assert_allclose(lazy.pvalue.values, eager.pvalue.values)


def test_spatial_coordinates_and_crs_are_kept():
    result = trend(_cube(np.random.default_rng(5).random((20, 3, 4))))
    assert result.slope.dims == ("y", "x")
    assert result.rio.crs.to_epsg() == 32643


def test_series_without_spatial_dimensions():
    da = xr.DataArray(np.arange(12.0), dims="time", coords={"time": YEARS[:12]})
    result = trend(da, per="year", min_valid=3)
    assert float(result.slope) == pytest.approx(1 / (365.2425 / 365.2425), rel=1e-2)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"per": "month"}, "per must be one of"),
        ({"alpha": 1.5}, "alpha must be between"),
        ({"min_valid": 2}, "min_valid must be at least 3"),
        ({"memory_mb": 0}, "memory_mb must be positive"),
        ({"dim": "date"}, "No dimension 'date'"),
    ],
)
def test_argument_errors(kwargs, message):
    with pytest.raises(ValueError, match=message):
        trend(_cube(np.ones((20, 1, 1))), **kwargs)


def test_time_must_be_datetime_and_unique():
    da = xr.DataArray(np.ones(10), dims="time", coords={"time": np.arange(10)})
    with pytest.raises(ValueError, match="must hold dates"):
        trend(da)
    dup = xr.DataArray(
        np.ones(10), dims="time", coords={"time": [YEARS[0]] * 2 + list(YEARS[2:10])}
    )
    with pytest.raises(ValueError, match="duplicate dates"):
        trend(dup, min_valid=3)


def test_slope_is_a_trend_not_the_source_variable():
    da = _cube(np.random.default_rng(6).random((20, 2, 2)))
    da.attrs["standard_name"] = "normalized_difference_vegetation_index"
    result = trend(da, per="decade")
    assert "standard_name" not in result.slope.attrs
    assert "standard_name" not in result.intercept.attrs
    assert result.slope.attrs["long_name"] == "Normalized Difference Vegetation Index trend"
    assert result.slope.attrs["units"] == "decade$^{-1}$"
    assert result.slope.attrs["source_variable"] == "ndvi"
    assert eofigs.variable(result.slope) == eofigs.variable("ndvi").trend(per="decade")
    assert eofigs.variable(result.slope).kind == "diverging"
    assert result.intercept.attrs["reference_time"] == "2001-01-01"
    assert result.intercept.attrs["units"] == "1"
    assert result.n_valid.dtype == np.int32


def test_trend_units_follow_the_data():
    da = _cube(np.random.default_rng(7).random((20, 1, 1)) + 290).rename("lst")
    da.attrs = {"units": "K"}
    result = trend(da, per="year")
    assert result.slope.attrs["units"] == "K yr$^{-1}$"
    var = eofigs.variable(result.slope)
    assert var.units == "K yr$^{-1}$" and var.cmap == "cmc.vik"


def test_unknown_variable_gets_generic_trend_labels():
    da = _cube(np.random.default_rng(8).random((20, 1, 1))).rename("band_1")
    da.attrs = {"units": "mm d-1", "long_name": "Water index"}
    result = trend(da)
    assert result.slope.attrs["long_name"] == "Water index trend"
    assert result.slope.attrs["units"] == "mm d$^{-1}$ decade$^{-1}$"
    unnamed = trend(xr.DataArray(np.arange(10.0), dims="time", coords={"time": YEARS[:10]}))
    assert unnamed.slope.attrs["long_name"] == "Value trend"
    assert unnamed.slope.attrs["units"] == "decade$^{-1}$"


# ----------------------------------------------------------------------------- false discovery rate

#: A worked Benjamini-Hochberg example: with q = 0.10 and m = 10 the step-up thresholds are
#: 0.01, 0.02, ..., 0.10; the largest p(i) <= i q / m is p(6) = 0.06, so six are rejected.
P_EXAMPLE = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216])


def test_fdr_mask_worked_example():
    from eofigs.stats import fdr_mask

    result = fdr_mask(P_EXAMPLE, q=0.10)
    assert result.mask.tolist() == [True] * 6 + [False] * 4
    assert result.p_threshold == 0.06
    assert result.n_tests == 10 and result.n_rejected == 6
    strict = fdr_mask(P_EXAMPLE, q=0.05)  # thresholds 0.005, 0.010, ...: p(2) = 0.008
    assert strict.n_rejected == 2 and strict.p_threshold == 0.008
    adjusted = sps.false_discovery_control(P_EXAMPLE, method="bh")
    assert np.array_equal(result.mask, adjusted <= 0.10)


def test_fdr_mask_family_nan_and_valid():
    from eofigs.stats import fdr_mask

    grid = np.full((3, 5), np.nan)
    grid.flat[:10] = P_EXAMPLE
    result = fdr_mask(grid, q=0.10)  # NaN is not a test
    assert result.mask.shape == (3, 5) and result.n_tests == 10 and result.n_rejected == 6
    valid = np.ones((3, 5), bool)
    valid.flat[7:] = False  # a smaller family: 7 tests
    smaller = fdr_mask(grid, q=0.10, valid=valid)
    assert smaller.n_tests == 7
    assert not smaller.mask.flat[7:].any()
    reference = sps.false_discovery_control(P_EXAMPLE[:7], method="bh") <= 0.10
    assert np.array_equal(smaller.mask.flat[:7], reference)


def test_fdr_mask_dataarray_none_rejected_and_errors():
    from eofigs.stats import fdr_mask

    da = xr.DataArray(P_EXAMPLE.reshape(2, 5), dims=("y", "x"),
                      coords={"y": [1.0, 0.0], "x": np.arange(5.0)})  # fmt: skip
    result = fdr_mask(da, q=0.10)
    assert isinstance(result.mask, xr.DataArray) and result.mask.dims == ("y", "x")
    assert int(result.mask.sum()) == 6
    none = fdr_mask(np.array([0.5, 0.6, np.nan]), q=0.10)
    assert none.n_rejected == 0 and none.p_threshold is None and not none.mask.any()
    empty = fdr_mask(np.array([np.nan, np.nan]))
    assert empty.n_tests == 0 and empty.p_threshold is None
    with pytest.raises(ValueError, match="q must be"):
        fdr_mask(P_EXAMPLE, q=1.5)
    with pytest.raises(ValueError, match="valid"):
        fdr_mask(P_EXAMPLE, valid=np.ones(3, bool))
    with pytest.raises(ValueError, match="between 0 and 1"):
        fdr_mask(np.array([0.2, 1.4]))


# ---------------------------------------------------------------------------- seasonal Mann-Kendall

#: Reference values from docs/scripts/seasonal_mk_reference.R (R 4.6.1, trend 1.1.6, rkt 1.9).
R_REFERENCE = {
    "trend": {"S": 558, "varS": 4898, "p": 1.73761730968e-15, "slope": 0.00271428571429,
              "varS_corrected": 36612, "p_corrected": 0.00360264257079},
    "none": {"S": -72, "varS": 4880, "p": 0.309457013533, "slope": -0.000285714285714,
             "varS_corrected": 16252.6666667, "p_corrected": 0.577579267813},
    "gaps": {"S": 519, "varS": 4077.66666667, "p": 4.4408920985e-16, "slope": 0.0029,
             "varS_corrected": 29649, "p_corrected": 0.00262692154149},
}  # fmt: skip


def _reference_series(kind):
    """The monthly series of seasonal_mk_reference.R (2001-2015), dated mid-month."""
    k = np.arange(180)
    year, month = k // 12, k % 12 + 1
    noise = ((k * 7919) % 101) / 101 - 0.5
    year_effect = ((year * 104729) % 97) / 97 - 0.5  # shared by the months of a year
    slope = 0.0 if kind == "none" else 0.003
    x = np.round(0.5 + 0.2 * np.sin(2 * np.pi * (month - 1) / 12) + slope * year
                 + 0.05 * noise + 0.03 * year_effect, 3)  # fmt: skip
    if kind == "gaps":
        x[(k * 31) % 17 == 0] = np.nan
    time = pd.to_datetime([f"{2001 + y}-{m:02d}-15" for y, m in zip(year, month, strict=True)])
    return xr.DataArray(x, dims="time", coords={"time": time}, name="value")


def _z_p(s, var):
    z = 0.0 if s == 0 or var <= 0 else (s - np.sign(s)) / np.sqrt(var)
    return 2.0 * sps.norm.sf(abs(z))


@pytest.mark.parametrize("kind", ["trend", "none", "gaps"])
def test_seasonal_matches_r(kind):
    ref = R_REFERENCE[kind]
    series = _reference_series(kind)
    plain = trend(series, per="year", seasonal="month", seasonal_correction=False)
    corrected = trend(series, per="year", seasonal="month")
    assert float(plain.pvalue) == pytest.approx(_z_p(ref["S"], ref["varS"]), rel=1e-9)
    assert float(corrected.pvalue) == pytest.approx(ref["p_corrected"], rel=1e-6)
    assert float(corrected.pvalue) == pytest.approx(_z_p(ref["S"], ref["varS_corrected"]), rel=1e-9)
    if kind != "gaps":  # rkt computes tiny p-values as 1 - pnorm; trend::smk.test is exact
        assert float(plain.pvalue) == pytest.approx(ref["p"], rel=1e-6)
    # R spaces the years exactly; here the dates are real (365 or 366 days apart)
    assert float(plain.slope) == pytest.approx(ref["slope"], rel=2e-3)
    assert float(corrected.slope) == float(plain.slope)
    assert corrected.attrs["seasonal"] == "month" and corrected.attrs["seasons"] == 12
    assert corrected.attrs["seasonal_correction"] == "Hirsch-Slack 1984"
    assert plain.attrs["seasonal_correction"] == "none"


def _loop_reference(values, years, year_index, seasons, n_years):
    """Seasonal S, variances and slope with plain loops (as in rkt; seasons < 4 values skipped)."""
    grid = np.full((n_years, seasons.max() + 1), np.nan)
    when = np.full_like(grid, np.nan)
    grid[year_index, seasons] = values
    when[year_index, seasons] = years
    used = [g for g in range(grid.shape[1]) if np.isfinite(grid[:, g]).sum() >= 4]
    s, var, slopes = 0.0, 0.0, []
    for g in used:
        col, t = grid[:, g], when[:, g]
        ok = np.isfinite(col)
        for i in range(n_years):
            for j in range(i + 1, n_years):
                if ok[i] and ok[j]:
                    s += np.sign(col[j] - col[i])
                    slopes.append((col[j] - col[i]) / (t[j] - t[i]))
        n = ok.sum()
        _, counts = np.unique(col[ok], return_counts=True)
        var += (n * (n - 1) * (2 * n + 5) - np.sum(counts * (counts - 1) * (2 * counts + 5))) / 18

    def ranks(col):
        ok = np.isfinite(col)
        r = np.full(col.size, (ok.sum() + 1) / 2.0)
        for i in np.nonzero(ok)[0]:
            r[i] = (ok.sum() + 1 + np.sum(np.sign(col[i] - col[ok]))) / 2.0
        return r

    corrected = 0.0
    for g in used:
        for h in used:
            a, b = grid[:, g], grid[:, h]
            k = 0.0
            for i in range(n_years):
                for j in range(i + 1, n_years):
                    product = (a[j] - a[i]) * (b[j] - b[i])
                    k += np.sign(product) if np.isfinite(product) else 0.0
            big_g = np.sum(ranks(a) * ranks(b))
            na, nb = np.isfinite(a).sum(), np.isfinite(b).sum()
            corrected += (k + 4 * big_g - n_years * (na + 1) * (nb + 1)) / 3
    return s, var, corrected, np.median(slopes)


def test_seasonal_matches_loop_reference_with_gaps_and_ties():
    rng = np.random.default_rng(11)
    q_time = pd.to_datetime([f"{y}-{m:02d}-15" for y in range(2001, 2013) for m in (1, 4, 7, 10)])
    labels = np.tile(["DJF", "MAM", "JJA", "SON"], 12)  # one value per season and year
    q_years = (q_time - q_time[0]).days.to_numpy() / 365.2425
    values = np.round(rng.normal(0, 1, (6, q_time.size)) + 0.1 * q_years, 1)  # ties
    values[rng.uniform(size=values.shape) < 0.1] = np.nan
    cube = xr.DataArray(values, dims=("pixel", "time"), coords={"time": q_time})
    result = trend(cube, per="year", seasonal=labels, min_valid=8)
    codes = np.unique(labels, return_inverse=True)[1]
    year_index = q_time.year.to_numpy() - 2001
    for px in range(cube.sizes["pixel"]):
        v = values[px]
        ok = np.isfinite(v)
        s, var, corrected, slope = _loop_reference(v[ok], q_years[ok], year_index[ok],
                                                   codes[ok], 12)  # fmt: skip
        assert float(result.slope[px]) == pytest.approx(slope, rel=1e-12)
        assert float(result.pvalue[px]) == pytest.approx(_z_p(s, corrected), rel=1e-9)
    plain = trend(cube, per="year", seasonal=labels, min_valid=8, seasonal_correction=False)
    v = values[0]
    ok = np.isfinite(v)
    s, var, _, _ = _loop_reference(v[ok], q_years[ok], year_index[ok], codes[ok], 12)
    assert float(plain.pvalue[0]) == pytest.approx(_z_p(s, var), rel=1e-9)


def test_seasonal_recovers_a_trend_under_a_seasonal_cycle():
    rng = np.random.default_rng(3)
    time = pd.date_range("2001-01-15", periods=20 * 12, freq="MS") + pd.Timedelta(days=14)
    t = (time - time[0]).days.to_numpy() / 365.2425
    cycle = 0.3 * np.sin(2 * np.pi * (time.month.to_numpy() - 1) / 12)
    trend_cube = 0.5 + cycle + 0.004 * t + rng.normal(0, 0.02, (10, 10, t.size))
    cube = xr.DataArray(trend_cube, dims=("y", "x", "time"), coords={"time": time})
    result = trend(cube, seasonal="month")
    assert float(result.slope.mean()) == pytest.approx(0.04, abs=0.003)  # per decade
    assert bool(result.significant.all())
    null = xr.DataArray(0.5 + cycle + rng.normal(0, 0.02, (30, 30, t.size)),
                        dims=("y", "x", "time"), coords={"time": time})  # fmt: skip
    share = float(trend(null, seasonal="month").significant.mean())
    assert share < 0.1  # about 5 % expected


def test_seasonal_labels_month_and_errors():
    series = _reference_series("trend")
    by_month = trend(series, seasonal="month")
    by_labels = trend(series, seasonal=series.time.dt.month.values)
    assert float(by_labels.pvalue) == float(by_month.pvalue)
    assert by_labels.attrs["seasonal"] == "labels"
    with pytest.raises(ValueError, match="seasonal must be"):
        trend(series, seasonal="week")
    with pytest.raises(ValueError, match="one label per time step"):
        trend(series, seasonal=np.arange(5))
    sixteen = pd.date_range("2001-01-01", "2012-12-31", freq="16D")
    composite = xr.DataArray(np.arange(sixteen.size, dtype=float), dims="time",
                             coords={"time": sixteen})  # fmt: skip
    with pytest.raises(ValueError, match=r"more than one value in a season and year.*2001"):
        trend(composite, seasonal="month")
    annual = xr.DataArray(
        np.arange(12.0),
        dims="time",
        coords={"time": pd.date_range("2001-07-01", periods=12, freq="YS")},
    )
    with pytest.raises(ValueError, match="at least 2 seasons"):
        trend(annual, seasonal="month")


def test_subannual_data_without_seasonal_warns():
    series = _reference_series("trend")
    with pytest.warns(eofigs.stats.TrendWarning, match="seasonal="):
        plain = trend(series)
    explicit = trend(series, seasonal="none")  # no warning: the choice is stated
    assert float(explicit.pvalue) == float(plain.pvalue)
    assert explicit.attrs["seasonal"] == "none"
    annual = xr.DataArray(
        np.arange(12.0),
        dims="time",
        coords={"time": pd.date_range("2001-07-01", periods=12, freq="YS")},
    )
    trend(annual)  # annual data: no warning


def test_short_record_falls_back_to_the_uncorrected_test():
    series = _reference_series("trend").isel(time=slice(0, 9 * 12))  # 9 complete years
    with pytest.warns(eofigs.stats.TrendWarning, match="10 complete years"):
        result = trend(series, seasonal="month")
    plain = trend(series, seasonal="month", seasonal_correction=False)
    assert float(result.pvalue) == float(plain.pvalue)
    assert result.attrs["seasonal_correction"].startswith("not applied")


def test_seasonal_blocks_and_dask_agree():
    rng = np.random.default_rng(5)
    time = pd.date_range("2001-01-15", periods=12 * 12, freq="MS") + pd.Timedelta(days=14)
    cube = xr.DataArray(rng.normal(0, 1, (7, 9, time.size)), dims=("y", "x", "time"),
                        coords={"time": time})  # fmt: skip
    full = trend(cube, seasonal="month")
    small = trend(cube, seasonal="month", memory_mb=0.01)
    lazy = trend(cube.chunk({"y": 3}), seasonal="month").compute()
    for result in (small, lazy):
        assert np.allclose(result.pvalue, full.pvalue, equal_nan=True)
        assert np.allclose(result.slope, full.slope, equal_nan=True)
