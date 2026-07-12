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


def _aggregate_resample(source, frequency, aggregation):
    resampler = source.set_index("datetime")["value"].resample(frequency)
    if aggregation == "median":
        return resampler.median().reset_index()
    if aggregation == "min":
        return resampler.min().reset_index()
    if aggregation == "max":
        return resampler.max().reset_index()
    if aggregation == "sum":
        return resampler.sum().reset_index()
    return resampler.mean().reset_index()


def resample_configured(data, variable_metadata):
    """Resample monitoring data to the standard hourly and daily means.

    V3.1 treats all monitored variables as 10-minute or 30-minute series, so
    the main analysis pipeline always produces both hourly and daily means.
    Registry metadata is still accepted for compatibility, but it no longer
    disables either frequency in the standard workflow.
    """
    source = sort_by_time(data)
    aggregation = "mean"
    return {
        "hourly": _with_metadata(_aggregate_resample(source, "h", aggregation), source),
        "daily": _with_metadata(_aggregate_resample(source, "D", aggregation), source),
    }
