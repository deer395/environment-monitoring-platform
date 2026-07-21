from pathlib import Path
from tempfile import NamedTemporaryFile
from io import BytesIO
from html import escape
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


def _inject_visual_styles():
    """Apply the Phase 1 visual system without changing application behaviour."""
    st.markdown(
        """
        <style>
        /* V5 Phase 1: restrained government / research / SaaS visual system. */
        :root {
            --app-navy: #123d63;
            --app-blue: #1f5f8b;
            --app-blue-soft: #eef5f9;
            --app-border: #d8e1e8;
            --app-muted: #5f6f7e;
            --app-surface: #ffffff;
            --app-success: #2f7d52;
            --app-warning: #a66a00;
            --app-danger: #a83d3d;
        }

        .stApp {
            background: #f6f8fa;
            color: #1e2c38;
        }
        .block-container {
            max-width: 1440px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        h1, h2, h3 {
            color: var(--app-navy);
            letter-spacing: 0;
        }
        h2 {
            margin-top: 2rem;
            padding-bottom: 0.55rem;
            border-bottom: 1px solid var(--app-border);
        }
        h3 {
            margin-top: 1.35rem;
            font-size: 1.1rem;
        }
        .app-hero {
            background: var(--app-surface);
            border: 1px solid var(--app-border);
            border-left: 5px solid var(--app-navy);
            border-radius: 10px;
            padding: 1.4rem 1.6rem;
            margin: 0 0 1.5rem 0;
            box-shadow: 0 2px 8px rgba(18, 61, 99, 0.05);
        }
        .app-hero__eyebrow {
            color: var(--app-blue);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            margin-bottom: 0.35rem;
        }
        .app-hero h1 {
            margin: 0;
            font-size: 2rem;
            line-height: 1.25;
        }
        .app-hero__subtitle {
            color: #425466;
            font-size: 1rem;
            margin: 0.55rem 0 1rem 0;
        }
        .app-hero__meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.65rem;
            align-items: center;
            color: var(--app-muted);
            font-size: 0.86rem;
        }
        .app-hero__task {
            background: var(--app-blue-soft);
            color: var(--app-navy);
            border-radius: 4px;
            padding: 0.32rem 0.55rem;
            font-weight: 600;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--app-border);
            border-radius: 9px;
            background: var(--app-surface);
            box-shadow: 0 1px 3px rgba(18, 61, 99, 0.035);
            padding: 0.25rem 0.45rem;
        }
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            border: 1px solid var(--app-border);
            border-radius: 7px;
            overflow: hidden;
        }
        div[data-testid="stDataFrame"] [role="columnheader"],
        div[data-testid="stDataEditor"] [role="columnheader"] {
            background: #f0f4f7;
            color: var(--app-navy);
            font-weight: 700;
        }
        div[data-testid="stAlert"] {
            border-radius: 7px;
            border-width: 1px;
        }
        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button {
            border-radius: 6px;
            min-height: 2.35rem;
            font-weight: 600;
            border-color: #b8c7d3;
        }
        div[data-testid="stButton"] > button[kind="primary"],
        div[data-testid="stDownloadButton"] > button[kind="primary"] {
            background: var(--app-navy);
            border-color: var(--app-navy);
        }
        div[data-testid="stSidebar"] {
            background: #f1f5f8;
            border-right: 1px solid var(--app-border);
        }
        div[data-testid="stSidebar"] [data-testid="stFileUploader"] {
            padding: 0.4rem;
            border: 1px solid #d5e0e8;
            border-radius: 7px;
            background: #ffffff;
            margin-bottom: 0.45rem;
        }
        .stCaption {
            color: var(--app-muted);
        }
        @media (max-width: 900px) {
            .block-container { padding: 1rem; }
            .app-hero { padding: 1.1rem; }
            .app-hero h1 { font-size: 1.55rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_product_header(variable_keys, uploads):
    """Render the visual-only product identity and live task summary."""
    site_name = escape(str(st.session_state.get("station_task:site_name", "")).strip() or "未命名站点")
    uploaded_count = sum(upload is not None for upload in uploads.values())
    st.markdown(
        f"""
        <section class="app-hero">
            <div class="app-hero__eyebrow">环境监测数据工作台</div>
            <h1>环境监测数据质控与分析工具</h1>
            <p class="app-hero__subtitle">面向环境监测数据的自动质量检查、人工复核与报告生成平台。</p>
            <div class="app-hero__meta">
                <span class="app-hero__task">当前任务：{site_name}</span>
                <span>已上传 {uploaded_count} / {len(variable_keys)} 个变量文件</span>
                <span>当前版本：V4.2</span>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_current_variable_status_card(variable_key, uploaded_file, review_table=None, station_progress=None):
    """Show existing variable-task state without changing any processing decisions."""
    metadata = get_variable_metadata(variable_key)
    variable_name = metadata.get("display_name_cn", variable_key)
    unit = metadata.get("unit", "")
    confirmed = st.session_state.get(_state_key(variable_key, "qc_confirmed"), False)
    invalid_reason = st.session_state.get(_state_key(variable_key, "confirmation_invalid_reason"))
    candidate_count = 0
    undecided_count = 0
    if review_table is not None:
        candidate_summary = summarize_candidate_decisions(review_table)
        candidate_count = candidate_summary["unique_candidate_count"]
        undecided_count = candidate_summary["candidate_undecided_count"]

    with st.container(border=True):
        st.subheader(f"当前处理变量：{variable_name}")
        st.caption(f"变量标识：{variable_key}｜单位：{unit or '未设置'}")
        file_col, check_col, review_col, result_col = st.columns(4)
        with file_col:
            if uploaded_file is None:
                st.caption("○ 文件未上传")
            else:
                st.success("文件已上传")
        with check_col:
            if review_table is None:
                st.caption("○ 自动质量检查未开始")
            else:
                st.success("自动质量检查完成")
        with review_col:
            if review_table is None:
                st.caption("○ 异常复核未开始")
            elif undecided_count:
                st.warning(f"待人工确认异常：{undecided_count} 条")
            elif candidate_count:
                st.success("异常复核已完成")
            else:
                st.success("未发现待确认异常")
        with result_col:
            if invalid_reason:
                st.error("需要重新确认")
            elif confirmed:
                st.success("质量确认已完成")
            else:
                st.caption("○ 质量确认未完成")

        if uploaded_file is None:
            st.info("下一步：请在左侧栏上传该变量的 Excel 文件。")
        elif review_table is None:
            st.info("下一步：系统正在准备自动质量检查结果。")
        elif invalid_reason:
            st.error(f"当前待办：{invalid_reason}")
        elif undecided_count:
            st.warning(f"当前待办：请在下方“异常确认与人工复核”区域完成 {undecided_count} 条异常记录的判定。")
        elif confirmed:
            st.success("当前变量已完成质量确认，可查看统计分析结果并生成变量分析报告。")
        else:
            st.info("下一步：请完成最终质量确认。")

        if station_progress is not None:
            st.markdown("**站点综合报告状态**")
            remaining_count = station_progress["变量总数"] - station_progress["已确认变量数"]
            if station_progress["可生成站点综合 Excel"]:
                st.success("九个变量均已完成质量确认，可生成站点综合报告。")
            elif remaining_count > 0:
                st.warning(f"尚有 {remaining_count} 个变量未完成质量确认，暂不可生成站点综合报告。")
            else:
                st.warning("九个变量均已完成质量确认，但仍有其他生成条件未满足。")


def _uploaded_bytes(uploaded_file):
    return uploaded_file.getvalue() if uploaded_file is not None else None


def _source_signature(variable_key, uploaded_file):
    if uploaded_file is not None:
        digest = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
        return f"upload:{variable_key}:{uploaded_file.name}:{digest}"
    raise ValueError("未上传文件")


def _source_label(variable_key, uploaded_file):
    if uploaded_file is not None:
        return f"上传文件：{uploaded_file.name}"
    return "未上传文件"


def _source_args(variable_key, uploaded_file):
    if uploaded_file is None:
        raise ValueError("未上传文件")
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
        raise ValueError(f"当前仍有 {decisions['candidate_undecided_count']} 条待人工确认异常未完成保留或删除判定，请完成复核后再确认最终质量控制结果。")
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
        return invalidate("存在待人工确认异常，需完成复核后重新确认")
    try:
        source_signature = _source_args(variable_key, upload)["source_signature"]
    except (FileNotFoundError, ValueError):
        return invalidate("未提供")
    if asset.get("source_signature") != source_signature:
        return invalidate("上传文件已变化，需重新确认")
    analysis_start = asset.get("analysis_start")
    analysis_end = asset.get("analysis_end")
    if current_context is not None and variable_key == current_context["variable_key"]:
        if pd.Timestamp(analysis_start) != pd.Timestamp(current_context["analysis_start"]) or pd.Timestamp(analysis_end) != pd.Timestamp(current_context["analysis_end"]):
            return invalidate("时间范围已变化，需重新确认")
        expected_token = current_context["qc_token"]
    else:
        expected_token = _build_qc_token(variable_key, source_signature, analysis_start, analysis_end, enable_range, enable_hampel, enable_constant)
    if asset.get("qc_token") != expected_token:
        return invalidate("质量检查规则已变化，需重新确认")
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
        "Hampel统计异常数": qc_summary["flagged_by_hampel"],
        "连续恒定值异常数": qc_summary["flagged_by_constant_value"],
        "自动应用数量": qc_summary["applied_flagged_count"],
        "最终有效记录数": final_valid,
    }])


