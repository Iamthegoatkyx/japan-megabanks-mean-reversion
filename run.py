"""Run the preregistered strategy and buy-and-hold, and write the results.

Usage:
    python run.py                         # IN-SAMPLE only (before 2018), the default
    python run.py --period out-of-sample --confirm
                                          # the one-time out-of-sample test

PREREGISTRATION.md says the out-of-sample period is looked at ONCE, so that
run needs the extra --confirm flag, to make it hard to do by accident.

Writes outputs/<period>/<bank>/results.md (+ equity_drawdown.png, trades.csv)
and outputs/<period>/portfolio/results.md with the preregistered test.
"""
import argparse

import pandas as pd
from pathlib import Path

from backtester import config
from backtester.backtest import equal_weight
from backtester.experiments import (common_dates, cost_sensitivity, criteria_markdown,
                                    preregistered_test, run_universe)
from backtester.metrics import markdown_table, summarize, summarize_portfolio, trade_list
from backtester.plots import cost_chart
from backtester.report import breakdown_markdown, data_fingerprint, write_results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=["in-sample", "out-of-sample"], default="in-sample")
    parser.add_argument("--confirm", action="store_true",
                        help="required for the one-time out-of-sample run")
    args = parser.parse_args()
    if args.period == "out-of-sample" and not args.confirm:
        raise SystemExit("Out-of-sample is run once (PREREGISTRATION.md). Add --confirm if you mean it.")

    period = args.period
    out = Path("outputs") / period
    universe = config.UNIVERSES[config.MAIN_UNIVERSE]
    cost = universe["cost_bps"]
    common_notes = [f"Costs: {cost:g} bps per side. Cash: JPY call rate, FRED "
                    f"`{universe['cash_rate_fred_id']}`.",
                    f"Rule: {config.ENTRY_BELOW_MA:.0%} below the {config.MA_WINDOW}-day MA, "
                    f"max hold {config.MAX_HOLD_DAYS} days, stop {config.STOP_LOSS:.0%}, "
                    "reset rule (see PREREGISTRATION.md)."]

    strategies, benchmarks = run_universe(period)
    all_rows = {}
    for ticker, name in universe["tickers"].items():
        s_bt, b_bt = strategies[name], benchmarks[name]
        rows = {"Strategy": summarize(s_bt, cost), "Buy & hold": summarize(b_bt, cost)}
        all_rows[f"{name} strategy"], all_rows[f"{name} buy & hold"] = rows.values()
        write_results(out / ticker, f"{name} ({ticker})", period, s_bt["net"], b_bt["net"],
                      rows, common_notes + [f"Data: {data_fingerprint(ticker)}."],
                      trades=trade_list(s_bt, cost))

    # ---- the portfolio, which is what the preregistered test is about
    port_s, port_b = common_dates(strategies), common_dates(benchmarks)
    rows = {"Strategy": summarize_portfolio(port_s, cost),
            "Buy & hold": summarize_portfolio(port_b, cost)}
    all_rows["Portfolio strategy"], all_rows["Portfolio buy & hold"] = rows.values()

    costs = cost_sensitivity(period)
    costs.to_csv(out / "cost_sensitivity.csv")
    cost_chart(costs, out / "cost_sensitivity.png", f"{period}: portfolio Sharpe vs trading cost",
               preregistered_bps=cost)
    test = preregistered_test(strategies, benchmarks, period)

    # All closed trades of the three banks together (each bank's own period).
    all_trades = pd.concat([trade_list(bt, cost) for bt in strategies.values()])
    extra = [criteria_markdown(test, period), "",
             breakdown_markdown(all_trades).replace("### Why trades ended",
                                                    "## Why trades ended, all three banks"), "",
             "## Cost sensitivity", "", "```", costs.round(3).to_string(), "```", "",
             "![Cost sensitivity](../cost_sensitivity.png)"]
    if period == "in-sample":
        extra += ["", "## Parameter grid (in-sample only)", "",
                  "![Parameter heatmap](../parameter_heatmap.png)",
                  "", "Made by `robustness.py`. A diagnostic, not a way to pick settings."]
    write_results(out / "portfolio", "Equal-weight portfolio (MUFG, SMFG, Mizuho)", period,
                  equal_weight({n: bt["net"] for n, bt in port_s.items()}),
                  equal_weight({n: bt["net"] for n, bt in port_b.items()}),
                  rows, common_notes + ["Daily rebalanced to 1/3 each; rebalancing costs ignored."],
                  extra_md="\n".join(extra))

    # ---- the same headline numbers on screen
    print(f"Period: {period}\n")
    print(markdown_table(all_rows), "\n")
    print(criteria_markdown(test, period))
    print(f"\nWritten to {out}/")


if __name__ == "__main__":
    main()
