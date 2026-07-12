from pathlib import Path
from tempfile import NamedTemporaryFile
from io import BytesIO
import hashlib
import sys

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.anomaly import calculate_intraday_anomaly
from src.loaders import load_excel_variable
from src.manual_qc import (
    REVIEW_DECISIONS,
    apply_manual_qc_decisions,
    apply_review_table_decisions,
    build_qc_review_table,
    ensure_record_id,
)
from src.metrics import calculate_metrics
from src.plotting import create_final_qc_figure, create_qc_candidate_figure
from src.qc import apply_quality_control
from src.report_tables import (
    build_basic_statistics_row,
    build_basic_statistics_table,
    build_depth_daily_range_table,
    build_qc_log_table,
    build_qc_summary_table,
    build_temperature_monthly_table,
)
from src.resampling import resample_daily_mean, resample_hourly_mean
from src.variable_registry import get_variable_metadata, list_v1_variables

DATA_DIR = PROJECT_ROOT / "data_private"
DEFAULT_FILES = {"depth": DATA_DIR / "depth.xls", "temperature": DATA_DIR / "temp.xls"}


def _uploaded_bytes(uploaded_file):
    return uploaded_file.getvalue() if uploaded_file is not None else None


def _source_signature(variable_key, uploaded_file):
    if uploaded_file is not None:
        digest = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
        return f"upload:{variable_key}:{uploaded_file.name}:{digest}"
    path = DEFAULT_FILES[variable_key]
    stat = path.stat()
    return f"default:{variable_key}:{path}:{stat.st_mtime_ns}:{stat.st_size}"


def _source_label(variable_key, uploaded_file):
    if uploaded_file is not None:
        return f"Uploaded file: {uploaded_file.name}"
    return f"Local default file: {DEFAULT_FILES[variable_key]}"


def _source_args(variable_key, uploaded_file):
    uploaded = _uploaded_bytes(uploaded_file)
    suffix = Path(uploaded_file.name).suffix if uploaded_file is not None else DEFAULT_FILES[variable_key].suffix
    return {
        "source_signature": _source_signature(variable_key, uploaded_file),
        "source_path": str(DEFAULT_FILES[variable_key]),
        "uploaded_bytes": uploaded,
        "uploaded_suffix": suffix,
    }


def _qc_params_key(variable_key):
    metadata = get_variable_metadata(variable_key)
    return (
        metadata.get("valid_min"),
        metadata.get("valid_max"),
        metadata.get("hampel_window"),
        metadata.get("hampel_sigma"),
        metadata.get("hampel_min_abs_deviation"),
        metadata.get("constant_value_window"),
        metadata.get("constant_value_tolerance"),
    )


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


def _run_after_qc(variable_key, final_qc_data, qc_summary):
    hourly = resample_hourly_mean(final_qc_data)
    daily = resample_daily_mean(final_qc_data)
    anomaly = calculate_intraday_anomaly(hourly, daily)
    metrics = calculate_metrics(variable_key, hourly, daily, anomaly)
    basic_row = build_basic_statistics_row(variable_key, hourly, metrics, qc_summary)
    return hourly, daily, anomaly, metrics, basic_row


def _health_table(raw, qc_summary, final_qc_data=None):
    final_valid = None if final_qc_data is None else int(final_qc_data["value"].notna().sum())
    return pd.DataFrame([{
        "raw_count": qc_summary["raw_count"],
        "missing_before_qc": qc_summary["missing_before_qc"],
        "time_range": f"{raw['datetime'].min()} to {raw['datetime'].max()}",
        "duplicate_datetime_count": int(raw["datetime"].duplicated().sum()),
        "physical_range_removed": qc_summary["removed_by_range"],
        "hampel_flagged": qc_summary["flagged_by_hampel"],
        "constant_value_flagged": qc_summary["flagged_by_constant_value"],
        "auto_applied_count": qc_summary["applied_flagged_count"],
        "final_valid_count": final_valid,
    }])


