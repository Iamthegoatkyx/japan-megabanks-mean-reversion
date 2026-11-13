"""Running the strategy on the whole universe, and the robustness experiments.

run.py and robustness.py both use these, so every number comes from the same code.
"""
from __future__ import annotations

import pandas as pd

from . import config
from .backtest import buy_and_hold, run_backtest
from .data import daily_cash_rate, load_cash_rate, load_prices
from .metrics import summarize_portfolio
from .signals import mean_reversion_signal

PERIODS = ("in-sample", "out-of-sample")


def backtest_bank(ticker: str, period: str, cost_bps: float, monthly_cash: pd.Series,
                  signal_kwargs: dict | None = None, earliest_start=None):
    """Strategy and buy-and-hold backtests for one bank, cut to the same dates.

    signal_kwargs: rule settings to override (only the parameter grid does this).
    earliest_start: don't measure before this date (lets the grid compare every
    combination over identical dates, whatever its MA window).
    """
    if period not in PERIODS:
        raise ValueError(f"period must be one of {PERIODS}")
    signal_kwargs = signal_kwargs or {}
    window = signal_kwargs.get("window", config.MA_WINDOW)

    prices = load_prices(ticker)
    split = pd.Timestamp(config.OUT_OF_SAMPLE_START)
    if period == "in-sample":
        # Cut BEFORE computing anything, so no out-of-sample price is ever used.
        prices = prices[prices.index < split]

    cash = daily_cash_rate(monthly_cash, prices.index)
    signal = mean_reversion_signal(prices, **signal_kwargs)
    strategy = run_backtest(prices, signal, cost_bps, cash, delay=config.EXECUTION_DELAY)

    if period == "in-sample":
        # First day the strategy COULD hold the stock: MA warm-up (window - 1 rows),
        # then signal -> trade -> first return (2 more rows).
        start = prices.index[window - 1 + 1 + config.EXECUTION_DELAY]
    else:
        # The MA warms up on in-sample history (it only looks backwards, so that's
        # allowed); results are measured from the split date.
        start = prices.index[prices.index >= split][0]
    if earliest_start is not None:
        start = max(start, prices.index[prices.index >= earliest_start][0])

    strategy = strategy.loc[start:]
    # The benchmark buys on the same first day and pays the same entry cost.
    benchmark = buy_and_hold(prices.loc[start:], cost_bps, cash.loc[start:])
    return strategy, benchmark


def run_universe(period: str, cost_bps: float | None = None,
                 signal_kwargs: dict | None = None, earliest_start=None):
    """Backtest every bank in the main universe. Returns ({name: strategy}, {name: benchmark})."""
    universe = config.UNIVERSES[config.MAIN_UNIVERSE]
    cost = universe["cost_bps"] if cost_bps is None else cost_bps
    monthly_cash = load_cash_rate(universe["cash_rate_fred_id"])
    strategies, benchmarks = {}, {}
    for ticker, name in universe["tickers"].items():
        strategies[name], benchmarks[name] = backtest_bank(
            ticker, period, cost, monthly_cash, signal_kwargs, earliest_start)
    return strategies, benchmarks


def common_dates(bts: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Cut every backtest to the dates all of them cover (the portfolio needs all three)."""
    start = max(bt.index[0] for bt in bts.values())
    end = min(bt.index[-1] for bt in bts.values())
    return {name: bt.loc[start:end] for name, bt in bts.items()}


def cost_sensitivity(period: str, costs=(0, 10, 25, 50)) -> pd.DataFrame:
    """Portfolio Sharpe of strategy and buy-and-hold at each cost level (bps per side)."""
    rows = []
    for cost in costs:
        strategies, benchmarks = run_universe(period, cost_bps=cost)
        s = summarize_portfolio(common_dates(strategies), cost)
        b = summarize_portfolio(common_dates(benchmarks), cost)
        rows.append({"cost_bps": cost, "strategy_sharpe": s["Sharpe"],
                     "buy_hold_sharpe": b["Sharpe"], "strategy_cagr": s["CAGR"],
                     "buy_hold_cagr": b["CAGR"], "trades": s["Trades"]})
    return pd.DataFrame(rows).set_index("cost_bps")


def parameter_grid(thresholds, windows) -> pd.DataFrame:
    """Portfolio Sharpe (strategy minus buy-and-hold) for every (threshold, window).

    IN-SAMPLE ONLY, by design: there is no `period` argument, so this can never
    be pointed at the out-of-sample data. Every combination is measured over the
    same dates: from the point where even the longest window has warmed up.
    """
    # Find the latest first-tradable date across banks for the LONGEST window.
    probe, _ = run_universe("in-sample", signal_kwargs={"window": max(windows)})
    earliest = max(bt.index[0] for bt in probe.values())

    cost = config.UNIVERSES[config.MAIN_UNIVERSE]["cost_bps"]
    rows = []
    for threshold in thresholds:
        for window in windows:
            kwargs = {"entry_below": threshold, "window": window}
            strategies, benchmarks = run_universe("in-sample", signal_kwargs=kwargs,
                                                  earliest_start=earliest)
            s = summarize_portfolio(common_dates(strategies), cost)
            b = summarize_portfolio(common_dates(benchmarks), cost)
            rows.append({"threshold": threshold, "window": window,
                         "sharpe_diff": s["Sharpe"] - b["Sharpe"],
                         "strategy_sharpe": s["Sharpe"], "trades": s["Trades"]})
    return pd.DataFrame(rows)
