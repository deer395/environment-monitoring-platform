from pathlib import Path
from tempfile import NamedTemporaryFile
from io import BytesIO
import hashlib
import re
import sys

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.anomaly import calculate_configured_anomaly
from src.loaders import load_excel_variable
from src.manual_qc import (
    REVIEW_DECISIONS,
    apply_manual_qc_decisions,
    apply_review_table_decisions,
    build_qc_review_table,
    ensure_record_id,
    summarize_candidate_decisions,
)
from src.metrics import calculate_metrics
from src.plotting import create_final_qc_figure, create_qc_candidate_figure
from src.qc import apply_quality_control
from src.report_tables import (
    build_basic_statistics_row,
    build_basic_statistics_table,
    build_qc_log_table,
    build_qc_summary_table,
    build_summary_workbook_sheets,
)
from src.resampling import resample_configured
from src.report_context import build_report_context
from src.station_task import (
    build_station_task_status,
    clear_all_variable_report_caches,
    clear_station_export_caches,
    clear_variable_result_caches,
    default_station_report_title,
    require_station_export,
    station_info_signature,
)
from src.station_report_context import build_station_report_context
from src.station_word_report import generate_station_word_report
from src.variable_registry import VARIABLE_REGISTRY, get_variable_metadata, list_enabled_variables
from src.word_report import generate_single_variable_report

DATA_DIR = PROJECT_ROOT / "data_private"
DEFAULT_FILES = {
    key: DATA_DIR / (metadata.get("default_file") or metadata.get("default_file_name"))
    for key, metadata in VARIABLE_REGISTRY.items()
    if metadata.get("default_file") or metadata.get("default_file_name")
}


def _uploaded_bytes(uploaded_file):
    return uploaded_file.getvalue() if uploaded_file is not None else None


def _source_signature(variable_key, uploaded_file):
    if uploaded_file is not None:
        digest = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
        return f"upload:{variable_key}:{uploaded_file.name}:{digest}"
    raise ValueError("未提供数据源")


def _source_label(variable_key, uploaded_file):
    if uploaded_file is not None:
        return f"上传文件：{uploaded_file.name}"
    return "未提供数据源"


def _source_args(variable_key, uploaded_file):
    if uploaded_file is None:
        raise ValueError("未提供数据源")
    uploaded = _uploaded_bytes(uploaded_file)
    suffix = Path(uploaded_file.name).suffix
    return {
        "source_signature": _source_signature(variable_key, uploaded_file),
        "source_path": "",
        "uploaded_bytes": uploaded,
        "uploaded_suffix": suffix,
    }


def _state_key(variable_key, name):
    return f"{variable_key}:{name}"


def _current_state_key(name):
    return _state_key(st.session_state.get("current_variable_key", ""), name)


def _qc_params_key(variable_key):
    metadata = get_variable_metadata(variable_key)
    return (
        metadata.get("zero_is_invalid", False),
        metadata.get("hard_min"),
        metadata.get("hard_max"),
        metadata.get("valid_min"),
        metadata.get("valid_max"),
        metadata.get("hampel_window"),
        metadata.get("hampel_sigma"),
        metadata.get("hampel_min_abs_deviation"),
        metadata.get("constant_value_window"),
        metadata.get("constant_value_tolerance"),
    )


def _build_qc_token(variable_key, source_signature, analysis_start, analysis_end, enable_range, enable_hampel, enable_constant):
    return (
        f"{variable_key}|{source_signature}|{pd.Timestamp(analysis_start).isoformat()}|"
        f"{pd.Timestamp(analysis_end).isoformat()}|{enable_range}|{enable_hampel}|"
        f"{enable_constant}|{_qc_params_key(variable_key)}"
    )


def _automatic_remove_mask(table):
    return table["existing_rule"].astype(str).str.contains("sensor_zero|hard_range|physical_range", na=False)


def _save_confirmed_qc_assets(variable_key, source_signature, analysis_start, analysis_end, qc_token):
    decisions = summarize_candidate_decisions(st.session_state.get(_state_key(variable_key, "review_table")))
    if decisions["candidate_undecided_count"]:
        raise ValueError(f"当前仍有{decisions['candidate_undecided_count']}条候选记录未完成人工判定，请先选择删除或保留后再确认最终质控结果。")
    st.session_state[_state_key(variable_key, "confirmed_qc_assets")] = {
        "qc_confirmed": True,
        "final_qc_data": st.session_state.get(_state_key(variable_key, "final_qc_data")),
        "raw_data": st.session_state.get(_state_key(variable_key, "raw_data")),
        "final_qc_log": st.session_state.get(_state_key(variable_key, "final_qc_log")),
        "qc_summary": st.session_state.get(_state_key(variable_key, "qc_summary")),
        "review_table": st.session_state.get(_state_key(variable_key, "review_table")),
        "source_signature": source_signature,
        "analysis_start": pd.Timestamp(analysis_start),
        "analysis_end": pd.Timestamp(analysis_end),
        "qc_token": qc_token,
    }
    st.session_state[_state_key(variable_key, "qc_confirmed")] = True
    st.session_state.pop(_state_key(variable_key, "confirmation_invalid_reason"), None)
    clear_variable_result_caches(st.session_state, variable_key)