def _display_task_status_table(table):
    """Translate task-status presentation only; internal status values remain unchanged."""
    display_table = table.rename(columns={
        "人工确认状态": "质量确认状态",
        "当前结果是否有效": "最终结果状态",
        "是否可纳入站点综合导出": "是否满足综合报告生成条件",
    }).copy()
    display_table = display_table.replace({
        "未提供": "未上传文件",
        "未处理": "待处理",
        "仅自动质控": "等待人工复核",
        "已人工确认": "已完成质量确认",
        "确认结果已失效": "需重新确认",
    })
    return display_table


COLUMN_LABELS = {
    "record_id": "记录ID",
    "datetime": "时间",
    "variable": "变量",
    "original_value": "原始值",
    "current_qc_value": "当前质量控制值",
    "qc_value": "质量控制后值",
    "existing_rule": "处理规则",
    "algorithm_flag": "异常标记",
    "user_decision": "复核决定",
    "rule": "处理规则",
    "reason": "处理原因",
    "is_flagged": "是否识别异常",
    "is_applied": "是否已处理",
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
    "missing_count_after_qc": "质量控制后缺测数",
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
        "Hampel统计异常数": int(qc_summary["flagged_by_hampel"]),
        "连续恒定值异常数": int(qc_summary["flagged_by_constant_value"]),
        "人工删除数": int(user_removed.sum()),
        "最终缺测数": int(final_qc_data["value"].isna().sum()),
        "最终有效记录数": int(final_qc_data["value"].notna().sum()),
        "待人工确认异常数": candidate["unique_candidate_count"], "异常确认删除数": candidate["candidate_removed_count"], "异常确认保留数": candidate["candidate_kept_count"], "待确认异常数": candidate["candidate_undecided_count"], "人工补充删除数": candidate["manual_extra_removed_count"],
    }


