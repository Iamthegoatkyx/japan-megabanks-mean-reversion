"""Is the difference real? A block bootstrap of the Sharpe-ratio gap."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import TRADING_DAYS


def _sharpe(excess: np.ndarray) -> float:
    """Annualised Sharpe of daily returns that are ALREADY in excess of cash."""
    sd = excess.std(ddof=1)
    return float(excess.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else float("nan")


def bootstrap_sharpe_diff(strategy: pd.Series, benchmark: pd.Series, cash_ret: pd.Series,
                          n_boot: int = 5000, block: int = 21, seed: int = 0) -> dict:
    """95% confidence interval for Sharpe(strategy) - Sharpe(benchmark).

    Why a BLOCK bootstrap: we build thousands of fake histories by gluing
    together random chunks of `block` consecutive days (21 ~ one month).
    Chunks keep calm and stormy weeks together (volatility clusters), which
    resampling single days would destroy.

    Why the SAME chunks for both series: on any given day the strategy and
    buy-and-hold face the same market, so we keep each day's pair together.

    The success test in PREREGISTRATION.md needs the whole interval above 0.
    """
    pair = pd.concat([strategy, benchmark], axis=1).dropna()
    cash = cash_ret.reindex(pair.index).to_numpy()
    excess = pair.to_numpy() - cash[:, None]          # both columns minus cash
    n = len(excess)
    if n < 2 * block:
        raise ValueError("not enough data for a block bootstrap")

    rng = np.random.default_rng(seed)                 # fixed seed: same answer every run
    n_blocks = int(np.ceil(n / block))
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        # Pick random block starting points, take `block` days from each,
        # glue them together and trim to the original length.
        starts = rng.integers(0, n - block + 1, n_blocks)
        rows = (starts[:, None] + np.arange(block)).ravel()[:n]
        sample = excess[rows]
        diffs[b] = _sharpe(sample[:, 0]) - _sharpe(sample[:, 1])

    low, high = np.nanpercentile(diffs, [2.5, 97.5])
    return {
        "observed_diff": _sharpe(excess[:, 0]) - _sharpe(excess[:, 1]),
        "ci_low": float(low),
        "ci_high": float(high),
        "share_not_better": float(np.mean(diffs <= 0)),
        "n_boot": n_boot,
        "block": block,
    }
