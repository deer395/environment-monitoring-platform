"""Quality control for V2 stage 1 depth and temperature data."""

import pandas as pd


QC_LOG_COLUMNS = [
    "datetime",
    "variable",
    "original_value",
    "qc_value",
    "rule",
    "reason",
    "is_flagged",
    "is_applied",
    "parameter",
    "user_decision",
]

QC_SUMMARY_FIELDS = [
    "raw_count",
    "missing_before_qc",
    "removed_by_range",
    "flagged_by_hampel",
    "flagged_by_rate_change",
    "flagged_by_constant_value",
    "applied_flagged_count",
    "missing_after_qc",
]


def _get_valid_range(variable_metadata):
    valid_min = variable_metadata.get("valid_min")
    valid_max = variable_metadata.get("valid_max")
    rules = variable_metadata.get("qc_rules", {})
    return rules.get("valid_min", valid_min), rules.get("valid_max", valid_max)


def _empty_qc_log():
    return pd.DataFrame(columns=QC_LOG_COLUMNS)


def _make_log_rows(data, mask, rule, reason, parameter, applied):
    if not mask.any():
        return _empty_qc_log()
    rows = data.loc[mask, ["datetime", "value"]].copy()
    rows["variable"] = data.attrs.get("variable_key")
    rows["original_value"] = rows["value"]
    rows["qc_value"] = pd.NA if applied else rows["value"]
    rows["rule"] = rule
    rows["reason"] = reason
    rows["is_flagged"] = True
    rows["is_applied"] = applied
    rows["parameter"] = parameter
    rows["user_decision"] = "auto_applied" if applied else "not_applied"
    return rows[[*QC_LOG_COLUMNS]]


def detect_hampel_candidates(data, variable_metadata):
    """V2 stage 1 placeholder: Hampel interface only, no algorithm yet."""
    return _empty_qc_log()


def detect_rate_change_candidates(data, variable_metadata):
    """V2 stage 1 placeholder: rate-change interface only, no algorithm yet."""
    return _empty_qc_log()


def detect_constant_value_candidates(data, variable_metadata):
    """V2 stage 1 placeholder: constant-value interface only, no algorithm yet."""
    return _empty_qc_log()


def apply_quality_control(
    data,
    variable_metadata,
    enable_intraday_2std=False,
    enable_valid_range=True,
):
    """Return qc_data, qc_summary, and qc_log.

    V2 stage 1 applies physical valid-range QC automatically. The legacy daily
    2-std rule is retained only for compatibility and is disabled by default.
    Hampel, rate-change, and constant-value checks are placeholders only.
    """
    result = data.copy()
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
    logs.append(
        _make_log_rows(
            result,
            range_mask,
            "valid_range",
            "超出物理合理范围",
            f"valid_min={valid_min}, valid_max={valid_max}",
            True,
        )
    )
    result.loc[range_mask, "value"] = pd.NA

    day = result["datetime"].dt.floor("D")
    daily_mean = result.groupby(day)["value"].transform("mean")
    daily_std = result.groupby(day)["value"].transform("std")
    legacy_mask = (
        result["value"].notna()
        & daily_std.notna()
        & (daily_std > 0)
        & ((result["value"] - daily_mean).abs() >= 2 * daily_std)
        if enable_intraday_2std
        else result["value"].notna() & False
    )
    logs.append(
        _make_log_rows(
            result,
            legacy_mask,
            "legacy_2std",
            "兼容旧版日内2倍标准差规则",
            "threshold=2*daily_std",
            True,
        )
    )
    result.loc[legacy_mask, "value"] = pd.NA

    logs.extend(
        [
            detect_hampel_candidates(result, variable_metadata),
            detect_rate_change_candidates(result, variable_metadata),
            detect_constant_value_candidates(result, variable_metadata),
        ]
    )
    logs = [log for log in logs if log is not None and not log.empty]
    qc_log = pd.concat(logs, ignore_index=True) if logs else _empty_qc_log()
    if qc_log.empty:
        qc_log = _empty_qc_log()

    qc_summary = {
        "raw_count": int(len(result)),
        "missing_before_qc": missing_before,
        "removed_by_range": int(range_mask.sum()),
        "flagged_by_hampel": 0,
        "flagged_by_rate_change": 0,
        "flagged_by_constant_value": 0,
        "applied_flagged_count": int(qc_log["is_applied"].sum()) if not qc_log.empty else 0,
        "missing_after_qc": int(result["value"].isna().sum()),
        # Backward-compatible aliases for existing exporters.
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
