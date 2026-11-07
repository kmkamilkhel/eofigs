import numpy as np
import pandas as pd
import pytest
import rioxarray  # noqa: F401
import xarray as xr
from scipy import stats as sps

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
    assert result.slope.attrs["units"] == "1 per decade"
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
