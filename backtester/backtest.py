"""Turning signals into positions, and positions into daily returns after costs.

Same design as the sti-backtest engine, with one change: the cash rate can be
a Series (a different annual rate on each day) instead of one fixed number,
because Japanese short-term rates moved from negative to about 1%.
"""
from __future__ import annotations

import pandas as pd

TRADING_DAYS = 252  # trading days in a year, used to annualise


def daily_cash_return(cash_rate):
    """Convert an annual cash rate (0.005 = 0.5% a year) to a daily return.

    Works on a single number or on a whole Series of rates. We compound
    rather than divide by 252: (1 + daily) ** 252 should equal (1 + annual).
    """
    return (1 + cash_rate) ** (1 / TRADING_DAYS) - 1


def positions_from_signal(signal: pd.Series, delay: int = 1) -> pd.Series:
    """The position held over each day's return (from close t-1 to close t).

    signal[t] is decided using closes up to and including day t.
    With delay=1 we trade at the NEXT close (t+1), so the first return we
    earn from that decision is the one from close t+1 to close t+2.
    That means position[t] = signal[t - 1 - delay], hence shift(1 + delay).

    This shift is the line that prevents look-ahead bias. Never remove it.
    Days before the first signal are spent in cash (position 0).
    """
    if delay < 0:
        raise ValueError("delay cannot be negative: that would trade on future information")
    return signal.shift(1 + delay).fillna(0.0).rename("position")


def pnl_from_positions(prices: pd.Series, position: pd.Series, cost_bps: float,
                       cash_rate) -> pd.DataFrame:
    """Daily gross and net returns for positions (1 = fully invested, 0 = all cash).

    cost_bps is charged on each unit traded, on each side, so a full round
    trip (0 -> 1 -> 0) costs 2 x cost_bps. It is charged on the day the
    position changes, i.e. the day of the trade.
    cash_rate: annual rate, either one number or a Series indexed like prices.
    Money not in the stock earns the cash rate for that day.
    """
    position = position.reindex(prices.index).fillna(0.0)
    stock_ret = prices.pct_change().fillna(0.0)

    # How much we bought or sold each day. On day 0, diff() is NaN, so we
    # use the position itself (going from nothing to `position`).
    traded = position.diff().fillna(position).abs()
    cost = traded * cost_bps / 10_000

    if isinstance(cash_rate, pd.Series):
        cash_ret = daily_cash_return(cash_rate.reindex(prices.index).ffill())
    else:
        cash_ret = pd.Series(daily_cash_return(cash_rate), index=prices.index)
    cash_ret.iloc[0] = 0.0  # no holding period before the first close

    gross = position * stock_ret + (1 - position) * cash_ret
    net = gross - cost
    return pd.DataFrame({
        "price": prices,
        "stock_ret": stock_ret,
        "position": position,
        "traded": traded,
        "cost": cost,
        "cash_ret": cash_ret,
        "gross": gross,
        "net": net,
        "equity": (1 + net).cumprod(),
    })


def run_backtest(prices: pd.Series, signal: pd.Series, cost_bps: float,
                 cash_rate, delay: int = 1) -> pd.DataFrame:
    """Backtest a 0/1 signal on one stock: signal -> positions -> returns."""
    position = positions_from_signal(signal.reindex(prices.index), delay)
    return pnl_from_positions(prices, position, cost_bps, cash_rate)


def buy_and_hold(prices: pd.Series, cost_bps: float, cash_rate) -> pd.DataFrame:
    """The benchmark: fully invested every day, paying one entry cost on day 0.

    Slice the result to the strategy's dates before comparing (see
    PREREGISTRATION.md: same dates for both).
    """
    position = pd.Series(1.0, index=prices.index)
    return pnl_from_positions(prices, position, cost_bps, cash_rate)


def equal_weight(returns_by_stock: dict[str, pd.Series]) -> pd.Series:
    """Daily return of a portfolio holding 1/3 in each stock, rebalanced daily.

    That is simply the average of the stocks' daily returns on each day.

    Cleaning drops different days for different stocks. If MUFG has a row on a
    day SMFG doesn't, SMFG's move for that day shows up in its NEXT row, so its
    return on the missing day is 0, not "unknown". We therefore fill those
    holes with 0 rather than dropping the whole day, which would throw away
    MUFG's and Mizuho's real returns. We start only once every stock has data.
    """
    table = pd.concat(returns_by_stock, axis=1)
    common_start = max(r.first_valid_index() for r in returns_by_stock.values())
    table = table.loc[common_start:].fillna(0.0)
    return table.mean(axis=1).rename("equal_weight")


def portfolio_cash(bts: dict[str, pd.DataFrame]) -> pd.Series:
    """The daily cash return for a portfolio of backtests.

    Every bank earns the same JPY rate, but cleaning removed different days
    from different banks, so we can't just take one bank's column: it would be
    missing on days only the others have. For each day, take the first bank
    that has a value (they're all the same number).
    """
    table = pd.concat({name: bt["cash_ret"] for name, bt in bts.items()}, axis=1, sort=True)
    return table.bfill(axis=1).iloc[:, 0].rename("cash_ret")
