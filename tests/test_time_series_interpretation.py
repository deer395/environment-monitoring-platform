"""Focused deterministic mode tests for V4.1.1 report narration."""
import numpy as np
import pandas as pd

from src.time_series_interpretation import extract_time_series_features


def _frames(values, monthly_values=None):
    hours = pd.date_range("2026-01-01", periods=len(values), freq="h")
    hourly = pd.DataFrame({"datetime": hours, "value": values})
    daily = hourly.set_index("datetime").resample("D").mean().reset_index()
    months = monthly_values if monthly_values is not None else [np.mean(values)]
    monthly = pd.DataFrame({"year_month": pd.period_range("2026-01", periods=len(months), freq="M").astype(str), "monthly_mean": months, "monthly_std": np.ones(len(months))})
    anomaly = pd.DataFrame({"datetime": hours, "anomaly": values - np.mean(values)})
    ranges = pd.DataFrame({"date": daily["datetime"], "daily_range": np.full(len(daily), np.ptp(values) / 4)})
    return hourly, daily, monthly, ranges, anomaly


def test_change_point_and_periodic():
    hourly, daily, monthly, ranges, anomaly = _frames(np.linspace(1, 2, 24 * 90), [4.0, 4.1, 4.0, 4.1, 2.9, 2.7])
    result = extract_time_series_features(hourly, daily, monthly, ranges, anomaly)
    assert result["primary_mode"] == "change_point"
    assert result["monthly_interpretation"]["change_month"] == "2026-05"
    periodic_values = 5 + np.sin(np.arange(24 * 20) * 2 * np.pi / 24)
    hourly, daily, monthly, ranges, anomaly = _frames(periodic_values, [5.0, 5.0, 5.0])
    periodic = extract_time_series_features(hourly, daily, monthly, ranges, anomaly)
    assert periodic["primary_mode"] == "periodic"


def test_short_data_is_safe():
    hourly, daily, monthly, ranges, anomaly = _frames([1, 2, 3])
    assert extract_time_series_features(hourly, daily, monthly, ranges, anomaly)["periodicity"]["detected"] is False