def _create_auto_rule_comparison_figure(raw, auto_qc_data, variable_key):
    metadata = get_variable_metadata(variable_key)
    name = metadata.get("display_name_cn", variable_key)
    unit = metadata.get("unit", "")
    fig = make_subplots(rows=1, cols=2, subplot_titles=("原始时序", "自动质量检查后时序"), shared_xaxes=True, shared_yaxes=True)
    fig.add_trace(go.Scattergl(x=raw["datetime"], y=raw["value"], mode="lines", name="原始时序", line={"color": "#1f77b4", "width": 1}), row=1, col=1)
    fig.add_trace(go.Scattergl(x=auto_qc_data["datetime"], y=auto_qc_data["value"], mode="lines", name="自动质量检查后", line={"color": "#d62728", "width": 1}), row=1, col=2)
    y_values = raw["value"].dropna()
    if not y_values.empty:
        y_min, y_max = y_values.min(), y_values.max()
        margin = max((y_max - y_min) * 0.05, 1e-6)
        fig.update_yaxes(range=[y_min - margin, y_max + margin])
    fig.update_layout(title=f"{name}自动质量检查前后对比", yaxis_title=f"{name}({unit})", hovermode="x unified", margin={"l": 50, "r": 20, "t": 60, "b": 40})
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
    return f"{safe or '变量分析报告'}.docx"


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
    with st.container(border=True):
        st.caption("填写本次站点任务的基础信息，内容将用于正式报告标题和封面信息。")
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


