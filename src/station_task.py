"""Pure state helpers for the V4.2 station-task workflow.

The module deliberately does not import Streamlit.  It turns the current
uploaded-source and confirmed-QC assets into a truthful task view, and is the
single gate used before creating a station-level workbook.
"""

from __future__ import annotations

from typing import Mapping

import pandas as pd


def default_station_report_title(site_name: str) -> str:
    """Return the editable default title for a station composite report."""
    site_name = (site_name or "").strip()
    return f"{site_name}站点环境监测综合报告" if site_name else "站点环境监测综合报告"


def station_info_signature(info: Mapping[str, str]) -> tuple[str, str, str, str, str]:
    """Return fields whose changes make generated Word bytes stale, not QC."""
    return tuple(str(info.get(key, "")).strip() for key in (
        "site_name", "project_name", "department", "author", "report_title",
    ))


STATION_EXPORT_CACHE_KEYS = (
    "station_task:summary_excel_bytes",
    # Reserved for the future station composite Word report.
    "station_task:station_word_report_bytes",
    "station_task:station_word_report_filename",
)


def variable_report_cache_keys(variable_key):
    """Return cached Word-output keys for exactly one variable."""
    return (f"{variable_key}:word_report_bytes", f"{variable_key}:word_report_filename")


def report_cache_keys(variable_keys):
    """Return only cached generated-report keys; QC assets are intentionally absent."""
    return [key for variable_key in variable_keys for key in variable_report_cache_keys(variable_key)]


def clear_variable_report_cache(session_state, variable_key) -> None:
    """Discard one variable's rendered Word bytes without touching QC state."""
    for key in variable_report_cache_keys(variable_key):
        session_state.pop(key, None)


def clear_report_caches(session_state, variable_keys) -> None:
    """Discard rendered Word files after station metadata changes."""
    for key in report_cache_keys(variable_keys):
        session_state.pop(key, None)


def clear_all_variable_report_caches(session_state, variable_keys) -> None:
    """Named public API for a global station-information change."""
    clear_report_caches(session_state, variable_keys)


def clear_station_export_caches(session_state) -> None:
    """Remove station composite exports so stale downloads cannot be shown."""
    for key in STATION_EXPORT_CACHE_KEYS:
        session_state.pop(key, None)


def clear_variable_result_caches(session_state, variable_key) -> None:
    """Invalidate outputs affected by one variable's data or QC-result change."""
    clear_variable_report_cache(session_state, variable_key)
    clear_station_export_caches(session_state)


def _source_status(source):
    if not source or not source.get("provided", False):
        return "未提供"
    if source.get("read_error"):
        return "读取失败"
    if source.get("read_success"):
        return "已上传"
    return "已上传"


def _manual_status(source_status, asset, confirmation_status):
    if source_status == "未提供":
        return "未处理"
    if source_status == "读取失败":
        return "未处理"
    if asset is not None and confirmation_status == "已人工确认":
        return "已人工确认"
    if asset is not None:
        return "确认结果已失效"
    if confirmation_status == "仅自动质控":
        return "仅自动质控"
    return "未处理"


def build_station_task_status(
    variable_keys,
    metadata_by_key: Mapping,
    source_states: Mapping,
    confirmed_assets: Mapping,
    confirmation_statuses: Mapping,
    station_info: Mapping[str, str],
):
    """Build status rows, progress, blockers, and a strict export decision.

    ``source_states`` is populated by the UI from actual uploads and loader
    results.  No registry default file participates in this calculation.
    """
    rows, blockers = [], []
    uploaded_count = confirmed_count = exportable_count = 0
    for variable_key in variable_keys:
        metadata = metadata_by_key[variable_key]
        source = source_states.get(variable_key, {})
        asset = confirmed_assets.get(variable_key)
        source_status = _source_status(source)
        confirmation_status = confirmation_statuses.get(variable_key, "未处理")
        manual_status = _manual_status(source_status, asset, confirmation_status)
        valid = manual_status == "已人工确认" and asset.get("final_qc_data") is not None if asset is not None else False
        if source_status == "已上传":
            uploaded_count += 1
        if manual_status == "已人工确认":
            confirmed_count += 1
        if valid:
            exportable_count += 1

        reason = ""
        if source_status == "未提供":
            reason = "未上传文件"
        elif source_status == "读取失败":
            reason = f"读取失败：{source.get('read_error')}"
        elif manual_status == "确认结果已失效":
            reason = confirmation_status or "确认结果已失效，需重新确认"
        elif manual_status == "仅自动质控":
            reason = "仅完成自动质控，尚未人工确认"
        elif manual_status == "未处理":
            reason = "尚未完成质控处理"
        if reason:
            blockers.append(f"{metadata.get('display_name_cn', variable_key)}：{reason}")

        file_start, file_end = source.get("start_time"), source.get("end_time")
        analysis_start = analysis_end = None
        analysis_raw_count = final_valid_count = ""
        if valid:
            analysis_start, analysis_end = asset.get("analysis_start"), asset.get("analysis_end")
            analysis_raw_count = asset.get("qc_summary", {}).get("raw_count", "")
            final_data = asset.get("final_qc_data")
            final_valid_count = int(pd.to_numeric(final_data.get("value"), errors="coerce").notna().sum())
        rows.append({
            "中文变量名称": metadata.get("display_name_cn", variable_key),
            "文件状态": source_status,
            "文件时间范围": f"{file_start} 至 {file_end}" if file_start is not None and file_end is not None else "",
            "文件记录数": source.get("raw_count", ""),
            "分析时间范围": f"{analysis_start} 至 {analysis_end}" if analysis_start is not None and analysis_end is not None else "",
            "分析范围原始记录数": analysis_raw_count,
            "最终有效记录数": final_valid_count,
            "人工确认状态": manual_status,
            "当前结果是否有效": "是" if valid else "否",
            "是否可纳入站点综合导出": "是" if valid else "否",
            "阻断原因": reason,
        })

    if not str(station_info.get("site_name", "")).strip():
        blockers.insert(0, "站点名称：尚未填写")
    ready = bool(str(station_info.get("site_name", "")).strip()) and exportable_count == len(variable_keys)
    progress = {
        "已上传变量数": uploaded_count,
        "已确认变量数": confirmed_count,
        "可导出变量数": exportable_count,
        "变量总数": len(variable_keys),
        "阻断项": blockers,
        "可生成站点综合 Excel": ready,
    }
    return pd.DataFrame(rows), progress


def require_station_export(progress, confirmed_assets, variable_keys):
    """Raise a clear error unless every registered variable has final QC data."""
    if not progress.get("可生成站点综合 Excel"):
        detail = "；".join(progress.get("阻断项", [])) or "站点任务尚未完成"
        raise ValueError(f"不能生成站点综合 Excel：{detail}")
    missing = [key for key in variable_keys if confirmed_assets.get(key, {}).get("final_qc_data") is None]
    if missing:
        raise ValueError(f"不能生成站点综合 Excel：缺少 final_qc_data（{', '.join(missing)}）")