def _confirmed_asset_status(variable_key, upload, enable_range, enable_hampel, enable_constant, current_context=None):
    def invalidate(reason):
        st.session_state[_state_key(variable_key, "qc_confirmed")] = False
        st.session_state[_state_key(variable_key, "confirmation_invalid_reason")] = reason
        clear_variable_result_caches(st.session_state, variable_key)
        return None, reason

    asset = st.session_state.get(_state_key(variable_key, "confirmed_qc_assets"))
    if not asset:
        return None, "仅自动质控"
    if summarize_candidate_decisions(asset.get("review_table"))["candidate_undecided_count"]:
        return invalidate("存在未完成判定的候选记录，需重新确认")
    try:
        source_signature = _source_args(variable_key, upload)["source_signature"]
    except (FileNotFoundError, ValueError):
        return invalidate("未提供")
    if asset.get("source_signature") != source_signature:
        return invalidate("数据源已变化，需重新确认")
    analysis_start = asset.get("analysis_start")
    analysis_end = asset.get("analysis_end")
    if current_context is not None and variable_key == current_context["variable_key"]:
        if pd.Timestamp(analysis_start) != pd.Timestamp(current_context["analysis_start"]) or pd.Timestamp(analysis_end) != pd.Timestamp(current_context["analysis_end"]):
            return invalidate("时间范围已变化，需重新确认")
        expected_token = current_context["qc_token"]
    else:
        expected_token = _build_qc_token(variable_key, source_signature, analysis_start, analysis_end, enable_range, enable_hampel, enable_constant)
    if asset.get("qc_token") != expected_token:
        return invalidate("自动质控规则已变化，需重新确认")
    if not asset.get("qc_confirmed") or asset.get("final_qc_data") is None or asset.get("qc_summary") is None:
        return None, "仅自动质控"
    return asset, "已人工确认"


def _collect_confirmed_qc_assets(uploads, enable_range, enable_hampel, enable_constant, current_context=None):
    assets, statuses = {}, {}
    for variable_key, upload in uploads.items():
        asset, status = _confirmed_asset_status(variable_key, upload, enable_range, enable_hampel, enable_constant, current_context)
        if asset is not None:
            assets[variable_key] = asset
        statuses[variable_key] = status
    return assets, statuses


@st.cache_data(show_spinner=False)
def _cached_load_excel(variable_key, source_signature, source_path, uploaded_bytes, uploaded_suffix):
    if uploaded_bytes is None:
        return load_excel_variable(source_path, variable_key)
    tmp_path = None
    with NamedTemporaryFile(delete=False, suffix=uploaded_suffix) as tmp:
        tmp.write(uploaded_bytes)
        tmp_path = Path(tmp.name)
    try:
        return load_excel_variable(tmp_path, variable_key)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


@st.cache_data(show_spinner=False)
def _cached_filter_raw(variable_key, source_signature, source_path, uploaded_bytes, uploaded_suffix, start_iso, end_iso):
    raw = _cached_load_excel(variable_key, source_signature, source_path, uploaded_bytes, uploaded_suffix)
    start_ts = pd.Timestamp(start_iso)
    end_ts = pd.Timestamp(end_iso)
    filtered = raw[(raw["datetime"] >= start_ts) & (raw["datetime"] <= end_ts)].reset_index(drop=True)
    filtered = ensure_record_id(filtered)
    metadata = get_variable_metadata(variable_key)
    filtered.attrs.update({"variable_key": variable_key, "unit": metadata["unit"]})
    return filtered


@st.cache_data(show_spinner=False)
def _cached_auto_qc_assets(variable_key, source_signature, source_path, uploaded_bytes, uploaded_suffix, start_iso, end_iso, enable_range, enable_hampel, enable_constant, qc_params_key):
    raw = _cached_filter_raw(variable_key, source_signature, source_path, uploaded_bytes, uploaded_suffix, start_iso, end_iso)
    metadata = get_variable_metadata(variable_key)
    auto_qc_data, qc_summary, qc_log = apply_quality_control(
        raw,
        metadata,
        enable_intraday_2std=False,
        enable_valid_range=enable_range,
        enable_hampel=enable_hampel,
        enable_constant_value=enable_constant,
    )
    review_table = _enforce_physical_range_hard_rule(build_qc_review_table(raw, auto_qc_data, qc_log))
    return raw, auto_qc_data, qc_summary, qc_log, review_table


def _get_auto_qc_assets(variable_key, source_args, start_ts, end_ts, enable_range, enable_hampel, enable_constant):
    return _cached_auto_qc_assets(
        variable_key,
        source_args["source_signature"],
        source_args["source_path"],
        source_args["uploaded_bytes"],
        source_args["uploaded_suffix"],
        pd.Timestamp(start_ts).isoformat(),
        pd.Timestamp(end_ts).isoformat(),
        enable_range,
        enable_hampel,
        enable_constant,
        _qc_params_key(variable_key),
    )


def _display_table(table):
    return table.rename(columns={key: value for key, value in COLUMN_LABELS.items() if key in table.columns})


def _editor_column_config():
    return {
        "record_id": st.column_config.TextColumn(COLUMN_LABELS["record_id"]),
        "datetime": st.column_config.DatetimeColumn(COLUMN_LABELS["datetime"]),
        "original_value": st.column_config.NumberColumn(COLUMN_LABELS["original_value"]),
        "existing_rule": st.column_config.TextColumn(COLUMN_LABELS["existing_rule"]),
        "algorithm_flag": st.column_config.TextColumn(COLUMN_LABELS["algorithm_flag"]),
        "current_qc_value": st.column_config.NumberColumn(COLUMN_LABELS["current_qc_value"]),
        "user_decision": st.column_config.SelectboxColumn(COLUMN_LABELS["user_decision"], options=REVIEW_DECISIONS, required=True),
    }


def _enforce_physical_range_hard_rule(table):
    result = table.copy()
    physical_mask = _automatic_remove_mask(result)
    result.loc[physical_mask, "user_decision"] = "remove"
    return result


def _apply_batch_decision(table, rule, decision):
    result = table.copy()
    mask = result["existing_rule"].fillna("").str.contains(rule)
    result.loc[mask, "user_decision"] = decision
    return _enforce_physical_range_hard_rule(result)