def _build_station_task_progress(variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info, current_context=None):
    """Reuse the existing station-export qualification calculation for status display."""
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
    return confirmed_assets, table, progress


def _overview_variable_stage(variable_key, uploaded_file, status_row):
    """Translate existing task state into the five overview stages only."""
    if uploaded_file is None:
        return "未上传"
    if status_row["人工确认状态"] == "已人工确认":
        return "已完成"

    review_table = st.session_state.get(_state_key(variable_key, "review_table"))
    if review_table is None or _state_key(variable_key, "auto_qc_data") not in st.session_state:
        return "待质量检查"
    if summarize_candidate_decisions(review_table)["candidate_undecided_count"]:
        return "待异常复核"
    return "待质量确认"


def _render_station_task_overview(
    variable_keys, uploads, enable_range, enable_hampel, enable_constant,
    station_info, current_variable_key,
):
    """Render a compact station-level view from existing task and QC state."""
    _, table, progress = _build_station_task_progress(
        variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info,
    )
    stages = {}
    for index, item_key in enumerate(variable_keys):
        stages[item_key] = _overview_variable_stage(item_key, uploads.get(item_key), table.iloc[index])

    total = progress["变量总数"]
    confirmed_count = progress["已确认变量数"]
    uploaded_count = progress["已上传变量数"]
    exportable_count = progress["可导出变量数"]
    current_name = get_variable_metadata(current_variable_key).get("display_name_cn", current_variable_key)
    site_name = str(station_info.get("site_name", "")).strip()

    with st.container(border=True):
        st.subheader("站点任务概览")
        upload_col, confirmation_col, export_col, report_col = st.columns(4)
        upload_col.metric("文件上传", f"{uploaded_count} / {total}")
        confirmation_col.metric("质量确认", f"{confirmed_count} / {total}")
        export_col.metric("可纳入综合结果", f"{exportable_count} / {total}")
        report_col.metric("综合报告", "可以生成" if progress["可生成站点综合 Excel"] else "暂不可生成")
        st.progress(confirmed_count / total if total else 0, text=f"站点任务进度：{confirmed_count} / {total} 个变量完成质量确认")

        st.markdown("**九变量状态摘要**")
        stage_columns = st.columns(3)
        for index, item_key in enumerate(variable_keys):
            metadata = get_variable_metadata(item_key)
            with stage_columns[index % 3]:
                st.caption(f"{metadata.get('display_name_cn', item_key)}：{stages[item_key]}")

        if not site_name:
            st.info("下一步：请填写站点名称。")
        elif uploaded_count == 0:
            st.info("下一步：请上传监测变量 Excel 文件。")
        elif uploads.get(current_variable_key) is None:
            st.info(f"下一步：请上传当前变量“{current_name}”的 Excel 文件。")
        elif stages[current_variable_key] in {"待质量检查", "待异常复核"}:
            st.warning(f"下一步：请完成当前变量“{current_name}”的异常确认与人工复核。")
        elif stages[current_variable_key] == "待质量确认":
            st.warning(f"下一步：请确认当前变量“{current_name}”的最终质量控制结果。")
        elif progress["可生成站点综合 Excel"]:
            st.success("下一步：九个变量均已完成质量确认，可以生成站点综合结果。")
        else:
            first_incomplete = next((item_key for item_key in variable_keys if stages[item_key] != "已完成"), None)
            if first_incomplete:
                next_name = get_variable_metadata(first_incomplete).get("display_name_cn", first_incomplete)
                st.info(f"下一步：当前变量已完成，请切换至尚未完成的变量继续处理（{next_name}）。")
            else:
                st.info("下一步：请查看综合报告生成条件。")
    return progress


