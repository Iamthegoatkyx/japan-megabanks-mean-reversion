"""The universes in config must match their preregistrations, and never share outputs."""
from pathlib import Path

from backtester import config

NEEDED = {"tickers", "currency", "cost_bps", "cash_rate_fred_id", "cash_rate_name", "noun",
          "preregistration"}


def test_every_universe_has_every_setting_the_scripts_use():
    for name, settings in config.UNIVERSES.items():
        assert NEEDED <= set(settings), name


def test_main_universe_is_still_japan_as_preregistered():
    japan = config.UNIVERSES[config.MAIN_UNIVERSE]
    assert config.MAIN_UNIVERSE == "japan_megabanks"
    assert list(japan["tickers"]) == ["8306.T", "8316.T", "8411.T"]
    assert japan["cost_bps"] == 15.0
    assert japan["cash_rate_fred_id"] == "IRSTCI01JPM156N"


def test_us_universe_matches_preregistration_us():
    us = config.UNIVERSES["us_chips"]
    assert list(us["tickers"]) == ["NVDA", "AMD", "INTC"]
    assert us["currency"] == "USD"
    assert us["cost_bps"] == 5.0
    assert us["cash_rate_fred_id"] == "FEDFUNDS"


def test_rule_settings_are_unchanged():
    assert (config.MA_WINDOW, config.ENTRY_BELOW_MA, config.MAX_HOLD_DAYS,
            config.STOP_LOSS, config.EXECUTION_DELAY) == (20, 0.05, 15, 0.10, 1)
    assert config.OUT_OF_SAMPLE_START == "2018-01-01"


def test_main_results_stay_where_they_were():
    assert config.output_root(config.MAIN_UNIVERSE) == Path("outputs")


def test_other_universes_can_never_overwrite_the_main_results():
    roots = {config.output_root(name) for name in config.UNIVERSES}
    assert len(roots) == len(config.UNIVERSES)          # all different
    assert config.output_root("us_chips") == Path("outputs") / "us_chips"
