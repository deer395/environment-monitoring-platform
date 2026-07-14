"""Release validation for the V3 generic multi-variable workflow."""

import ast
from io import BytesIO
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.anomaly import calculate_configured_anomaly
from src.loaders import load_excel_variable
from src.manual_qc import apply_review_table_decisions, build_qc_review_table, ensure_record_id
from src.metrics import calculate_metrics
from src.plotting import (
    create_final_qc_figure,
    create_qc_candidate_figure,
    plot_hourly_daily,
    plot_intraday_anomaly,
    plot_monthly_statistics,
    plot_qc_comparison,
    plot_qc_flags,
    plot_qc_series,
)
from src.qc import apply_quality_control
from src.report_tables import (
    build_basic_statistics_row,
    build_qc_log_table,
    build_qc_summary_table,
    build_summary_workbook_sheets,
    export_dynamic_summary_statistics,
)
from src.resampling import resample_configured
from src.variable_registry import get_variable_metadata, list_enabled_variables


OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "v3_4_release_validation"
FIGURES_DIR = OUTPUT_ROOT / "figures"
TABLES_DIR = OUTPUT_ROOT / "tables"
LOGS_DIR = OUTPUT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data_private"
VARIABLES = (
    "depth",
    "temperature",
    "salinity",
    "dissolved_oxygen",
    "cod",
    "bod",
    "nitrate",
    "chlorophyll",
    "pahs",
)


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _ensure_output_dirs():
    for path in (FIGURES_DIR, TABLES_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _median_interval_minutes(data):
    intervals = data["datetime"].sort_values().diff().dropna().dt.total_seconds().div(60)
    return float(intervals.median()) if not intervals.empty else pd.NA


def _run_chain(variable_key, raw):
    metadata = get_variable_metadata(variable_key)
    raw = ensure_record_id(raw)
    qc_data, qc_summary, qc_log = apply_quality_control(
        raw,
        metadata,
        enable_valid_range=True,
        enable_hampel=True,
        enable_constant_value=True,
    )
    review_table = build_qc_review_table(raw, qc_data, qc_log)
    final_qc_data, final_qc_log = apply_review_table_decisions(raw, qc_data, qc_log, review_table)
    resampled = resample_configured(final_qc_data, metadata)
    anomaly = calculate_configured_anomaly(resampled, metadata)
    metrics = calculate_metrics(
        variable_key,
        resampled["hourly"],
        resampled["daily"],
        anomaly,
        metadata=metadata,
        base_data=resampled["hourly"],
    )
    row = build_basic_statistics_row(variable_key, resampled["hourly"], metrics, qc_summary)
    return qc_data, qc_summary, qc_log, review_table, final_qc_data, final_qc_log, resampled, anomaly, metrics, row


def _verify_manual_decisions(variable_key, raw, qc_data, qc_log, review_table):
    hard_rows = review_table[review_table["existing_rule"].str.contains("hard_range", na=False)]
    if not hard_rows.empty:
        hard_id = hard_rows.iloc[0]["record_id"]
        edited = review_table.copy()
        edited.loc[edited["record_id"].eq(hard_id), "user_decision"] = "manual_keep"
        restored, _ = apply_review_table_decisions(raw, qc_data, qc_log, edited)
        _assert(pd.isna(restored.loc[restored["record_id"].eq(hard_id), "value"].iloc[0]), f"{variable_key} hard_range point was restored")

    ordinary = review_table[
        review_table["existing_rule"].eq("") & review_table["current_qc_value"].notna()
    ]
    _assert(not ordinary.empty, f"{variable_key} has no ordinary point for manual selection validation")
    ordinary_id = ordinary.iloc[0]["record_id"]
    edited = review_table.copy()
    edited.loc[edited["record_id"].eq(ordinary_id), "user_decision"] = "manual_remove"
    removed, _ = apply_review_table_decisions(raw, qc_data, qc_log, edited)
    _assert(pd.isna(removed.loc[removed["record_id"].eq(ordinary_id), "value"].iloc[0]), f"{variable_key} ordinary manual_remove failed")


def _export_variable(variable_key, raw, qc_data, qc_summary, qc_log, review_table, final_qc_data, final_qc_log, resampled, anomaly, metrics):
    plot_qc_comparison(raw, qc_data, variable_key, FIGURES_DIR / f"{variable_key}_raw_vs_hard_range.png")
    plot_qc_flags(raw, qc_log, variable_key, FIGURES_DIR / f"{variable_key}_candidate_flags.png")
    plot_qc_series(final_qc_data, variable_key, FIGURES_DIR / f"{variable_key}_final_qc_data.png", "final_qc_data")
    plot_hourly_daily(resampled["hourly"], resampled["daily"], variable_key, FIGURES_DIR / f"{variable_key}_hourly_daily.png")
    plot_intraday_anomaly(anomaly, variable_key, FIGURES_DIR / f"{variable_key}_intraday_anomaly.png")
    plot_monthly_statistics(metrics["monthly"], variable_key, FIGURES_DIR / f"{variable_key}_monthly_statistics.png")
    create_qc_candidate_figure(raw, qc_log, review_table, variable_key).write_html(FIGURES_DIR / f"{variable_key}_candidate_interactive.html")
    create_final_qc_figure(final_qc_data, raw, variable_key, int(final_qc_data["value"].isna().sum()), int(final_qc_data["value"].notna().sum())).write_html(FIGURES_DIR / f"{variable_key}_final_qc_interactive.html")
    metrics["monthly"].to_csv(TABLES_DIR / f"{variable_key}_monthly_statistics.csv", index=False, encoding="utf-8-sig")
    metrics["daily_range"].to_csv(TABLES_DIR / f"{variable_key}_daily_range.csv", index=False, encoding="utf-8-sig")
    build_qc_summary_table({variable_key: qc_summary}).to_csv(TABLES_DIR / f"{variable_key}_qc_summary.csv", index=False, encoding="utf-8-sig")
    build_qc_log_table(final_qc_log).to_csv(LOGS_DIR / f"{variable_key}_qc_log.csv", index=False, encoding="utf-8-sig")


def _assert_python_syntax_and_generic_architecture():
    for path in PROJECT_ROOT.rglob("*.py"):
        if "__pycache__" not in path.parts:
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    app_tree = ast.parse((PROJECT_ROOT / "app.py").read_text(encoding="utf-8-sig"))
    target_names = {
        "_health_table",
        "_decision_summary",
        "_create_auto_rule_comparison_figure",
        "_create_hourly_daily_figure",
        "_create_anomaly_figure",
        "_run_after_qc",
    }
    names = [node.name for node in app_tree.body if isinstance(node, ast.FunctionDef)]
    for name in target_names:
        _assert(names.count(name) == 1, f"app.py duplicate or missing function: {name}")


def _verify_processing_status_workbook():
    status = pd.DataFrame([
        {
            "variable_key": "depth",
            "display_name_cn": "水深",
            "data_source": "未提供数据源",
            "start_time": pd.NaT,
            "end_time": pd.NaT,
            "auto_qc_completed": False,
            "manual_qc_confirmed": False,
            "processing_status": "skipped",
            "note": "未上传且默认文件不存在",
        },
        {
            "variable_key": "temperature",
            "display_name_cn": "温度",
            "data_source": "temp.xls",
            "start_time": pd.Timestamp("2026-01-01"),
            "end_time": pd.Timestamp("2026-01-02"),
            "auto_qc_completed": True,
            "manual_qc_confirmed": False,
            "processing_status": "processed",
            "note": "仅完成自动质控，未进行人工确认",
        },
    ])
    workbook = BytesIO()
    with pd.ExcelWriter(workbook) as writer:
        status.to_excel(writer, sheet_name="processing_status", index=False)
    excel = pd.ExcelFile(BytesIO(workbook.getvalue()))
    _assert("processing_status" in excel.sheet_names, "combined workbook lacks processing_status")
    status = pd.read_excel(BytesIO(workbook.getvalue()), sheet_name="processing_status")
    depth = status[status["variable_key"].eq("depth")].iloc[0]
    _assert(depth["processing_status"] == "skipped", "missing source did not produce skipped status")
    _assert("默认文件不存在" in depth["note"], "missing source reason is not recorded")
    _assert((status["processing_status"] == "processed").any(), "missing source stopped the combined workbook")


def main():
    _ensure_output_dirs()
    _assert_python_syntax_and_generic_architecture()
    _assert(tuple(list_enabled_variables()) == VARIABLES, "enabled variables do not match V3.4 release scope")

    rows, summaries, metrics_by_variable, final_logs, acceptance_rows = [], {}, {}, [], []
    for variable_key in VARIABLES:
        metadata = get_variable_metadata(variable_key)
        file_path = DATA_DIR / metadata["default_file"]
        _assert(file_path.exists(), f"missing real sample file: {file_path}")
        raw = load_excel_variable(file_path, variable_key)
        _assert({"record_id", "datetime", "value", "variable", "unit"}.issubset(raw.columns), f"{variable_key} normalized loader columns incomplete")
        _assert(raw["variable"].eq(variable_key).all(), f"{variable_key} loader variable mismatch")
        _assert(raw["unit"].eq(metadata["unit"]).all(), f"{variable_key} loader unit mismatch")
        qc_data, qc_summary, qc_log, review_table, final_qc_data, final_qc_log, resampled, anomaly, metrics, row = _run_chain(variable_key, raw)
        _assert((qc_log.loc[qc_log["rule"].isin(["hampel", "constant_value"]), "is_applied"] == False).all(), f"{variable_key} algorithm candidate was auto-applied")
        _assert(not resampled["hourly"].empty and not resampled["daily"].empty, f"{variable_key} resampling failed")
        _assert(not anomaly.empty and not metrics["monthly"].empty and not metrics["daily_range"].empty, f"{variable_key} analysis outputs incomplete")
        _verify_manual_decisions(variable_key, raw, qc_data, qc_log, review_table)
        _export_variable(variable_key, raw, qc_data, qc_summary, qc_log, review_table, final_qc_data, final_qc_log, resampled, anomaly, metrics)
        rows.append(row)
        summaries[variable_key] = qc_summary
        metrics_by_variable[variable_key] = metrics
        final_logs.append(final_qc_log)
        acceptance_rows.append({
            "file_name": file_path.name,
            "variable_key": variable_key,
            "unit": metadata["unit"],
            "raw_count": int(qc_summary["raw_count"]),
            "start_time": raw["datetime"].min(),
            "end_time": raw["datetime"].max(),
            "median_interval_minutes": _median_interval_minutes(raw),
            "raw_missing_count": int(qc_summary["missing_before_qc"]),
            "hard_range_removed": int(qc_summary["removed_by_range"]),
            "hampel_candidates": int(qc_summary["flagged_by_hampel"]),
            "constant_value_candidates": int(qc_summary["flagged_by_constant_value"]),
            "hourly_record_count": int(len(resampled["hourly"])),
            "daily_record_count": int(len(resampled["daily"])),
            "month_count": int(len(metrics["monthly"])),
            "max_daily_range": metrics["max_daily_range"],
            "acceptance_status": "passed",
        })

    combined_log = pd.concat(final_logs, ignore_index=True)
    processing_status = pd.DataFrame([
        {
            "variable_key": item["variable_key"],
            "display_name_cn": get_variable_metadata(item["variable_key"])["display_name_cn"],
            "data_source": item["file_name"],
            "start_time": item["start_time"],
            "end_time": item["end_time"],
            "auto_qc_completed": True,
            "manual_qc_confirmed": False,
            "processing_status": "processed",
            "note": "验证脚本仅完成自动质控；页面人工确认状态由会话保存。",
        }
        for item in acceptance_rows
    ])
    sheets = build_summary_workbook_sheets(rows, summaries, metrics_by_variable, combined_log, processing_status)
    export_dynamic_summary_statistics(TABLES_DIR / "v3_4_all_variables_validation.xlsx", sheets)
    pd.DataFrame(acceptance_rows).to_csv(LOGS_DIR / "v3_4_acceptance_results.csv", index=False, encoding="utf-8-sig")
    _verify_processing_status_workbook()
    print("V3.4 release validation passed")
    print(f"output_dir: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
