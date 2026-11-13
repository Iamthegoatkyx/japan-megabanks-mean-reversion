"""Performance numbers for a backtest, and the list of individual trades."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import TRADING_DAYS


# ---------------------------------------------------------------- return metrics

def sharpe(net: pd.Series, cash_ret: pd.Series) -> float:
    """Annualised Sharpe ratio: average daily return ABOVE CASH, divided by its
    volatility, scaled up by sqrt(252).

    We subtract the cash return because a strategy that sits in cash shouldn't
    get credit for the interest; Sharpe asks "how much extra for the risk?".
    """
    cash = cash_ret.reindex(net.index)
    if cash.isna().any():
        # Fail loudly: pandas would silently skip these days in mean() and std().
        raise ValueError(f"cash return missing on {int(cash.isna().sum())} days")
    excess = net - cash
    sd = excess.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return float("nan")
    return float(excess.mean() / sd * np.sqrt(TRADING_DAYS))


def cagr(net: pd.Series) -> float:
    """Compound annual growth rate, using real calendar time.

    Calendar years (days / 365.25) rather than rows / 252, because cleaning
    removed some rows: counting rows would make the period look shorter.
    """
    growth = (1 + net).prod()
    years = (net.index[-1] - net.index[0]).days / 365.25
    return float(growth ** (1 / years) - 1)


def max_drawdown(net: pd.Series) -> float:
    """Worst fall from a previous peak of the equity curve (e.g. -0.35 = -35%)."""
    equity = (1 + net).cumprod()
    # Start the running peak at 1.0, so a loss on day one also counts.
    peak = np.maximum(equity.cummax(), 1.0)
    return float((equity / peak - 1).min())


# ---------------------------------------------------------------- trades

def trade_list(bt: pd.DataFrame, cost_bps: float, max_gap_days: int = 7) -> pd.DataFrame:
    """One row per trade, built from the `position` column of a backtest.

    A trade is a run of consecutive days with position 1. If position is 1 on
    days a..b, then we BOUGHT at the close of the day before a, and SOLD at the
    close of day b (position is 1 over the returns we earn while holding).

    Columns:
      buy_date, sell_date : the closes we traded at
      days_held           : trading days from buy to sell, both included
      net_return          : price change, minus one cost on each side
      crosses_gap         : True if any two consecutive rows in the trade are
                            more than `max_gap_days` calendar days apart
                            (missing data, see PREREGISTRATION.md Amendment 2)
      open                : True if still holding on the last day of data
    """
    position = bt["position"].to_numpy()
    prices = bt["price"]
    dates = bt.index
    cost = cost_bps / 10_000
    trades = []

    i = 0
    while i < len(position):
        if position[i] != 1:
            i += 1
            continue
        start = i                                   # first day holding (a)
        while i < len(position) and position[i] == 1:
            i += 1
        end = i - 1                                 # last day holding (b)

        buy = max(start - 1, 0)                     # we bought at the close before a
        still_open = end == len(position) - 1
        gross = prices.iloc[end] / prices.iloc[buy] - 1
        sides_paid = 1 if still_open else 2         # not sold yet -> no exit cost yet
        net = (1 + gross) * (1 - cost) ** sides_paid - 1
        span = dates[buy:end + 1].to_series().diff().dt.days
        trades.append({
            "buy_date": dates[buy],
            "sell_date": dates[end],
            "days_held": end - buy + 1,
            "net_return": net,
            "crosses_gap": bool((span > max_gap_days).any()),
            "open": still_open,
        })
    return pd.DataFrame(trades, columns=["buy_date", "sell_date", "days_held",
                                         "net_return", "crosses_gap", "open"])


# ---------------------------------------------------------------- summary

def summarize(bt: pd.DataFrame, cost_bps: float) -> dict:
    """The headline numbers for one backtest (any output of pnl_from_positions).

    Trade statistics count CLOSED trades only, so a trade still open at the
    end of the period doesn't count as a win or a loss.
    """
    net = bt["net"]
    trades = trade_list(bt, cost_bps)
    closed = trades[~trades["open"]]
    return {
        "CAGR": cagr(net),
        "Vol": float(net.std(ddof=1) * np.sqrt(TRADING_DAYS)),
        "Sharpe": sharpe(net, bt["cash_ret"]),
        "Max DD": max_drawdown(net),
        "In market": float(bt["position"].mean()),
        "Trades": len(closed),
        "Win rate": float((closed["net_return"] > 0).mean()) if len(closed) else float("nan"),
        "Avg days": float(closed["days_held"].mean()) if len(closed) else float("nan"),
        "Avg trade": float(closed["net_return"].mean()) if len(closed) else float("nan"),
        "Gap trades": int(trades["crosses_gap"].sum()),
    }


def summarize_portfolio(bank_bts: dict[str, pd.DataFrame], cost_bps: float) -> dict:
    """Headline numbers for the equal-weight portfolio of several backtests.

    All backtests must already be cut to the same dates. The portfolio's daily
    return is the average of the banks' daily returns (see equal_weight).
    Trades are the total number of closed trades across all the banks.
    """
    from .backtest import equal_weight, portfolio_cash

    net = equal_weight({name: bt["net"] for name, bt in bank_bts.items()})
    per_bank = [summarize(bt, cost_bps) for bt in bank_bts.values()]
    return {
        "CAGR": cagr(net),
        "Vol": float(net.std(ddof=1) * np.sqrt(TRADING_DAYS)),
        "Sharpe": sharpe(net, portfolio_cash(bank_bts)),
        "Max DD": max_drawdown(net),
        "In market": float(np.mean([s["In market"] for s in per_bank])),
        "Trades": int(sum(s["Trades"] for s in per_bank)),
        "Win rate": float("nan"),     # per-trade stats are shown per bank
        "Avg days": float("nan"),
        "Avg trade": float("nan"),
        "Gap trades": int(sum(s["Gap trades"] for s in per_bank)),
    }


# ---------------------------------------------------------------- formatting

PERCENT = {"CAGR", "Vol", "Max DD", "In market", "Win rate", "Avg trade"}


def fmt(key: str, value) -> str:
    """Format one number for a table: percentages as %, counts as whole numbers."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    if key in PERCENT:
        return f"{value:.2%}" if key == "Avg trade" else f"{value:.1%}"
    if isinstance(value, (int, np.integer)):
        return str(value)
    return f"{value:.2f}"


def markdown_table(rows: dict[str, dict]) -> str:
    """{row name: {column: value}} -> a GitHub-style markdown table."""
    columns = list(next(iter(rows.values())).keys())
    lines = ["| | " + " | ".join(columns) + " |",
             "|---|" + "---:|" * len(columns)]
    for name, row in rows.items():
        lines.append(f"| {name} | " + " | ".join(fmt(c, row.get(c)) for c in columns) + " |")
    return "\n".join(lines)
