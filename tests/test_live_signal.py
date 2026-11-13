"""live_signal.py: correct rows, no duplicate log lines, no half-finished days."""
import datetime as dt

import pandas as pd

from live_signal import COLUMNS, TOKYO, append_log, drop_unfinished_day, todays_row


def prices_ending(last_day: str, closes):
    dates = pd.bdate_range(end=last_day, periods=len(closes))
    return pd.Series(closes, index=dates, dtype=float)


def test_live_price_during_tokyo_trading_hours_is_dropped():
    prices = prices_ending("2027-02-05", [100.0] * 25)
    during = dt.datetime(2027, 2, 5, 11, 0, tzinfo=TOKYO)
    after = dt.datetime(2027, 2, 5, 17, 0, tzinfo=TOKYO)
    assert drop_unfinished_day(prices, during).index[-1].date() == dt.date(2027, 2, 4)
    assert drop_unfinished_day(prices, after).index[-1].date() == dt.date(2027, 2, 5)


def test_row_for_a_fresh_entry_signal():
    # 24 flat days (reset), then a 10% drop: today's signal is a new entry.
    prices = prices_ending("2027-02-05", [100.0] * 24 + [90.0])
    row, action = todays_row("MUFG", prices)
    assert list(row) == COLUMNS
    assert row["signal"] == 1 and row["position"] == 0   # decided today, bought tomorrow
    assert row["moving_average"] == 99.5                  # (19 x 100 + 90) / 20
    assert row["pct_below_average"] == round((1 - 90 / 99.5) * 100, 2)
    assert action == "BUY at the next close"


def test_running_twice_on_the_same_day_adds_no_duplicates(tmp_path):
    log = tmp_path / "paper_log.csv"
    row = {"date": "2027-02-05", "stock": "MUFG", "close": 1.0, "moving_average": 1.0,
           "pct_below_average": 0.0, "signal": 0, "position": 0}
    assert append_log([row], log) == 1
    assert append_log([row], log) == 0
    assert append_log([{**row, "stock": "SMFG"}], log) == 1
    assert len(pd.read_csv(log)) == 2
