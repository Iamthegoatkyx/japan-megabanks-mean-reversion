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
    # Keep the moving average next to each day, computed on the FULL history
    # (before slicing), so trade_list can tell why each trade ended.
    strategy["ma"] = prices.rolling(window).mean()

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
                 signal_kwargs: dict | None = None, earliest_start=None,
                 universe: str = config.MAIN_UNIVERSE):
    """Backtest every stock in a universe (default: the main, Japan one).
    Returns ({name: strategy}, {name: benchmark})."""
    settings = config.UNIVERSES[universe]
    cost = settings["cost_bps"] if cost_bps is None else cost_bps
    monthly_cash = load_cash_rate(settings["cash_rate_fred_id"])
    strategies, benchmarks = {}, {}
    for ticker, name in settings["tickers"].items():
        strategies[name], benchmarks[name] = backtest_bank(
            ticker, period, cost, monthly_cash, signal_kwargs, earliest_start)
    return strategies, benchmarks


def common_dates(bts: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Cut every backtest to the dates all of them cover (the portfolio needs all three)."""
    start = max(bt.index[0] for bt in bts.values())
    end = min(bt.index[-1] for bt in bts.values())
    return {name: bt.loc[start:end] for name, bt in bts.items()}


def cost_sensitivity(period: str, costs=(0, 10, 25, 50),
                     universe: str = config.MAIN_UNIVERSE) -> pd.DataFrame:
    """Portfolio Sharpe of strategy and buy-and-hold at each cost level (bps per side)."""
    rows = []
    for cost in costs:
        strategies, benchmarks = run_universe(period, cost_bps=cost, universe=universe)
        s = summarize_portfolio(common_dates(strategies), cost)
        b = summarize_portfolio(common_dates(benchmarks), cost)
        rows.append({"cost_bps": cost, "strategy_sharpe": s["Sharpe"],
                     "buy_hold_sharpe": b["Sharpe"], "strategy_cagr": s["CAGR"],
                     "buy_hold_cagr": b["CAGR"], "trades": s["Trades"]})
    return pd.DataFrame(rows).set_index("cost_bps")


def parameter_grid(thresholds, windows, universe: str = config.MAIN_UNIVERSE) -> pd.DataFrame:
    """Portfolio Sharpe (strategy minus buy-and-hold) for every (threshold, window).

    IN-SAMPLE ONLY, by design: there is no `period` argument, so this can never
    be pointed at the out-of-sample data. Every combination is measured over the
    same dates: from the point where even the longest window has warmed up.
    """
    # Find the latest first-tradable date across banks for the LONGEST window.
    probe, _ = run_universe("in-sample", signal_kwargs={"window": max(windows)},
                            universe=universe)
    earliest = max(bt.index[0] for bt in probe.values())

    cost = config.UNIVERSES[universe]["cost_bps"]
    rows = []
    for threshold in thresholds:
        for window in windows:
            kwargs = {"entry_below": threshold, "window": window}
            strategies, benchmarks = run_universe("in-sample", signal_kwargs=kwargs,
                                                  earliest_start=earliest, universe=universe)
            s = summarize_portfolio(common_dates(strategies), cost)
            b = summarize_portfolio(common_dates(benchmarks), cost)
            rows.append({"threshold": threshold, "window": window,
                         "sharpe_diff": s["Sharpe"] - b["Sharpe"],
                         "strategy_sharpe": s["Sharpe"], "trades": s["Trades"],
                         "strategy_cagr": s["CAGR"], "strategy_max_dd": s["Max DD"]})
    return pd.DataFrame(rows)


def preregistered_test(strategies: dict, benchmarks: dict, period: str,
                       universe: str = config.MAIN_UNIVERSE) -> dict:
    """Apply the success criteria from PREREGISTRATION.md (the same criteria are
    used in PREREGISTRATION_US.md), mechanically.

    `strategies` / `benchmarks` are the backtests from run_universe at the
    universe's own cost (15 bps for Japan, 5 bps for the US).
    This only checks the written rules; what the result MEANS is for the README.
    """
    from .backtest import equal_weight, portfolio_cash
    from .stats import bootstrap_sharpe_diff

    port_s, port_b = common_dates(strategies), common_dates(benchmarks)
    cost = config.UNIVERSES[universe]["cost_bps"]
    s, b = summarize_portfolio(port_s, cost), summarize_portfolio(port_b, cost)
    boot = bootstrap_sharpe_diff(
        equal_weight({n: bt["net"] for n, bt in port_s.items()}),
        equal_weight({n: bt["net"] for n, bt in port_b.items()}),
        portfolio_cash(port_s))

    s25_runs, b25_runs = run_universe(period, cost_bps=25, universe=universe)
    s25 = summarize_portfolio(common_dates(s25_runs), 25)
    b25 = summarize_portfolio(common_dates(b25_runs), 25)

    criteria = [
        (f"1. Sharpe higher than buy & hold at {cost:g} bps",
         f"{s['Sharpe']:.2f} vs {b['Sharpe']:.2f}", s["Sharpe"] > b["Sharpe"]),
        ("2. 95% bootstrap interval of Sharpe difference entirely above 0",
         f"[{boot['ci_low']:.2f}, {boot['ci_high']:.2f}]", boot["ci_low"] > 0),
        ("3. Sharpe still higher at 25 bps",
         f"{s25['Sharpe']:.2f} vs {b25['Sharpe']:.2f}", s25["Sharpe"] > b25["Sharpe"]),
        ("4. At least 20 closed trades in total", str(s["Trades"]), s["Trades"] >= 20),
    ]
    sharpe_gap = s["Sharpe"] - b["Sharpe"]
    dd_better_by = s["Max DD"] - b["Max DD"]           # both negative; positive = smaller DD
    partial = [
        ("Sharpe within ±0.10 of buy & hold", f"{sharpe_gap:+.2f}", abs(sharpe_gap) <= 0.10),
        ("Max drawdown at least 10 points smaller", f"{dd_better_by * 100:+.1f} points",
         dd_better_by >= 0.10),
    ]
    if all(met for *_, met in criteria):
        outcome = "WORKS (all four criteria met)"
    elif all(met for *_, met in partial):
        outcome = "PARTIAL: risk reduction, not an edge"
    else:
        outcome = "DOES NOT WORK (by the preregistered criteria)"
    return {"criteria": criteria, "partial": partial, "outcome": outcome,
            "bootstrap": boot, "strategy": s, "benchmark": b}


def criteria_markdown(result: dict, period: str) -> str:
    """The preregistered test as a markdown section."""
    lines = ["## Preregistered test" + ("" if period == "out-of-sample"
             else " (in-sample, FOR REFERENCE ONLY: the real test is out-of-sample)"), "",
             "| Criterion | Value | Met? |", "|---|---|---|"]
    lines += [f"| {c} | {v} | {'yes' if m else 'no'} |" for c, v, m in result["criteria"]]
    lines += ["", "Partial-result check:", "", "| Condition | Value | Met? |", "|---|---|---|"]
    lines += [f"| {c} | {v} | {'yes' if m else 'no'} |" for c, v, m in result["partial"]]
    boot = result["bootstrap"]
    lines += ["", f"**Mechanical outcome: {result['outcome']}**", "",
              f"Bootstrap: {boot['n_boot']} resamples, {boot['block']}-day blocks, "
              f"observed difference {boot['observed_diff']:+.3f}, share of resamples where "
              f"the strategy is not better: {boot['share_not_better']:.1%}."]
    return "\n".join(lines)
