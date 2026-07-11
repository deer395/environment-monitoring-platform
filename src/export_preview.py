"""Export V1 summary statistics workbook."""

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.anomaly import calculate_intraday_anomaly
from src.loaders import load_depth_and_temperature
from src.metrics import calculate_metrics
from src.qc import apply_quality_control
from src.report_tables import (
    build_basic_statistics_row,
    build_basic_statistics_table,
    build_depth_daily_range_table,
    build_qc_summary_table,
    build_temperature_monthly_table,
    export_summary_statistics,
)
from src.resampling import resample_daily_mean, resample_hourly_mean
from src.variable_registry import get_variable_metadata


OUTPUT_PATH = PROJECT_ROOT / "outputs" / "summary_statistics.xlsx"


def run_export_preview(data_dir=PROJECT_ROOT / "data_private", output_path=OUTPUT_PATH):
    """Run the existing V1 pipeline and export summary statistics."""
    loaded = load_depth_and_temperature(data_dir)

    basic_rows = []
    qc_summaries = {}
    qc_logs = []
    metrics_by_variable = {}

    for variable_key, raw in loaded.items():
        metadata = get_variable_metadata(variable_key)
        qc_data, qc_summary, qc_log = apply_quality_control(raw, metadata)
        hourly = resample_hourly_mean(qc_data)
        daily = resample_daily_mean(qc_data)
        anomaly = calculate_intraday_anomaly(hourly, daily)
        metrics_result = calculate_metrics(variable_key, hourly, daily, anomaly)

        qc_summaries[variable_key] = qc_summary
        qc_logs.append(qc_log)
        metrics_by_variable[variable_key] = metrics_result
        basic_rows.append(
            build_basic_statistics_row(variable_key, hourly, metrics_result, qc_summary)
        )

    export_summary_statistics(
        output_path,
        build_basic_statistics_table(basic_rows),
        build_temperature_monthly_table(metrics_by_variable["temperature"]),
        build_depth_daily_range_table(metrics_by_variable["depth"]),
        build_qc_summary_table(qc_summaries),
        pd.concat(qc_logs, ignore_index=True) if qc_logs else None,
    )
    print(output_path)


if __name__ == "__main__":
    run_export_preview()
