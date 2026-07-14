"""Report table builders for V1 deterministic outputs."""

from pathlib import Path

import pandas as pd

try:
    from .variable_registry import get_variable_metadata
except ImportError:  # pragma: no cover
    from variable_registry import get_variable_metadata


ROUND_DIGITS = 4


def _round_numeric(df):
    result = df.copy()
    numeric_cols = result.select_dtypes(include="number").columns
    result[numeric_cols] = result[numeric_cols].round(ROUND_DIGITS)
    return result


def build_basic_statistics_row(variable_key, hourly_df, metrics_result, qc_summary):
    """Build one basic statistics row for a variable."""
    valid = hourly_df["value"].notna()
    metadata = get_variable_metadata(variable_key)
    return {
        "variable": variable_key,
        "display_name_cn": metadata.get("display_name_cn", variable_key),
        "unit": metadata.get("unit", hourly_df.attrs.get("unit")),
        "start_time": hourly_df.loc[valid, "datetime"].min() if valid.any() else pd.NaT,
        "end_time": hourly_df.loc[valid, "datetime"].max() if valid.any() else pd.NaT,
        "raw_count": qc_summary.get("raw_record_count"),
        "count": metrics_result.get("count"),
        "valid_count": int(valid.sum()),
        "missing_count": metrics_result.get("missing_count"),
        "missing_count_after_qc": qc_summary.get("post_qc_missing_count"),
        "mean": metrics_result.get("mean"),
        "max": metrics_result.get("max"),
        "min": metrics_result.get("min"),
        "median": metrics_result.get("median"),
        "std": metrics_result.get("std"),
    }


def build_basic_statistics_table(rows):
    """Build the basic_statistics sheet."""
    columns = [
        "variable",
        "display_name_cn",
        "unit",
        "start_time",
        "end_time",
        "raw_count",
        "count",
        "valid_count",
        "missing_count",
        "missing_count_after_qc",
        "mean",
        "max",
        "min",
        "median",
        "std",
    ]
    return _round_numeric(pd.DataFrame(rows, columns=columns))


def build_temperature_monthly_table(metrics_result):
    """Build the temperature_monthly sheet sorted by year-month."""
    table = metrics_result["monthly"][["year_month", "monthly_mean", "monthly_std"]].copy()
    table["_sort_key"] = pd.PeriodIndex(table["year_month"], freq="M").to_timestamp()
    table = table.sort_values("_sort_key").drop(columns="_sort_key").reset_index(drop=True)
    return _round_numeric(table)


def build_depth_daily_range_table(metrics_result):
    """Build the depth_daily_range sheet sorted by date."""
    table = metrics_result["daily_range"][["date", "daily_range"]].copy()
    table["date"] = pd.to_datetime(table["date"])
    table = table.sort_values("date").reset_index(drop=True)
    table["date"] = table["date"].dt.date
    return _round_numeric(table)


def build_metric_detail_tables(metrics_by_variable):
    """Build dynamic detail tables for metrics that produce tabular outputs."""
    tables = {}
    for variable_key, metrics_result in metrics_by_variable.items():
        if metrics_result.get("monthly") is not None:
            monthly = metrics_result["monthly"]
            tables[f"{variable_key}_monthly_statistics"] = _round_numeric(monthly.copy())
        if metrics_result.get("daily_range") is not None:
            daily_range = metrics_result["daily_range"]
            table = daily_range.copy()
            if "date" in table.columns:
                table["date"] = pd.to_datetime(table["date"]).dt.date
            tables[f"{variable_key}_daily_range_statistics"] = _round_numeric(table)
    return tables


def build_summary_workbook_sheets(
    basic_rows,
    qc_summaries,
    metrics_by_variable,
    qc_log=None,
    processing_status=None,
):
    """Build workbook sheets from actual generated metrics instead of fixed variable sheets."""
    sheets = {
        "basic_statistics": build_basic_statistics_table(basic_rows),
        "qc_summary": build_qc_summary_table(qc_summaries),
    }
    sheets.update(build_metric_detail_tables(metrics_by_variable))
    if qc_log is not None:
        sheets["qc_log"] = build_qc_log_table(qc_log)
    if processing_status is not None:
        sheets["processing_status"] = processing_status.copy()
    return sheets


def build_qc_summary_table(qc_summaries):
    """Build the qc_summary sheet with export-facing field names."""
    rows = []
    for variable_key, summary in qc_summaries.items():
        metadata = get_variable_metadata(variable_key)
        rows.append(
            {
                "variable": variable_key,
                "display_name_cn": metadata.get("display_name_cn", variable_key),
                "raw_count": summary.get("raw_count", summary.get("raw_record_count")),
                "missing_before_qc": summary.get("missing_before_qc", summary.get("raw_missing_count")),
                "removed_by_sensor_zero": summary.get("removed_by_sensor_zero", 0),
                "removed_by_intraday_2std": summary.get("daily_2std_removed_count", 0),
                "removed_by_valid_range": summary.get("removed_by_range", summary.get("range_removed_count")),
                "flagged_by_hampel": summary.get("flagged_by_hampel", 0),
                "flagged_by_rate_change": summary.get("flagged_by_rate_change", 0),
                "flagged_by_constant_value": summary.get("flagged_by_constant_value", 0),
                "applied_flagged_count": summary.get("applied_flagged_count", 0),
                "missing_after_qc": summary.get("missing_after_qc", summary.get("post_qc_missing_count")),
            }
        )
    return pd.DataFrame(rows)


def build_qc_log_table(qc_log):
    """Build a normalized QC log export table."""
    columns = [
        "record_id",
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
        "decision_source",
    ]
    if qc_log is None or qc_log.empty:
        return pd.DataFrame(columns=columns)
    source = qc_log.copy()
    for column in columns:
        if column not in source.columns:
            source[column] = pd.NA
    table = source[columns].copy()
    table["datetime"] = pd.to_datetime(table["datetime"], errors="coerce")
    return table.sort_values(["variable", "datetime", "rule"]).reset_index(drop=True)


def export_qc_log(qc_log, output_path):
    """Export QC log to an Excel workbook."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path) as writer:
        build_qc_log_table(qc_log).to_excel(writer, sheet_name="qc_log", index=False)


def export_summary_statistics(
    output_path,
    basic_statistics,
    temperature_monthly,
    depth_daily_range,
    qc_summary,
    qc_log=None,
):
    """Export all V1 summary statistics tables to one Excel workbook."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path) as writer:
        basic_statistics.to_excel(writer, sheet_name="basic_statistics", index=False)
        temperature_monthly.to_excel(writer, sheet_name="temperature_monthly", index=False)
        depth_daily_range.to_excel(writer, sheet_name="depth_daily_range", index=False)
        qc_summary.to_excel(writer, sheet_name="qc_summary", index=False)
        if qc_log is not None:
            build_qc_log_table(qc_log).to_excel(writer, sheet_name="qc_log", index=False)


def export_dynamic_summary_statistics(output_path, sheets):
    """Export dynamically generated summary workbook sheets."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path) as writer:
        for sheet_name, table in sheets.items():
            safe_name = sheet_name[:31]
            table.to_excel(writer, sheet_name=safe_name, index=False)