def _decision_summary(review_table, final_qc_data, auto_qc_data):
    candidates = review_table[review_table["algorithm_flag"].astype(str).ne("")]
    auto_missing = int(auto_qc_data["value"].isna().sum())
    final_missing = int(final_qc_data["value"].isna().sum())
    return {
        "candidate_count": int(len(candidates)),
        "remove_count": int(review_table["user_decision"].eq("remove").sum()),
        "keep_count": int(review_table["user_decision"].eq("keep").sum()),
        "undecided_count": int(review_table["user_decision"].eq("undecided").sum()),
        "final_removed_count": final_missing,
        "user_added_removed_count": max(final_missing - auto_missing, 0),
        "final_valid_count": int(final_qc_data["value"].notna().sum()),
    }


def _enforce_physical_range_hard_rule(table):
    result = table.copy()
    physical_mask = result["existing_rule"].astype(str).str.contains("physical_range", na=False)
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
    physical_mask = result["existing_rule"].astype(str).str.contains("physical_range", na=False)
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
    physical_mask = result["existing_rule"].astype(str).str.contains("physical_range", na=False)
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
    table = st.session_state.get("review_table")
    ids = st.session_state.get("selected_record_ids", [])
    if table is not None:
        st.session_state["review_table"] = _apply_selected_decision(table, ids, decision)
        st.session_state["qc_confirmed"] = False


def _clear_selection():
    st.session_state["selected_record_ids"] = []


def _set_range_decision(start_ts, end_ts, decision):
    table = st.session_state.get("review_table")
    if table is not None:
        st.session_state["review_table"] = _apply_range_decision(table, start_ts, end_ts, decision)
        st.session_state["qc_confirmed"] = False


def _create_auto_rule_comparison_figure(raw, auto_qc_data, variable_key):
    metadata = get_variable_metadata(variable_key)
    name = metadata.get("display_name_cn", variable_key)
    unit = metadata.get("unit", "")
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Raw series", "After physical_range"), shared_xaxes=True, shared_yaxes=True)
    fig.add_trace(go.Scattergl(x=raw["datetime"], y=raw["value"], mode="lines", name="raw", line={"color": "#1f77b4", "width": 1}), row=1, col=1)
    fig.add_trace(go.Scattergl(x=auto_qc_data["datetime"], y=auto_qc_data["value"], mode="lines", name="auto_qc", line={"color": "#d62728", "width": 1}), row=1, col=2)
    y_values = raw["value"].dropna()
    if not y_values.empty:
        y_min, y_max = y_values.min(), y_values.max()
        margin = max((y_max - y_min) * 0.05, 1e-6)
        fig.update_yaxes(range=[y_min - margin, y_max + margin])
    fig.update_layout(title=f"{name} auto-rule comparison", yaxis_title=f"{name}({unit})", hovermode="x unified", margin={"l": 50, "r": 20, "t": 60, "b": 40})
    fig.update_xaxes(tickformat="%Y/%m/%d")
    return fig


def _create_hourly_daily_figure(hourly, daily, variable_key):
    metadata = get_variable_metadata(variable_key)
    name = metadata.get("display_name_cn", variable_key)
    unit = metadata.get("unit", "")
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=hourly["datetime"], y=hourly["value"], mode="lines", name="hourly", line={"color": "#1f77b4", "width": 1}))
    fig.add_trace(go.Scatter(x=daily["datetime"], y=daily["value"], mode="lines", name="daily mean", line={"color": "#d62728", "width": 2}))
    fig.update_layout(title=f"{name} hourly and daily mean", xaxis_title="date", yaxis_title=f"{name}({unit})", hovermode="x unified")
    fig.update_xaxes(tickformat="%Y/%m/%d")
    return fig


def _create_anomaly_figure(anomaly, variable_key):
    metadata = get_variable_metadata(variable_key)
    name = metadata.get("display_name_cn", variable_key)
    unit = metadata.get("unit", "")
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=anomaly["datetime"], y=anomaly["anomaly"], mode="lines", name="intraday anomaly", line={"color": "#1f77b4", "width": 1}))
    fig.add_hline(y=0, line_color="#333333", line_width=1)
    fig.update_layout(title=f"{name} intraday anomaly", xaxis_title="date", yaxis_title=f"{name} anomaly({unit})", hovermode="x unified")
    fig.update_xaxes(tickformat="%Y/%m/%d")
    return fig


def _excel_bytes(sheets):
    output = BytesIO()
    with pd.ExcelWriter(output) as writer:
        for sheet_name, table in sheets.items():
            table.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return output.getvalue()


