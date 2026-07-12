"""Preview V2 stage 3 QC UI outputs without launching Streamlit."""

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.anomaly import calculate_intraday_anomaly
from src.loaders import load_depth_and_temperature
from src.metrics import calculate_metrics
from src.output_paths import ensure_stage_dirs, figure_path, log_path, table_path
from src.plotting import plot_qc_comparison, plot_qc_flags
from src.qc import apply_quality_control
from src.report_tables import (
    build_basic_statistics_row,
    build_basic_statistics_table,
    build_qc_log_table,
    build_qc_summary_table,
    export_qc_log,
)
from src.resampling import resample_daily_mean, resample_hourly_mean
from src.variable_registry import get_variable_metadata


def run_preview(data_dir=PROJECT_ROOT / "data_private"):
    paths = ensure_stage_dirs()
    loaded = load_depth_and_temperature(data_dir)
    all_logs = []
    qc_summaries = {}
    basic_rows = []

    for variable_key, raw in loaded.items():
        metadata = get_variable_metadata(variable_key)
        qc_data, qc_summary, qc_log = apply_quality_control(
            raw,
            metadata,
            enable_intraday_2std=False,
            enable_valid_range=True,
            enable_hampel=True,
            enable_constant_value=True,
        )
        hourly = resample_hourly_mean(qc_data)
        daily = resample_daily_mean(qc_data)
        anomaly = calculate_intraday_anomaly(hourly, daily)
        metrics = calculate_metrics(variable_key, hourly, daily, anomaly)

        qc_summaries[variable_key] = qc_summary
        basic_rows.append(build_basic_statistics_row(variable_key, hourly, metrics, qc_summary))
        all_logs.append(qc_log)

        plot_qc_comparison(raw, qc_data, variable_key, figure_path(f"{variable_key}_qc_comparison.png"))
        plot_qc_flags(raw, qc_log, variable_key, figure_path(f"{variable_key}_qc_flags.png"))

    qc_log = pd.concat(all_logs, ignore_index=True) if all_logs else None
    qc_log_xlsx = log_path("qc_log.xlsx")
    export_qc_log(qc_log, qc_log_xlsx)

    qc_summary_xlsx = table_path("qc_summary.xlsx")
    basic_statistics_xlsx = table_path("basic_statistics.xlsx")
    with pd.ExcelWriter(qc_summary_xlsx) as writer:
        build_qc_summary_table(qc_summaries).to_excel(writer, sheet_name="qc_summary", index=False)
    with pd.ExcelWriter(basic_statistics_xlsx) as writer:
        build_basic_statistics_table(basic_rows).to_excel(writer, sheet_name="basic_statistics", index=False)

    print(f"stage_root: {paths['root']}")
    print(f"figures: {paths['figures']}")
    print(f"tables: {paths['tables']}")
    print(f"logs: {paths['logs']}")
    print(f"qc_log: {qc_log_xlsx}")
    print(f"qc_summary: {qc_summary_xlsx}")
    print(f"basic_statistics: {basic_statistics_xlsx}")
    print(f"depth_qc_comparison: {figure_path('depth_qc_comparison.png')}")
    print(f"depth_qc_flags: {figure_path('depth_qc_flags.png')}")
    print(f"temperature_qc_comparison: {figure_path('temperature_qc_comparison.png')}")
    print(f"temperature_qc_flags: {figure_path('temperature_qc_flags.png')}")


if __name__ == "__main__":
    run_preview()
