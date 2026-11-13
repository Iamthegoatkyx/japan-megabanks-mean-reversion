"""Tests for mean_reversion_signal. They FAIL until you write the function.

Most tests use window=4 so you can check every moving average by hand.
Read each test's comments: they are worked examples of the rule.
Run just these with:   pytest tests/test_signals.py -v
"""
import numpy as np
import pandas as pd
import pytest

from backtester.backtest import positions_from_signal
from backtester.signals import mean_reversion_signal

NAN = np.nan


def signal_for(closes, **rule):
    """Run the signal on a list of closes (window=4 unless a test says otherwise)."""
    rule.setdefault("window", 4)
    prices = pd.Series(closes, index=pd.bdate_range("2021-01-04", periods=len(closes)),
                       dtype=float)
    return mean_reversion_signal(prices, **rule)


def assert_signal(result, expected):
    """Compare day by day; NaN counts as equal to NaN."""
    pd.testing.assert_series_equal(
        result, pd.Series(expected, index=result.index, dtype=float),
        check_names=False)


# ---------------------------------------------------------------- basics

def test_output_has_same_dates_and_nan_during_warm_up():
    result = signal_for([100, 100, 100, 100, 100])
    assert result.index.equals(signal_for([1, 2, 3, 4, 5]).index)
    # The 4-day MA first exists on day 3 (the 4th close).
    assert_signal(result, [NAN, NAN, NAN, 0, 0])


# ---------------------------------------------------------------- entry

def test_enters_when_close_is_5pct_below_ma():
    # Day 3: close 100 = MA 100 -> that's a reset.
    # Day 4: MA = (100+100+100+90)/4 = 97.5; 0.95 * 97.5 = 92.625; 90 <= 92.625 -> ENTER.
    assert_signal(signal_for([100, 100, 100, 100, 90]), [NAN, NAN, NAN, 0, 1])


def test_no_entry_when_only_4pct_below_ma():
    # Day 4: MA = 99; 0.95 * 99 = 94.05; 96 > 94.05 -> no entry.
    assert_signal(signal_for([100, 100, 100, 100, 96]), [NAN, NAN, NAN, 0, 0])


def test_no_entry_at_the_start_before_any_reset():
    # The price falls from day 0 and never closes at/above its MA,
    # so we never "reset". Days 5 and 6 are >5% below the MA, but no entry.
    assert_signal(signal_for([100, 98, 96, 94, 90, 86, 82]),
                  [NAN, NAN, NAN, 0, 0, 0, 0])


# ---------------------------------------------------------------- exit 1: back to average

def test_exits_when_close_gets_back_to_ma():
    # Day 4: enter (as above).
    # Day 5: close 92 (entry price), MA = 95.5, still below -> hold.
    # Day 6: close 100, MA = (100+90+92+100)/4 = 95.5; 100 >= 95.5 -> EXIT.
    assert_signal(signal_for([100, 100, 100, 100, 90, 92, 100, 100]),
                  [NAN, NAN, NAN, 0, 1, 1, 0, 0])


def test_back_to_ma_exit_counts_as_reset_so_can_re_enter_next_day():
    # Day 5: close 100 >= MA 97.5 -> exit, and that close is also the reset.
    # Day 6: MA = (100+90+100+88)/4 = 94.5; 0.95 * 94.5 = 89.775; 88 <= it -> ENTER again.
    assert_signal(signal_for([100, 100, 100, 100, 90, 100, 88]),
                  [NAN, NAN, NAN, 0, 1, 0, 1])


# ---------------------------------------------------------------- exit 2: time stop

def drifting_down():
    """Reset, a drop on day 4, then -0.5% a day: always below the MA, but too
    slow to hit a 10% stop within 14 days."""
    closes = [100, 100, 100, 100, 90]
    for _ in range(20):
        closes.append(closes[-1] * 0.995)
    return closes


def test_time_stop_signal_fires_on_holding_day_14():
    # Entry signal day 4. Holding day 1 = day 5. Holding day 14 = day 18 -> exit signal.
    # After that: no reset (still below MA), so it stays out.
    expected = [NAN, NAN, NAN, 0] + [1] * 14 + [0] * 7
    assert_signal(signal_for(drifting_down(), max_hold=15), expected)


def test_time_stop_means_never_holding_more_than_15_trading_days():
    signal = signal_for(drifting_down(), max_hold=15)
    position = positions_from_signal(signal)
    # Bought at close of day 5, sold at close of day 19: 15 trading days,
    # which is 14 daily returns earned while holding.
    assert (position == 1).sum() == 14


# ---------------------------------------------------------------- exit 3: stop-loss

def test_stop_loss_is_measured_from_the_price_actually_paid():
    # Day 4: signal close 90 -> enter. Day 5: close 95 = ENTRY PRICE (what we pay).
    # Day 6: close 85. MA = 92.5, so not back to average.
    #   From the entry price: 85 <= 0.90 * 95 = 85.5 -> STOP. (Correct.)
    #   From the signal-day close: 85 <= 0.90 * 90 = 81? No -> would wrongly hold.
    assert_signal(signal_for([100, 100, 100, 100, 90, 95, 85, 85]),
                  [NAN, NAN, NAN, 0, 1, 1, 0, 0])


def test_stop_loss_triggers_at_exactly_10pct_down():
    # Entry price 100 (day 5). Day 6: close 90 = exactly 0.90 * 100 -> STOP ("<=").
    assert_signal(signal_for([110, 110, 110, 110, 100, 100, 90]),
                  [NAN, NAN, NAN, 0, 1, 1, 0])


def test_stop_loss_does_not_trigger_just_above_10pct_down():
    # Same, but day 6 closes at 90.01 > 90 -> keep holding.
    assert_signal(signal_for([110, 110, 110, 110, 100, 100, 90.01]),
                  [NAN, NAN, NAN, 0, 1, 1, 1])


# ---------------------------------------------------------------- reset

def test_no_re_entry_after_stop_loss_until_close_gets_back_to_ma():
    # Day 6: stop-loss exit (as in the stop-loss test above).
    # Days 7-8: >5% below the MA again, but no reset yet -> stay out.
    # Day 10: close 80 = MA 80 -> reset.
    # Day 12: MA = 78; 0.95 * 78 = 74.1; 72 <= 74.1 -> ENTER.
    closes = [100, 100, 100, 100, 90, 95, 85, 80, 80, 80, 80, 80, 72]
    assert_signal(signal_for(closes),
                  [NAN, NAN, NAN, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1])


# ---------------------------------------------------------------- no look-ahead

@pytest.mark.parametrize("cutoff", range(40, 400, 20))
def test_scrambling_future_prices_does_not_change_past_signals(cutoff):
    rng = np.random.default_rng(cutoff)
    dates = pd.bdate_range("2015-01-01", periods=420)
    prices = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 420))), index=dates)
    scrambled = prices.copy()
    scrambled.iloc[cutoff + 1:] = rng.permutation(prices.iloc[cutoff + 1:].to_numpy()) * 0.7

    before = mean_reversion_signal(prices)     # the real preregistered settings
    after = mean_reversion_signal(scrambled)
    pd.testing.assert_series_equal(before.iloc[:cutoff + 1], after.iloc[:cutoff + 1])
