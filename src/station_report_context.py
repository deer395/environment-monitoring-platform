"""Build a deterministic station-report context from confirmed QC assets only."""

from __future__ import annotations

import pandas as pd

from .anomaly import calculate_configured_anomaly
from .metrics import calculate_metrics
from .report_context import build_report_context
from .resampling import resample_configured
from .station_task import require_station_export
from .variable_registry import get_variable_metadata


def _manual_remove_count(review):
    if review is None or review.empty:
        return 0
    automatic = review.get("existing_rule", pd.Series("", index=review.index)).fillna("").astype(str)
    decisions = review.get("user_decision", pd.Series("", index=review.index)).fillna("")
    return int((decisions.isin(["remove", "manual_remove"]) & ~automatic.str.contains("sensor_zero|hard_range|physical_range")).sum())


def build_station_report_context(variable_keys, confirmed_assets, progress, station_info):
    """Create report-ready facts without re-reading files or re-running QC."""
    require_station_export(progress, confirmed_assets, variable_keys)
    variables, overview_rows, qc_rows = [], [], []
    for key in variable_keys:
        asset = confirmed_assets[key]
        final = asset["final_qc_data"]
        raw = asset.get("raw_data")
        if raw is None:
            # Older in-memory confirmations cannot safely provide a comparison
            # section; they must be reconfirmed in the current session.
            raise ValueError(f"{key} 缺少确认时保存的原始分析数据，请重新确认该变量。")
        metadata = get_variable_metadata(key)
        resampled = resample_configured(final, metadata)
        anomaly = calculate_configured_anomaly(resampled, metadata)
        metrics = calculate_metrics(key, resampled["hourly"], resampled["daily"], anomaly, metadata=metadata, base_data=resampled["hourly"])
        report_context = build_report_context(
            variable_key=key, raw_data=raw, final_qc_data=final,
            final_qc_log=asset.get("final_qc_log"), qc_summary=asset["qc_summary"],
            review_table=asset.get("review_table"), resampled=resampled, anomaly=anomaly,
            metrics=metrics, qc_token=asset["qc_token"], confirmed_qc_token=asset["qc_token"],
            project_name=station_info.get("site_name", ""), project_title=station_info.get("project_name", ""),
            organization=station_info.get("department", ""), author=station_info.get("author", ""),
        )
        data, qc = report_context["data_summary"], asset["qc_summary"]
        start = pd.Timestamp(asset["analysis_start"]).strftime("%Y-%m-%d")
        end = pd.Timestamp(asset["analysis_end"]).strftime("%Y-%m-%d")
        overview_rows.append((metadata["display_name_cn"], metadata["unit"], f"{start} 至 {end}", f"{qc.get('raw_count', 0):,}", f"{data['final_valid_count']:,}", f"{data['final_missing_count']:,}", f"{data['valid_rate']:.2f}%"))
        qc_rows.append((metadata["display_name_cn"], qc.get("missing_before_qc", 0), qc.get("removed_by_sensor_zero", 0), qc.get("removed_by_range", 0), qc.get("flagged_by_hampel", 0), qc.get("flagged_by_constant_value", 0), _manual_remove_count(asset.get("review_table")), data["final_valid_count"]))
        variables.append({"key": key, "context": report_context, "asset": asset})
    return {
        "station_info": dict(station_info), "variables": variables,
        "overview_rows": overview_rows, "qc_rows": qc_rows,
    }
