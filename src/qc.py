"""Quality control for V2 depth and temperature data."""

import pandas as pd


QC_LOG_COLUMNS = [
    "record_id",
    "datetime", "variable", "original_value", "qc_value", "rule", "reason",
    "is_flagged", "is_applied", "parameter", "user_decision", "decision_source",
]

QC_SUMMARY_FIELDS = [
    "raw_count", "missing_before_qc", "removed_by_range", "flagged_by_hampel",
    "flagged_by_rate_change", "flagged_by_constant_value", "applied_flagged_count",
    "missing_after_qc",
]


def _get_valid_range(variable_metadata):
    rules = variable_metadata.get("qc_rules", {})
    return (
        rules.get("valid_min", variable_metadata.get("valid_min")),
        rules.get("valid_max", variable_metadata.get("valid_max")),
    )


def _empty_qc_log():
    return pd.DataFrame(columns=QC_LOG_COLUMNS)


def _make_log_rows(data, mask, rule, reason, parameter, applied):
    if mask is None or not mask.any():
        return _empty_qc_log()
    columns = ["record_id", "datetime", "value"] if "record_id" in data.columns else ["datetime", "value"]
    rows = data.loc[mask, columns].copy()
    if "record_id" not in rows.columns:
        rows["record_id"] = data.loc[mask].index.astype(str)
    rows["variable"] = data.attrs.get("variable_key")
    rows["original_value"] = rows["value"]
    rows["qc_value"] = pd.NA if applied else rows["value"]
    rows["rule"] = rule
    rows["reason"] = reason
    rows["is_flagged"] = True
    rows["is_applied"] = applied
    rows["parameter"] = parameter
    rows["user_decision"] = "remove" if applied else "undecided"
    rows["decision_source"] = "automatic" if applied else "algorithm_suggestion"
    return rows[QC_LOG_COLUMNS]


def detect_hampel_candidates(data, variable_metadata):
    """Flag Hampel outliers with rolling median and MAD; do not apply removal."""
    window = int(variable_metadata.get("hampel_window") or 7)
    sigma = float(variable_metadata.get("hampel_sigma") or 3.0)
    min_abs_deviation = float(variable_metadata.get("hampel_min_abs_deviation") or 0.0)
    if window < 3:
        window = 3
    if window % 2 == 0:
        window += 1

    values = pd.to_numeric(data["value"], errors="coerce")
    rolling = values.rolling(window=window, center=True, min_periods=3)
    median = rolling.median()

    def mad(series):
        med = series.median(skipna=True)
        return (series - med).abs().median(skipna=True)

    mad_values = rolling.apply(mad, raw=False)
    threshold = sigma * 1.4826 * mad_values
    if min_abs_deviation > 0:
        threshold = threshold.clip(lower=min_abs_deviation)
    mask = values.notna() & median.notna() & mad_values.notna() & (mad_values > 0)
    mask &= (values - median).abs() > threshold

    return _make_log_rows(
        data,
        mask,
        "hampel",
        "Hampel滚动中位数与MAD异常标记",
        f"window={window}, sigma={sigma}, min_abs_deviation={min_abs_deviation}",
        False,
    )


def detect_rate_change_candidates(data, variable_metadata):
    """V2 stage 2 placeholder: rate-change interface only, no algorithm yet."""
    return _empty_qc_log()


def detect_constant_value_candidates(data, variable_metadata):
    """Flag runs of nearly constant values; do not apply removal."""
    window = int(variable_metadata.get("constant_value_window") or 0)
    tolerance = float(variable_metadata.get("constant_value_tolerance") or 0.0)
    if window < 2:
        return _empty_qc_log()

    values = pd.to_numeric(data["value"], errors="coerce")
    valid = values.notna()
    group = ((values.diff().abs() > tolerance) | valid.ne(valid.shift())).cumsum()
    run_lengths = values.groupby(group).transform("size")
    mask = valid & (run_lengths >= window)

    return _make_log_rows(
        data,
        mask,
        "constant_value",
        "连续恒定值或变化小于容差",
        f"window={window}, tolerance={tolerance}",
        False,
    )


