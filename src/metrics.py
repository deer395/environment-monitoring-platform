"""Deterministic, registry-driven metrics for environmental variables."""

import pandas as pd

try:
    from .variable_registry import get_variable_metadata
except ImportError:  # pragma: no cover
    from variable_registry import get_variable_metadata


DEFAULT_SCALAR_METRICS = ["count", "valid_count", "missing_count", "mean", "min", "max", "median", "std"]
STANDARD_METRICS = DEFAULT_SCALAR_METRICS + ["monthly_mean", "monthly_std", "daily_range", "max_daily_range"]


def _empty_series_frame(data):
    if data is None:
        return pd.DataFrame(columns=["datetime", "value"])
    return data.copy()


def _metric_source(primary_data, daily_mean_data=None):
    source = _empty_series_frame(primary_data)
    if source.empty and daily_mean_data is not None:
        source = _empty_series_frame(daily_mean_data)
    return source


def _safe_value_series(data):
    if data is None or data.empty or "value" not in data.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(data["value"], errors="coerce")


def _scalar_metrics(data):
    values = _safe_value_series(data)
    return {
        "count": int(len(values)),
        "valid_count": int(values.notna().sum()),
        "missing_count": int(values.isna().sum()),
        "mean": values.mean(skipna=True),
        "min": values.min(skipna=True),
        "max": values.max(skipna=True),
        "median": values.median(skipna=True),
        "std": values.std(skipna=True),
    }


def _monthly_metrics(data):
    source = _empty_series_frame(data)
    if source.empty or "datetime" not in source.columns:
        return pd.DataFrame(columns=["year_month", "monthly_mean", "monthly_std"])
    source = source.copy()
    source["datetime"] = pd.to_datetime(source["datetime"], errors="coerce")
    source["value"] = pd.to_numeric(source["value"], errors="coerce")
    source = source.dropna(subset=["datetime"])
    if source.empty:
        return pd.DataFrame(columns=["year_month", "monthly_mean", "monthly_std"])
    month = source["datetime"].dt.to_period("M").astype(str)
    monthly = source.groupby(month)["value"].agg(monthly_mean="mean", monthly_std="std")
    return monthly.rename_axis("year_month").reset_index()


def _daily_range_metrics(anomaly_data):
    anomaly = _empty_series_frame(anomaly_data)
    if anomaly.empty or "datetime" not in anomaly.columns or "anomaly" not in anomaly.columns:
        return pd.DataFrame(columns=["date", "daily_range"]), pd.NA
    anomaly = anomaly.copy()
    anomaly["datetime"] = pd.to_datetime(anomaly["datetime"], errors="coerce")
    anomaly["anomaly"] = pd.to_numeric(anomaly["anomaly"], errors="coerce")
    anomaly = anomaly.dropna(subset=["datetime"])
    if anomaly.empty:
        return pd.DataFrame(columns=["date", "daily_range"]), pd.NA
    day = anomaly["datetime"].dt.floor("D")
    daily_range = anomaly.groupby(day)["anomaly"].agg(
        lambda values: values.max(skipna=True) - values.min(skipna=True)
    )
    table = daily_range.rename_axis("date").reset_index(name="daily_range")
    return table, daily_range.max(skipna=True)


def _metadata_for(variable_key, metadata):
    if metadata is not None:
        return metadata
    try:
        return get_variable_metadata(variable_key)
    except KeyError:
        return {"metrics": STANDARD_METRICS}


def calculate_metrics(variable_key, hourly_data=None, daily_mean_data=None, anomaly_data=None, metadata=None, base_data=None):
    """Calculate metrics by metric name instead of variable name.

    The function keeps the old positional signature for compatibility, but the
    all monitored variables receive the standard V3.1 statistics. Unknown
    variable names still work and receive the same metric set instead of
    raising an unsupported-variable error.
    """
    variable_metadata = _metadata_for(variable_key, metadata)
    source = _metric_source(base_data if base_data is not None else hourly_data, daily_mean_data)
    result = {}

    scalar_values = _scalar_metrics(source)
    for metric in DEFAULT_SCALAR_METRICS:
        result[metric] = scalar_values[metric]

    result["monthly"] = _monthly_metrics(source)

    daily_range, max_daily_range = _daily_range_metrics(anomaly_data)
    result["daily_range"] = daily_range
    result["max_daily_range"] = max_daily_range

    return result


# Backward-compatible helpers retained for older scripts/imports.
def calculate_temperature_metrics(hourly_data, daily_mean_data=None):
    return calculate_metrics("temperature", hourly_data, daily_mean_data, metadata={"metrics": STANDARD_METRICS})


def calculate_depth_metrics(hourly_data, daily_mean_data=None, anomaly_data=None):
    return calculate_metrics("depth", hourly_data, daily_mean_data, anomaly_data, metadata={"metrics": STANDARD_METRICS})
