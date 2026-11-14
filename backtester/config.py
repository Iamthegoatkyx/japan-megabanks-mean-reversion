"""Every setting in one place, so that every script runs the SAME preregistered rule.

To add a robustness universe later (e.g. Korean or Hong Kong banks), add an
entry to UNIVERSES with its own tickers, currency, costs and cash rate.
Do NOT touch the RULE settings: they are fixed by PREREGISTRATION.md.
"""
from pathlib import Path

# --- The trading rule (fixed by PREREGISTRATION.md, same for every universe) ---
MA_WINDOW = 20          # moving average length, in trading days
ENTRY_BELOW_MA = 0.05   # enter when close <= (1 - 0.05) * MA
MAX_HOLD_DAYS = 15      # a trade never lasts more than 15 trading days
STOP_LOSS = 0.10        # exit signal when close <= (1 - 0.10) * entry price
EXECUTION_DELAY = 1     # signal at close t, trade at close t+1

# --- The in-sample / out-of-sample split ---
OUT_OF_SAMPLE_START = "2018-01-01"   # in-sample is everything before this date

# --- Stock universes ---
# Each universe gets its own currency, cost and cash-rate assumptions,
# because trading costs and interest rates differ from market to market.
UNIVERSES = {
    "japan_megabanks": {
        "tickers": {"8306.T": "MUFG", "8316.T": "SMFG", "8411.T": "Mizuho"},
        "currency": "JPY",
        "cost_bps": 15.0,   # per side
        # Japan overnight call rate, % per year, monthly (OECD via FRED).
        "cash_rate_fred_id": "IRSTCI01JPM156N",
        "cash_rate_name": "JPY call rate",
        "noun": "banks",
        "preregistration": "PREREGISTRATION.md",
    },
    # Robustness test, preregistered separately in PREREGISTRATION_US.md.
    "us_chips": {
        "tickers": {"NVDA": "NVIDIA", "AMD": "AMD", "INTC": "Intel"},
        "currency": "USD",
        "cost_bps": 5.0,    # per side (very liquid US large caps)
        # US effective federal funds rate, % per year, monthly (FRED).
        "cash_rate_fred_id": "FEDFUNDS",
        "cash_rate_name": "USD fed funds rate",
        "noun": "stocks",
        "preregistration": "PREREGISTRATION_US.md",
    },
}

# The universe used for the preregistered main test.
MAIN_UNIVERSE = "japan_megabanks"


def output_root(universe: str) -> Path:
    """Where a universe's results go. The main (Japan) test keeps outputs/ as it
    was; every other universe gets its own folder, outputs/<universe>/, so a
    robustness run can never overwrite the main results."""
    return Path("outputs") if universe == MAIN_UNIVERSE else Path("outputs") / universe
