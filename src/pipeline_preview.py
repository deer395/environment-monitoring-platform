"""Run the V1 minimal deterministic pipeline for depth and temperature."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.anomaly import calculate_intraday_anomaly
from src.loaders import load_depth_and_temperature
from src.metrics import calculate_metrics
from src.qc import apply_quality_control
from src.resampling import resample_daily_mean, resample_hourly_mean
from src.variable_registry import get_variable_metadata


def _print_metrics(metrics_result):
    for key, value in metrics_result.items():
        if hasattr(value, "head"):
            print(f"{key}:")
            print(value.head().to_string(index=False))
        else:
            print(f"{key}: {value}")


def run_preview(data_dir=PROJECT_ROOT / "data_private"):
    """Read Excel files and print QC, resampling, anomaly, and metrics outputs."""
    loaded = load_depth_and_temperature(data_dir)

    for variable_key, raw in loaded.items():
        metadata = get_variable_metadata(variable_key)
        qc_data, qc_summary, qc_log = apply_quality_control(raw, metadata)
        hourly = resample_hourly_mean(qc_data)
        daily = resample_daily_mean(qc_data)
        anomaly = calculate_intraday_anomaly(hourly, daily)
        metrics_result = calculate_metrics(variable_key, hourly, daily, anomaly)

        print(f"\n=== {variable_key} ===")
        print("QC summary:")
        print(qc_summary)
        print(f"hourly rows: {len(hourly)}")
        print(f"daily rows: {len(daily)}")
        print("anomaly head:")
        print(anomaly.head().to_string(index=False))
        print("metrics:")
        _print_metrics(metrics_result)


if __name__ == "__main__":
    run_preview()