def _summary_workbook_bytes(depth_upload, temp_upload, date_range, enable_range, enable_hampel, enable_constant, current_variable, current_final_qc_data, current_qc_summary, current_final_qc_log):
    uploads = {"depth": depth_upload, "temperature": temp_upload}
    all_rows, all_qc, all_metrics, all_logs = [], {}, {}, []
    start_ts = pd.Timestamp(date_range[0])
    end_ts = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    for key, upload in uploads.items():
        args = _source_args(key, upload)
        raw, auto_qc, qc_summary, qc_log, review = _get_auto_qc_assets(key, args, start_ts, end_ts, enable_range, enable_hampel, enable_constant)
        if key == current_variable and current_final_qc_data is not None:
            final_qc = current_final_qc_data
            final_log = current_final_qc_log
            summary_for_stats = current_qc_summary or qc_summary
        else:
            final_qc, final_log = apply_manual_qc_decisions(raw, auto_qc, qc_log)
            summary_for_stats = qc_summary
        hourly, daily, anomaly, metrics, row = _run_after_qc(key, final_qc, summary_for_stats)
        all_rows.append(row)
        all_qc[key] = summary_for_stats
        all_metrics[key] = metrics
        if final_log is not None:
            all_logs.append(final_log)
    return _excel_bytes({
        "basic_statistics": build_basic_statistics_table(all_rows),
        "temperature_monthly": build_temperature_monthly_table(all_metrics["temperature"]),
        "depth_daily_range": build_depth_daily_range_table(all_metrics["depth"]),
        "qc_summary": build_qc_summary_table(all_qc),
        "final_qc_log": build_qc_log_table(pd.concat(all_logs, ignore_index=True) if all_logs else None),
    })