def apply_quality_control(
    data,
    variable_metadata,
    enable_intraday_2std=False,
    enable_valid_range=True,
    enable_hampel=False,
    enable_constant_value=False,
):
    """Return qc_data, qc_summary, and qc_log."""
    result = data.copy()
    if "record_id" not in result.columns:
        result.insert(0, "record_id", [f"rec_{idx}" for idx in range(len(result))])
    result["record_id"] = result["record_id"].astype(str)
    result["datetime"] = pd.to_datetime(result["datetime"], errors="coerce")
    result["value"] = pd.to_numeric(result["value"], errors="coerce")
    result["variable"] = result.attrs.get("variable_key")
    result["unit"] = result.attrs.get("unit")

    original_value = result["value"].copy()
    logs = []
    missing_before = int(result["value"].isna().sum())

    valid_min, valid_max = _get_valid_range(variable_metadata)
    range_mask = result["value"].notna() & False
    if enable_valid_range and valid_min is not None:
        range_mask |= result["value"].notna() & (result["value"] < valid_min)
    if enable_valid_range and valid_max is not None:
        range_mask |= result["value"].notna() & (result["value"] > valid_max)
    logs.append(_make_log_rows(result, range_mask, "physical_range", "超出物理合理范围", f"valid_min={valid_min}, valid_max={valid_max}", True))
    result.loc[range_mask, "value"] = pd.NA

    day = result["datetime"].dt.floor("D")
    daily_mean = result.groupby(day)["value"].transform("mean")
    daily_std = result.groupby(day)["value"].transform("std")
    legacy_mask = (
        result["value"].notna() & daily_std.notna() & (daily_std > 0)
        & ((result["value"] - daily_mean).abs() >= 2 * daily_std)
        if enable_intraday_2std else result["value"].notna() & False
    )
    logs.append(_make_log_rows(result, legacy_mask, "legacy_2std", "兼容旧版日内2倍标准差规则", "threshold=2*daily_std", True))
    result.loc[legacy_mask, "value"] = pd.NA

    hampel_log = detect_hampel_candidates(result, variable_metadata) if enable_hampel else _empty_qc_log()
    rate_log = detect_rate_change_candidates(result, variable_metadata)
    constant_log = detect_constant_value_candidates(result, variable_metadata) if enable_constant_value else _empty_qc_log()
    logs.extend([hampel_log, rate_log, constant_log])

    logs = [
        log
        for log in logs
        if log is not None and not log.empty and not log.dropna(axis=1, how="all").empty
    ]
    qc_log = (
        pd.DataFrame(
            [record for log in logs for record in log.to_dict("records")],
            columns=QC_LOG_COLUMNS,
        )
        if logs
        else _empty_qc_log()
    )

    qc_summary = {
        "raw_count": int(len(result)),
        "missing_before_qc": missing_before,
        "removed_by_range": int(range_mask.sum()),
        "flagged_by_hampel": int((qc_log["rule"] == "hampel").sum()) if not qc_log.empty else 0,
        "flagged_by_rate_change": int((qc_log["rule"] == "rate_change").sum()) if not qc_log.empty else 0,
        "flagged_by_constant_value": int((qc_log["rule"] == "constant_value").sum()) if not qc_log.empty else 0,
        "applied_flagged_count": int(qc_log["is_applied"].sum()) if not qc_log.empty else 0,
        "missing_after_qc": int(result["value"].isna().sum()),
        "raw_record_count": int(len(result)),
        "raw_missing_count": missing_before,
        "daily_2std_removed_count": int(legacy_mask.sum()),
        "range_removed_count": int(range_mask.sum()),
        "post_qc_missing_count": int(result["value"].isna().sum()),
    }

    result["value_before_qc"] = original_value
    result.attrs.update(data.attrs)
    result.attrs["qc_summary"] = qc_summary
    return result, qc_summary, qc_log


def summarize_quality_control(qc_result):
    """Return QC summary attached by apply_quality_control."""
    return qc_result.attrs.get("qc_summary", {})
