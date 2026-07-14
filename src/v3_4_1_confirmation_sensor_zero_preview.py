"""Focused regression checks for V3.4 multi-variable confirmations and sensor_zero."""

from io import BytesIO
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app
from src.manual_qc import apply_review_table_decisions, build_qc_review_table, ensure_record_id
from src.qc import apply_quality_control
from src.variable_registry import get_variable_metadata, list_enabled_variables


VARIABLES = tuple(list_enabled_variables())
CONFIRMED = ("salinity", "temperature", "cod")


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _synthetic_sensor_zero(variable_key):
    metadata = get_variable_metadata(variable_key)
    hard_min = metadata["hard_min"]
    negative = hard_min - 1.0
    values = [0, 0.0, 0.0001, negative, hard_min + 1.0, metadata["hard_max"] + 1.0]
    raw = pd.DataFrame({
        "record_id": [f"{variable_key}_{index}" for index in range(len(values))],
        "datetime": pd.date_range("2026-01-01", periods=len(values), freq="30min"),
        "value": values,
        "variable": variable_key,
        "unit": metadata["unit"],
    })
    raw.attrs.update({"variable_key": variable_key, "unit": metadata["unit"]})
    return raw


def _verify_sensor_zero(variable_key):
    metadata = get_variable_metadata(variable_key)
    _assert(metadata["zero_is_invalid"] is True, f"{variable_key} zero_is_invalid is not configured")
    raw = _synthetic_sensor_zero(variable_key)
    qc_data, summary, qc_log = apply_quality_control(raw, metadata, enable_valid_range=True)
    values = qc_data.set_index("record_id")["value"]
    _assert(summary["removed_by_sensor_zero"] == 2, f"{variable_key} exact zero count mismatch")
    _assert(summary["removed_by_range"] == 2, f"{variable_key} hard_range count mismatch")
    _assert(pd.isna(values[f"{variable_key}_0"]) and pd.isna(values[f"{variable_key}_1"]), f"{variable_key} zeros were not removed")
    _assert(pd.notna(values[f"{variable_key}_2"]), f"{variable_key} 0.0001 was incorrectly removed")
    _assert(pd.isna(values[f"{variable_key}_3"]) and pd.isna(values[f"{variable_key}_5"]), f"{variable_key} hard range failed")
    _assert((qc_log[qc_log["rule"].eq("sensor_zero")]["original_value"] == 0).all(), f"{variable_key} sensor_zero log lost original values")
    review = build_qc_review_table(raw, qc_data, qc_log)
    review.loc[review["record_id"].isin([f"{variable_key}_0", f"{variable_key}_1"]), "user_decision"] = "manual_keep"
    final, _ = apply_review_table_decisions(raw, qc_data, qc_log, review)
    _assert(final.loc[final["record_id"].isin([f"{variable_key}_0", f"{variable_key}_1"]), "value"].isna().all(), f"{variable_key} sensor_zero was restored")


def _confirmed_asset(variable_key):
    metadata = get_variable_metadata(variable_key)
    source_args = app._source_args(variable_key, None)
    raw = app._cached_load_excel(
        variable_key,
        source_args["source_signature"],
        source_args["source_path"],
        source_args["uploaded_bytes"],
        source_args["uploaded_suffix"],
    )
    start = raw["datetime"].min()
    end = min(start + pd.Timedelta(days=7), raw["datetime"].max())
    raw = ensure_record_id(raw[(raw["datetime"] >= start) & (raw["datetime"] <= end)].reset_index(drop=True))
    qc_data, summary, log = apply_quality_control(raw, metadata, enable_valid_range=True, enable_hampel=True, enable_constant_value=True)
    review = build_qc_review_table(raw, qc_data, log)
    final, final_log = apply_review_table_decisions(raw, qc_data, log, review)
    token = app._build_qc_token(variable_key, source_args["source_signature"], start, end, True, True, True)
    return {
        "qc_confirmed": True,
        "final_qc_data": final,
        "final_qc_log": final_log,
        "qc_summary": summary,
        "review_table": review,
        "source_signature": source_args["source_signature"],
        "analysis_start": start,
        "analysis_end": end,
        "qc_token": token,
    }


def _verify_multi_variable_confirmation_export():
    assets = {key: _confirmed_asset(key) for key in CONFIRMED}
    for key, asset in assets.items():
        app.st.session_state[app._state_key(key, "confirmed_qc_assets")] = asset
    uploads = {key: None for key in VARIABLES}
    context = {
        "variable_key": "cod",
        "analysis_start": assets["cod"]["analysis_start"],
        "analysis_end": assets["cod"]["analysis_end"],
        "qc_token": assets["cod"]["qc_token"],
    }
    collected, _ = app._collect_confirmed_qc_assets(uploads, True, True, True, context)
    _assert(set(collected) == set(CONFIRMED), "confirmed assets were lost after variable switching")
    blob = app._summary_workbook_bytes(uploads, True, True, True, collected)
    status = pd.read_excel(BytesIO(blob), sheet_name="processing_status")
    for key in CONFIRMED:
        row = status[status["variable_key"].eq(key)].iloc[0]
        _assert(bool(row["manual_qc_confirmed"]), f"{key} was not exported as manually confirmed")
        _assert("已人工确认" in row["note"], f"{key} confirmation note is incorrect")
    for key in set(VARIABLES) - set(CONFIRMED):
        row = status[status["variable_key"].eq(key)].iloc[0]
        _assert(not bool(row["manual_qc_confirmed"]), f"{key} should remain automatic")

    changed_context = {**context, "variable_key": "salinity", "analysis_end": assets["salinity"]["analysis_end"] + pd.Timedelta(minutes=30), "qc_token": "changed"}
    stale, stale_status = app._confirmed_asset_status("salinity", None, True, True, True, changed_context)
    intact, intact_status = app._confirmed_asset_status("temperature", None, True, True, True, context)
    _assert(stale is None and "时间范围已变化" in stale_status, "changed range did not invalidate its confirmation")
    _assert(intact is not None and intact_status == "已人工确认", "other variable confirmation was affected")


def main():
    for variable_key in VARIABLES:
        _verify_sensor_zero(variable_key)
    _verify_multi_variable_confirmation_export()
    print("V3.4.1 confirmation and sensor_zero preview passed")


if __name__ == "__main__":
    main()
