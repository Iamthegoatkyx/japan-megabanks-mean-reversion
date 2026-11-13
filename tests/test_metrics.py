"""Metrics and the trade list must match numbers we can work out by hand."""
import numpy as np
import pandas as pd
import pytest

from backtester.backtest import pnl_from_positions
from backtester.metrics import cagr, max_drawdown, sharpe, summarize, trade_list


def backtest_of(prices, position, dates=None, cost_bps=15):
    dates = dates if dates is not None else pd.bdate_range("2021-01-04", periods=len(prices))
    p = pd.Series(prices, index=dates, dtype=float)
    pos = pd.Series(position, index=dates, dtype=float)
    return pnl_from_positions(p, pos, cost_bps=cost_bps, cash_rate=0.0)


def test_cagr_of_doubling_in_two_calendar_years():
    dates = pd.to_datetime(["2020-01-01", "2021-01-01", "2022-01-01"])
    net = pd.Series([0.0, 1.0, 0.0], index=dates)        # equity goes 1 -> 2
    assert cagr(net) == pytest.approx(2 ** (1 / (731 / 365.25)) - 1)


def test_max_drawdown_from_peak():
    net = pd.Series([0.10, -0.50, 0.20])                  # 1.1 -> 0.55 -> 0.66
    assert max_drawdown(net) == pytest.approx(0.55 / 1.1 - 1)


def test_max_drawdown_counts_a_loss_on_day_one():
    assert max_drawdown(pd.Series([-0.2, 0.1])) == pytest.approx(-0.2)


def test_sharpe_is_zero_when_return_equals_cash_on_average():
    net = pd.Series([0.01, -0.01, 0.01, -0.01])
    assert sharpe(net, pd.Series(0.0, index=net.index)) == pytest.approx(0.0)


def test_one_round_trip_trade():
    # Position 1 on days 2-3: bought at close of day 1 (100), sold at close of day 3 (110).
    bt = backtest_of([100, 100, 105, 110, 110], [0, 0, 1, 1, 0])
    trades = trade_list(bt, cost_bps=15)
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["buy_date"] == bt.index[1] and t["sell_date"] == bt.index[3]
    assert t["days_held"] == 3
    assert t["net_return"] == pytest.approx(1.10 * (1 - 0.0015) ** 2 - 1)
    assert not t["open"] and not t["crosses_gap"]


def test_trade_still_open_at_the_end_is_marked_and_not_counted():
    bt = backtest_of([100, 100, 90, 95], [0, 0, 1, 1])
    trades = trade_list(bt, cost_bps=15)
    assert bool(trades["open"].iloc[0])
    assert summarize(bt, cost_bps=15)["Trades"] == 0


def test_trade_across_a_data_gap_is_flagged():
    dates = pd.to_datetime(["2008-12-22", "2008-12-24", "2009-01-05", "2009-01-06", "2009-01-07"])
    bt = backtest_of([100, 100, 110, 111, 111], [0, 0, 1, 1, 0], dates=dates)
    assert bool(trade_list(bt, cost_bps=15)["crosses_gap"].iloc[0])


def test_win_rate_and_average_trade():
    # Two trades: +10% then -10% (before costs).
    bt = backtest_of([100, 100, 110, 110, 110, 99, 99], [0, 0, 1, 0, 0, 1, 0])
    s = summarize(bt, cost_bps=0)
    assert s["Trades"] == 2
    assert s["Win rate"] == pytest.approx(0.5)
    assert s["Avg trade"] == pytest.approx(0.0)
    assert s["Avg days"] == pytest.approx(2)
