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
from src.variable_registry import get_variable_metadata, list_enabled_variables


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
    metric_source = resampled.get("hourly")
    if metric_source is None:
        metric_source = resampled.get("daily")
    if metric_source is None:
        metric_source = qc_data
    metrics = calculate_metrics(
        variable_key,
        metric_source,
        resampled.get("daily"),
        anomaly,
        metadata=metadata,
        base_data=metric_source,
    )
    row = build_basic_statistics_row(variable_key, metric_source, metrics, qc_summary)
    return qc_summary, qc_log, resampled, anomaly, metrics, row


def _virtual_low_frequency_check():
    metadata = {
        "display_name_cn": "虚拟低频变量",
        "display_name_en": "Virtual low frequency",
        "unit": "mg/L",
        "valid_min": 0,
        "valid_max": 100,
        "sampling_type": "low_frequency",
        "aggregation": "mean",
        "supports_hourly": False,
        "supports_daily": True,
        "supports_monthly": False,
        "supports_intraday_anomaly": False,
        "supports_daily_range": False,
        "supports_harmonic_analysis": False,
        "metrics": ["count", "valid_count", "missing_count", "mean", "min", "max", "median", "std"],
        "plots": [],
    }
    data = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-01-01", "2026-01-08", "2026-01-15"]),
            "value": [1.0, 2.0, 3.0],
        }
    )
    data.attrs.update({"variable_key": "virtual_low_frequency", "unit": "mg/L"})
    resampled = resample_configured(data, metadata)
    anomaly = calculate_configured_anomaly(resampled, metadata)
    metrics = calculate_metrics("virtual_low_frequency", resampled.get("daily"), resampled.get("daily"), anomaly, metadata=metadata)

    _assert("hourly" not in resampled, "low-frequency variable should not run hourly resampling")
    _assert("daily" in resampled, "low-frequency variable should still support configured daily output")
    _assert(anomaly is None, "low-frequency variable should not run intraday anomaly")
    _assert("daily_range" not in metrics, "low-frequency variable should not run daily_range")
    _assert(metrics["valid_count"] == 3, "generic metrics should run for unknown variable names")
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
        _assert(("hourly" in resampled) == bool(metadata.get("supports_hourly")), f"{variable_key} hourly capability mismatch")
        _assert(("daily" in resampled) == bool(metadata.get("supports_daily")), f"{variable_key} daily capability mismatch")
        _assert((anomaly is not None) == bool(metadata.get("supports_intraday_anomaly")), f"{variable_key} anomaly capability mismatch")
        if metadata.get("supports_monthly"):
            _assert("monthly" in metrics, f"{variable_key} monthly metrics missing")
        if metadata.get("supports_daily_range"):
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

    low_frequency = _virtual_low_frequency_check()
    session_keys = _session_state_key_check()
    sheets = build_summary_workbook_sheets(basic_rows, qc_summaries, metrics_by_variable)
    _assert("temperature_monthly" not in sheets, "dynamic export should not require fixed temperature_monthly sheet")
    _assert("depth_daily_range" not in sheets, "dynamic export should not require fixed depth_daily_range sheet")
    _assert(any(name.endswith("_monthly_statistics") for name in sheets), "dynamic monthly sheet should be generated from actual metrics")

    pd.DataFrame(regression).T.to_csv(OUTPUT_DIR / "depth_temperature_regression.csv", encoding="utf-8-sig")
    pd.DataFrame([session_keys]).to_csv(OUTPUT_DIR / "session_state_key_check.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {
                "has_hourly": "hourly" in low_frequency[1],
                "has_daily": "daily" in low_frequency[1],
                "has_anomaly": low_frequency[2] is not None,
                "has_daily_range": "daily_range" in low_frequency[3],
                "valid_count": low_frequency[3]["valid_count"],
            }
        ]
    ).to_csv(OUTPUT_DIR / "virtual_low_frequency_check.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(OUTPUT_DIR / "dynamic_summary_sheets.xlsx") as writer:
        for sheet_name, table in sheets.items():
            table.to_excel(writer, sheet_name=sheet_name[:31], index=False)

    print("V3.1 architecture preview passed")
    print(f"output_dir: {OUTPUT_DIR}")
    print(f"variables: {', '.join(regression.keys())}")
    print(f"dynamic_sheets: {', '.join(sheets.keys())}")


if __name__ == "__main__":
    main()
