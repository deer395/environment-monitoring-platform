"""Build deterministic, single-variable report data without Streamlit state."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from .variable_registry import get_variable_metadata
from .time_series_interpretation import extract_time_series_features
from .version import BUSINESS_BASELINE_TAG, BUSINESS_CORE_VERSION


SOFTWARE_VERSION = BUSINESS_CORE_VERSION
BASELINE_TAG = BUSINESS_BASELINE_TAG


def _timestamp(value):
    value = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(value) else value


def _manual_remove_count(review_table):
    if review_table is None or review_table.empty:
        return 0
    review = review_table.copy()
    automatic = review.get("existing_rule", pd.Series("", index=review.index)).fillna("").astype(str)
    decisions = review.get("user_decision", pd.Series("", index=review.index)).fillna("")
    return int((decisions.isin(["remove", "manual_remove"]) & ~automatic.str.contains("sensor_zero|hard_range|physical_range")).sum())


def _sampling_interval_minutes(raw_data):
    if raw_data is None or raw_data.empty or "datetime" not in raw_data:
        return None
    times = pd.to_datetime(raw_data["datetime"], errors="coerce").dropna().drop_duplicates().sort_values()
    if len(times) < 2:
        return None
    return float(times.diff().dropna().dt.total_seconds().median() / 60)


def _number(value):
    if value is None or pd.isna(value): return "—"
    digits = 2 if abs(value) >= 1 else 3 if abs(value) >= .01 else 4
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def _value(value, unit):
    return f"{_number(value)} {unit}"


def _range(low, high, unit):
    return f"{_number(low)}～{_number(high)} {unit}"


def _month(value):
    period = pd.Period(str(value), freq="M")
    return f"{period.year}年{period.month}月"


def _month_span(start, end):
    return _month(start) if start == end else f"{_month(start)}至{_month(end)}"


def _monthly_stage_narrative(data, unit, monthly_info):
    """Describe sustained directional runs; no variable-name special cases."""
    values, months = data["monthly_mean"].to_numpy(), data["year_month"].tolist()
    threshold = max((max(values) - min(values)) * .10, 1e-9)
    signs = ["stable"] + ["increase" if values[i]-values[i-1] > threshold else "decrease" if values[i]-values[i-1] < -threshold else "stable" for i in range(1, len(values))]
    # Stable transitions belong to their surrounding directional run.
    for i in range(1, len(signs)-1):
        if signs[i] == "stable" and signs[i-1] == signs[i+1] != "stable": signs[i] = signs[i-1]
    runs, start = [], 0
    for i in range(1, len(signs)):
        if signs[i] != signs[i-1]: runs.append((start, i-1, signs[i-1])); start = i
    runs.append((start, len(values)-1, signs[-1]))
    sentences = []
    for index, (begin, end, direction) in enumerate(runs):
        # A direction is sustained only when it covers at least two monthly
        # changes.  ``begin`` and ``end`` index changes (rather than months),
        # so two adjacent entries already meet that requirement.
        sustained = end - begin >= 1
        prefix = "随后"
        if direction == "stable":
            if begin == end: text = f"{_month(months[begin])}月平均值为{_value(values[begin], unit)}。"
            else: text = f"{_month_span(months[begin], months[end])}总体维持在{_range(min(values[begin:end+1]), max(values[begin:end+1]), unit)}之间。"
        elif direction == "increase":
            previous_direction = next((run[2] for run in reversed(runs[:index]) if run[2] != "stable"), None)
            reversed_direction = previous_direction == "decrease"
            verb = "阶段性回升" if sustained and reversed_direction else ("持续上升" if sustained else ("短暂回升" if reversed_direction else "上升"))
            text = f"{_month_span(months[max(0, begin-1)], months[end])}{verb}至{_value(values[end], unit)}。"
        else:
            previous_direction = next((run[2] for run in reversed(runs[:index]) if run[2] != "stable"), None)
            reversed_direction = previous_direction == "increase"
            verb = "阶段性回落" if sustained and reversed_direction else ("持续下降" if sustained else ("短暂回落" if reversed_direction else "下降"))
            text = f"{_month_span(months[max(0, begin-1)], months[end])}{verb}至{_value(values[end], unit)}。"
        sentences.append(text)
    if monthly_info.get("max_std_month") is not None: sentences.append(f"{_month(monthly_info['max_std_month'])}月标准差为{_value(monthly_info['max_std'], unit)}，为观测期最大。")
    return "".join(sentences)


def _build_narratives(name, unit, stats, features):
    interp = features["interpretation"]; monthly = stats.get("monthly", pd.DataFrame()); monthly_info = interp.get("monthly_interpretation", {})
    hourly = f"小时平均{name}的90%分布在{_range(interp.get('p5'), interp.get('p95'), unit)}之间，平均值为{_value(stats.get('mean'), unit)}，中位数为{_value(stats.get('median'), unit)}。观测期最高小时平均值为{_value(interp.get('max_value'), unit)}，最低小时平均值为{_value(interp.get('min_value'), unit)}。"
    if interp.get("primary_mode") == "trend": hourly += "日平均序列呈持续性变化。"
    elif interp.get("primary_mode") == "change_point": hourly += "日平均序列在前期总体维持较高水平，后期出现明显水平变化。"
    else: hourly += "日平均序列整体存在阶段性起伏。"
    if interp.get("primary_mode") == "periodic":
        intraday = f"{name}日内距平呈持续而规律的重复变化，识别出的主要周期约为{_number(interp.get('periodicity', {}).get('period_hours'))}小时。日变化幅度中位数为{_value(interp.get('daily_range_median'), unit)}，95%的日变化幅度不超过{_value(interp.get('daily_range_p95'), unit)}"
    else:
        intraday = f"{name}日内距平总体围绕0 {unit}波动，未识别出稳定的周期性变化。日变化幅度中位数为{_value(interp.get('daily_range_median'), unit)}，95%的日变化幅度不超过{_value(interp.get('daily_range_p95'), unit)}"
    if pd.notna(interp.get("max_daily_range")):
        date = pd.Timestamp(interp["max_daily_range_date"])
        intraday += f"，最大日变化幅度为{_value(interp['max_daily_range'], unit)}，出现在{date.year}年{date.month}月{date.day}日。"
    else: intraday += "。"
    monthly_text = ""
    if monthly is not None and not monthly.empty:
        data = monthly.dropna(subset=["monthly_mean"]).reset_index(drop=True)
        cp = monthly_info.get("change_month")
        cp_index = data.index[data["year_month"].eq(cp)][0] if cp and data["year_month"].eq(cp).any() else None
        if cp and cp_index is not None and cp_index >= 3 and len(data) >= 6 and interp.get("primary_mode") == "change_point":
            before = data.iloc[:cp_index]; after = data.iloc[cp_index:]
            max_row, min_row = data.loc[data.monthly_mean.idxmax()], data.loc[data.monthly_mean.idxmin()]
            first_end = min(len(before)-1, 4)
            monthly_text = f"{_month_span(data.iloc[0]['year_month'], data.iloc[first_end]['year_month'])}，月平均值主要在{_range(before['monthly_mean'].min(), before['monthly_mean'].max(), unit)}之间小幅波动。"
            if max_row.name > first_end: monthly_text += f"{_month(max_row['year_month'])}升至{_value(max_row['monthly_mean'], unit)}，为观测期最高值。"
            if len(before) - first_end > 1: monthly_text += f"{_month_span(data.iloc[first_end + 1]['year_month'], before.iloc[-1]['year_month'])}月平均值总体维持在约{_value(before.iloc[first_end + 1:]['monthly_mean'].mean(), unit)}。"
            monthly_text += f"{_month(after.iloc[0]['year_month'])}起明显{('下降' if monthly_info.get('direction') == 'decrease' else '上升')}，{_month(after.iloc[-1]['year_month'])}进一步达到{_value(after.iloc[-1]['monthly_mean'], unit)}。"
            if monthly_info.get("max_std_month") is not None: monthly_text += f"{_month(monthly_info['max_std_month'])}月标准差达到{_value(monthly_info['max_std'], unit)}，为观测期最大。"
        elif len(data) >= 5:
            monthly_text = _monthly_stage_narrative(data, unit, monthly_info)
        else:
            monthly_text = f"月平均值在{_range(data.monthly_mean.min(), data.monthly_mean.max(), unit)}之间变化。"
        # Stage narration is always generated from the full sequence; a single
        # maximum jump may inform mode selection but must not replace all stages.
        if len(data) >= 2:
            monthly_text = _monthly_stage_narrative(data, unit, monthly_info)
    if monthly is not None and not monthly.empty:
        data = monthly.dropna(subset=["monthly_mean"]).reset_index(drop=True)
        values = data["monthly_mean"].to_numpy()
        high_index, low_index = int(values.argmax()), int(values.argmin())
        high, low, last = data.iloc[high_index], data.iloc[low_index], data.iloc[-1]
        material_change = max((values.max() - values.min()) * .10, 1e-9)
        periodicity = interp.get("periodicity", {}).get("period_hours")
        prefix = f"观测期内，日内变化呈约{_number(periodicity)}小时的规律周期。" if interp.get("primary_mode") == "periodic" and pd.notna(periodicity) else ""
        if high_index < low_index < len(data) - 1 and last.monthly_mean > low.monthly_mean + material_change:
            conclusion = f"月平均值前期处于相对较高水平，{_month(high.year_month)}达到观测期高值{_value(high.monthly_mean, unit)}，随后于{_month(low.year_month)}降至低值{_value(low.monthly_mean, unit)}，并在{_month_span(data.iloc[low_index + 1].year_month, last.year_month)}回升至{_value(last.monthly_mean, unit)}。"
        elif low_index < high_index and last.monthly_mean < high.monthly_mean - material_change:
            conclusion = f"月平均值由前期较低水平逐步上升，{_month(high.year_month)}达到观测期高值{_value(high.monthly_mean, unit)}，随后回落至{_value(last.monthly_mean, unit)}。"
        else:
            conclusion = f"月平均值在{_month(data.iloc[0].year_month)}至{_month(last.year_month)}呈阶段性变化，{_month(high.year_month)}处于高值阶段，{_month(low.year_month)}处于低值阶段。"
        conclusion = prefix + conclusion
        if monthly_info.get("max_std_month") is not None: conclusion += f"{_month(monthly_info['max_std_month'])}月波动相对更明显。"
    else: conclusion = hourly.split("。", 1)[0] + "。"
    return {"hourly": hourly, "intraday": intraday, "monthly": monthly_text, "conclusion": conclusion}


def build_report_context(
    *,
    variable_key,
    raw_data,
    final_qc_data,
    final_qc_log,
    qc_summary,
    review_table,
    resampled,
    anomaly,
    metrics,
    qc_token,
    confirmed_qc_token,
    project_name="",
    project_title="",
    report_title="",
    organization="",
    author="",
    generated_at=None,
):
    """Return the explicit data contract consumed by the Word generator.

    The token comparison deliberately prevents an invalidated confirmation from
    being reused after source, time range, or QC parameter changes.
    """
    if not confirmed_qc_token or qc_token != confirmed_qc_token:
        raise ValueError("当前变量的人工确认结果已失效，请重新确认最终质控结果。")
    if final_qc_data is None or qc_summary is None:
        raise ValueError("当前变量缺少已确认的最终质控结果。")

    metadata = get_variable_metadata(variable_key)
    raw = raw_data.copy() if raw_data is not None else pd.DataFrame()
    final = final_qc_data.copy()
    raw_times = pd.to_datetime(raw.get("datetime"), errors="coerce") if "datetime" in raw else pd.Series(dtype="datetime64[ns]")
    valid = pd.to_numeric(final.get("value"), errors="coerce").notna() if "value" in final else pd.Series(dtype=bool)
    start = _timestamp(raw_times.min())
    end = _timestamp(raw_times.max())
    duplicate_count = int(raw_times.duplicated(keep="first").sum()) if not raw_times.empty else 0
    raw_missing = int(pd.to_numeric(raw.get("value"), errors="coerce").isna().sum()) if "value" in raw else 0
    final_valid = int(valid.sum())
    raw_count = int(len(raw))
    manual_removed = _manual_remove_count(review_table)
    generated = _timestamp(generated_at) or pd.Timestamp(datetime.now())

    default_title = f"{metadata.get('display_name_cn', variable_key)}监测数据质控与统计分析报告"
    hourly = (resampled or {}).get("hourly", pd.DataFrame())
    daily = (resampled or {}).get("daily", pd.DataFrame())
    time_features = extract_time_series_features(hourly, daily, (metrics or {}).get("monthly"), (metrics or {}).get("daily_range"), anomaly)
    raw_final_values = pd.to_numeric(final.get("value"), errors="coerce")
    hourly_values = pd.to_numeric(hourly.get("value"), errors="coerce")
    calendar_days = (end.normalize() - start.normalize()).days + 1 if start is not None and end is not None else None
    actual_days = int(pd.to_datetime(raw.loc[pd.to_numeric(raw.get("value"), errors="coerce").notna(), "datetime"], errors="coerce").dt.normalize().nunique()) if not raw.empty else 0
    return {
        "project_info": {"site_name": project_name.strip(), "project_name": project_title.strip(), "report_title": report_title.strip() or default_title, "department": organization.strip(), "author": author.strip()},
        "variable_info": {"variable_key": variable_key, "display_name": metadata.get("display_name_cn", variable_key), "unit": metadata.get("unit", "")},
        "data_summary": {"start_time": start, "end_time": end, "raw_count": raw_count, "raw_missing_count": raw_missing, "duplicate_count": duplicate_count, "median_sampling_interval_minutes": _sampling_interval_minutes(raw), "final_valid_count": final_valid, "final_missing_count": int(len(final) - final_valid), "valid_rate": (final_valid / raw_count * 100) if raw_count else 0.0, "calendar_days": calendar_days, "actual_data_days": actual_days, "date_coverage_rate": (actual_days / calendar_days * 100) if calendar_days else pd.NA},
        "qc_summary": {**dict(qc_summary), "manual_remove_count": manual_removed},
        "statistics": {**dict(metrics or {}), "raw_final_statistics": {"min": raw_final_values.min(), "max": raw_final_values.max(), "p5": raw_final_values.quantile(.05), "p95": raw_final_values.quantile(.95)}, "hourly_statistics": {"min": hourly_values.min(), "max": hourly_values.max(), "p5": hourly_values.quantile(.05), "p95": hourly_values.quantile(.95)}},
        "time_features": {"resampled": resampled or {}, "anomaly": anomaly, "metrics": metrics or {}, "interpretation": time_features},
        "narratives": _build_narratives(metadata.get("display_name_cn", variable_key), metadata.get("unit", ""), {**dict(metrics or {}), "raw_final_statistics": {"min": raw_final_values.min(), "max": raw_final_values.max()}, "hourly_statistics": {"min": hourly_values.min(), "max": hourly_values.max()}}, {"interpretation": time_features}),
        "source_data": {"raw_data": raw, "final_qc_data": final, "final_qc_log": final_qc_log, "review_table": review_table},
        "parameters": {"sensor_zero_enabled": bool(metadata.get("zero_is_invalid", False)), "hard_min": metadata.get("hard_min"), "hard_max": metadata.get("hard_max"), "hampel_window": metadata.get("hampel_window"), "hampel_threshold": metadata.get("hampel_sigma"), "hampel_min_abs_deviation": metadata.get("hampel_min_abs_deviation"), "constant_value_window": metadata.get("constant_value_window"), "constant_value_tolerance": metadata.get("constant_value_tolerance")},
        "software_info": {"software_version": SOFTWARE_VERSION, "git_tag": BASELINE_TAG, "generated_at": generated, "qc_confirmed": True, "qc_token": qc_token},
    }
