"""Getting prices and the cash rate, caching them, and checking they look sane."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------- stock prices

def download_prices(ticker: str) -> pd.Series:
    """Download the full history of daily dividend-adjusted closes from Yahoo.

    auto_adjust=True means Yahoo rescales past prices for dividends and splits,
    so the % change from one close to the next is the TOTAL return
    (price change + dividend). That is why we don't add dividends separately.
    """
    import yfinance as yf  # imported here so tests don't need the internet

    df = yf.download(ticker, period="max", auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"Yahoo returned no data for {ticker}")
    close = df["Close"]
    # Newer yfinance versions return a one-column DataFrame here; we want a Series.
    if isinstance(close, pd.DataFrame):
        close = close[ticker]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.dropna().rename(ticker)


def load_prices(ticker: str, refresh: bool = False) -> pd.Series:
    """Load closes from data/<ticker>.csv, downloading them first if needed.

    Caching means every run uses the same numbers, and we don't hit Yahoo
    each time. Pass refresh=True to re-download (e.g. for the latest prices).
    """
    path = DATA_DIR / f"{ticker}.csv"
    if refresh or not path.exists():
        prices = download_prices(ticker)
        DATA_DIR.mkdir(exist_ok=True)
        prices.to_csv(path, index_label="date")
    prices = pd.read_csv(path, index_col="date", parse_dates=True).iloc[:, 0]
    return prices.rename(ticker)


# ---------------------------------------------------------------- data quality

def find_gaps(prices: pd.Series, max_calendar_days: int = 7) -> pd.DataFrame:
    """Places where more than `max_calendar_days` pass between two trading days.

    Weekends (3 days) and Japan's Golden Week / New Year holidays (up to ~6 days)
    are normal. Longer gaps usually mean missing data.
    """
    dates = prices.index.to_series()
    days_since_previous = dates.diff().dt.days
    gaps = days_since_previous[days_since_previous > max_calendar_days]
    return pd.DataFrame({"previous_date": dates.shift(1)[gaps.index],
                         "calendar_days": gaps})


def find_stale(prices: pd.Series, min_run: int = 5) -> pd.DataFrame:
    """Runs of `min_run` or more identical closes in a row.

    A big bank's price almost never closes unchanged 5 days running, so this
    usually means the data provider just copied the last price forward.
    """
    runs = []
    run_start = 0
    values = prices.to_numpy()
    for i in range(1, len(values) + 1):
        # A run ends when the price changes, or when we reach the end.
        if i == len(values) or values[i] != values[run_start]:
            length = i - run_start
            if length >= min_run:
                runs.append({"start": prices.index[run_start],
                             "end": prices.index[i - 1],
                             "days": length,
                             "price": values[run_start]})
            run_start = i
    return pd.DataFrame(runs, columns=["start", "end", "days", "price"])


def find_jumps(prices: pd.Series, threshold: float = 0.20) -> pd.DataFrame:
    """Days where the close moved more than `threshold` (20%) from the day before.

    A real crash can do this, but so can a split or reverse split that the
    data provider forgot to adjust for. Each one should be checked by hand.
    """
    returns = prices.pct_change()
    big = returns[returns.abs() > threshold]
    return pd.DataFrame({"previous_close": prices.shift(1)[big.index],
                         "close": prices[big.index],
                         "return": big})


def quality_report(prices: pd.Series) -> dict:
    """Run every check and return the results in one dictionary."""
    return {
        "first_date": prices.index[0].date(),
        "last_date": prices.index[-1].date(),
        "trading_days": len(prices),
        "missing_values": int(prices.isna().sum()),
        "non_positive": int((prices <= 0).sum()),
        "duplicate_dates": int(prices.index.duplicated().sum()),
        "gaps": find_gaps(prices),
        "stale": find_stale(prices),
        "jumps": find_jumps(prices),
    }


# ---------------------------------------------------------------- cash rate

def load_cash_rate(fred_id: str, refresh: bool = False) -> pd.Series:
    """Monthly short-term interest rate from FRED, as a decimal (0.5% -> 0.005).

    Cached to data/<fred_id>.csv, like the prices.
    """
    path = DATA_DIR / f"{fred_id}.csv"
    if refresh or not path.exists():
        import requests  # installed with yfinance; brings its own SSL certificates

        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fred_id}"
        # We use requests rather than pd.read_csv(url): Python from python.org
        # on a Mac often can't verify HTTPS certificates on its own.
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        DATA_DIR.mkdir(exist_ok=True)
        path.write_text(response.text)
    raw = pd.read_csv(path, parse_dates=["observation_date"])
    # FRED writes "." for a missing value; to_numeric turns that into NaN.
    rate = pd.to_numeric(raw[fred_id], errors="coerce") / 100
    return pd.Series(rate.to_numpy(), index=raw["observation_date"],
                     name="cash_rate").dropna()


def daily_cash_rate(monthly_rate: pd.Series, trading_days: pd.DatetimeIndex) -> pd.Series:
    """Give each trading day the annual rate of its calendar month.

    FRED dates each monthly value on the 1st of the month, so a trading day
    on 17 March gets the March value. If the latest months aren't published
    yet, the last known value is carried forward (as PREREGISTRATION.md says).
    This is interest we EARN over the month, never an input to a trading
    decision, so using the same month's value is not look-ahead.
    """
    month_start = trading_days.to_period("M").to_timestamp()
    rate = monthly_rate.reindex(month_start.union(monthly_rate.index)).ffill()
    return pd.Series(rate.loc[month_start].to_numpy(), index=trading_days,
                     name="cash_rate")