def _apply_range_decision(table, start_ts, end_ts, decision):
    result = table.copy()
    mask = (result["datetime"] >= start_ts) & (result["datetime"] <= end_ts)
    physical_mask = _automatic_remove_mask(result)
    if decision in {"manual_keep", "keep", "undecided"}:
        mask = mask & ~physical_mask
    result.loc[mask, "user_decision"] = decision
    return _enforce_physical_range_hard_rule(result)


def _update_review_table(global_table, edited_range_table):
    result = global_table.copy()
    edited = edited_range_table[["record_id", "user_decision"]].copy()
    edited["record_id"] = edited["record_id"].astype(str)
    edited = edited.drop_duplicates("record_id", keep="last")
    updates = edited.set_index("record_id")["user_decision"].to_dict()
    mask = result["record_id"].astype(str).isin(updates.keys())
    result.loc[mask, "user_decision"] = result.loc[mask, "record_id"].astype(str).map(updates)
    return _enforce_physical_range_hard_rule(result)


def _range_decisions_changed(before, after):
    before_cmp = before[["record_id", "user_decision"]].copy()
    after_cmp = after[["record_id", "user_decision"]].copy()
    before_cmp["record_id"] = before_cmp["record_id"].astype(str)
    after_cmp["record_id"] = after_cmp["record_id"].astype(str)
    before_cmp = before_cmp.sort_values("record_id").reset_index(drop=True)
    after_cmp = after_cmp.sort_values("record_id").reset_index(drop=True)
    return not before_cmp.equals(after_cmp)


def _selected_record_ids(plot_event):
    if not plot_event:
        return []
    selection = plot_event.get("selection") if isinstance(plot_event, dict) else getattr(plot_event, "selection", None)
    if not selection:
        return []
    points = selection.get("points", []) if isinstance(selection, dict) else getattr(selection, "points", [])
    ids = []
    for point in points:
        customdata = point.get("customdata") if isinstance(point, dict) else getattr(point, "customdata", None)
        if customdata is not None and len(customdata) > 0:
            ids.append(str(customdata[0]))
    return sorted(set(ids))


def _apply_selected_decision(table, record_ids, decision):
    result = table.copy()
    if not record_ids:
        return _enforce_physical_range_hard_rule(result)
    mask = result["record_id"].astype(str).isin([str(item) for item in record_ids])
    physical_mask = _automatic_remove_mask(result)
    if decision == "remove":
        algorithm_mask = mask & result["algorithm_flag"].astype(str).ne("")
        ordinary_mask = mask & ~algorithm_mask & ~physical_mask
        result.loc[algorithm_mask, "user_decision"] = "remove"
        result.loc[ordinary_mask, "user_decision"] = "manual_remove"
        result.loc[mask & physical_mask, "user_decision"] = "remove"
    elif decision == "keep":
        algorithm_mask = mask & result["algorithm_flag"].astype(str).ne("")
        ordinary_mask = mask & ~physical_mask
        result.loc[algorithm_mask | ordinary_mask, "user_decision"] = "keep"
    elif decision == "manual_keep":
        result.loc[mask & ~physical_mask, "user_decision"] = "manual_keep"
    return _enforce_physical_range_hard_rule(result)


def _set_selected_decision(decision):
    table = st.session_state.get(_current_state_key("review_table"))
    ids = st.session_state.get(_current_state_key("selected_record_ids"), [])
    if table is not None:
        st.session_state[_current_state_key("review_table")] = _apply_selected_decision(table, ids, decision)
        st.session_state[_current_state_key("qc_confirmed")] = False
        clear_variable_result_caches(st.session_state, st.session_state.get("current_variable_key", ""))


def _clear_selection():
    st.session_state[_current_state_key("selected_record_ids")] = []


def _set_range_decision(start_ts, end_ts, decision):
    table = st.session_state.get(_current_state_key("review_table"))
    if table is not None:
        st.session_state[_current_state_key("review_table")] = _apply_range_decision(table, start_ts, end_ts, decision)
        st.session_state[_current_state_key("qc_confirmed")] = False
        clear_variable_result_caches(st.session_state, st.session_state.get("current_variable_key", ""))


def _excel_bytes(sheets):
    output = BytesIO()
    with pd.ExcelWriter(output) as writer:
        for sheet_name, table in sheets.items():
            table.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    output.seek(0)
    return output.getvalue()


def _summary_workbook_bytes(variable_keys, confirmed_qc_assets, progress):
    """Build the formal station workbook from confirmed final-QC assets only."""
    require_station_export(progress, confirmed_qc_assets, variable_keys)
    all_rows, all_qc, all_metrics, all_logs = [], {}, {}, []
    processing_rows = []
    for key in variable_keys:
        metadata = get_variable_metadata(key)
        confirmed = confirmed_qc_assets[key]
        final_qc = confirmed["final_qc_data"]
        qc_summary = confirmed["qc_summary"]
        final_log = confirmed.get("final_qc_log")
        status = {
            "variable_key": key,
            "display_name_cn": metadata.get("display_name_cn", key),
            "data_source": "用户上传文件",
            "start_time": final_qc["datetime"].min(),
            "end_time": final_qc["datetime"].max(),
            "auto_qc_completed": True,
            "manual_qc_confirmed": True,
            "processing_status": "processed",
            "note": "使用该变量已人工确认的 final_qc_data",
        }
        resampled, anomaly, metrics, row = _run_after_qc(key, final_qc, qc_summary)
        all_rows.append(row)
        all_qc[key] = qc_summary
        all_metrics[key] = metrics
        if final_log is not None:
            all_logs.append(final_log)
        processing_rows.append(status)
    combined_log = pd.concat(all_logs, ignore_index=True) if all_logs else None
    sheets = build_summary_workbook_sheets(
        all_rows,
        all_qc,
        all_metrics,
        combined_log,
        processing_status=pd.DataFrame(processing_rows),
    )
    return _excel_bytes(sheets)

