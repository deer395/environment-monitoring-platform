"""Preview and checks for V2 stage 4 manual QC."""

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.loaders import load_depth_and_temperature
from src.manual_qc import LOG_COLUMNS, apply_manual_qc_decisions, candidate_decision_table
from src.output_paths import ensure_stage_dirs, figure_path, log_path, table_path
from src.plotting import plot_qc_comparison, plot_qc_flags
from src.qc import apply_quality_control
from src.report_tables import build_qc_log_table, export_qc_log
from src.variable_registry import get_variable_metadata


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _first_time(table, rule):
    rows = table[table["rule"].eq(rule)]
    return None if rows.empty else rows.iloc[0]["datetime"]


def run_preview(data_dir=PROJECT_ROOT / "data_private"):
    paths = ensure_stage_dirs()
    loaded = load_depth_and_temperature(data_dir)
    all_logs = []

    stage3_root = PROJECT_ROOT / "outputs" / "v2_stage3_qc_ui"
    stage3_snapshot = sorted(str(p) for p in stage3_root.rglob("*") if p.is_file()) if stage3_root.exists() else []

    for variable_key, raw in loaded.items():
        metadata = get_variable_metadata(variable_key)
        auto_qc, summary, qc_log = apply_quality_control(
            raw,
            metadata,
            enable_intraday_2std=False,
            enable_valid_range=True,
            enable_hampel=True,
            enable_constant_value=True,
        )
        candidates = candidate_decision_table(qc_log)

        _assert(summary["removed_by_range"] >= 0, "physical_range count missing")
        _assert(auto_qc is not raw, "auto_qc_data must be separate from raw_data")
        _assert(raw["value"].isna().sum() == 0, "raw_data should not be modified")

        final_default, log_default = apply_manual_qc_decisions(raw, auto_qc, qc_log, candidates)
        _assert(final_default["value"].isna().sum() == auto_qc["value"].isna().sum(), "Hampel default should not delete")

        if not candidates.empty:
            remove_candidates = candidates.copy()
            remove_candidates.loc[remove_candidates.index[0], "user_decision"] = "remove"
            remove_time = remove_candidates.loc[remove_candidates.index[0], "datetime"]
            final_remove, log_remove = apply_manual_qc_decisions(raw, auto_qc, qc_log, remove_candidates)
            _assert(final_remove.loc[final_remove["datetime"].eq(remove_time), "value"].isna().all(), "remove decision should delete")

            keep_candidates = remove_candidates.copy()
            keep_candidates.loc[keep_candidates.index[0], "user_decision"] = "keep"
            final_keep, log_keep = apply_manual_qc_decisions(raw, auto_qc, qc_log, keep_candidates)
            _assert(final_keep.loc[final_keep["datetime"].eq(remove_time), "value"].notna().all(), "keep decision should preserve")

            manual_final, manual_log = apply_manual_qc_decisions(
                raw,
                auto_qc,
                qc_log,
                remove_candidates,
                manual_keep_datetimes=[remove_time],
            )
            _assert(manual_final.loc[manual_final["datetime"].eq(remove_time), "value"].notna().all(), "manual_keep should restore")
        else:
            log_remove = log_default

        manual_remove_time = raw.iloc[len(raw) // 2]["datetime"]
        manual_removed, manual_removed_log = apply_manual_qc_decisions(
            raw,
            auto_qc,
            qc_log,
            candidates,
            manual_remove_datetimes=[manual_remove_time],
        )
        _assert(manual_removed.loc[manual_removed["datetime"].eq(manual_remove_time), "value"].isna().all(), "manual_remove should delete")
        _assert(set(LOG_COLUMNS).issubset(manual_removed_log.columns), "final log fields incomplete")

        all_logs.append(manual_removed_log)
        plot_qc_comparison(raw, manual_removed, variable_key, figure_path(f"{variable_key}_stage4_final_qc_comparison.png"))
        plot_qc_flags(raw, manual_removed_log, variable_key, figure_path(f"{variable_key}_stage4_final_qc_flags.png"))

    final_log = pd.concat(all_logs, ignore_index=True) if all_logs else pd.DataFrame(columns=LOG_COLUMNS)
    log_file = log_path("final_qc_log.xlsx")
    export_qc_log(final_log, log_file)
    build_qc_log_table(final_log).to_csv(table_path("final_qc_log.csv"), index=False, encoding="utf-8-sig")

    stage3_after = sorted(str(p) for p in stage3_root.rglob("*") if p.is_file()) if stage3_root.exists() else []
    _assert(stage3_snapshot == stage3_after, "stage3 outputs should not be overwritten")

    print("V2 stage 4 preview checks passed")
    print(f"stage_root: {paths['root']}")
    print(f"figures: {paths['figures']}")
    print(f"tables: {paths['tables']}")
    print(f"logs: {paths['logs']}")
    print(f"final_qc_log: {log_file}")


if __name__ == "__main__":
    run_preview()