def main():
    st.set_page_config(page_title="Marine Ranch V2 Stage 4.1 QC", layout="wide")
    st.title("Marine Ranch V2 Stage 4.1 QC Workflow")
    st.caption("Auto rules first; algorithm suggestions and manual QC share one review workspace. Downstream analysis uses final_qc_data only.")

    depth_upload = st.sidebar.file_uploader("Upload depth Excel", type=["xls", "xlsx"], key="depth_upload")
    temp_upload = st.sidebar.file_uploader("Upload temperature Excel", type=["xls", "xlsx"], key="temp_upload")
    variable_key = st.sidebar.selectbox("Variable", list_v1_variables(), format_func=lambda x: get_variable_metadata(x)["display_name_cn"])
    enable_range = st.sidebar.checkbox("Enable physical range QC (auto remove)", value=True)
    enable_hampel = st.sidebar.checkbox("Enable Hampel flags (suggest only)", value=True)
    enable_constant = st.sidebar.checkbox("Enable constant-value flags (suggest only)", value=True)

    uploaded = depth_upload if variable_key == "depth" else temp_upload
    source_args = _source_args(variable_key, uploaded)
    st.info(f"Data source: {_source_label(variable_key, uploaded)}")

    try:
        preview = _cached_load_excel(variable_key, source_args["source_signature"], source_args["source_path"], source_args["uploaded_bytes"], source_args["uploaded_suffix"])
        min_date = preview["datetime"].min().date()
        max_date = preview["datetime"].max().date()
        date_range = st.sidebar.date_input("Analysis date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
        if len(date_range) != 2:
            st.warning("Please select start and end dates.")
            return

        start_ts = pd.Timestamp(date_range[0])
        end_ts = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        token = f"{variable_key}|{source_args['source_signature']}|{start_ts.isoformat()}|{end_ts.isoformat()}|{enable_range}|{enable_hampel}|{enable_constant}|{_qc_params_key(variable_key)}"
        if st.session_state.get("qc_token") != token:
            st.session_state["qc_token"] = token
            st.session_state["qc_confirmed"] = False
            st.session_state["review_table"] = None
            st.session_state["selected_record_ids"] = []
            st.session_state.pop("qc_log_excel_bytes", None)
            st.session_state.pop("summary_excel_bytes", None)

        raw, auto_qc_data, qc_summary, qc_log, initial_review_table = _get_auto_qc_assets(variable_key, source_args, start_ts, end_ts, enable_range, enable_hampel, enable_constant)
        if raw.empty:
            st.warning("No data in the selected time range.")
            return

        st.session_state["raw_data"] = raw
        st.session_state["auto_qc_data"] = auto_qc_data
        st.session_state["qc_log"] = qc_log
        if st.session_state.get("review_table") is None:
            st.session_state["review_table"] = initial_review_table.copy()

        st.header("Step 1: Automatic Rules")
        st.dataframe(_health_table(raw, qc_summary), use_container_width=True)
        st.caption("This comparison shows only physical_range auto removal. Hampel, constant_value, and manual decisions are not applied here.")
        st.plotly_chart(_create_auto_rule_comparison_figure(raw, auto_qc_data, variable_key), use_container_width=True)

        st.header("Step 2: Candidate Review and Manual QC")
        review_table = _enforce_physical_range_hard_rule(st.session_state["review_table"])
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("Remove all Hampel"):
            review_table = _apply_batch_decision(review_table, "hampel", "remove")
            st.session_state["qc_confirmed"] = False
        if c2.button("Keep all Hampel"):
            review_table = _apply_batch_decision(review_table, "hampel", "keep")
            st.session_state["qc_confirmed"] = False
        if c3.button("Remove all constant"):
            review_table = _apply_batch_decision(review_table, "constant_value", "remove")
            st.session_state["qc_confirmed"] = False
        if c4.button("Keep all constant"):
            review_table = _apply_batch_decision(review_table, "constant_value", "keep")
            st.session_state["qc_confirmed"] = False
        st.session_state["review_table"] = review_table

        final_qc_data, final_qc_log = apply_review_table_decisions(raw, auto_qc_data, qc_log, review_table)
        st.session_state["final_qc_data"] = final_qc_data
        st.session_state["final_qc_log"] = final_qc_log
        summary_counts = _decision_summary(review_table, final_qc_data, auto_qc_data)
        st.dataframe(pd.DataFrame([summary_counts]), use_container_width=True)

        st.caption("Left: selectable candidate flags. Right: live final_qc_data preview.")
        left, right = st.columns(2)
        with left:
            selected_event = st.plotly_chart(
                create_qc_candidate_figure(raw, qc_log, review_table, variable_key),
                use_container_width=True,
                on_select="rerun",
                selection_mode=["points", "box", "lasso"],
                key=f"{variable_key}_candidate_plot",
            )
        with right:
            st.plotly_chart(
                create_final_qc_figure(final_qc_data, raw, variable_key, summary_counts["final_removed_count"], summary_counts["final_valid_count"]),
                use_container_width=True,
                key=f"{variable_key}_final_plot",
            )

        selected_ids = _selected_record_ids(selected_event)
        if selected_ids:
            st.session_state["selected_record_ids"] = selected_ids
        selected_ids = st.session_state.get("selected_record_ids", [])
        selected_table = review_table[review_table["record_id"].astype(str).isin(selected_ids)].copy()
        st.subheader("Selected data points")
        st.dataframe(selected_table, use_container_width=True)
        s1, s2, s3, s4 = st.columns(4)
        s1.button("Remove selected", disabled=not selected_ids, on_click=_set_selected_decision, args=("remove",))
        s2.button("Keep selected", disabled=not selected_ids, on_click=_set_selected_decision, args=("keep",))
        s3.button("Restore selected", disabled=not selected_ids, on_click=_set_selected_decision, args=("manual_keep",))
        s4.button("Clear selection", disabled=not selected_ids, on_click=_clear_selection)

        st.subheader("Manual Review Time Range")
        raw_min = raw["datetime"].min()
        raw_max = raw["datetime"].max()
        default_start = raw_min
        default_end = min(raw_min + pd.Timedelta(days=7), raw_max)
        r1, r2 = st.columns(2)
        with r1:
            check_start_date = st.date_input("Start date", value=default_start.date(), min_value=raw_min.date(), max_value=raw_max.date(), key="check_start_date")
            check_start_time = st.time_input("Start time", value=default_start.time().replace(microsecond=0), key="check_start_time")
        with r2:
            check_end_date = st.date_input("End date", value=default_end.date(), min_value=raw_min.date(), max_value=raw_max.date(), key="check_end_date")
            check_end_time = st.time_input("End time", value=default_end.time().replace(microsecond=0), key="check_end_time")
        check_start = pd.Timestamp.combine(check_start_date, check_start_time)
        check_end = pd.Timestamp.combine(check_end_date, check_end_time)
        if check_start > check_end:
            st.warning("Manual review start time cannot be later than end time.")
            return
        b1, b2 = st.columns(2)
        b1.button("Remove current range", on_click=_set_range_decision, args=(check_start, check_end, "manual_remove"))
        b2.button("Restore current range", on_click=_set_range_decision, args=(check_start, check_end, "manual_keep"))

        range_mask = (review_table["datetime"] >= check_start) & (review_table["datetime"] <= check_end)
        range_table = review_table.loc[range_mask].copy()
        st.subheader("Current Range Point Editor")
        st.caption(f"Showing {check_start} to {check_end}: {len(range_table)} records.")
        edited_range = st.data_editor(
            range_table,
            use_container_width=True,
            hide_index=True,
            height=320,
            column_config={"user_decision": st.column_config.SelectboxColumn("user_decision", options=REVIEW_DECISIONS, required=True)},
            disabled=["record_id", "datetime", "original_value", "existing_rule", "algorithm_flag", "current_qc_value"],
            key=f"{variable_key}_review_editor",
        )
        if _range_decisions_changed(range_table, edited_range):
            st.session_state["review_table"] = _update_review_table(review_table, edited_range)
            st.session_state["qc_confirmed"] = False
            st.rerun()

        st.subheader("Final QC Log")
        final_log_table = build_qc_log_table(final_qc_log)
        rule_options = ["all"] + sorted(final_log_table["rule"].dropna().unique().tolist()) if not final_log_table.empty else ["all"]
        selected_rule = st.selectbox("Filter by rule", rule_options)
        shown_log = final_log_table if selected_rule == "all" else final_log_table[final_log_table["rule"] == selected_rule]
        st.dataframe(shown_log, use_container_width=True)
        if st.button("Generate QC log Excel"):
            st.session_state["qc_log_excel_bytes"] = _excel_bytes({"qc_log": final_log_table})
        if "qc_log_excel_bytes" in st.session_state:
            st.download_button("Download final QC log Excel", st.session_state["qc_log_excel_bytes"], "final_qc_log.xlsx")

        if st.button("Confirm final QC result"):
            st.session_state["qc_confirmed"] = True
        if not st.session_state.get("qc_confirmed", False):
            st.info("Confirm final QC before resampling, statistics, plotting, and export.")
            return

        st.header("Analysis After Confirmation")
        hourly, daily, anomaly, metrics, basic_row = _run_after_qc(variable_key, final_qc_data, qc_summary)
        st.write(f"hourly rows: {len(hourly)}; daily rows: {len(daily)}")
        basic_df = build_basic_statistics_table([basic_row])
        st.dataframe(basic_df, use_container_width=True)
        st.download_button("Download current variable statistics CSV", basic_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"), f"{variable_key}_statistics.csv", "text/csv")
        p1, p2 = st.columns(2)
        with p1:
            st.plotly_chart(_create_hourly_daily_figure(hourly, daily, variable_key), use_container_width=True)
        with p2:
            st.plotly_chart(_create_anomaly_figure(anomaly, variable_key), use_container_width=True)

        if variable_key == "temperature":
            monthly_df = build_temperature_monthly_table(metrics)
            st.dataframe(monthly_df, use_container_width=True)
        else:
            depth_range_df = build_depth_daily_range_table(metrics)
            st.dataframe(depth_range_df, use_container_width=True)
            st.metric("Max daily range over observation period", round(metrics["max_daily_range"], 4))

        if st.button("Generate summary_statistics.xlsx"):
            st.session_state["summary_excel_bytes"] = _summary_workbook_bytes(depth_upload, temp_upload, date_range, enable_range, enable_hampel, enable_constant, variable_key, final_qc_data, qc_summary, final_qc_log)
        if "summary_excel_bytes" in st.session_state:
            st.download_button("Download summary_statistics.xlsx", st.session_state["summary_excel_bytes"], "summary_statistics.xlsx")

    except Exception as exc:
        st.error(f"Processing failed: {exc}")


if __name__ == "__main__":
    main()
