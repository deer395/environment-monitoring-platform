"""Preview checks for V3.3 remaining variable onboarding and full regression."""

from pathlib import Path
import re
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


OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "v3_3_remaining_variables"
FIGURES_DIR = OUTPUT_ROOT / "figures"
TABLES_DIR = OUTPUT_ROOT / "tables"
LOGS_DIR = OUTPUT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data_private"

NEW_VARIABLES = ("bod", "nitrate", "chlorophyll", "pahs")
REGRESSION_VARIABLES = ("depth", "temperature", "salinity", "dissolved_oxygen", "cod")
ALL_VARIABLES = REGRESSION_VARIABLES + NEW_VARIABLES
EXPECTED_HARD_RANGES = {
    "depth": (0, 100),
    "temperature": (-2.5, 50),
    "salinity": (0, 50),
    "dissolved_oxygen": (0, 100),
    "cod": (0, 100),
    "bod": (0, 100),
    "nitrate": (0, 100),
    "chlorophyll": (0, 100),
    "pahs": (0, 100),
}


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _ensure_output_dirs():
    for path in (OUTPUT_ROOT, FIGURES_DIR, TABLES_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _metadata_file(variable_key):
    metadata = get_variable_metadata(variable_key)
    return DATA_DIR / (metadata.get("default_file") or metadata.get("default_file_name"))


def _read_excel_structure(path):
    excel = pd.ExcelFile(path)
    frame = pd.read_excel(path, sheet_name=0)
    return excel.sheet_names, frame


def _load_real_data(variable_key):
    path = _metadata_file(variable_key)
    _assert(path.exists(), f"{variable_key} real sample file is missing: {path}")
    return load_excel_variable(path, variable_key), path


def _median_interval_minutes(data):
    intervals = data["datetime"].sort_values().diff().dropna().dt.total_seconds().div(60)
    return float(intervals.median()) if not intervals.empty else pd.NA


def _sample_structure(variable_key, raw, path):
    sheets, original = _read_excel_structure(path)
    return {
        "variable": variable_key,
        "file": path.name,
        "sheets": ",".join(sheets),
        "source_datetime_column": raw.attrs.get("source_datetime_column"),
        "source_value_column": raw.attrs.get("source_value_column"),
        "unit_column_in_file": "no",
        "registry_unit": get_variable_metadata(variable_key)["unit"],
        "time_format": str(raw["datetime"].dropna().iloc[0]) if raw["datetime"].notna().any() else "",
        "raw_columns": ",".join(str(column) for column in original.columns),
        "raw_rows_before_loader_drop": int(len(original)),
        "loaded_records": int(len(raw)),
        "start_time": raw["datetime"].min(),
        "end_time": raw["datetime"].max(),
        "median_interval_minutes": _median_interval_minutes(raw),
        "missing_datetime_after_loader": int(raw["datetime"].isna().sum()),
        "missing_value_after_loader": int(raw["value"].isna().sum()),
        "min_value": raw["value"].min(skipna=True),
        "max_value": raw["value"].max(skipna=True),
        "below_0_count": int((raw["value"] < 0).sum()),
        "above_100_count": int((raw["value"] > 100).sum()),
    }


def _make_synthetic_frame(variable_key):
    metadata = get_variable_metadata(variable_key)
    baseline = {
        "bod": 5.0,
        "nitrate": 1.2,
        "chlorophyll": 2.5,
        "pahs": 3.0,
        "depth": 20.0,
        "temperature": 18.0,
        "salinity": 30.0,
        "dissolved_oxygen": 8.0,
        "cod": 4.0,
    }.get(variable_key, 5.0)
    values = [baseline + ((idx % 9) - 4) * 0.03 for idx in range(96)]
    values[3] = -0.1
    values[4] = 0.0
    values[5] = 100.0
    values[6] = 100.1
    values[35] = baseline + 12.0
    for idx in range(70, 82):
        values[idx] = baseline - 0.5
    data = pd.DataFrame(
        {
            "record_id": [f"{variable_key}_synthetic_{idx}" for idx in range(len(values))],
            "datetime": pd.date_range("2026-06-01", periods=len(values), freq="30min"),
            "value": values,
        }
    )
    data["variable"] = variable_key
    data["unit"] = metadata["unit"]
    data.attrs.update({"variable_key": variable_key, "display_name": metadata["display_name"], "unit": metadata["unit"]})
    return data


def _run_chain(variable_key, raw):
    metadata = get_variable_metadata(variable_key)
    raw = ensure_record_id(raw)
    raw.attrs.update({"variable_key": variable_key, "unit": metadata["unit"], "display_name": metadata["display_name"]})
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


def _assert_algorithm_candidates_only_mark(variable_key, qc_log):
    for rule in ("hampel", "constant_value"):
        rows = qc_log[qc_log["rule"].eq(rule)] if qc_log is not None and not qc_log.empty else pd.DataFrame()
        if not rows.empty:
            _assert(not bool(rows["is_applied"].any()), f"{variable_key} {rule} should only flag")


def _verify_synthetic_qc(variable_key):
    raw = _make_synthetic_frame(variable_key)
    qc_data, qc_summary, qc_log, review_table, final_qc_data, _, resampled, anomaly, metrics, _ = _run_chain(variable_key, raw)
    values = qc_data.set_index("record_id")["value"]
    _assert(pd.isna(values[f"{variable_key}_synthetic_3"]), f"{variable_key} value < 0 should be hard_range removed")
    _assert(pd.isna(values[f"{variable_key}_synthetic_4"]), f"{variable_key} value == 0 should be sensor_zero removed")
    _assert(pd.notna(values[f"{variable_key}_synthetic_5"]), f"{variable_key} value == 100 should be retained")
    _assert(pd.isna(values[f"{variable_key}_synthetic_6"]), f"{variable_key} value > 100 should be hard_range removed")
    _assert(qc_summary["removed_by_range"] == 2, f"{variable_key} synthetic hard_range should remove only below and above")
    _assert(qc_summary["removed_by_sensor_zero"] == 1, f"{variable_key} synthetic zero should be removed once")
    _assert(qc_summary["flagged_by_hampel"] >= 1, f"{variable_key} synthetic Hampel candidate missing")
    _assert(qc_summary["flagged_by_constant_value"] >= 1, f"{variable_key} synthetic constant_value candidate missing")
    _assert_algorithm_candidates_only_mark(variable_key, qc_log)

    hard_ids = [f"{variable_key}_synthetic_3", f"{variable_key}_synthetic_4", f"{variable_key}_synthetic_6"]
    edited = review_table.copy()
    edited.loc[edited["record_id"].isin(hard_ids), "user_decision"] = "manual_keep"
    restored, _ = apply_review_table_decisions(raw, qc_data, qc_log, edited)
    restored_values = restored.set_index("record_id")["value"]
    _assert(restored_values[hard_ids].isna().all(), f"{variable_key} automatic removal should not recover")

    ordinary_id = review_table[
        review_table["existing_rule"].astype(str).eq("") & review_table["current_qc_value"].notna()
    ]["record_id"].iloc[0]
    edited = review_table.copy()
    edited.loc[edited["record_id"].eq(ordinary_id), "user_decision"] = "manual_remove"
    manual_removed, _ = apply_review_table_decisions(raw, qc_data, qc_log, edited)
    _assert(pd.isna(manual_removed.loc[manual_removed["record_id"].eq(ordinary_id), "value"].iloc[0]), f"{variable_key} ordinary point manual_remove failed")

    _assert("hourly" in resampled and not resampled["hourly"].empty, f"{variable_key} synthetic hourly missing")
    _assert(not metrics["monthly"].empty, f"{variable_key} synthetic monthly missing")
    _assert(not metrics["daily_range"].empty, f"{variable_key} synthetic daily range missing")
    _assert(anomaly is not None and not anomaly.empty, f"{variable_key} synthetic anomaly missing")
    return {
        "synthetic_hard_range_removed": int(qc_summary["removed_by_range"]),
        "synthetic_sensor_zero_removed": int(qc_summary["removed_by_sensor_zero"]),
        "synthetic_hampel_candidates": int(qc_summary["flagged_by_hampel"]),
        "synthetic_constant_value_candidates": int(qc_summary["flagged_by_constant_value"]),
        "ordinary_manual_remove_ok": True,
        "hard_range_nonrecoverable_ok": True,
    }


def _export_variable_outputs(variable_key, raw, qc_data, qc_summary, qc_log, review_table, final_qc_data, final_qc_log, resampled, anomaly, metrics):
    plot_qc_comparison(raw, qc_data, variable_key, FIGURES_DIR / f"{variable_key}_raw_vs_hard_range.png")
    plot_qc_flags(raw, qc_log, variable_key, FIGURES_DIR / f"{variable_key}_candidate_flags.png")
    plot_qc_series(final_qc_data, variable_key, FIGURES_DIR / f"{variable_key}_final_qc_data.png", "final_qc_data")
    plot_hourly_daily(resampled["hourly"], resampled["daily"], variable_key, FIGURES_DIR / f"{variable_key}_hourly_daily.png")
    plot_intraday_anomaly(anomaly, variable_key, FIGURES_DIR / f"{variable_key}_intraday_anomaly.png")
    plot_monthly_statistics(metrics["monthly"], variable_key, FIGURES_DIR / f"{variable_key}_monthly_statistics.png")
    create_qc_candidate_figure(raw, qc_log, review_table, variable_key).write_html(FIGURES_DIR / f"{variable_key}_candidate_interactive.html")
    create_final_qc_figure(
        final_qc_data,
        raw,
        variable_key,
        int(final_qc_data["value"].isna().sum()),
        int(final_qc_data["value"].notna().sum()),
    ).write_html(FIGURES_DIR / f"{variable_key}_final_qc_interactive.html")

    metrics["daily_range"].to_csv(TABLES_DIR / f"{variable_key}_daily_range.csv", index=False, encoding="utf-8-sig")
    metrics["monthly"].to_csv(TABLES_DIR / f"{variable_key}_monthly_statistics.csv", index=False, encoding="utf-8-sig")
    build_qc_summary_table({variable_key: qc_summary}).to_csv(TABLES_DIR / f"{variable_key}_qc_summary.csv", index=False, encoding="utf-8-sig")
    build_qc_log_table(final_qc_log).to_csv(LOGS_DIR / f"{variable_key}_qc_log.csv", index=False, encoding="utf-8-sig")


def _verify_chlorophyll_project_decision(raw, qc_data, qc_log, final_qc_data):
    high_raw = raw[raw["value"] > 100]
    high_logs = qc_log[(qc_log["rule"].eq("hard_range")) & (qc_log["original_value"] > 100)]
    _assert(len(high_raw) == 77, f"chlorophyll expected 77 values > 100, got {len(high_raw)}")
    _assert(len(high_logs) == 77, f"chlorophyll expected 77 high hard_range log rows, got {len(high_logs)}")
    _assert(int((raw["value"] < 0).sum()) >= 1, "chlorophyll negative sample values should exist")
    _assert(int(qc_data["value"].max(skipna=True)) <= 100, "chlorophyll qc_data should not retain values > 100")
    _assert(int(final_qc_data["value"].max(skipna=True)) <= 100, "chlorophyll final_qc_data should not retain values > 100")
    figure = create_final_qc_figure(final_qc_data, raw, "chlorophyll", int(final_qc_data["value"].isna().sum()), int(final_qc_data["value"].notna().sum()))
    axis_range = figure.layout.yaxis.range
    _assert(axis_range is not None and axis_range[1] < 200, "chlorophyll final_qc_data y axis should not be compressed by 1000+ raw values")


def _run_real_variable(variable_key, export_outputs=True):
    metadata = get_variable_metadata(variable_key)
    _assert(variable_key in list_enabled_variables(), f"{variable_key} should appear in enabled variables")
    expected_min, expected_max = EXPECTED_HARD_RANGES[variable_key]
    _assert(metadata["hard_min"] == expected_min, f"{variable_key} hard_min should be {expected_min}")
    _assert(metadata["hard_max"] == expected_max, f"{variable_key} hard_max should be {expected_max}")
    _assert(metadata["valid_min"] == expected_min and metadata["valid_max"] == expected_max, f"{variable_key} valid range should mirror hard range")
    _assert(metadata.get("supports_harmonic_analysis") is False, f"{variable_key} harmonic analysis should be disabled")

    raw, path = _load_real_data(variable_key)
    required_columns = {"record_id", "datetime", "value", "variable", "unit"}
    _assert(required_columns.issubset(raw.columns), f"{variable_key} loader normalized columns missing")
    _assert(raw["variable"].eq(variable_key).all(), f"{variable_key} variable column mismatch")
    _assert(raw["unit"].eq(metadata["unit"]).all(), f"{variable_key} unit column mismatch")
    structure = _sample_structure(variable_key, raw, path)

    qc_data, qc_summary, qc_log, review_table, final_qc_data, final_qc_log, resampled, anomaly, metrics, row = _run_chain(variable_key, raw)
    _assert_algorithm_candidates_only_mark(variable_key, qc_log)
    _assert("hourly" in resampled and not resampled["hourly"].empty, f"{variable_key} hourly output missing")
    _assert("daily" in resampled and not resampled["daily"].empty, f"{variable_key} daily output missing")
    _assert(anomaly is not None and not anomaly.empty, f"{variable_key} anomaly output missing")
    _assert(not metrics["monthly"].empty, f"{variable_key} monthly statistics missing")
    _assert(not metrics["daily_range"].empty, f"{variable_key} daily range missing")

    if variable_key == "chlorophyll":
        _verify_chlorophyll_project_decision(raw, qc_data, qc_log, final_qc_data)

    if export_outputs:
        _export_variable_outputs(variable_key, raw, qc_data, qc_summary, qc_log, review_table, final_qc_data, final_qc_log, resampled, anomaly, metrics)

    record = {
        "variable": variable_key,
        "data_source": "real_sample_file",
        "file": path.name,
        "raw_count": int(qc_summary["raw_count"]),
        "start_time": raw["datetime"].min(),
        "end_time": raw["datetime"].max(),
        "median_interval_minutes": _median_interval_minutes(raw),
        "hard_range_removed": int(qc_summary["removed_by_range"]),
        "hampel_candidates": int(qc_summary["flagged_by_hampel"]),
        "constant_value_candidates": int(qc_summary["flagged_by_constant_value"]),
        "final_valid_count": int(final_qc_data["value"].notna().sum()),
        "final_status": "passed",
    }
    return row, qc_summary, metrics, final_qc_log, structure, record


def _check_no_new_variable_branches():
    variables = ("bod", "nitrate", "chlorophyll", "pahs")
    files = ("app.py", "src/metrics.py", "src/loaders.py")
    branch_pattern = re.compile(r"\b(if|elif)\s+[^:\n]*(variable|variable_key)[^:\n]*==[^:\n]*(bod|nitrate|chlorophyll|pahs)")
    for relative in files:
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        match = branch_pattern.search(text)
        _assert(match is None, f"{relative} contains a variable-name branch for new V3.3 variables")
    for variable_key in variables:
        _assert(variable_key in list_enabled_variables(), f"{variable_key} missing from page variable list source")


def main():
    _ensure_output_dirs()
    _check_no_new_variable_branches()

    rows = []
    qc_summaries = {}
    metrics_by_variable = {}
    final_logs = []
    structures = []
    new_records = []
    synthetic_records = []
    regression_records = []

    for variable_key in NEW_VARIABLES:
        row, qc_summary, metrics, final_qc_log, structure, record = _run_real_variable(variable_key, export_outputs=True)
        rows.append(row)
        qc_summaries[variable_key] = qc_summary
        metrics_by_variable[variable_key] = metrics
        final_logs.append(final_qc_log)
        structures.append(structure)
        new_records.append(record)
        synthetic_records.append({"variable": variable_key, **_verify_synthetic_qc(variable_key)})

    for variable_key in REGRESSION_VARIABLES:
        row, qc_summary, metrics, final_qc_log, structure, record = _run_real_variable(variable_key, export_outputs=False)
        rows.append(row)
        qc_summaries[variable_key] = qc_summary
        metrics_by_variable[variable_key] = metrics
        final_logs.append(final_qc_log)
        structures.append(structure)
        regression_records.append(record)

    combined_log = pd.concat(final_logs, ignore_index=True) if final_logs else pd.DataFrame()
    sheets = build_summary_workbook_sheets(rows, qc_summaries, metrics_by_variable, qc_log=combined_log)
    export_dynamic_summary_statistics(TABLES_DIR / "v3_3_summary_statistics.xlsx", sheets)
    pd.DataFrame(structures).to_csv(LOGS_DIR / "sample_file_structure.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(new_records).to_csv(LOGS_DIR / "new_variable_real_sample_results.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(synthetic_records).to_csv(LOGS_DIR / "synthetic_qc_boundary_results.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(regression_records).to_csv(LOGS_DIR / "existing_variable_regression.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({"enabled_variables": list(list_enabled_variables())}).to_csv(LOGS_DIR / "enabled_variables.csv", index=False, encoding="utf-8-sig")

    print("V3.3 remaining variables preview passed")
    print(f"output_dir: {OUTPUT_ROOT}")
    print(f"new_variables_real_samples: {', '.join(NEW_VARIABLES)}")
    print(f"regression_variables: {', '.join(REGRESSION_VARIABLES)}")
    print(f"all_supported_variables: {', '.join(ALL_VARIABLES)}")


if __name__ == "__main__":
    main()