def _health_table(raw, qc_summary, final_qc_data=None):
    final_valid = None if final_qc_data is None else int(final_qc_data["value"].notna().sum())
    return pd.DataFrame([{
        "原始记录数": qc_summary["raw_count"],
        "原始缺测数": qc_summary["missing_before_qc"],
        "时间范围": f"{raw['datetime'].min()} 至 {raw['datetime'].max()}",
        "重复时间数量": int(raw["datetime"].duplicated().sum()),
        "传感器 0 值自动删除数": qc_summary.get("removed_by_sensor_zero", 0),
        "硬范围自动删除数": qc_summary["removed_by_range"],
        "Hampel 候选数": qc_summary["flagged_by_hampel"],
        "恒定值候选数": qc_summary["flagged_by_constant_value"],
        "自动应用数量": qc_summary["applied_flagged_count"],
        "最终有效记录数": final_valid,
    }])


COLUMN_LABELS = {
    "record_id": "记录ID",
    "datetime": "时间",
    "variable": "变量",
    "original_value": "原始值",
    "current_qc_value": "当前质控值",
    "qc_value": "质控后值",
    "existing_rule": "已有规则",
    "algorithm_flag": "算法标记",
    "user_decision": "用户决定",
    "rule": "规则",
    "reason": "原因",
    "is_flagged": "是否标记",
    "is_applied": "是否应用",
    "parameter": "参数",
    "decision_source": "决定来源",
    "display_name_cn": "中文名称",
    "unit": "单位",
    "start_time": "开始时间",
    "end_time": "结束时间",
    "raw_count": "原始记录数",
    "count": "统计记录数",
    "valid_count": "有效记录数",
    "missing_count": "缺测数",
    "missing_count_after_qc": "质控后缺测数",
    "mean": "平均值",
    "max": "最大值",
    "min": "最小值",
    "median": "中位数",
    "std": "标准差",
    "date": "日期",
    "daily_range": "日变化幅度",
    "max_daily_range": "最大日变化幅度",
    "year_month": "年月",
    "monthly_mean": "月平均",
    "monthly_std": "月标准差",
}


def _decision_summary(review_table, final_qc_data, auto_qc_data, qc_summary):
    user_removed = review_table["user_decision"].isin(["remove", "manual_remove"]) & ~_automatic_remove_mask(review_table)
    candidate = summarize_candidate_decisions(review_table)
    return {
        "原始缺测数": int(qc_summary["missing_before_qc"]),
        "传感器 0 值自动删除数": int(qc_summary.get("removed_by_sensor_zero", 0)),
        "硬范围自动删除数": int(qc_summary["removed_by_range"]),
        "Hampel 候选数": int(qc_summary["flagged_by_hampel"]),
        "恒定值候选数": int(qc_summary["flagged_by_constant_value"]),
        "人工删除数": int(user_removed.sum()),
        "最终缺测数": int(final_qc_data["value"].isna().sum()),
        "最终有效记录数": int(final_qc_data["value"].notna().sum()),
        "唯一候选记录数": candidate["unique_candidate_count"], "候选删除数": candidate["candidate_removed_count"], "候选保留数": candidate["candidate_kept_count"], "候选未决定数": candidate["candidate_undecided_count"], "人工补充删除数": candidate["manual_extra_removed_count"],
    }


def _create_auto_rule_comparison_figure(raw, auto_qc_data, variable_key):
    metadata = get_variable_metadata(variable_key)
    name = metadata.get("display_name_cn", variable_key)
    unit = metadata.get("unit", "")
    fig = make_subplots(rows=1, cols=2, subplot_titles=("原始时序", "仅应用传感器无效值和 hard_range 后时序"), shared_xaxes=True, shared_yaxes=True)
    fig.add_trace(go.Scattergl(x=raw["datetime"], y=raw["value"], mode="lines", name="原始时序", line={"color": "#1f77b4", "width": 1}), row=1, col=1)
    fig.add_trace(go.Scattergl(x=auto_qc_data["datetime"], y=auto_qc_data["value"], mode="lines", name="自动规则后", line={"color": "#d62728", "width": 1}), row=1, col=2)
    y_values = raw["value"].dropna()
    if not y_values.empty:
        y_min, y_max = y_values.min(), y_values.max()
        margin = max((y_max - y_min) * 0.05, 1e-6)
        fig.update_yaxes(range=[y_min - margin, y_max + margin])
    fig.update_layout(title=f"{name}自动规则前后对比", yaxis_title=f"{name}({unit})", hovermode="x unified", margin={"l": 50, "r": 20, "t": 60, "b": 40})
    fig.update_xaxes(title_text="日期", tickformat="%Y/%m/%d")
    return fig


def _create_hourly_daily_figure(hourly, daily, variable_key):
    metadata = get_variable_metadata(variable_key)
    name = metadata.get("display_name_cn", variable_key)
    unit = metadata.get("unit", "")
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=hourly["datetime"], y=hourly["value"], mode="lines", name="小时平均", line={"color": "#1f77b4", "width": 0.7}, opacity=0.35))
    fig.add_trace(go.Scattergl(x=daily["datetime"], y=daily["value"], mode="lines", name="日平均", line={"color": "#ff3333", "width": 2.2}))
    fig.update_layout(title=f"{name}小时平均与日平均", xaxis_title="日期", yaxis_title=f"{name}({unit})", hovermode="x unified")
    fig.update_xaxes(tickformat="%Y/%m/%d")
    return fig


