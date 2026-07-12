"""Preview checks for V3.2 new variable onboarding."""

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


OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "v3_2_new_variables"
FIGURES_DIR = OUTPUT_ROOT / "figures"
TABLES_DIR = OUTPUT_ROOT / "tables"
LOGS_DIR = OUTPUT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data_private"
NEW_VARIABLES = ("salinity", "dissolved_oxygen", "cod")
REGRESSION_VARIABLES = ("depth", "temperature")


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _ensure_output_dirs():
    for path in (OUTPUT_ROOT, FIGURES_DIR, TABLES_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _metadata_file(variable_key):
    metadata = get_variable_metadata(variable_key)
    return DATA_DIR / (metadata.get("default_file") or metadata.get("default_file_name"))


def _load_real_data(variable_key):
    path = _metadata_file(variable_key)
    if not path.exists():
        return None, "synthetic_missing_real_file", f"missing: {path}"
    return load_excel_variable(path, variable_key), "real_sample_file", str(path)


def _synthetic_values(variable_key, periods=96):
    baselines = {"salinity": 30.0, "dissolved_oxygen": 8.0, "cod": 3.0}
    spikes = {"salinity": 45.0, "dissolved_oxygen": 33.0, "cod": 28.0}
    base = baselines.get(variable_key, 10.0)
    values = [base + ((idx % 12) - 6) * 0.03 for idx in range(periods)]
    if periods > 8:
        values[8] = -1.0
    if periods > 44:
        values[44] = spikes.get(variable_key, base + 25.0)
    for idx in range(70, min(82, periods)):
        values[idx] = base - 1.0
    return values


def _make_synthetic_frame(variable_key):
    metadata = get_variable_metadata(variable_key)
    data = pd.DataFrame(
        {
            "datetime": pd.date_range("2026-06-01", periods=96, freq="30min"),
            "value": _synthetic_values(variable_key),
        }
    )
    data.insert(0, "record_id", [f"{variable_key}_synthetic_{idx}" for idx in range(len(data))])
    data["variable"] = variable_key
    data["unit"] = metadata["unit"]
    data.attrs.update(
        {
            "variable_key": variable_key,
            "display_name": metadata["display_name"],
            "unit": metadata["unit"],
            "source_file": "synthetic_in_memory",
        }
    )
    return data


def _write_and_load_alias_fixture(variable_key):
    metadata = get_variable_metadata(variable_key)
    value_alias = {
        "salinity": "盐度",
        "dissolved_oxygen": "DO",
        "cod": "COD",
    }[variable_key]
    fixture = pd.DataFrame(
        {
            "监测时间": pd.date_range("2026-07-01", periods=8, freq="30min"),
            value_alias: _synthetic_values(variable_key, periods=8),
        }
    )
    path = LOGS_DIR / f"{variable_key}_alias_fixture.xlsx"
    fixture.to_excel(path, index=False)
    loaded = load_excel_variable(path, variable_key)
    _assert({"datetime", "value", "variable", "unit", "record_id"}.issubset(loaded.columns), f"{variable_key} loader normalized columns missing")
    _assert(loaded["variable"].eq(variable_key).all(), f"{variable_key} loader variable column mismatch")
    _assert(loaded["unit"].eq(metadata["unit"]).all(), f"{variable_key} loader unit column mismatch")
    return str(path)


def _run_chain(variable_key, raw):
    metadata = get_variable_metadata(variable_key)
    raw = ensure_record_id(raw)
    raw.attrs.update({"variable_key": variable_key, "unit": metadata["unit"]})
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


def _verify_synthetic_qc(variable_key):
    raw = _make_synthetic_frame(variable_key)
    qc_data, qc_summary, qc_log, review_table, _, _, resampled, anomaly, metrics, _ = _run_chain(variable_key, raw)
    _assert(qc_summary["removed_by_range"] >= 1, f"{variable_key} negative values should be removed by physical_range")
    _assert(qc_summary["flagged_by_hampel"] >= 1, f"{variable_key} Hampel should flag synthetic spike")
    _assert(qc_summary["flagged_by_constant_value"] >= 1, f"{variable_key} constant_value should flag synthetic run")

    hampel_log = qc_log[qc_log["rule"].eq("hampel")]
    constant_log = qc_log[qc_log["rule"].eq("constant_value")]
    _assert(not bool(hampel_log["is_applied"].any()), f"{variable_key} Hampel must only mark")
    _assert(not bool(constant_log["is_applied"].any()), f"{variable_key} constant_value must only mark")

    candidate_id = str(hampel_log.iloc[0]["record_id"])
    auto_value = qc_data.loc[qc_data["record_id"].astype(str).eq(candidate_id), "value"].iloc[0]
    _assert(pd.notna(auto_value), f"{variable_key} Hampel candidate should remain before user remove")

    edited = review_table.copy()
    edited.loc[edited["record_id"].astype(str).eq(candidate_id), "user_decision"] = "remove"
    final_qc_data, final_qc_log = apply_review_table_decisions(raw, qc_data, qc_log, edited)
    removed_value = final_qc_data.loc[final_qc_data["record_id"].astype(str).eq(candidate_id), "value"].iloc[0]
    _assert(pd.isna(removed_value), f"{variable_key} user remove should delete candidate in final_qc_data")

    _assert(not metrics["monthly"].empty, f"{variable_key} monthly statistics missing")
    _assert(not metrics["daily_range"].empty, f"{variable_key} daily range missing")
    _assert("hourly" in resampled and "daily" in resampled, f"{variable_key} resampling outputs missing")
    _assert(anomaly is not None and not anomaly.empty, f"{variable_key} anomaly output missing")
    return {
        "synthetic_removed_by_range": qc_summary["removed_by_range"],
        "synthetic_flagged_by_hampel": qc_summary["flagged_by_hampel"],
        "synthetic_flagged_by_constant_value": qc_summary["flagged_by_constant_value"],
        "synthetic_user_remove_applied": bool(pd.isna(removed_value)),
        "synthetic_final_qc_log_rows": len(final_qc_log),
    }


def _export_variable_outputs(variable_key, raw, qc_data, qc_summary, qc_log, review_table, final_qc_data, final_qc_log, resampled, anomaly, metrics):
    plot_qc_comparison(raw, qc_data, variable_key, FIGURES_DIR / f"{variable_key}_raw_vs_auto_qc.png")
    plot_qc_flags(raw, qc_log, variable_key, FIGURES_DIR / f"{variable_key}_candidate_flags.png")
    plot_qc_series(final_qc_data, variable_key, FIGURES_DIR / f"{variable_key}_final_qc_data.png", "final_qc_data", raw_df=raw)
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


def _check_no_new_variable_branches():
    app_text = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
    metrics_text = (PROJECT_ROOT / "src" / "metrics.py").read_text(encoding="utf-8")
    forbidden = ("salinity", "dissolved_oxygen", "cod")
    branch_tokens = ("if variable_key ==", "elif variable_key ==", "if variable ==", "elif variable ==")
    for text, name in ((app_text, "app.py"), (metrics_text, "metrics.py")):
        for token in branch_tokens:
            for variable_key in forbidden:
                _assert(f'{token} "{variable_key}"' not in text, f"{name} contains variable branch for {variable_key}")
                _assert(f"{token} '{variable_key}'" not in text, f"{name} contains variable branch for {variable_key}")


def _run_variable_preview(variable_key):
    metadata = get_variable_metadata(variable_key)
    target_hard_max = {"salinity": 50, "dissolved_oxygen": 100, "cod": 100}
    _assert(metadata["variable_key"] == variable_key, f"{variable_key} variable_key missing")
    _assert(metadata["hard_min"] == 0, f"{variable_key} hard_min must be 0")
    _assert(metadata["hard_max"] == target_hard_max[variable_key], f"{variable_key} hard_max mismatch")
    _assert(metadata["valid_min"] == metadata["hard_min"], f"{variable_key} valid_min should mirror hard_min")
    _assert(metadata["valid_max"] == metadata["hard_max"], f"{variable_key} valid_max should mirror hard_max")
    _assert(metadata.get("supports_harmonic_analysis") is False, f"{variable_key} harmonic analysis should be disabled")
    _assert(variable_key in list_enabled_variables(), f"{variable_key} should appear in enabled variable list")

    alias_fixture = _write_and_load_alias_fixture(variable_key)
    raw, data_source, source_note = _load_real_data(variable_key)
    if raw is None:
        raw = _make_synthetic_frame(variable_key)

    required_columns = {"datetime", "value", "variable", "unit", "record_id"}
    _assert(required_columns.issubset(raw.columns), f"{variable_key} loaded data missing normalized columns")
    _assert(raw["variable"].eq(variable_key).all(), f"{variable_key} variable column mismatch")
    _assert(raw["unit"].eq(metadata["unit"]).all(), f"{variable_key} unit column mismatch")

    qc_data, qc_summary, qc_log, review_table, final_qc_data, final_qc_log, resampled, anomaly, metrics, row = _run_chain(variable_key, raw)
    _assert(not metrics["monthly"].empty, f"{variable_key} real/synthetic monthly statistics missing")
    _assert(not metrics["daily_range"].empty, f"{variable_key} real/synthetic daily range missing")
    _export_variable_outputs(variable_key, raw, qc_data, qc_summary, qc_log, review_table, final_qc_data, final_qc_log, resampled, anomaly, metrics)
    synthetic_checks = _verify_synthetic_qc(variable_key)
    return row, qc_summary, metrics, {
        "variable": variable_key,
        "display_name_cn": metadata["display_name_cn"],
        "unit": metadata["unit"],
        "default_file": metadata["default_file"],
        "valid_min": metadata["valid_min"],
        "valid_max": metadata["valid_max"],
        "valid_range_note": metadata.get("valid_range_note"),
        "data_source_for_full_chain": data_source,
        "source_note": source_note,
        "alias_fixture": alias_fixture,
        "raw_count": qc_summary["raw_count"],
        "final_valid_count": row["valid_count"],
        **synthetic_checks,
    }


def _run_regression(variable_key):
    raw, data_source, source_note = _load_real_data(variable_key)
    _assert(raw is not None, f"{variable_key} regression requires real sample file")
    _, qc_summary, _, _, _, _, resampled, anomaly, metrics, row = _run_chain(variable_key, raw)
    _assert("hourly" in resampled and not resampled["hourly"].empty, f"{variable_key} regression hourly missing")
    _assert("daily" in resampled and not resampled["daily"].empty, f"{variable_key} regression daily missing")
    _assert(anomaly is not None and not anomaly.empty, f"{variable_key} regression anomaly missing")
    _assert(not metrics["monthly"].empty, f"{variable_key} regression monthly missing")
    _assert(not metrics["daily_range"].empty, f"{variable_key} regression daily range missing")
    return row, qc_summary, metrics, {
        "variable": variable_key,
        "data_source_for_full_chain": data_source,
        "source_note": source_note,
        "raw_count": qc_summary["raw_count"],
        "final_valid_count": row["valid_count"],
        "has_hourly": True,
        "has_daily": True,
        "has_anomaly": True,
        "has_monthly": True,
        "has_daily_range": True,
    }


def main():
    _ensure_output_dirs()
    _check_no_new_variable_branches()

    rows = []
    qc_summaries = {}
    metrics_by_variable = {}
    test_records = []

    for variable_key in NEW_VARIABLES:
        row, qc_summary, metrics, record = _run_variable_preview(variable_key)
        rows.append(row)
        qc_summaries[variable_key] = qc_summary
        metrics_by_variable[variable_key] = metrics
        test_records.append(record)

    regression_records = []
    for variable_key in REGRESSION_VARIABLES:
        row, qc_summary, metrics, record = _run_regression(variable_key)
        rows.append(row)
        qc_summaries[variable_key] = qc_summary
        metrics_by_variable[variable_key] = metrics
        regression_records.append(record)

    sheets = build_summary_workbook_sheets(rows, qc_summaries, metrics_by_variable)
    export_dynamic_summary_statistics(TABLES_DIR / "v3_2_summary_statistics.xlsx", sheets)
    pd.DataFrame(test_records).to_csv(LOGS_DIR / "new_variable_test_sources.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(regression_records).to_csv(LOGS_DIR / "depth_temperature_regression.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        {
            "enabled_variables": list(list_enabled_variables()),
        }
    ).to_csv(LOGS_DIR / "enabled_variables.csv", index=False, encoding="utf-8-sig")

    print("V3.2 new variable preview passed")
    print(f"output_dir: {OUTPUT_ROOT}")
    print(f"new_variables: {', '.join(NEW_VARIABLES)}")
    print("real_sample_variables: " + ", ".join(record["variable"] for record in test_records if record["data_source_for_full_chain"] == "real_sample_file"))
    print("synthetic_qc_checks: " + ", ".join(NEW_VARIABLES))
    print(f"regression_variables: {', '.join(REGRESSION_VARIABLES)}")


if __name__ == "__main__":
    main()
