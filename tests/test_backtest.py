"""The engine must never use the future, and must charge costs exactly."""
import numpy as np
import pandas as pd
import pytest

from backtester.backtest import (
    buy_and_hold, daily_cash_return, equal_weight, pnl_from_positions,
    positions_from_signal, run_backtest,
)


def random_prices(n=300, seed=1):
    """A made-up random-walk price series on business days."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=n)
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, n))), index=dates)


def toy_signal(prices):
    """A stand-in signal (NOT the real rule): long when below the 20-day MA.
    Like the real one, it only uses closes up to and including day t."""
    ma = prices.rolling(20).mean()
    return (prices < ma).astype(float).where(ma.notna())


# ---------------------------------------------------------------- look-ahead

def test_signal_is_traded_one_day_late():
    signal = pd.Series([0, 1, 1, 0, 0], dtype=float)
    # Decided at close 1, bought at close 2, so first earns the return on day 3.
    assert list(positions_from_signal(signal)) == [0, 0, 0, 1, 1]


def test_negative_delay_is_refused():
    with pytest.raises(ValueError):
        positions_from_signal(pd.Series([0.0, 1.0]), delay=-1)


@pytest.mark.parametrize("cutoff", range(30, 290, 10))
def test_scrambling_future_prices_does_not_change_past_returns(cutoff):
    # Many cutoffs, not one: a leak only shows on days where the scrambled
    # future happens to flip the signal, so a single cutoff can miss it.
    prices = random_prices()
    # Same history up to day `cutoff`, completely different prices afterwards.
    scrambled = prices.copy()
    rng = np.random.default_rng(cutoff)
    scrambled.iloc[cutoff + 1:] = rng.permutation(prices.iloc[cutoff + 1:].to_numpy()) * 1.5

    before = run_backtest(prices, toy_signal(prices), cost_bps=15, cash_rate=0.01)
    after = run_backtest(scrambled, toy_signal(scrambled), cost_bps=15, cash_rate=0.01)

    pd.testing.assert_series_equal(before["net"].iloc[:cutoff + 1],
                                   after["net"].iloc[:cutoff + 1])
    # Sanity check that the scramble actually changed something later on.
    assert not before["net"].iloc[cutoff + 1:].equals(after["net"].iloc[cutoff + 1:])


# ---------------------------------------------------------------- costs

def test_round_trip_costs_exactly_two_sides():
    prices = pd.Series([100.0] * 6, index=pd.bdate_range("2021-01-04", periods=6))
    position = pd.Series([0, 0, 1, 1, 0, 0], index=prices.index, dtype=float)
    bt = pnl_from_positions(prices, position, cost_bps=15, cash_rate=0.0)
    # Flat prices and no cash interest: the only thing that changes equity is cost.
    assert bt["cost"].sum() == pytest.approx(2 * 15 / 10_000)
    assert list(bt["cost"] > 0) == [False, False, True, False, True, False]
    assert bt["equity"].iloc[-1] == pytest.approx((1 - 0.0015) ** 2)


def test_buy_and_hold_pays_one_entry_cost_only():
    prices = random_prices(50)
    bt = buy_and_hold(prices, cost_bps=15, cash_rate=0.0)
    assert bt["cost"].sum() == pytest.approx(0.0015)
    assert bt["cost"].iloc[0] == pytest.approx(0.0015)


# ---------------------------------------------------------------- cash

def test_cash_compounds_to_the_annual_rate():
    assert (1 + daily_cash_return(0.02)) ** 252 == pytest.approx(1.02)


def test_cash_rate_series_is_used_day_by_day():
    dates = pd.bdate_range("2021-01-04", periods=3)
    prices = pd.Series([100.0, 110.0, 120.0], index=dates)
    rates = pd.Series([0.0, -0.001, 0.01], index=dates)   # negative rate allowed
    bt = pnl_from_positions(prices, pd.Series(0.0, index=dates), 15, rates)
    # Out of the market: we earn only cash, so stock moves don't matter.
    assert bt["net"].iloc[1] == pytest.approx(daily_cash_return(-0.001))
    assert bt["net"].iloc[2] == pytest.approx(daily_cash_return(0.01))


# ---------------------------------------------------------------- portfolio

def test_equal_weight_fills_a_missing_day_with_zero_not_dropping_the_day():
    d = pd.bdate_range("2021-01-04", periods=3)
    a = pd.Series([0.0, 0.03, 0.01], index=d)
    b = pd.Series([0.0, 0.06], index=d[[0, 2]])  # b has no row on the middle day
    port = equal_weight({"a": a, "b": b})
    assert list(port) == pytest.approx([0.0, 0.015, 0.035])


def test_portfolio_cash_covers_days_missing_from_one_bank():
    from backtester.backtest import portfolio_cash
    d = pd.bdate_range("2021-01-04", periods=3)
    a = pd.DataFrame({"cash_ret": [0.0, 0.0001, 0.0001]}, index=d)
    b = pd.DataFrame({"cash_ret": [0.0, 0.0001]}, index=d[[0, 2]])   # b misses day 1
    cash = portfolio_cash({"b": b, "a": a})
    assert not cash.isna().any() and len(cash) == 3


def test_sharpe_refuses_missing_cash_days():
    from backtester.metrics import sharpe
    net = pd.Series([0.01, -0.01, 0.02], index=pd.bdate_range("2021-01-04", periods=3))
    with pytest.raises(ValueError):
        sharpe(net, net.iloc[:2] * 0)
