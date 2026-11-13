"""Paper trading: today's signal and position for each bank, logged to paper_log.csv.

Usage:  python live_signal.py        (run weekly, after the Tokyo close)

It downloads fresh prices every time but does NOT overwrite the cached
backtest data in data/, so the backtest results stay reproducible.
It uses exactly the same cleaning and the same mean_reversion_signal as the
backtest, so the paper trades follow the rule that was tested.

Signal vs position (the same convention as the backtest):
  signal   = the decision made at today's close (1 = want to hold, 0 = cash).
  position = what you actually hold today. A decision is traded at the NEXT
             close, so a change in today's signal becomes a trade tomorrow.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from backtester import config
from backtester.backtest import positions_from_signal
from backtester.data import clean_prices, download_prices
from backtester.signals import mean_reversion_signal

LOG = Path("paper_log.csv")
COLUMNS = ["date", "stock", "close", "moving_average", "pct_below_average",
           "signal", "position"]
TOKYO = ZoneInfo("Asia/Tokyo")
CLOSE_IS_FINAL_AFTER = dt.time(16, 0)   # TSE closes 15:30 JST; give data 30 minutes


def drop_unfinished_day(prices: pd.Series, now_tokyo: dt.datetime) -> pd.Series:
    """During Tokyo trading hours Yahoo's last row is a live price, not a close.

    The rule is defined on closes only, so if the last row is today and the
    market hasn't finished, we leave it out.
    """
    last = prices.index[-1].date()
    if last == now_tokyo.date() and now_tokyo.time() < CLOSE_IS_FINAL_AFTER:
        return prices.iloc[:-1]
    return prices


def todays_row(stock: str, prices: pd.Series) -> tuple[dict, str]:
    """One log row for the latest close, plus what to do at the next close."""
    signal = mean_reversion_signal(prices)
    position = positions_from_signal(signal, delay=config.EXECUTION_DELAY)
    ma = prices.rolling(config.MA_WINDOW).mean()

    # Yesterday's decision was traded at today's close, so after today's close
    # you hold `yesterday`. Today's decision is traded at the next close.
    today, yesterday = signal.iloc[-1], signal.iloc[-2]
    if today == 1 and yesterday != 1:
        action = "BUY at the next close"
    elif today == 0 and yesterday == 1:
        action = "SELL at the next close"
    elif today == 1:
        action = "hold"
    else:
        action = "stay in cash"

    row = {
        "date": prices.index[-1].date().isoformat(),
        "stock": stock,
        "close": round(float(prices.iloc[-1]), 2),
        "moving_average": round(float(ma.iloc[-1]), 2),
        # Positive = below the average, so 5.0 means "5% below": the entry level.
        "pct_below_average": round(float((1 - prices.iloc[-1] / ma.iloc[-1]) * 100), 2),
        "signal": int(today),
        "position": int(position.iloc[-1]),
    }
    return row, action


def append_log(rows: list[dict], path: Path = LOG) -> int:
    """Append rows to the CSV, skipping any (date, stock) already logged.

    Running the script twice on the same day must not create duplicate rows.
    Returns the number of rows actually added.
    """
    old = pd.read_csv(path, dtype={"date": str}) if path.exists() else pd.DataFrame(columns=COLUMNS)
    seen = set(zip(old["date"], old["stock"]))
    new = [r for r in rows if (r["date"], r["stock"]) not in seen]
    if new:
        pd.concat([old, pd.DataFrame(new, columns=COLUMNS)]).to_csv(path, index=False)
    return len(new)


def main() -> None:
    now = dt.datetime.now(TOKYO)
    universe = config.UNIVERSES[config.MAIN_UNIVERSE]
    rows = []
    print(f"Run at {now:%Y-%m-%d %H:%M} Tokyo time\n")
    for ticker, name in universe["tickers"].items():
        kept, _ = clean_prices(download_prices(ticker))
        prices = drop_unfinished_day(kept["Close"].rename(ticker), now)
        row, action = todays_row(name, prices)
        rows.append(row)
        print(f"{name:7s} {row['date']}  close {row['close']:>9,.1f}  "
              f"MA {row['moving_average']:>9,.1f}  "
              f"{abs(row['pct_below_average']):5.2f}% {'below' if row['pct_below_average'] >= 0 else 'above'} MA  "
              f"signal {row['signal']}  position {row['position']}  -> {action}")
    added = append_log(rows)
    print(f"\n{added} new row(s) added to {LOG}"
          + ("" if added == len(rows) else " (the rest were already logged for that date)"))


if __name__ == "__main__":
    main()
