# Preregistration: US robustness test (NVDA, AMD, INTC)

Written before any US price data was downloaded. Any later change must be a
separate, dated "Amendment" commit at the bottom of this file, with the reason,
so the git history shows it.

This is a **second, separate test of the same rule** as `PREREGISTRATION.md`.
The Japan out-of-sample result was already known when this file was written
(it did not pass). Nothing here changes the Japan test or its result.

## Question
Do three US chip makers, NVIDIA (NVDA), AMD (AMD) and Intel (INTC), bounce back
after sharp drops enough to beat buy-and-hold of the same stocks after trading
costs?

## Hypothesis (written by the author, before any US data)
I expect the rule to fail on these chip stocks, probably worse
than on the Japanese banks. They are much more volatile, so a 5% drop below
the 20-day average is ordinary noise rather than an overreaction, and the
rule should trade more often and hit more stop-losses. Their drops are often
caused by real news, like earnings or the chip cycle, which tends to keep
going rather than reverse. NVDA also rose enormously in this period, so
buy-and-hold is a very hard benchmark for a strategy that is mostly in cash.
The rule could only work if sharp sell-offs in these stocks are short
panics that recover within a few weeks.

## How the stocks were chosen (stated honestly)
NVDA was picked first because it is well known, and AMD and INTC were added
as the other two large US chip makers that have traded since before 1999.
This choice was made **with hindsight**: NVDA in particular is known to have
risen a great deal over the test period. Any result must be read with that
selection bias in mind. It is listed under Limitations.

## Data
- Daily dividend-adjusted closes from Yahoo Finance (yfinance, `auto_adjust=True`).
- Signals use closing prices only.
- Data cleaning: the same rule as Japan (Amendment 2 of `PREREGISTRATION.md`):
  drop rows with zero volume, and drop rows whose Open, High, Low, Close and
  Volume all equal the previous row's. Code: `clean_prices` in `backtester/data.py`.
- All returns are in USD. No currency conversion.
- Cash rate: US effective federal funds rate, % per year, monthly, FRED series
  `FEDFUNDS`. Each trading day earns the rate of its calendar month, converted
  to a daily rate. If the latest month is not yet published, the last available
  value is carried forward.

## The rule (unchanged from `PREREGISTRATION.md`, no tuning for these stocks)
- 20-day simple moving average (MA) of closes, including today.
- Signal at day t's close, traded at day t+1's close.
- Entry: close <= 0.95 × MA, not in a trade, and reset since the last exit.
- Exit, whichever comes first: close >= MA; 15-trading-day maximum hold;
  close <= 0.90 × entry price (entry price = the t+1 close actually paid).
- Reset after any exit: no new entry until a close at or above the MA.
- Out of the market: cash earns the USD rate above.
- **Costs: 5 bps per side (10 bps per round trip).** Chosen for very liquid US
  large caps: a tight bid-ask spread plus some slippage, no commission.

The entry threshold will **not** be changed for this test, whatever the
in-sample entry counts are. The point is to test the same rule elsewhere.

## Benchmark
Buy-and-hold of the same stock, dividends included, in USD, same 5 bps costs,
over exactly the same dates. Main test: equal-weight buy-and-hold of the three.

## Samples
- In-sample: start of data to 2017-12-31. The portfolio starts on the first
  date all three stocks have data (NVDA listed in January 1999).
- Out-of-sample: 2018-01-01 to the run date. Looked at once, with the rule above.

## What counts as success (out-of-sample only, after costs)
The same criteria as the Japan test. One portfolio holding 1/3 of capital in
each stock's strategy (rebalanced daily, rebalancing costs ignored), compared
with 1/3 in buy-and-hold of each. The strategy "works" only if ALL hold:
1. Its Sharpe ratio is higher than buy-and-hold's at 5 bps.
2. The 95% block-bootstrap interval for (strategy Sharpe − buy-and-hold Sharpe)
   is entirely above zero.
3. Its Sharpe is still higher than buy-and-hold's at 25 bps.
4. At least 20 completed trades in total across the three stocks.

**Partial result: "risk reduction, not an edge."** Sharpe difference within
±0.10 of buy-and-hold, AND the strategy's max drawdown is at least
10 percentage points smaller than buy-and-hold's.

**Anything else:** the strategy does not work on these stocks, and I write up why.

Per-stock results are reported but are secondary. They cannot turn a failed
main test into a success.

## Amendments
_None yet._
