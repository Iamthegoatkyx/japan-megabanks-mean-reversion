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

The pre-registered rule failed. Out-of-sample (4 Jan 2018 to 13 Nov 2026),
after 15 bps per side, an equal-weight portfolio of the strategy on MUFG,
SMFG and Mizuho barely broke even, while buy-and-hold of the same banks
grew almost sixfold.

| Out-of-sample, portfolio | Strategy | Buy & hold |
|---|---:|---:|
| Sharpe | 0.05 | 0.89 |
| CAGR | 0.1% | 22.0% |
| Max drawdown | -29.7% | -47.5% |
| Time in market | 8.6% | 100% |
| ¥1 grew to | ¥1.01 | ¥5.84 |

Against the success criteria I set before any data existed:

| Criterion | Result | Met? |
|---|---|---|
| Higher Sharpe at 15 bps | 0.05 vs 0.89 | No |
| Bootstrap 95% interval above 0 | [-1.54, -0.15] | No |
| Higher Sharpe at 25 bps | 0.00 vs 0.89 | No |
| At least 20 trades | 60 | Yes |

The partial-result test also failed: the drawdown was 17.8 points smaller,
but the Sharpe gap (-0.84) was far outside ±0.10. In-sample (Oct 2005 to
Dec 2017) the rule also lagged, with a Sharpe of -0.04 against 0.07. In
the 42-combination parameter grid there was no smooth region where the
rule beat buy-and-hold; my pre-registered cell scored -0.07.

## Why it might not work

1. **It is rarely in the market.** The rule held stock only 8–17% of the
   time and earned a near-zero yen cash rate the rest. Mizuho shows this
   best: a 71% win rate and +1.8% per trade out-of-sample, but 3.7% a year
   against 21.3% for buy-and-hold.
2. **Slow drifts lose money, not just crashes.** In-sample, 57 trades hit
   the 15-day time stop (average -3.5%), more than the 31 that hit the
   stop-loss (average -11.3%).
3. **The stop-loss overshoots.** Selling one day after the signal means
   stops lost 11.3% on average, not 10%.
4. **Costs eat what edge there is.** The portfolio's out-of-sample Sharpe
   falls from 0.12 at 0 bps to -0.11 at 50 bps.
5. **The regime matters.** My hypothesis, which I haven't tested: before
   2018, buying dips during Japan's long bank decline often meant catching
   falling knives. After 2018, and especially as bank stocks rallied
   strongly in the 2020s, the strategy sat in cash while buy-and-hold
   captured the gains.

## Limitations

- **Small scope:** one market, three closely related stocks, one rule and
  60 out-of-sample trades.
- **One data source:** only Yahoo Finance. I couldn't check prices against
  a second source because Stooq blocked automated downloads.
- **Cleaned-out days:** removing bad rows in 2007–08 leaves gaps where the
  price path is hidden. No strategy trade crossed one.
- **Outside knowledge:** I knew Japanese banks rallied in 2023–26 before
  choosing them. Git proves when I wrote the rule, not what I already knew.
- **Untested explanation:** what drove the banks' rally (for example,
  expectations of higher Japanese rates) is my reading, not something
  this project tested.
- **Simple execution model:** trades at the next close with a flat cost
  and no taxes, so market impact and price gaps within a day aren't modelled.
- **Weekly paper log:** checking once a week misses trades that start and
  end within the same week.
