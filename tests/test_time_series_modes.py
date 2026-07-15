import numpy as np
import pandas as pd

from src.time_series_interpretation import (
    detect_change_point_mode, detect_high_variability_mode, detect_monthly_pattern_mode,
    detect_periodic_mode, detect_stable_mode, detect_trend_mode,
)


def _monthly(values):
    return pd.DataFrame({"year_month": pd.period_range("2025-01", periods=len(values), freq="M").astype(str), "monthly_mean": values, "monthly_std": np.ones(len(values))})


def _daily(values):
    return pd.DataFrame({"datetime": pd.date_range("2025-01-01", periods=len(values), freq="D"), "value": values})


def test_trend_up_and_down():
    up = detect_trend_mode(_daily(np.arange(12)), 0, 12)
    down = detect_trend_mode(_daily(np.arange(12, 0, -1)), 0, 12)
    assert up["is_match"] and up["evidence"]["direction"] == "increase"
    assert down["is_match"] and down["evidence"]["direction"] == "decrease"


def test_change_and_monthly_pattern():
    change = detect_change_point_mode(_monthly([5, 5.1, 5, 5.1, 3, 3.1]))
    assert change["is_match"] and change["evidence"]["direction"] == "decrease"
    pattern = detect_monthly_pattern_mode(_monthly([3, 3, 4, 4, 3, 2]), {"segments": [{}, {}]})
    assert pattern["is_match"]


def test_variability_and_periodic_and_stable():
    ranges = pd.DataFrame({"daily_range": [2, 3, 4, 5]})
    assert detect_high_variability_mode(ranges, 2, 0, 5)["is_match"]
    index = pd.date_range("2025-01-01", periods=24 * 12, freq="h")
    hourly = pd.DataFrame({"datetime": index, "value": np.sin(np.arange(len(index)) * 2 * np.pi / 24)})
    assert detect_periodic_mode(hourly)["is_match"]
    stable = detect_stable_mode({"trend": {"is_match": False}, "change_point": {"is_match": False}, "monthly_pattern": {"is_match": False}, "high_variability": {"is_match": False}, "periodic": {"is_match": False}}, 4.9, 5.1, _monthly([5, 5.01, 4.99]))
    assert stable["is_match"]
