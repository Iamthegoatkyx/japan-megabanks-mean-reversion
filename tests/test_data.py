"""The data-quality checks must catch the problems they claim to catch.

These use small made-up price series, so they never need the internet.
"""
import pandas as pd

from backtester.data import daily_cash_rate, find_gaps, find_jumps, find_stale


def make_prices(values, start="2020-01-06"):
    """A price series on consecutive business days (Mon-Fri)."""
    dates = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=dates, dtype=float)


def test_normal_weekends_are_not_gaps():
    prices = make_prices(range(100, 120))
    assert find_gaps(prices).empty


def test_a_missing_fortnight_is_a_gap():
    prices = make_prices(range(100, 130))
    prices = prices.drop(prices.index[10:20])  # delete two weeks of data
    gaps = find_gaps(prices)
    assert len(gaps) == 1
    # Last day kept: Fri 17 Jan. Next day kept: Mon 3 Feb. That's 17 calendar days.
    assert gaps["calendar_days"].iloc[0] == 17


def test_stale_run_is_found_with_its_length():
    prices = make_prices([100, 101, 102, 102, 102, 102, 102, 102, 103])
    stale = find_stale(prices, min_run=5)
    assert len(stale) == 1
    assert stale["days"].iloc[0] == 6


def test_short_flat_run_is_not_stale():
    prices = make_prices([100, 101, 101, 101, 102])
    assert find_stale(prices, min_run=5).empty


def test_stale_run_at_the_very_end_is_found():
    prices = make_prices([100, 101, 99, 99, 99, 99, 99])
    assert len(find_stale(prices, min_run=5)) == 1


def test_unadjusted_reverse_split_shows_as_a_jump():
    # A 1-for-10 reverse split the provider forgot to adjust: price x10 overnight.
    prices = make_prices([150, 152, 1510, 1505])
    jumps = find_jumps(prices, threshold=0.20)
    assert list(jumps.index) == [prices.index[2]]


def test_ordinary_moves_are_not_jumps():
    prices = make_prices([100, 105, 98, 110, 100])  # all moves under 20%
    assert find_jumps(prices).empty


def test_cash_rate_uses_each_days_own_month_and_carries_forward():
    monthly = pd.Series([0.001, 0.002],
                        index=pd.to_datetime(["2024-01-01", "2024-02-01"]))
    days = pd.to_datetime(["2024-01-15", "2024-02-20", "2024-04-10"])
    daily = daily_cash_rate(monthly, pd.DatetimeIndex(days))
    # January day -> January rate; February day -> February rate;
    # April isn't published yet -> carry February forward.
    assert list(daily) == [0.001, 0.002, 0.002]
