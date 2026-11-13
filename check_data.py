"""Download (or load cached) prices, check their quality, and count entry episodes.

Usage:
    python check_data.py            # in-sample period only (the default)
    python check_data.py --full     # whole history, incl. out-of-sample

The default looks at IN-SAMPLE data only. PREREGISTRATION.md promises not to
look at anything out-of-sample until the threshold decision is locked.
"""
import argparse

import pandas as pd

from backtester import config
from backtester.data import load_cash_rate, load_prices, quality_report


def count_entry_episodes(prices: pd.Series) -> int:
    """Approximate number of entry chances: times the close drops to 5%+ below
    the MA after having been at or above the MA.

    This is an UPPER BOUND on real trades, because it ignores that while you're
    in a trade you can't enter again. It is NOT the trading signal; that's
    mean_reversion_signal, which you'll write in step 5.
    """
    ma = prices.rolling(config.MA_WINDOW).mean()
    episodes = 0
    armed = False  # True once the close has been at/above the MA ("reset")
    for close, avg in zip(prices, ma):
        if pd.isna(avg):
            continue  # MA warm-up: not enough history yet
        if close >= avg:
            armed = True
        elif armed and close <= (1 - config.ENTRY_BELOW_MA) * avg:
            episodes += 1
            armed = False  # wait for the next reset
    return episodes


def print_table(title: str, df: pd.DataFrame) -> None:
    print(f"  {title}: {len(df)}")
    if not df.empty:
        print("    " + df.to_string().replace("\n", "\n    "))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="include out-of-sample data")
    parser.add_argument("--refresh", action="store_true", help="re-download from Yahoo")
    args = parser.parse_args()

    universe = config.UNIVERSES[config.MAIN_UNIVERSE]
    split = pd.Timestamp(config.OUT_OF_SAMPLE_START)
    print(f"Universe: {config.MAIN_UNIVERSE}  |  period: "
          f"{'FULL history' if args.full else f'in-sample only (before {split.date()})'}\n")

    for ticker, name in universe["tickers"].items():
        prices = load_prices(ticker, refresh=args.refresh)
        if not args.full:
            prices = prices[prices.index < split]
        report = quality_report(prices)

        print(f"=== {name} ({ticker})")
        for key in ["first_date", "last_date", "trading_days",
                    "missing_values", "non_positive", "duplicate_dates"]:
            print(f"  {key}: {report[key]}")
        print_table("gaps over 7 calendar days", report["gaps"])
        print_table("stale runs (5+ identical closes)", report["stale"])
        print_table("jumps over 20% in a day", report["jumps"])

        episodes = count_entry_episodes(prices)
        years = report["trading_days"] / 252
        print(f"  entry episodes: {episodes} in {years:.1f} years "
              f"= {episodes / years:.2f} per year\n")

    cash = load_cash_rate(universe["cash_rate_fred_id"], refresh=args.refresh)
    print(f"Cash rate {universe['cash_rate_fred_id']}: {cash.index[0].date()} "
          f"to {cash.index[-1].date()}, {len(cash)} months")


if __name__ == "__main__":
    main()