def _create_anomaly_figure(anomaly, variable_key):
    metadata = get_variable_metadata(variable_key)
    name = metadata.get("display_name_cn", variable_key)
    unit = metadata.get("unit", "")
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=anomaly["datetime"], y=anomaly["anomaly"], mode="lines", name="日内距平", line={"color": "#1f77b4", "width": 1}))
    fig.add_hline(y=0, line_color="#333333", line_width=1)
    fig.update_layout(title=f"{name}日内距平", xaxis_title="日期", yaxis_title=f"{name}距平({unit})", hovermode="x unified")
    fig.update_xaxes(tickformat="%Y/%m/%d")
    return fig


def _create_monthly_statistics_figure(monthly, variable_key):
    metadata = get_variable_metadata(variable_key)
    name = metadata.get("display_name_cn", variable_key)
    unit = metadata.get("unit", "")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=monthly["year_month"].astype(str),
            y=monthly["monthly_mean"],
            mode="lines+markers",
            name="月平均",
            error_y={"type": "data", "array": monthly["monthly_std"], "visible": True},
            line={"color": "#1f77b4", "width": 2},
        )
    )
    fig.update_layout(
        title=f"{name}月平均和月标准差",
        xaxis_title="年月",
        yaxis_title=f"{name}({unit})",
        hovermode="x unified",
    )
    return fig


def _run_after_qc(variable_key, final_qc_data, qc_summary):
    metadata = get_variable_metadata(variable_key)
    resampled = resample_configured(final_qc_data, metadata)
    anomaly = calculate_configured_anomaly(resampled, metadata)
    metric_source = resampled["hourly"]
    metrics = calculate_metrics(
        variable_key,
        metric_source,
        resampled["daily"],
        anomaly,
        metadata=metadata,
        base_data=metric_source,
    )
    basic_row = build_basic_statistics_row(variable_key, metric_source, metrics, qc_summary)
    return resampled, anomaly, metrics, basic_row


def _safe_report_filename(value):
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value)).strip(" ._")
    return f"{safe or '当前变量详细报告'}.docx"


def _refresh_station_report_title():
    """Keep the composite title automatic until the user edits it."""
    title_key = "station_task:report_title"
    old_auto = st.session_state.get("station_task:last_auto_title", "")
    new_auto = default_station_report_title(st.session_state.get("station_task:site_name", ""))
    if not st.session_state.get(title_key) or st.session_state.get(title_key) == old_auto:
        st.session_state[title_key] = new_auto
    st.session_state["station_task:last_auto_title"] = new_auto


def _render_station_task_info(variable_keys):
    st.header("站点任务信息")
    if "station_task:report_title" not in st.session_state:
        _refresh_station_report_title()
    c1, c2 = st.columns(2)
    site_name = c1.text_input("站点名称 *", key="station_task:site_name", on_change=_refresh_station_report_title)
    project_name = c2.text_input("项目名称", key="station_task:project_name")
    c3, c4 = st.columns(2)
    department = c3.text_input("编制部门", key="station_task:department")
    author = c4.text_input("编制人", key="station_task:author")
    report_title = st.text_input("站点综合报告标题", key="station_task:report_title")
    info = {
        "site_name": site_name,
        "project_name": project_name,
        "department": department,
        "author": author,
        "report_title": report_title,
    }
    signature = station_info_signature(info)
    previous = st.session_state.get("station_task:info_signature")
    if previous is not None and previous != signature:
        clear_all_variable_report_caches(st.session_state, variable_keys)
        clear_station_export_caches(st.session_state)
    st.session_state["station_task:info_signature"] = signature
    return info


def _station_source_states(uploads):
    """Probe actual uploaded files for the status table; never use defaults."""
    states = {}
    for variable_key, upload in uploads.items():
        if upload is None:
            states[variable_key] = {"provided": False}
            continue
        try:
            args = _source_args(variable_key, upload)
            raw = _cached_load_excel(
                variable_key, args["source_signature"], args["source_path"],
                args["uploaded_bytes"], args["uploaded_suffix"],
            )
            states[variable_key] = {
                "provided": True,
                "read_success": True,
                "start_time": raw["datetime"].min() if not raw.empty else None,
                "end_time": raw["datetime"].max() if not raw.empty else None,
                "raw_count": len(raw),
            }
        except Exception as exc:
            states[variable_key] = {"provided": True, "read_error": str(exc)}
    return states


