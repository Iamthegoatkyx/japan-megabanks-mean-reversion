"""The bootstrap should say 'no difference' when there is none, and find a clear one."""
import numpy as np
import pandas as pd
import pytest

from backtester.stats import bootstrap_sharpe_diff


def series(values):
    return pd.Series(values, index=pd.bdate_range("2018-01-01", periods=len(values)))


def test_identical_series_have_zero_difference():
    rng = np.random.default_rng(0)
    r = series(rng.normal(0.0005, 0.01, 1000))
    out = bootstrap_sharpe_diff(r, r, series(np.zeros(1000)), n_boot=200)
    assert out["observed_diff"] == pytest.approx(0)
    assert out["ci_low"] == pytest.approx(0) and out["ci_high"] == pytest.approx(0)


def test_clearly_better_strategy_has_interval_above_zero():
    rng = np.random.default_rng(1)
    market = rng.normal(0.0, 0.01, 2000)
    bench = series(market)
    strat = series(market * 0.5 + 0.001)       # half the risk plus a steady 0.1% a day
    out = bootstrap_sharpe_diff(strat, bench, series(np.zeros(2000)), n_boot=500)
    assert out["ci_low"] > 0


def test_pure_noise_difference_interval_contains_zero():
    rng = np.random.default_rng(2)
    a, b = series(rng.normal(0, 0.01, 1500)), series(rng.normal(0, 0.01, 1500))
    out = bootstrap_sharpe_diff(a, b, series(np.zeros(1500)), n_boot=500)
    assert out["ci_low"] < 0 < out["ci_high"]


def test_same_seed_same_answer():
    rng = np.random.default_rng(3)
    a, b = series(rng.normal(0, 0.01, 500)), series(rng.normal(0, 0.01, 500))
    cash = series(np.zeros(500))
    assert bootstrap_sharpe_diff(a, b, cash, n_boot=100) == bootstrap_sharpe_diff(a, b, cash, n_boot=100)
