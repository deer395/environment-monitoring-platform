"""Preview V2 stage 2 QC algorithms and validation plots."""

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.loaders import load_depth_and_temperature
from src.plotting import plot_qc_comparison, plot_qc_flags
from src.qc import apply_quality_control
from src.report_tables import build_qc_log_table
from src.variable_registry import get_variable_metadata


OUTPUT_DIR = PROJECT_ROOT / "outputs"
SCENARIOS = [
    ("physical_range_only", dict(enable_valid_range=True, enable_hampel=False, enable_constant_value=False)),
    ("physical_range_hampel", dict(enable_valid_range=True, enable_hampel=True, enable_constant_value=False)),
    ("physical_range_hampel_constant", dict(enable_valid_range=True, enable_hampel=True, enable_constant_value=True)),
]


def _print_summary(variable_key, scenario, summary):
    print(f"\n=== {variable_key} | {scenario} ===")
    print(f"raw_count: {summary['raw_count']}")
    print(f"missing_before_qc: {summary['missing_before_qc']}")
    print(f"removed_by_range: {summary['removed_by_range']}")
    print(f"flagged_by_hampel: {summary['flagged_by_hampel']}")
    print(f"flagged_by_constant_value: {summary['flagged_by_constant_value']}")
    print(f"applied_flagged_count: {summary['applied_flagged_count']}")
    print(f"missing_after_qc: {summary['missing_after_qc']}")


def run_preview(data_dir=PROJECT_ROOT / "data_private", output_dir=OUTPUT_DIR):
    output_dir.mkdir(parents=True, exist_ok=True)
    loaded = load_depth_and_temperature(data_dir)
    all_logs = []
    final_results = {}

    for variable_key, raw in loaded.items():
        metadata = get_variable_metadata(variable_key)
        for scenario, options in SCENARIOS:
            qc_data, summary, qc_log = apply_quality_control(
                raw,
                metadata,
                enable_intraday_2std=False,
                **options,
            )
            log_table = build_qc_log_table(qc_log)
            if not log_table.empty:
                log_table.insert(0, "scenario", scenario)
                all_logs.append(log_table)
            _print_summary(variable_key, scenario, summary)
            if scenario == "physical_range_hampel_constant":
                final_results[variable_key] = (qc_data, qc_log)

    all_logs = [
        log
        for log in all_logs
        if log is not None and not log.empty and not log.dropna(axis=1, how="all").empty
    ]
    export_log = (
        pd.DataFrame(
            [record for log in all_logs for record in log.to_dict("records")]
        )
        if all_logs
        else build_qc_log_table(None)
    )
    log_path = output_dir / "v2_stage2_qc_log.xlsx"
    with pd.ExcelWriter(log_path) as writer:
        export_log.to_excel(writer, sheet_name="qc_log", index=False)

    for variable_key, raw in loaded.items():
        qc_data, qc_log = final_results[variable_key]
        plot_qc_comparison(raw, qc_data, variable_key, output_dir / f"{variable_key}_qc_comparison.png")
        plot_qc_flags(raw, qc_log, variable_key, output_dir / f"{variable_key}_qc_flags.png")

    print(f"\nqc_log_excel: {log_path}")
    print(f"plot: {output_dir / 'depth_qc_comparison.png'}")
    print(f"plot: {output_dir / 'depth_qc_flags.png'}")
    print(f"plot: {output_dir / 'temperature_qc_comparison.png'}")
    print(f"plot: {output_dir / 'temperature_qc_flags.png'}")


if __name__ == "__main__":
    run_preview()
