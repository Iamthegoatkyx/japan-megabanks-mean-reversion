"""Run the preregistered strategy and the buy-and-hold benchmark.

Usage:
    python run.py                         # IN-SAMPLE only (before 2018), the default
    python run.py --period out-of-sample --confirm
                                          # the one-time out-of-sample test

PREREGISTRATION.md says the out-of-sample period is looked at ONCE, so that
run needs the extra --confirm flag, to make it hard to do by accident.
"""
import argparse

import pandas as pd

from backtester import config
from backtester.backtest import buy_and_hold, run_backtest
from backtester.data import daily_cash_rate, load_cash_rate, load_prices
from backtester.metrics import markdown_table, summarize, summarize_portfolio, trade_list
from backtester.signals import mean_reversion_signal


def backtest_one_bank(ticker: str, period: str, cost_bps: float, monthly_cash: pd.Series):
    """Strategy and benchmark backtests for one bank, cut to the same dates."""
    prices = load_prices(ticker)
    split = pd.Timestamp(config.OUT_OF_SAMPLE_START)
    if period == "in-sample":
        # Cut BEFORE computing anything, so no out-of-sample price is ever used.
        prices = prices[prices.index < split]

    cash = daily_cash_rate(monthly_cash, prices.index)
    signal = mean_reversion_signal(prices)
    strategy = run_backtest(prices, signal, cost_bps, cash, delay=config.EXECUTION_DELAY)

    if period == "in-sample":
        # First day the strategy COULD hold the stock: MA warm-up (window - 1 rows),
        # then signal -> trade -> first return (2 more rows).
        start = prices.index[config.MA_WINDOW - 1 + 1 + config.EXECUTION_DELAY]
    else:
        # The signal used in-sample history to warm up its MA (that's allowed:
        # it only looks backwards). Results are measured from the split date.
        start = prices.index[prices.index >= split][0]

    strategy = strategy.loc[start:]
    # The benchmark buys on the same first day and pays the same entry cost.
    benchmark = buy_and_hold(prices.loc[start:], cost_bps, cash.loc[start:])
    return strategy, benchmark


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=["in-sample", "out-of-sample"], default="in-sample")
    parser.add_argument("--confirm", action="store_true",
                        help="required for the one-time out-of-sample run")
    args = parser.parse_args()
    if args.period == "out-of-sample" and not args.confirm:
        raise SystemExit("Out-of-sample is run once (PREREGISTRATION.md). Add --confirm if you mean it.")

    universe = config.UNIVERSES[config.MAIN_UNIVERSE]
    cost = universe["cost_bps"]
    monthly_cash = load_cash_rate(universe["cash_rate_fred_id"])

    strategies, benchmarks, rows = {}, {}, {}
    for ticker, name in universe["tickers"].items():
        strategy, benchmark = backtest_one_bank(ticker, args.period, cost, monthly_cash)
        strategies[name], benchmarks[name] = strategy, benchmark
        print(f"{name}: {strategy.index[0].date()} to {strategy.index[-1].date()}")
        rows[f"{name} strategy"] = summarize(strategy, cost)
        rows[f"{name} buy & hold"] = summarize(benchmark, cost)

    # The portfolio needs all three banks, so it starts when the youngest one does.
    common_start = max(bt.index[0] for bt in strategies.values())
    common_end = min(bt.index[-1] for bt in strategies.values())
    def cut(bts):
        return {n: bt.loc[common_start:common_end] for n, bt in bts.items()}
    print(f"Portfolio: {common_start.date()} to {common_end.date()}\n")
    rows["Portfolio strategy"] = summarize_portfolio(cut(strategies), cost)
    rows["Portfolio buy & hold"] = summarize_portfolio(cut(benchmarks), cost)

    print(f"Period: {args.period}  |  costs {cost:g} bps per side  |  "
          f"cash: {universe['cash_rate_fred_id']}\n")
    print(markdown_table(rows))

    gap_trades = pd.concat(
        [trade_list(bt, cost).assign(bank=n) for n, bt in strategies.items()])
    gap_trades = gap_trades[gap_trades["crosses_gap"]]
    if not gap_trades.empty:
        print("\nTrades open across a data gap (check by hand):")
        print(gap_trades.to_string(index=False))


if __name__ == "__main__":
    main()
