"""Deterministic metrics for V1 depth and temperature."""


def _scalar_metrics(series):
    return {
        "mean": series.mean(skipna=True),
        "max": series.max(skipna=True),
        "min": series.min(skipna=True),
        "std": series.std(skipna=True),
    }


def calculate_temperature_metrics(hourly_data, daily_mean_data=None):
    """Calculate temperature mean, max, min, std, monthly mean and monthly std."""
    data = hourly_data.copy()
    result = _scalar_metrics(data["value"])
    month = data["datetime"].dt.to_period("M").astype(str)
    monthly = data.groupby(month)["value"].agg(monthly_mean="mean", monthly_std="std")
    result["monthly"] = monthly.rename_axis("year_month").reset_index()
    return result


def calculate_depth_metrics(hourly_data, daily_mean_data=None, anomaly_data=None):
    """Calculate depth scalar metrics and daily range from intra-day anomaly."""
    data = hourly_data.copy()
    result = _scalar_metrics(data["value"])
    if anomaly_data is None:
        raise ValueError("depth daily_range requires anomaly_data.")

    anomaly = anomaly_data.copy()
    day = anomaly["datetime"].dt.floor("D")
    daily_range = anomaly.groupby(day)["anomaly"].agg(
        lambda values: values.max(skipna=True) - values.min(skipna=True)
    )
    result["daily_range"] = daily_range.rename_axis("date").reset_index(name="daily_range")
    result["max_daily_range"] = daily_range.max(skipna=True)
    return result


def calculate_metrics(variable_key, hourly_data, daily_mean_data=None, anomaly_data=None):
    """Dispatch V1 deterministic metric calculation."""
    if variable_key == "temperature":
        return calculate_temperature_metrics(hourly_data, daily_mean_data)
    if variable_key == "depth":
        return calculate_depth_metrics(hourly_data, daily_mean_data, anomaly_data)
    raise ValueError(f"Unsupported V1 variable: {variable_key!r}")
