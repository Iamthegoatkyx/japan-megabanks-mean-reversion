# Do Japan's megabanks mean-revert?

**Question.** Do MUFG (8306.T), SMFG (8316.T) and Mizuho (8411.T) bounce back
after sharp drops enough to beat buy-and-hold of the same stocks, after
trading costs?

The rule, the data, the test period and what counts as success were written
down in [PREREGISTRATION.md](PREREGISTRATION.md) **before** any price data was
downloaded, and every change since is a dated, numbered amendment in that file.
The git history on GitHub shows the order: rule first, data and code next,
out-of-sample run last (run once).

## Method

**Data.** Daily dividend-adjusted closes from Yahoo Finance (`auto_adjust=True`),
so each daily % change is the total return. Rows with zero volume or that exactly
copy the previous day are removed (Amendment 2): they are exchange holidays,
days Yahoo is missing, or copied rows. All returns are in JPY. Idle cash earns
Japan's overnight call rate (FRED `IRSTCI01JPM156N`), negative values included.

**The rule** (the same for all three banks, no per-stock tuning):

| | |
|---|---|
| Entry | close at least 5% below its 20-day moving average, after a "reset" (a close at or above the average since the last exit) |
| Exit | the first of: back to the average; holding day 14 (sold on day 15); close 10% below the price paid |
| Execution | a decision made at day t's close is traded at day t+1's close |
| Costs | 15 bps per side (30 bps per round trip) |

**Test.** In-sample: start of data to 2017-12-31. Out-of-sample: 2018-01-01 to
the run date. The main test compares an equal-weight portfolio of the three
strategies with an equal-weight buy-and-hold of the three banks, over the same
dates, with four criteria set in advance (Sharpe higher at 15 bps; 95% block
bootstrap interval of the Sharpe difference above zero; Sharpe still higher at
25 bps; at least 20 trades).

**Robustness.** Cost sensitivity at 0, 10, 25 and 50 bps; a 42-combination
(threshold, window) grid on in-sample data only, as a diagnostic, never used to
pick settings; a block bootstrap (21-day blocks, 5,000 resamples) of the
Sharpe difference.

**Checks against fooling myself.** Tests show that scrambling future prices
never changes past signals or returns, that a round trip costs exactly
2 × 15 bps, and that each exit rule fires on exactly the right day. The tests
were also run against deliberately broken code to check that they fail.

## How to run it (Mac)

```bash
cd japan-megabanks-mean-reversion
python3 -m venv .venv          # a private Python just for this project
source .venv/bin/activate      # use it in this terminal (run again in each new terminal)
pip install -r requirements.txt
pytest                         # all tests should pass
```

| Command | What it does |
|---|---|
| `python check_data.py` | downloads/caches prices, data-quality report (in-sample only; `--full` for everything) |
| `python run.py` | in-sample backtest, writes `outputs/in-sample/` |
| `python robustness.py` | in-sample cost sensitivity and parameter grid heatmap |
| `python run.py --period out-of-sample --confirm` | the one-time out-of-sample test, writes `outputs/out-of-sample/` |
| `python live_signal.py` | paper trading: today's signal per bank, appended to `paper_log.csv` (run after the Tokyo close) |

Prices are cached in `data/` (not committed; each `results.md` records the
download date and a SHA-256 of the file used). Yahoo revises adjusted prices
over time, so a fresh download can give slightly different numbers.

## Project layout

```
backtester/
  config.py       every setting: the rule, the split date, the universe
  data.py         download, cache, cleaning, quality checks, cash rate
  signals.py      mean_reversion_signal: the rule, as a three-state loop
  backtest.py     signal -> positions (traded one day later) -> returns after costs
  metrics.py      CAGR, volatility, Sharpe, drawdown, trade list
  stats.py        block bootstrap of the Sharpe difference
  experiments.py  running the universe, cost sensitivity, grid, preregistered test
  plots.py        charts
  report.py       results.md files
tests/            pytest tests for all of the above
outputs/          results and charts, per period and per bank
```

Where the numbers are: [in-sample portfolio](outputs/in-sample/portfolio/results.md),
[out-of-sample portfolio](outputs/out-of-sample/portfolio/results.md), and one
folder per bank next to each.

## Results

<!-- Written by me. -->

## Why it might not work

<!-- Written by me. -->

## Limitations

<!-- Written by me. -->
