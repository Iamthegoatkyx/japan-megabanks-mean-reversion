"""Robustness checks on IN-SAMPLE data: cost sensitivity and the parameter grid.

Usage:  python robustness.py

The grid is a diagnostic, NOT a way to choose a better rule: the rule is fixed
by PREREGISTRATION.md. If we picked the best cell and then reported it, we'd be
reporting the luckiest of many tries. That's why the number of combinations is
printed: it tells the reader how many chances there were to get lucky.
"""
from pathlib import Path

from backtester import config
from backtester.experiments import cost_sensitivity, parameter_grid
from backtester.plots import cost_chart, heatmap

OUT = Path("outputs") / "in-sample"

# Chosen BEFORE running anything: a spread around the preregistered 5% / 20 days.
THRESHOLDS = [0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10]
WINDOWS = [10, 15, 20, 30, 40, 60]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    print("Cost sensitivity, equal-weight portfolio, in-sample:")
    costs = cost_sensitivity("in-sample")
    print(costs.round(3).to_string(), "\n")
    costs.to_csv(OUT / "cost_sensitivity.csv")
    cost_chart(costs, OUT / "cost_sensitivity.png",
               "In-sample portfolio Sharpe vs trading cost",
               preregistered_bps=config.UNIVERSES[config.MAIN_UNIVERSE]["cost_bps"])

    n = len(THRESHOLDS) * len(WINDOWS)
    print(f"Parameter grid: {len(THRESHOLDS)} thresholds x {len(WINDOWS)} windows "
          f"= {n} combinations tried (in-sample only)")
    grid = parameter_grid(THRESHOLDS, WINDOWS)
    grid.to_csv(OUT / "parameter_grid.csv", index=False)
    print(grid.pivot(index="threshold", columns="window", values="sharpe_diff")
              .round(2).to_string())
    print("\nTrades per combination:")
    print(grid.pivot(index="threshold", columns="window", values="trades").to_string())
    heatmap(grid, "sharpe_diff", OUT / "parameter_heatmap.png",
            f"In-sample: portfolio Sharpe minus buy-and-hold ({n} combinations)",
            highlight=(config.ENTRY_BELOW_MA, config.MA_WINDOW))
    print(f"\nCharts and CSVs saved in {OUT}/")


if __name__ == "__main__":
    main()