def _render_station_task_completion(variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info, current_context=None):
    confirmed_assets, confirmation_statuses = _collect_confirmed_qc_assets(
        uploads, enable_range, enable_hampel, enable_constant, current_context,
    )
    source_states = _station_source_states(uploads)
    for variable_key, source in source_states.items():
        if source.get("read_success") and variable_key not in confirmed_assets and _state_key(variable_key, "auto_qc_data") not in st.session_state:
            confirmation_statuses[variable_key] = "未处理"
    table, progress = build_station_task_status(
        variable_keys,
        {key: get_variable_metadata(key) for key in variable_keys},
        source_states,
        confirmed_assets,
        confirmation_statuses,
        station_info,
    )
    st.subheader("站点任务完成状态")
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.write(f"已上传变量数：{progress['已上传变量数']} / {progress['变量总数']}；已确认变量数：{progress['已确认变量数']}；可导出变量数：{progress['可导出变量数']}")
    if progress["阻断项"]:
        st.warning("站点综合导出阻断项：\n\n- " + "\n- ".join(progress["阻断项"]))
    else:
        st.success("九个变量均已人工确认，站点综合 Excel 将全部使用 final_qc_data。")
    st.subheader("站点综合导出")
    export_key = "station_task:summary_excel_bytes"
    if st.button("生成站点综合 Excel", disabled=not progress["可生成站点综合 Excel"]):
        st.session_state[export_key] = _summary_workbook_bytes(variable_keys, confirmed_assets, progress)
    if export_key in st.session_state and progress["可生成站点综合 Excel"]:
        st.download_button("下载 summary_statistics.xlsx", st.session_state[export_key], "summary_statistics.xlsx")
    word_key = "station_task:station_word_report_bytes"
    if st.button("生成站点综合 Word", disabled=not progress["可生成站点综合 Excel"]):
        try:
            context = build_station_report_context(variable_keys, confirmed_assets, progress, station_info)
            st.session_state[word_key] = generate_station_word_report(context)
            st.session_state["station_task:station_word_report_filename"] = _safe_report_filename(station_info.get("report_title", "站点环境监测综合报告"))
        except Exception as exc:
            st.error(f"站点综合 Word 生成失败：{exc}")
    if word_key in st.session_state and progress["可生成站点综合 Excel"]:
        st.download_button("下载站点综合 Word", st.session_state[word_key], st.session_state.get("station_task:station_word_report_filename", "站点环境监测综合报告.docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def _render_single_variable_report_entry(
    variable_key, uploaded_file, enable_range, enable_hampel, enable_constant,
    current_context, raw, resampled, anomaly, metrics, station_info,
):
    """Render the small report entry point after analysis, keeping generation out of app.py."""
    st.subheader("当前变量详细报告")
    confirmed, status = _confirmed_asset_status(
        variable_key, uploaded_file, enable_range, enable_hampel, enable_constant, current_context,
    )
    if confirmed is None:
        st.info("请先完成当前变量的人工确认，再生成详细 Word 报告。")
        return
    metadata = get_variable_metadata(variable_key)
    report_title = f"{station_info.get('site_name', '').strip()} {metadata.get('display_name_cn', variable_key)}监测数据质控与统计分析报告".strip()
    report_key = _state_key(variable_key, "word_report_bytes")
    if st.button("生成当前变量详细报告", key=_state_key(variable_key, "generate_word_report")):
        try:
            context = build_report_context(
                variable_key=variable_key, raw_data=raw,
                final_qc_data=confirmed["final_qc_data"], final_qc_log=confirmed.get("final_qc_log"),
                qc_summary=confirmed["qc_summary"], review_table=confirmed.get("review_table"),
                resampled=resampled, anomaly=anomaly, metrics=metrics,
                qc_token=current_context["qc_token"], confirmed_qc_token=confirmed.get("qc_token"),
                project_name=station_info.get("site_name", ""), project_title=station_info.get("project_name", ""),
                report_title=report_title, organization=station_info.get("department", ""), author=station_info.get("author", ""),
            )
            st.session_state[report_key] = generate_single_variable_report(context)
            st.session_state[_state_key(variable_key, "word_report_filename")] = _safe_report_filename(context["project_info"]["report_title"])
            st.success("当前变量详细 Word 报告已生成。")
        except Exception as exc:
            st.error(f"报告生成失败：{exc}")
    if report_key in st.session_state:
        st.download_button("下载 Word 报告", st.session_state[report_key], st.session_state.get(_state_key(variable_key, "word_report_filename"), "当前变量详细报告.docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def main():
    st.set_page_config(page_title="环境监测数据质控与分析工具", layout="wide")
    st.title("环境监测数据质控与分析工具")
    st.caption("当前开发版本：V4.2 站点任务版")
    st.caption("自动规则先处理；算法候选和人工质控在同一复核区完成。后续分析只使用 final_qc_data。")

    variable_keys = list(list_enabled_variables())
    station_info = _render_station_task_info(variable_keys)
    st.header("九变量上传")
    uploads = {}
    for key in variable_keys:
        metadata = get_variable_metadata(key)
        label = f"上传{metadata.get('display_name_cn', key)} Excel"
        uploads[key] = st.sidebar.file_uploader(label, type=["xls", "xlsx"], key=f"{key}_upload")
    variable_key = st.sidebar.selectbox("变量选择", variable_keys, format_func=lambda x: get_variable_metadata(x)["display_name_cn"])
    st.session_state["current_variable_key"] = variable_key
    enable_range = st.sidebar.checkbox("启用物理合理范围质控（自动删除）", value=True)
    enable_hampel = st.sidebar.checkbox("启用 Hampel 候选标记（仅标记）", value=True)
    enable_constant = st.sidebar.checkbox("启用连续恒定值标记（仅标记）", value=True)

    uploaded = uploads.get(variable_key)
    st.header("当前变量质控与分析")
    if uploaded is None:
        st.info("当前变量未提供上传文件，不会读取本地默认测试数据。")
        _render_station_task_completion(
            variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info,
        )
        return
    source_args = _source_args(variable_key, uploaded)
    st.info(f"当前数据源：{_source_label(variable_key, uploaded)}")

    try:
        preview = _cached_load_excel(variable_key, source_args["source_signature"], source_args["source_path"], source_args["uploaded_bytes"], source_args["uploaded_suffix"])
        min_date = preview["datetime"].min().date()
        max_date = preview["datetime"].max().date()
        date_range = st.sidebar.date_input("分析时间范围", value=(min_date, max_date), min_value=min_date, max_value=max_date)
        if len(date_range) != 2:
            st.warning("请选择完整的开始和结束日期。")
            _render_station_task_completion(
                variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info,
            )
            return

        start_ts = pd.Timestamp(date_range[0])
        end_ts = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        token = _build_qc_token(
            variable_key,
            source_args["source_signature"],
            start_ts,
            end_ts,
            enable_range,
            enable_hampel,
            enable_constant,
        )
        current_context = {
            "variable_key": variable_key,
            "analysis_start": start_ts,
            "analysis_end": end_ts,
            "qc_token": token,
        }
        if st.session_state.get(_state_key(variable_key, "qc_token")) != token:
            if st.session_state.get(_state_key(variable_key, "confirmed_qc_assets")):
                st.session_state[_state_key(variable_key, "confirmation_invalid_reason")] = "自动质控规则、数据源或时间范围已变化，请重新确认该变量。"
            st.session_state[_state_key(variable_key, "qc_token")] = token
            st.session_state[_state_key(variable_key, "qc_confirmed")] = False
            st.session_state[_state_key(variable_key, "review_table")] = None
            st.session_state[_state_key(variable_key, "selected_record_ids")] = []
            st.session_state.pop(_state_key(variable_key, "qc_log_excel_bytes"), None)
            st.session_state.pop(_state_key(variable_key, "summary_excel_bytes"), None)
            clear_variable_result_caches(st.session_state, variable_key)

        raw, auto_qc_data, qc_summary, qc_log, initial_review_table = _get_auto_qc_assets(variable_key, source_args, start_ts, end_ts, enable_range, enable_hampel, enable_constant)
        if raw.empty:
            st.warning("当前时间范围内没有数据。")
            _render_station_task_completion(
                variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info, current_context,
            )
            return

        st.session_state[_state_key(variable_key, "raw_data")] = raw
        st.session_state[_state_key(variable_key, "auto_qc_data")] = auto_qc_data
        st.session_state[_state_key(variable_key, "qc_log")] = qc_log
        st.session_state[_state_key(variable_key, "qc_summary")] = qc_summary
        st.session_state[_state_key(variable_key, "source_signature")] = source_args["source_signature"]
        st.session_state[_state_key(variable_key, "analysis_start")] = start_ts
        st.session_state[_state_key(variable_key, "analysis_end")] = end_ts
        if st.session_state.get(_state_key(variable_key, "review_table")) is None:
            st.session_state[_state_key(variable_key, "review_table")] = initial_review_table.copy()

        st.header("第一步：自动规则")
        st.dataframe(_display_table(_health_table(raw, qc_summary)), use_container_width=True)
        st.caption("该对比仅展示传感器无效值和 hard_range 自动删除结果，不应用 Hampel、constant_value 或人工决策。")
        st.plotly_chart(_create_auto_rule_comparison_figure(raw, auto_qc_data, variable_key), use_container_width=True)

        st.header("第二步：候选异常确认与人工补充质控")
        review_table = _enforce_physical_range_hard_rule(st.session_state[_state_key(variable_key, "review_table")])
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("全部 Hampel 删除"):
            review_table = _apply_batch_decision(review_table, "hampel", "remove")
            st.session_state[_state_key(variable_key, "qc_confirmed")] = False
            clear_variable_result_caches(st.session_state, variable_key)
        if c2.button("全部 Hampel 保留"):
            review_table = _apply_batch_decision(review_table, "hampel", "keep")
            st.session_state[_state_key(variable_key, "qc_confirmed")] = False
            clear_variable_result_caches(st.session_state, variable_key)
        if c3.button("全部恒定值删除"):
            review_table = _apply_batch_decision(review_table, "constant_value", "remove")
            st.session_state[_state_key(variable_key, "qc_confirmed")] = False
            clear_variable_result_caches(st.session_state, variable_key)
        if c4.button("全部恒定值保留"):
            review_table = _apply_batch_decision(review_table, "constant_value", "keep")
            st.session_state[_state_key(variable_key, "qc_confirmed")] = False
            clear_variable_result_caches(st.session_state, variable_key)
        st.session_state[_state_key(variable_key, "review_table")] = review_table

        final_qc_data, final_qc_log = apply_review_table_decisions(raw, auto_qc_data, qc_log, review_table)
        st.session_state[_state_key(variable_key, "final_qc_data")] = final_qc_data
        st.session_state[_state_key(variable_key, "final_qc_log")] = final_qc_log
        summary_counts = _decision_summary(review_table, final_qc_data, auto_qc_data, qc_summary)
        st.dataframe(pd.DataFrame([summary_counts]), use_container_width=True)

        st.subheader("人工检查时间范围")
        raw_min = raw["datetime"].min()
        raw_max = raw["datetime"].max()
        default_start = raw_min
        default_end = min(raw_min + pd.Timedelta(days=7), raw_max)
        r1, r2 = st.columns(2)
        with r1:
            check_start_date = st.date_input("开始日期", value=default_start.date(), min_value=raw_min.date(), max_value=raw_max.date(), key=f"{variable_key}_check_start_date")
            check_start_time = st.time_input("开始时间", value=default_start.time().replace(microsecond=0), key=f"{variable_key}_check_start_time")
        with r2:
            check_end_date = st.date_input("结束日期", value=default_end.date(), min_value=raw_min.date(), max_value=raw_max.date(), key=f"{variable_key}_check_end_date")
            check_end_time = st.time_input("结束时间", value=default_end.time().replace(microsecond=0), key=f"{variable_key}_check_end_time")
        check_start = pd.Timestamp.combine(check_start_date, check_start_time)
        check_end = pd.Timestamp.combine(check_end_date, check_end_time)
        if check_start > check_end:
            st.warning("人工检查开始时间不能晚于结束时间。")
            _render_station_task_completion(
                variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info, current_context,
            )
            return
        b1, b2 = st.columns(2)
        b1.button("当前时间范围全部删除", on_click=_set_range_decision, args=(check_start, check_end, "manual_remove"))
        b2.button("当前时间范围全部恢复为原始状态", on_click=_set_range_decision, args=(check_start, check_end, "manual_keep"))

        range_mask = (review_table["datetime"] >= check_start) & (review_table["datetime"] <= check_end)
        selectable_raw = raw.loc[raw["record_id"].astype(str).isin(review_table.loc[range_mask, "record_id"].astype(str))].copy()

        st.caption("左图：背景线已下采样，候选异常完整显示，当前人工检查时间范围内的原始点可点选、框选和套索选择。右图：final_qc_data 实时预览。")
        left, right = st.columns(2)
        with left:
            selected_event = st.plotly_chart(
                create_qc_candidate_figure(raw, qc_log, review_table, variable_key, selectable_raw_df=selectable_raw),
                use_container_width=True,
                on_select="rerun",
                selection_mode=["points", "box", "lasso"],
                key=f"{variable_key}_candidate_plot",
            )
        with right:
            st.plotly_chart(
                create_final_qc_figure(final_qc_data, raw, variable_key, summary_counts["最终缺测数"], summary_counts["最终有效记录数"]),
                use_container_width=True,
                key=f"{variable_key}_final_plot",
            )

        selected_ids = _selected_record_ids(selected_event)
        if selected_ids:
            st.session_state[_state_key(variable_key, "selected_record_ids")] = selected_ids
        selected_ids = st.session_state.get(_state_key(variable_key, "selected_record_ids"), [])
        selected_table = review_table[review_table["record_id"].astype(str).isin(selected_ids)].copy()
        st.subheader("已选择的数据点")
        st.dataframe(_display_table(selected_table), use_container_width=True)
        s1, s2, s3, s4 = st.columns(4)
        s1.button("删除选中点", disabled=not selected_ids, on_click=_set_selected_decision, args=("remove",))
        s2.button("保留选中点", disabled=not selected_ids, on_click=_set_selected_decision, args=("keep",))
        s3.button("恢复选中点", disabled=not selected_ids, on_click=_set_selected_decision, args=("manual_keep",))
        s4.button("清除当前选择", disabled=not selected_ids, on_click=_clear_selection)

        range_table = review_table.loc[range_mask].copy()
        st.subheader("当前时间范围逐点编辑表")
        st.caption(f"当前表格仅显示 {check_start} 至 {check_end}，共 {len(range_table)} 条记录。")
        edited_range = st.data_editor(
            range_table,
            use_container_width=True,
            hide_index=True,
            height=320,
            column_config=_editor_column_config(),
            disabled=["record_id", "datetime", "original_value", "existing_rule", "algorithm_flag", "current_qc_value"],
            key=f"{variable_key}_review_editor",
        )
        if _range_decisions_changed(range_table, edited_range):
            st.session_state[_state_key(variable_key, "review_table")] = _update_review_table(review_table, edited_range)
            st.session_state[_state_key(variable_key, "qc_confirmed")] = False
            clear_variable_result_caches(st.session_state, variable_key)
            st.rerun()

        st.subheader("最终质控日志")
        final_log_table = build_qc_log_table(final_qc_log)
        rule_options = ["全部"] + sorted(final_log_table["rule"].dropna().unique().tolist()) if not final_log_table.empty else ["全部"]
        selected_rule = st.selectbox("按规则筛选最终日志", rule_options)
        shown_log = final_log_table if selected_rule == "全部" else final_log_table[final_log_table["rule"] == selected_rule]
        st.dataframe(_display_table(shown_log), use_container_width=True)
        if st.button("生成 QC 日志 Excel"):
            st.session_state[_state_key(variable_key, "qc_log_excel_bytes")] = _excel_bytes({"qc_log": final_log_table})
        if _state_key(variable_key, "qc_log_excel_bytes") in st.session_state:
            st.download_button("下载 QC 日志 Excel", st.session_state[_state_key(variable_key, "qc_log_excel_bytes")], "final_qc_log.xlsx")

        if st.button("确认最终质控结果"):
            try:
                _save_confirmed_qc_assets(variable_key, source_args["source_signature"], start_ts, end_ts, token)
            except ValueError as exc:
                st.warning(str(exc))
        if not st.session_state.get(_state_key(variable_key, "qc_confirmed"), False):
            st.info("请先确认最终质控结果，再进入重采样、统计、绘图和导出。")
            _render_station_task_completion(
                variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info, current_context,
            )
            return

        st.header("分析结果")
        resampled, anomaly, metrics, basic_row = _run_after_qc(variable_key, final_qc_data, qc_summary)
        hourly = resampled["hourly"]
        daily = resampled["daily"]
        st.write(f"小时平均数据条数：{len(hourly)}；日平均数据条数：{len(daily)}")
        basic_df = build_basic_statistics_table([basic_row])
        st.subheader("基础统计表")
        st.dataframe(_display_table(basic_df), use_container_width=True)
        st.download_button("下载当前变量统计 CSV", basic_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"), f"{variable_key}_statistics.csv", "text/csv")

        st.plotly_chart(_create_hourly_daily_figure(hourly, daily, variable_key), use_container_width=True)
        st.plotly_chart(_create_anomaly_figure(anomaly, variable_key), use_container_width=True)

        st.subheader("月平均和月标准差")
        st.dataframe(_display_table(metrics["monthly"]), use_container_width=True)
        st.plotly_chart(_create_monthly_statistics_figure(metrics["monthly"], variable_key), use_container_width=True)
        st.subheader("日变化幅度")
        st.dataframe(_display_table(metrics["daily_range"]), use_container_width=True)
        if pd.notna(metrics.get("max_daily_range")):
            st.metric("整个观测期最大日变化幅度", round(metrics["max_daily_range"], 4))

        _render_single_variable_report_entry(
            variable_key, uploads[variable_key], enable_range, enable_hampel, enable_constant,
            current_context, raw, resampled, anomaly, metrics, station_info,
        )
        _render_station_task_completion(
            variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info, current_context,
        )
        if st.session_state.get(_state_key(variable_key, "confirmation_invalid_reason")):
            st.warning(st.session_state[_state_key(variable_key, "confirmation_invalid_reason")])

    except Exception as exc:
        st.error(f"处理失败：{exc}")
        _render_station_task_completion(
            variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info,
        )


if __name__ == "__main__":
    main()
