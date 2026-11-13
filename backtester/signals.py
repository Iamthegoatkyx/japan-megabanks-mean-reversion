"""Trading signals. A signal on day t may only use closes up to and including day t."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def mean_reversion_signal(prices: pd.Series,
                          window: int = config.MA_WINDOW,
                          entry_below: float = config.ENTRY_BELOW_MA,
                          max_hold: int = config.MAX_HOLD_DAYS,
                          stop_loss: float = config.STOP_LOSS) -> pd.Series:
    """Decide, at each day's close, whether we want to hold the stock.

    Returns a Series with the same index as `prices`:
      1.0  = "after today's close, I want to be in the stock"
      0.0  = "after today's close, I want to be in cash"
      NaN  = the first `window - 1` days, before the moving average exists
    The engine (positions_from_signal) trades every decision one day later,
    at the next close. This function must not do that shift itself.

    The rule (PREREGISTRATION.md):
      MA[t] = average of the last `window` closes, including day t.

      ENTRY on day t if ALL of these hold:
        - we are not already in a trade,
        - close[t] <= (1 - entry_below) * MA[t],
        - we have "reset": there has been a close >= MA since the last exit.
          At the very start of the data we have NOT reset yet.

      Once in a trade, the ENTRY PRICE is the close of the day AFTER the entry
      signal (that's the price we actually pay). Call that day "holding day 1".

      EXIT on day t (signal goes back to 0) at the first of:
        1. close[t] >= MA[t]                                  (back to average)
        2. day t is holding day (max_hold - 1)                 (time stop)
           -> with max_hold=15 the exit signal fires on holding day 14,
              the sale happens on day 15, so no trade lasts more than 15 days.
        3. close[t] <= (1 - stop_loss) * entry price           (stop-loss)
           (impossible on the entry signal day, since there's no entry price yet)

      RESET: after an exit by rule 2 or 3, no new entry until a close >= MA.
      An exit by rule 1 is itself a close >= MA, so it counts as the reset.
    """
    ma = prices.rolling(window).mean()
    signal = pd.Series(np.nan, index=prices.index)

    state = "WAITING"
    entry_day = None
    entry_price = None

    for i in range(len(prices)):
        close = prices.iloc[i]
        avg = ma.iloc[i]
        if pd.isna(avg):
            continue

        if state == "WAITING":
            signal.iloc[i] = 0
            if close >= avg:
                state = "READY"

        if state == "READY":
            if close <= (1 - entry_below) * avg:
                state = "IN"
                entry_day = i
                entry_price = None
                signal.iloc[i] = 1
            else:
                signal.iloc[i] = 0

        elif state == "IN":
            days_held = i - entry_day
            if days_held == 1:
                entry_price = close

            if close >= avg:
                state = "READY"
                signal.iloc[i] = 0
            elif days_held >= max_hold - 1:
                state = "WAITING"
                signal.iloc[i] = 0
            elif close <= (1 - stop_loss) * entry_price:
                state = "WAITING"
                signal.iloc[i] = 0
            else:
                signal.iloc[i] = 1

    return signal                       