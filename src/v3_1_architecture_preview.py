"""Preview checks for V3.1 registry-driven variable architecture."""

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.anomaly import calculate_configured_anomaly
from src.loaders import load_variables
from src.metrics import calculate_metrics
from src.output_paths import ensure_stage_dirs
from src.qc import apply_quality_control
from src.report_tables import build_basic_statistics_row, build_summary_workbook_sheets
from src.resampling import resample_configured
from src.variable_registry import STANDARD_METRICS, VARIABLE_REGISTRY, get_variable_metadata, list_enabled_variables


OUTPUT_DIR = PROJECT_ROOT / "outputs" / "v3_1_architecture"


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _run_variable(variable_key, raw):
    metadata = get_variable_metadata(variable_key)
    qc_data, qc_summary, qc_log = apply_quality_control(
        raw,
        metadata,
        enable_valid_range=True,
        enable_hampel=True,
        enable_constant_value=True,
    )
    resampled = resample_configured(qc_data, metadata)
    anomaly = calculate_configured_anomaly(resampled, metadata)
    metric_source = resampled["hourly"]
    metrics = calculate_metrics(
        variable_key,
        metric_source,
        resampled["daily"],
        anomaly,
        metadata=metadata,
        base_data=metric_source,
    )
    row = build_basic_statistics_row(variable_key, metric_source, metrics, qc_summary)
    return qc_summary, qc_log, resampled, anomaly, metrics, row


def _virtual_variable_check():
    variable_key = "virtual_variable"
    metadata = {
        "display_name_cn": "虚拟变量",
        "display_name_en": "Virtual variable",
        "unit": "mg/L",
        "valid_min": 0,
        "valid_max": 100,
        "sampling_type": "high_frequency",
        "aggregation": "mean",
        "supports_hourly": True,
        "supports_daily": True,
        "supports_monthly": True,
        "supports_intraday_anomaly": True,
        "supports_daily_range": True,
        "supports_harmonic_analysis": False,
        "metrics": STANDARD_METRICS.copy(),
        "plots": ["raw_hourly_with_daily_mean", "anomaly_series", "monthly_statistics", "daily_range"],
    }
    data = pd.DataFrame(
        {
            "datetime": pd.date_range("2026-01-01", periods=24, freq="30min"),
            "value": [float((idx % 8) + 1) for idx in range(24)],
        }
    )
    data.attrs.update({"variable_key": variable_key, "unit": "mg/L"})
    VARIABLE_REGISTRY[variable_key] = metadata
    try:
        registry_metadata = get_variable_metadata(variable_key)
        resampled = resample_configured(data, registry_metadata)
        anomaly = calculate_configured_anomaly(resampled, registry_metadata)
        metrics = calculate_metrics(variable_key, resampled["hourly"], resampled["daily"], anomaly, metadata=registry_metadata)
    finally:
        VARIABLE_REGISTRY.pop(variable_key, None)

    _assert("hourly" in resampled, "new configured variable should run hourly resampling")
    _assert("daily" in resampled, "new configured variable should run daily resampling")
    _assert(anomaly is not None, "new configured variable should run intraday anomaly")
    _assert("monthly" in metrics, "new configured variable should run monthly metrics")
    _assert("daily_range" in metrics, "new configured variable should run daily_range")
    _assert(metrics["valid_count"] == len(resampled["hourly"]), "generic metrics should run for configured variable names")
    return metadata, resampled, anomaly, metrics


def _session_state_key_check():
    depth_key = f"depth:review_table"
    temperature_key = f"temperature:review_table"
    _assert(depth_key != temperature_key, "session_state keys must be isolated by variable_key")
    return {"depth_key": depth_key, "temperature_key": temperature_key}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data_dir = PROJECT_ROOT / "data_private"
    loaded = load_variables(data_dir, list_enabled_variables())

    basic_rows = []
    qc_summaries = {}
    metrics_by_variable = {}
    regression = {}

    for variable_key in ("depth", "temperature"):
        raw = loaded[variable_key]
        qc_summary, qc_log, resampled, anomaly, metrics, row = _run_variable(variable_key, raw)
        metadata = get_variable_metadata(variable_key)
        _assert("hourly" in resampled, f"{variable_key} hourly output missing")
        _assert("daily" in resampled, f"{variable_key} daily output missing")
        _assert(anomaly is not None, f"{variable_key} anomaly output missing")
        _assert("monthly" in metrics, f"{variable_key} monthly metrics missing")
        _assert("daily_range" in metrics, f"{variable_key} daily_range missing")

        basic_rows.append(row)
        qc_summaries[variable_key] = qc_summary
        metrics_by_variable[variable_key] = metrics
        regression[variable_key] = {
            "raw_count": qc_summary["raw_count"],
            "valid_count": row["valid_count"],
            "has_hourly": "hourly" in resampled,
            "has_daily": "daily" in resampled,
            "has_anomaly": anomaly is not None,
            "metric_keys": sorted(metrics.keys()),
        }

    virtual_variable = _virtual_variable_check()
    session_keys = _session_state_key_check()
    metrics_by_variable["virtual_variable"] = virtual_variable[3]
    sheets = build_summary_workbook_sheets(basic_rows, qc_summaries, metrics_by_variable)
    _assert("temperature_monthly" not in sheets, "dynamic export should not require fixed temperature_monthly sheet")
    _assert("depth_daily_range" not in sheets, "dynamic export should not require fixed depth_daily_range sheet")
    _assert(any(name.endswith("_monthly_statistics") for name in sheets), "dynamic monthly sheet should be generated from actual metrics")
    _assert("virtual_variable_monthly_statistics" in sheets, "dynamic export should include virtual variable monthly sheet")
    _assert("virtual_variable_daily_range_statistics" in sheets, "dynamic export should include virtual variable daily_range sheet")

    pd.DataFrame(regression).T.to_csv(OUTPUT_DIR / "depth_temperature_regression.csv", encoding="utf-8-sig")
    pd.DataFrame([session_keys]).to_csv(OUTPUT_DIR / "session_state_key_check.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {
                "has_hourly": "hourly" in virtual_variable[1],
                "has_daily": "daily" in virtual_variable[1],
                "has_anomaly": virtual_variable[2] is not None,
                "has_monthly": "monthly" in virtual_variable[3],
                "has_daily_range": "daily_range" in virtual_variable[3],
                "valid_count": virtual_variable[3]["valid_count"],
            }
        ]
    ).to_csv(OUTPUT_DIR / "virtual_variable_check.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(OUTPUT_DIR / "dynamic_summary_sheets.xlsx") as writer:
        for sheet_name, table in sheets.items():
            table.to_excel(writer, sheet_name=sheet_name[:31], index=False)

    print("V3.1 architecture preview passed")
    print(f"output_dir: {OUTPUT_DIR}")
    print(f"variables: {', '.join(regression.keys())}")
    print(f"dynamic_sheets: {', '.join(sheets.keys())}")


if __name__ == "__main__":
    main()
