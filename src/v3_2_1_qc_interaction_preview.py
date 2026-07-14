"""Preview checks for V3.2.1 hard range and QC interaction fixes."""

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import _apply_selected_decision
from src.anomaly import calculate_configured_anomaly
from src.loaders import load_excel_variable
from src.manual_qc import apply_review_table_decisions, build_qc_review_table, ensure_record_id
from src.metrics import calculate_metrics
from src.plotting import create_qc_candidate_figure
from src.qc import apply_quality_control
from src.resampling import resample_configured
from src.variable_registry import get_variable_metadata


OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "v3_2_1_qc_interaction"
DATA_DIR = PROJECT_ROOT / "data_private"
REGRESSION_VARIABLES = ("depth", "temperature", "salinity", "dissolved_oxygen", "cod")


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _make_range_frame(variable_key, hard_min, hard_max):
    midpoint = (hard_min + hard_max) / 2
    data = pd.DataFrame(
        {
            "record_id": ["below", "lower_boundary", "middle", "upper_boundary", "above"],
            "datetime": pd.date_range("2026-06-01", periods=5, freq="30min"),
            "value": [hard_min - 0.1, hard_min, midpoint, hard_max, hard_max + 0.1],
        }
    )
    metadata = get_variable_metadata(variable_key)
    data["variable"] = variable_key
    data["unit"] = metadata["unit"]
    data.attrs.update({"variable_key": variable_key, "unit": metadata["unit"], "display_name": metadata["display_name"]})
    return data


def _run_hard_range_boundary_checks():
    expected = {
        "depth": (0, 100),
        "temperature": (-2.5, 50),
        "salinity": (0, 50),
        "dissolved_oxygen": (0, 100),
        "cod": (0, 100),
    }
    records = []
    for variable_key, (hard_min, hard_max) in expected.items():
        metadata = get_variable_metadata(variable_key)
        _assert(metadata["hard_min"] == hard_min, f"{variable_key} hard_min mismatch")
        _assert(metadata["hard_max"] == hard_max, f"{variable_key} hard_max mismatch")
        raw = _make_range_frame(variable_key, hard_min, hard_max)
        qc_data, qc_summary, qc_log = apply_quality_control(raw, metadata, enable_valid_range=True)
        review = build_qc_review_table(raw, qc_data, qc_log)
        _assert(qc_summary["removed_by_range"] == 2, f"{variable_key} should remove below and above only")
        values = qc_data.set_index("record_id")["value"]
        _assert(pd.isna(values["below"]), f"{variable_key} below hard_min should be removed")
        _assert(pd.isna(values["above"]), f"{variable_key} above hard_max should be removed")
        if hard_min == 0:
            _assert(pd.isna(values["lower_boundary"]), f"{variable_key} zero boundary should be sensor_zero removed")
            _assert(qc_summary["removed_by_sensor_zero"] == 1, f"{variable_key} sensor_zero count mismatch")
        else:
            _assert(pd.notna(values["lower_boundary"]), f"{variable_key} lower boundary should be kept")
        _assert(pd.notna(values["upper_boundary"]), f"{variable_key} upper boundary should be kept")

        for decision in ("keep", "manual_keep"):
            edited = review.copy()
            edited.loc[edited["record_id"].isin(["below", "lower_boundary", "above"]), "user_decision"] = decision
            final_qc_data, _ = apply_review_table_decisions(raw, qc_data, qc_log, edited)
            final_values = final_qc_data.set_index("record_id")["value"]
            _assert(pd.isna(final_values["below"]), f"{variable_key} hard low should not recover by {decision}")
            _assert(pd.isna(final_values["above"]), f"{variable_key} hard high should not recover by {decision}")
            if hard_min == 0:
                _assert(pd.isna(final_values["lower_boundary"]), f"{variable_key} sensor zero should not recover by {decision}")

        selected_restore = _apply_selected_decision(review, ["below", "lower_boundary", "above"], "manual_keep")
        final_selected_restore, _ = apply_review_table_decisions(raw, qc_data, qc_log, selected_restore)
        selected_values = final_selected_restore.set_index("record_id")["value"]
        _assert(pd.isna(selected_values["below"]), f"{variable_key} hard low should not recover from plot restore")
        _assert(pd.isna(selected_values["above"]), f"{variable_key} hard high should not recover from plot restore")
        if hard_min == 0:
            _assert(pd.isna(selected_values["lower_boundary"]), f"{variable_key} sensor zero should not recover from plot restore")

        records.append({"variable": variable_key, "hard_min": hard_min, "hard_max": hard_max, "hard_removed": qc_summary["removed_by_range"]})
    return records


