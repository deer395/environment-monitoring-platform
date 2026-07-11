"""Hourly and daily resampling for V1."""


def _with_metadata(frame, source):
    frame.attrs.update(source.attrs)
    frame["variable"] = source.attrs.get("variable_key")
    frame["unit"] = source.attrs.get("unit")
    return frame


def sort_by_time(data):
    """Sort normalized data by timestamp."""
    result = data.sort_values("datetime").reset_index(drop=True)
    result.attrs.update(data.attrs)
    return result


def resample_hourly_mean(data):
    """Resample QC data to hourly means, ignoring NaN values."""
    source = sort_by_time(data)
    result = source.set_index("datetime")["value"].resample("h").mean().reset_index()
    return _with_metadata(result, source)


def resample_daily_mean(data):
    """Resample QC data to daily means, ignoring NaN values."""
    source = sort_by_time(data)
    result = source.set_index("datetime")["value"].resample("D").mean().reset_index()
    return _with_metadata(result, source)