def _render_station_task_completion(variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info, current_context=None):
    confirmed_assets, table, progress = _build_station_task_progress(
        variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info, current_context,
    )
    with st.container(border=True):
        st.subheader("详细任务状态")
        st.dataframe(_display_task_status_table(table), use_container_width=True, hide_index=True)
        st.caption(f"已上传文件：{progress['已上传变量数']} / {progress['变量总数']}；已完成质量确认：{progress['已确认变量数']}；已满足综合报告条件：{progress['可导出变量数']}")
        if progress["阻断项"]:
            st.warning("暂不满足综合报告生成条件：\n\n- " + "\n- ".join(progress["阻断项"]))
        else:
            st.success("九个变量均已完成质量确认，可以生成综合 Excel 和综合报告。")
    with st.container(border=True):
        st.subheader("综合结果导出")
        st.caption("全部变量完成质量确认后，可生成站点综合 Excel 和综合报告。")
        export_key = "station_task:summary_excel_bytes"
        if st.button("生成站点综合 Excel", disabled=not progress["可生成站点综合 Excel"], type="primary"):
            st.session_state[export_key] = _summary_workbook_bytes(variable_keys, confirmed_assets, progress)
        if export_key in st.session_state and progress["可生成站点综合 Excel"]:
            st.download_button("下载 summary_statistics.xlsx", st.session_state[export_key], "summary_statistics.xlsx")
        word_key = "station_task:station_word_report_bytes"
        if st.button("生成站点综合报告", disabled=not progress["可生成站点综合 Excel"], type="primary"):
            try:
                context = build_station_report_context(variable_keys, confirmed_assets, progress, station_info)
                st.session_state[word_key] = generate_station_word_report(context)
                st.session_state["station_task:station_word_report_filename"] = _safe_report_filename(station_info.get("report_title", "站点环境监测综合报告"))
            except Exception as exc:
                st.error(f"站点综合报告生成失败：{exc}")
        if word_key in st.session_state and progress["可生成站点综合 Excel"]:
            st.download_button("下载站点综合报告", st.session_state[word_key], st.session_state.get("station_task:station_word_report_filename", "站点环境监测综合报告.docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def _render_single_variable_report_entry(
    variable_key, uploaded_file, enable_range, enable_hampel, enable_constant,
    current_context, raw, resampled, anomaly, metrics, station_info,
):
    """Render the small report entry point after analysis, keeping generation out of app.py."""
    with st.container(border=True):
        st.subheader("变量分析报告")
        st.caption("报告基于当前变量已确认的最终质量控制结果生成。")
        confirmed, status = _confirmed_asset_status(
            variable_key, uploaded_file, enable_range, enable_hampel, enable_constant, current_context,
        )
        if confirmed is None:
            st.info("请先完成当前变量的质量确认，再生成变量分析报告。")
            return
        metadata = get_variable_metadata(variable_key)
        report_title = f"{station_info.get('site_name', '').strip()} {metadata.get('display_name_cn', variable_key)}监测数据质控与统计分析报告".strip()
        report_key = _state_key(variable_key, "word_report_bytes")
        if st.button("生成变量分析报告", key=_state_key(variable_key, "generate_word_report"), type="primary"):
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
                st.success("变量分析报告已生成。")
            except Exception as exc:
                st.error(f"变量分析报告生成失败：{exc}")
        if report_key in st.session_state:
            st.download_button("下载变量分析报告", st.session_state[report_key], st.session_state.get(_state_key(variable_key, "word_report_filename"), "变量分析报告.docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def main():
    st.set_page_config(page_title="环境监测数据质控与分析工具", layout="wide")
    _inject_visual_styles()

    variable_keys = list(list_enabled_variables())
    uploads = {}
    with st.sidebar:
        st.markdown("### 当前处理变量")
        variable_key = st.selectbox("变量选择", variable_keys, format_func=lambda x: get_variable_metadata(x)["display_name_cn"])
        selected_metadata = get_variable_metadata(variable_key)
        st.markdown(f"**{selected_metadata.get('display_name_cn', variable_key)}**")
        st.caption(f"{variable_key}｜单位：{selected_metadata.get('unit', '未设置')}")
        if st.session_state.get(_state_key(variable_key, "qc_confirmed"), False):
            st.success("当前变量已完成质量确认")
        else:
            st.caption("○ 待完成质量确认")

        st.markdown("### 监测数据上传")
        st.caption("请上传各监测变量 Excel 文件，上传状态将在下方显示。")
        for key in variable_keys:
            metadata = get_variable_metadata(key)
            label = f"上传{metadata.get('display_name_cn', key)} Excel"
            uploads[key] = st.file_uploader(label, type=["xls", "xlsx"], key=f"{key}_upload")
            st.caption("✓ 已上传" if uploads[key] is not None else "○ 未上传")

        st.markdown("### 分析时间范围")
        st.caption("时间范围仅作用于当前选择变量。")
        analysis_range_slot = st.empty()

    # 质量检查流程为固定系统规则，保留现有默认启用状态，不在侧边栏提供配置入口。
    enable_range = True
    enable_hampel = True
    enable_constant = True
    st.session_state["current_variable_key"] = variable_key

    _render_product_header(variable_keys, uploads)
    station_info = _render_station_task_info(variable_keys)
    _render_station_task_overview(
        variable_keys, uploads, enable_range, enable_hampel, enable_constant,
        station_info, variable_key,
    )
    st.header("监测文件上传")
    with st.container(border=True):
        st.caption("请在左侧栏上传九个监测变量的 Excel 文件，并选择需要处理的变量。")

    uploaded = uploads.get(variable_key)
    current_variable_metadata = get_variable_metadata(variable_key)
    current_variable_name = current_variable_metadata.get("display_name_cn", variable_key)
    st.header(f"当前变量工作区：{current_variable_name}")
    if uploaded is None:
        _, _, station_progress = _build_station_task_progress(
            variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info,
        )
        _render_current_variable_status_card(variable_key, uploaded, station_progress=station_progress)
        _render_station_task_completion(
            variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info,
        )
        return
    source_args = _source_args(variable_key, uploaded)

    try:
        preview = _cached_load_excel(variable_key, source_args["source_signature"], source_args["source_path"], source_args["uploaded_bytes"], source_args["uploaded_suffix"])
        min_date = preview["datetime"].min().date()
        max_date = preview["datetime"].max().date()
        with analysis_range_slot.container():
            date_range = st.date_input("分析时间范围", value=(min_date, max_date), min_value=min_date, max_value=max_date)
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
                st.session_state[_state_key(variable_key, "confirmation_invalid_reason")] = "质量检查规则、上传文件或分析时间范围已变化，请重新确认该变量。"
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

        status_card_placeholder = st.empty()
        _, _, station_progress = _build_station_task_progress(
            variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info, current_context,
        )
        with status_card_placeholder.container():
            _render_current_variable_status_card(
                variable_key,
                uploaded,
                st.session_state[_state_key(variable_key, "review_table")],
                station_progress,
            )
        st.caption(f"当前数据源：{_source_label(variable_key, uploaded)}")
        st.header("自动质量检查")
        st.dataframe(_display_table(_health_table(raw, qc_summary)), use_container_width=True)
        st.caption("系统默认执行：合理范围检测、Hampel 异常检测、连续恒定值检测。")
        st.caption("此处仅展示传感器无效值和范围异常检测的自动处理结果；Hampel 统计异常、连续恒定值异常及人工复核结果将在下一步显示。")
        st.plotly_chart(_create_auto_rule_comparison_figure(raw, auto_qc_data, variable_key), use_container_width=True)

        st.header("异常确认与人工复核")
        review_table = _enforce_physical_range_hard_rule(st.session_state[_state_key(variable_key, "review_table")])
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("全部 Hampel 异常标记为删除"):
            review_table = _apply_batch_decision(review_table, "hampel", "remove")
            st.session_state[_state_key(variable_key, "qc_confirmed")] = False
            clear_variable_result_caches(st.session_state, variable_key)
        if c2.button("全部 Hampel 异常标记为保留"):
            review_table = _apply_batch_decision(review_table, "hampel", "keep")
            st.session_state[_state_key(variable_key, "qc_confirmed")] = False
            clear_variable_result_caches(st.session_state, variable_key)
        if c3.button("全部恒定值异常标记为删除"):
            review_table = _apply_batch_decision(review_table, "constant_value", "remove")
            st.session_state[_state_key(variable_key, "qc_confirmed")] = False
            clear_variable_result_caches(st.session_state, variable_key)
        if c4.button("全部恒定值异常标记为保留"):
            review_table = _apply_batch_decision(review_table, "constant_value", "keep")
            st.session_state[_state_key(variable_key, "qc_confirmed")] = False
            clear_variable_result_caches(st.session_state, variable_key)
        st.session_state[_state_key(variable_key, "review_table")] = review_table
        _, _, station_progress = _build_station_task_progress(
            variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info, current_context,
        )
        with status_card_placeholder.container():
            _render_current_variable_status_card(variable_key, uploaded, review_table, station_progress)

        final_qc_data, final_qc_log = apply_review_table_decisions(raw, auto_qc_data, qc_log, review_table)
        st.session_state[_state_key(variable_key, "final_qc_data")] = final_qc_data
        st.session_state[_state_key(variable_key, "final_qc_log")] = final_qc_log
        summary_counts = _decision_summary(review_table, final_qc_data, auto_qc_data, qc_summary)
        st.dataframe(pd.DataFrame([summary_counts]), use_container_width=True)

        st.subheader("人工复核时间范围")
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
            st.warning("人工复核的开始时间不能晚于结束时间。")
            _render_station_task_completion(
                variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info, current_context,
            )
            return
        b1, b2 = st.columns(2)
        b1.button("删除当前时间范围内的全部记录", on_click=_set_range_decision, args=(check_start, check_end, "manual_remove"))
        b2.button("保留当前时间范围内的全部记录", on_click=_set_range_decision, args=(check_start, check_end, "manual_keep"))

        range_mask = (review_table["datetime"] >= check_start) & (review_table["datetime"] <= check_end)
        selectable_raw = raw.loc[raw["record_id"].astype(str).isin(review_table.loc[range_mask, "record_id"].astype(str))].copy()

        st.caption("左图显示待人工确认异常；当前复核时间范围内的原始记录可点选、框选或套索选择。右图为最终质量控制结果实时预览。")
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
        st.subheader("逐条复核记录")
        st.caption(f"当前显示 {check_start} 至 {check_end} 的记录，共 {len(range_table)} 条。")
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

        st.subheader("质量控制操作记录")
        final_log_table = build_qc_log_table(final_qc_log)
        rule_options = ["全部"] + sorted(final_log_table["rule"].dropna().unique().tolist()) if not final_log_table.empty else ["全部"]
        selected_rule = st.selectbox("按处理规则筛选记录", rule_options)
        shown_log = final_log_table if selected_rule == "全部" else final_log_table[final_log_table["rule"] == selected_rule]
        st.dataframe(_display_table(shown_log), use_container_width=True)
        if st.button("生成质量控制记录 Excel"):
            st.session_state[_state_key(variable_key, "qc_log_excel_bytes")] = _excel_bytes({"qc_log": final_log_table})
        if _state_key(variable_key, "qc_log_excel_bytes") in st.session_state:
            st.download_button("下载质量控制记录 Excel", st.session_state[_state_key(variable_key, "qc_log_excel_bytes")], "final_qc_log.xlsx")

        if st.button("确认最终质量控制结果", type="primary"):
            try:
                _save_confirmed_qc_assets(variable_key, source_args["source_signature"], start_ts, end_ts, token)
            except ValueError as exc:
                st.warning(str(exc))
            else:
                # Refresh the top status card immediately after confirmation succeeds.
                st.rerun()
        if not st.session_state.get(_state_key(variable_key, "qc_confirmed"), False):
            st.info("请先确认最终质量控制结果，再查看统计分析结果或生成报告。")
            _render_station_task_completion(
                variable_keys, uploads, enable_range, enable_hampel, enable_constant, station_info, current_context,
            )
            return

        st.header("统计分析结果")
        resampled, anomaly, metrics, basic_row = _run_after_qc(variable_key, final_qc_data, qc_summary)
        hourly = resampled["hourly"]
        daily = resampled["daily"]
        st.caption(f"小时平均记录数：{len(hourly)}；日平均记录数：{len(daily)}")
        basic_df = build_basic_statistics_table([basic_row])
        st.subheader("基础统计摘要")
        st.dataframe(_display_table(basic_df), use_container_width=True)
        st.download_button("下载当前变量统计结果 CSV", basic_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"), f"{variable_key}_statistics.csv", "text/csv")

        st.plotly_chart(_create_hourly_daily_figure(hourly, daily, variable_key), use_container_width=True)
        st.plotly_chart(_create_anomaly_figure(anomaly, variable_key), use_container_width=True)

        st.subheader("月度统计摘要")
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