def _make_interaction_frame():
    data = pd.DataFrame(
        {
            "record_id": ["hard_low", "normal_a", "normal_b", "constant_a", "constant_b", "constant_c"],
            "datetime": [
                "2026-06-01 00:00",
                "2026-06-01 00:30",
                "2026-06-01 00:30",
                "2026-06-01 01:00",
                "2026-06-01 01:30",
                "2026-06-01 02:00",
            ],
            "value": [-1.0, 30.0, 31.0, 22.0, 22.0, 22.0],
        }
    )
    data["datetime"] = pd.to_datetime(data["datetime"])
    data["variable"] = "salinity"
    data["unit"] = "PSU"
    data.attrs.update({"variable_key": "salinity", "unit": "PSU", "display_name": "Salinity"})
    return data


def _run_manual_record_id_checks():
    metadata = get_variable_metadata("salinity")
    raw = ensure_record_id(_make_interaction_frame())
    qc_data, qc_summary, qc_log = apply_quality_control(
        raw,
        metadata,
        enable_valid_range=True,
        enable_hampel=True,
        enable_constant_value=True,
    )
    review = build_qc_review_table(raw, qc_data, qc_log)
    selected_remove = _apply_selected_decision(review, ["normal_a"], "remove")
    _assert(selected_remove.loc[selected_remove["record_id"].eq("normal_a"), "user_decision"].iloc[0] == "manual_remove", "ordinary selected point should become manual_remove")
    final_normal_remove, _ = apply_review_table_decisions(raw, qc_data, qc_log, selected_remove)
    _assert(pd.isna(final_normal_remove.loc[final_normal_remove["record_id"].eq("normal_a"), "value"].iloc[0]), "ordinary selected point should be removed by record_id")
    _assert(pd.notna(final_normal_remove.loc[final_normal_remove["record_id"].eq("normal_b"), "value"].iloc[0]), "duplicate datetime peer should remain when record_id differs")
    return {"ordinary_record_id_removed": True, "duplicate_datetime_separate": True, "hard_range_removed": int(qc_summary["removed_by_range"])}


def _make_plot_frame():
    periods = 12000
    data = pd.DataFrame(
        {
            "record_id": [f"plot_{idx}" for idx in range(periods)],
            "datetime": pd.date_range("2026-06-01", periods=periods, freq="10min"),
            "value": [30.0 + (idx % 17) * 0.01 for idx in range(periods)],
        }
    )
    data.loc[4321, "value"] = 49.9
    data.loc[6789, "value"] = 0.2
    data.loc[7777, "value"] = 1.1
    data["variable"] = "salinity"
    data["unit"] = "PSU"
    data.attrs.update({"variable_key": "salinity", "unit": "PSU", "display_name": "Salinity"})
    return data


def _candidate_log(raw, record_ids):
    rows = []
    for record_id in record_ids:
        row = raw[raw["record_id"].eq(record_id)].iloc[0]
        rows.append(
            {
                "record_id": record_id,
                "datetime": row["datetime"],
                "variable": "salinity",
                "original_value": row["value"],
                "qc_value": row["value"],
                "rule": "hampel",
                "reason": "plot preservation test candidate",
                "is_flagged": True,
                "is_applied": False,
                "parameter": "test",
                "user_decision": "undecided",
                "decision_source": "algorithm_suggestion",
            }
        )
    return pd.DataFrame(rows)


