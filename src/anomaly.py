"""Intra-day anomaly calculation for V1."""


def calculate_intraday_anomaly(hourly_data, daily_mean_data):
    """Calculate anomaly = hourly value - corresponding same-day daily mean."""
    hourly = hourly_data.copy()
    daily = daily_mean_data[["datetime", "value"]].copy()
    hourly["date"] = hourly["datetime"].dt.floor("D")
    daily["date"] = daily["datetime"].dt.floor("D")
    daily = daily.rename(columns={"value": "daily_mean"})[["date", "daily_mean"]]

    result = hourly.merge(daily, on="date", how="left")
    result["anomaly"] = result["value"] - result["daily_mean"]
    result["variable"] = hourly_data.attrs.get("variable_key")
    result["unit"] = hourly_data.attrs.get("unit")
    result = result[["datetime", "variable", "value", "daily_mean", "anomaly", "unit"]]
    result.attrs.update(hourly_data.attrs)
    return result
