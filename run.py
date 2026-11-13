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
from backtester.experiments import common_dates, run_universe
from backtester.metrics import markdown_table, summarize, summarize_portfolio, trade_list


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
    strategies, benchmarks = run_universe(args.period)

    rows = {}
    for name in strategies:
        bt = strategies[name]
        print(f"{name}: {bt.index[0].date()} to {bt.index[-1].date()}")
        rows[f"{name} strategy"] = summarize(bt, cost)
        rows[f"{name} buy & hold"] = summarize(benchmarks[name], cost)

    # The portfolio needs all three banks, so it starts when the youngest one does.
    port_s, port_b = common_dates(strategies), common_dates(benchmarks)
    first = next(iter(port_s.values())).index
    print(f"Portfolio: {first[0].date()} to {first[-1].date()}\n")
    rows["Portfolio strategy"] = summarize_portfolio(port_s, cost)
    rows["Portfolio buy & hold"] = summarize_portfolio(port_b, cost)

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