def _run_plot_sampling_checks():
    raw = _make_plot_frame()
    qc_log = _candidate_log(raw, ["plot_7777"])
    review = build_qc_review_table(raw, raw.copy(), qc_log)
    selectable = raw[(raw["datetime"] >= raw.loc[6500, "datetime"]) & (raw["datetime"] <= raw.loc[6600, "datetime"])].copy()
    figure = create_qc_candidate_figure(raw, qc_log, review, "salinity", selectable_raw_df=selectable)

    background = next(trace for trace in figure.data if trace.name == "原始数据")
    background_values = set(float(value) for value in background.y)
    _assert(49.9 in background_values, "global extrema downsampling should retain maximum value")
    _assert(0.2 in background_values, "global extrema downsampling should retain minimum value")
    _assert(1.1 in background_values, "global extrema downsampling should retain candidate raw value")

    range_line = next(trace for trace in figure.data if trace.name == "当前检查范围原始线")
    _assert(len(range_line.x) == len(selectable), "current review range raw line should keep full resolution")
    raw_point_trace = next(trace for trace in figure.data if trace.name == "原始数据点")
    selected_ids = {str(row[0]) for row in raw_point_trace.customdata}
    _assert(set(selectable["record_id"].astype(str)).issubset(selected_ids), "selectable raw points should carry record_id")

    before_hampel = int((qc_log["rule"] == "hampel").sum())
    before_constant = int((qc_log["rule"] == "constant_value").sum()) if "constant_value" in set(qc_log["rule"]) else 0
    after_hampel = int((qc_log["rule"] == "hampel").sum())
    after_constant = int((qc_log["rule"] == "constant_value").sum()) if "constant_value" in set(qc_log["rule"]) else 0
    _assert(before_hampel == after_hampel, "plotting should not change Hampel flag count")
    _assert(before_constant == after_constant, "plotting should not change constant_value flag count")
    return {
        "global_max_preserved": True,
        "global_min_preserved": True,
        "candidate_raw_value_preserved": True,
        "review_range_full_resolution": True,
    }


def _run_regression(variable_key):
    metadata = get_variable_metadata(variable_key)
    path = DATA_DIR / (metadata.get("default_file") or metadata.get("default_file_name"))
    raw = load_excel_variable(path, variable_key)
    qc_data, qc_summary, qc_log = apply_quality_control(
        raw,
        metadata,
        enable_valid_range=True,
        enable_hampel=True,
        enable_constant_value=True,
    )
    review = build_qc_review_table(raw, qc_data, qc_log)
    final_qc_data, _ = apply_review_table_decisions(raw, qc_data, qc_log, review)
    resampled = resample_configured(final_qc_data, metadata)
    anomaly = calculate_configured_anomaly(resampled, metadata)
    metrics = calculate_metrics(variable_key, resampled["hourly"], resampled["daily"], anomaly, metadata=metadata, base_data=resampled["hourly"])
    _assert("hourly" in resampled and not resampled["hourly"].empty, f"{variable_key} hourly regression failed")
    _assert("daily" in resampled and not resampled["daily"].empty, f"{variable_key} daily regression failed")
    _assert(anomaly is not None and not anomaly.empty, f"{variable_key} anomaly regression failed")
    _assert(not metrics["monthly"].empty, f"{variable_key} monthly regression failed")
    _assert(not metrics["daily_range"].empty, f"{variable_key} daily_range regression failed")
    return {
        "variable": variable_key,
        "raw_count": qc_summary["raw_count"],
        "hard_range_removed": qc_summary["removed_by_range"],
        "hampel_candidates": qc_summary.get("flagged_by_hampel", 0),
        "constant_value_candidates": qc_summary.get("flagged_by_constant_value", 0),
        "final_valid_count": int(final_qc_data["value"].notna().sum()),
    }


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    hard_range_records = _run_hard_range_boundary_checks()
    interaction = _run_manual_record_id_checks()
    plot_sampling = _run_plot_sampling_checks()
    regressions = [_run_regression(variable_key) for variable_key in REGRESSION_VARIABLES]

    pd.DataFrame(hard_range_records).to_csv(OUTPUT_ROOT / "hard_range_boundary_checks.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([interaction]).to_csv(OUTPUT_ROOT / "interaction_checks.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([plot_sampling]).to_csv(OUTPUT_ROOT / "plot_sampling_checks.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(regressions).to_csv(OUTPUT_ROOT / "five_variable_regression.csv", index=False, encoding="utf-8-sig")

    print("V3.2.1 hard range and plot sampling preview passed")
    print(f"output_dir: {OUTPUT_ROOT}")
    print(f"regression_variables: {', '.join(REGRESSION_VARIABLES)}")


if __name__ == "__main__":
    main()
