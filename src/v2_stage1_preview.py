"""Lightweight checks for V2 stage 1 registry and QC structure."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.anomaly import calculate_intraday_anomaly
from src.loaders import load_depth_and_temperature
from src.metrics import calculate_metrics
from src.qc import QC_LOG_COLUMNS, QC_SUMMARY_FIELDS, apply_quality_control
from src.resampling import resample_daily_mean, resample_hourly_mean
from src.variable_registry import get_variable_metadata, list_v1_variables


def _assert_fields(name, actual, expected):
    missing = [field for field in expected if field not in actual]
    if missing:
        raise AssertionError(f"{name} missing fields: {missing}")


def run_preview(data_dir=PROJECT_ROOT / "data_private"):
    loaded = load_depth_and_temperature(data_dir)

    for variable_key in list_v1_variables():
        metadata = get_variable_metadata(variable_key)
        for field in [
            "display_name_cn",
            "display_name_en",
            "unit",
            "valid_min",
            "valid_max",
            "y_axis_range",
            "qc_profile",
            "hampel_window",
            "hampel_sigma",
            "rate_change_limit",
            "constant_value_window",
            "metrics",
            "plots",
            "has_monthly_statistics",
            "has_daily_range",
            "special_handling",
        ]:
            if field not in metadata:
                raise AssertionError(f"{variable_key} registry missing {field}")

        raw = loaded[variable_key]
        qc_data, qc_summary, qc_log = apply_quality_control(raw, metadata)
        _assert_fields(f"{variable_key} qc_summary", qc_summary, QC_SUMMARY_FIELDS)
        _assert_fields(f"{variable_key} qc_log", qc_log.columns, QC_LOG_COLUMNS)

        if qc_summary["removed_by_range"] < 0:
            raise AssertionError("removed_by_range must be non-negative")
        if qc_summary["applied_flagged_count"] != qc_summary["removed_by_range"]:
            raise AssertionError("legacy_2std should be disabled by default")

        hourly = resample_hourly_mean(qc_data)
        daily = resample_daily_mean(qc_data)
        anomaly = calculate_intraday_anomaly(hourly, daily)
        calculate_metrics(variable_key, hourly, daily, anomaly)

    print("V2 stage 1 preview checks passed")


if __name__ == "__main__":
    run_preview()
