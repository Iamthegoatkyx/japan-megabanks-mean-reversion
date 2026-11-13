# Preregistration

Written before any backtest on real data. Any later change must be a separate,
dated "Amendment" commit at the bottom of this file, with the reason, so the
git history shows it.

## Question
Do DBS (D05.SI), OCBC (O39.SI) and UOB (U11.SI) bounce back after sharp drops
enough to beat buy-and-hold of the same stocks after trading costs?

## Data
- Daily dividend-adjusted closes from Yahoo Finance (yfinance, `auto_adjust=True`).
- Signals use closing prices only.

## The rule (identical for all three banks, no per-stock tuning)
- **Moving average (MA):** simple average of the last 20 closes, including today.
- **Execution:** every signal computed at day t's close is traded at day t+1's close.
- **Entry signal (day t):** all of:
  - close <= 0.95 × MA (at least 5% below the 20-day MA),
  - not currently in a trade,
  - the stock has "reset" since the last exit (see below).
- **Entry price:** the close on the day the buy is executed (t+1), i.e. the price actually paid.
- **Exit signal (day t), whichever comes first:**
  1. Back to average: close >= MA.
  2. Time stop: day t is the 14th trading day of holding (entry day = day 1),
     so the sale executes on day 15. A trade never lasts more than 15 trading days.
  3. Stop-loss: close <= 0.90 × entry price. Because the sale happens at the
     next close, the realised loss can be larger than 10%.
- **Reset after any exit:** no new entry signal until a close at or above the MA.
- **Out of the market:** cash earns 2% a year.
- **Costs:** 15 bps per side (30 bps per round trip).

## Benchmark
Buy-and-hold of the same stock, dividends included, same 15 bps costs,
measured over exactly the same dates as the strategy.

## Samples
- In-sample: start of data to 2017-12-31.
- Out-of-sample: 2018-01-01 to the run date. Looked at once, with the rule above.

## Allowed in-sample check before results (none of it looks at returns)
After this file is committed, I will count entry episodes per bank per year
in-sample. If any bank has fewer than 2 a year, I may change the 5% threshold
once, in an Amendment that records the counts and the reason. I will not look
at any returns, Sharpe ratios or equity curves before that decision is made.

## What counts as success (out-of-sample only, after costs)

**Main test.** One portfolio holding 1/3 of capital in each bank's strategy
(rebalanced daily, rebalancing costs ignored), compared with a portfolio
holding 1/3 in buy-and-hold of each bank (same rebalancing). The strategy
"works" only if ALL of these hold:
1. Its Sharpe ratio is higher than buy-and-hold's at 15 bps.
2. The 95% block-bootstrap interval for (strategy Sharpe − buy-and-hold Sharpe)
   is entirely above zero.
3. Its Sharpe is still higher than buy-and-hold's at 25 bps.
4. At least 20 completed trades in total across the three banks.

**Partial result: "risk reduction, not an edge."** Sharpe difference within
±0.10 of buy-and-hold, AND the strategy's max drawdown is at least
10 percentage points smaller than buy-and-hold's.

**Anything else:** the strategy does not work, and I write up why.

Per-bank results are reported but are secondary. They cannot turn a failed
main test into a success.

## Amendments
_None yet._
