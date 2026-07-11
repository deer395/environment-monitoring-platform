from pathlib import Path
from io import BytesIO
import sys
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.anomaly import calculate_intraday_anomaly
from src.loaders import load_excel_variable
from src.metrics import calculate_metrics
from src.plotting import (
    plot_hourly_daily,
    plot_intraday_anomaly,
    plot_temperature_monthly,
)
from src.qc import apply_quality_control
from src.report_tables import (
    build_basic_statistics_row,
    build_basic_statistics_table,
    build_depth_daily_range_table,
    build_qc_summary_table,
    build_temperature_monthly_table,
)
from src.resampling import resample_daily_mean, resample_hourly_mean
from src.variable_registry import get_variable_metadata, list_v1_variables


DATA_DIR = PROJECT_ROOT / "data_private"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_FILES = {
    "depth": DATA_DIR / "depth.xls",
    "temperature": DATA_DIR / "temp.xls",
}
def _save_upload(uploaded_file):
    suffix = Path(uploaded_file.name).suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return Path(tmp.name)


def _source_path(variable_key, uploaded_file):
    if uploaded_file is not None:
        return _save_upload(uploaded_file), f"上传文件：{uploaded_file.name}"
    return DEFAULT_FILES[variable_key], f"本地默认文件：{DEFAULT_FILES[variable_key]}"


def _run_variable_pipeline(variable_key, source_path, start_date, end_date, enable_2std, enable_range):
    metadata = get_variable_metadata(variable_key)
    raw = load_excel_variable(source_path, variable_key)
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    raw = raw[(raw["datetime"] >= start_ts) & (raw["datetime"] <= end_ts)].reset_index(drop=True)
    raw.attrs.update({"variable_key": variable_key, "unit": metadata["unit"]})

    qc_data, qc_summary, qc_log = apply_quality_control(raw, metadata, enable_2std, enable_range)
    hourly = resample_hourly_mean(qc_data)
    daily = resample_daily_mean(qc_data)
    anomaly = calculate_intraday_anomaly(hourly, daily)
    metrics = calculate_metrics(variable_key, hourly, daily, anomaly)
    basic_row = build_basic_statistics_row(variable_key, hourly, metrics, qc_summary)
    return raw, qc_summary, qc_log, hourly, daily, anomaly, metrics, basic_row


def _csv_download(df):
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def main():
    st.set_page_config(page_title="海洋牧场 V1 数据分析", layout="wide")
    st.title("海洋牧场 V1 数据分析")
    st.caption("Excel-only；不支持 MAT；不做 AI 报告。")

    depth_upload = st.sidebar.file_uploader("上传水深 Excel", type=["xls", "xlsx"], key="depth")
    temp_upload = st.sidebar.file_uploader("上传温度 Excel", type=["xls", "xlsx"], key="temperature")
    variables = list_v1_variables()
    variable_key = st.sidebar.selectbox(
        "变量选择",
        variables,
        format_func=lambda x: get_variable_metadata(x)["display_name_cn"],
    )
    enable_range = st.sidebar.checkbox("启用物理合理范围质控", value=True)
    enable_2std = st.sidebar.checkbox("启用 legacy_2std 兼容质控", value=False)

    uploaded = depth_upload if variable_key == "depth" else temp_upload
    source_path, source_label = _source_path(variable_key, uploaded)
    st.info(f"当前数据源：{source_label}")

    try:
        preview = load_excel_variable(source_path, variable_key)
        min_date = preview["datetime"].min().date()
        max_date = preview["datetime"].max().date()
        date_range = st.sidebar.date_input("时间范围", value=(min_date, max_date), min_value=min_date, max_value=max_date)
        if len(date_range) != 2:
            st.warning("请选择开始和结束日期。")
            return

        raw, qc_summary, qc_log, hourly, daily, anomaly, metrics, basic_row = _run_variable_pipeline(
            variable_key, source_path, date_range[0], date_range[1], enable_2std, enable_range
        )
        if raw.empty:
            st.warning("当前时间范围内没有数据。")
            return

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        hourly_daily_png = OUTPUT_DIR / f"{variable_key}_hourly_daily_streamlit.png"
        anomaly_png = OUTPUT_DIR / f"{variable_key}_intraday_anomaly_streamlit.png"
        plot_hourly_daily(hourly, daily, variable_key, hourly_daily_png)
        plot_intraday_anomaly(anomaly, variable_key, anomaly_png)

        st.subheader("质控摘要")
        st.dataframe(build_qc_summary_table({variable_key: qc_summary}), use_container_width=True)

        st.subheader("基础统计结果")
        basic_df = build_basic_statistics_table([basic_row])
        st.dataframe(basic_df, use_container_width=True)
        st.download_button("下载当前变量统计 CSV", _csv_download(basic_df), f"{variable_key}_statistics.csv", "text/csv")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("原始序列 + 日平均序列")
            st.image(str(hourly_daily_png))
            st.download_button("下载该图", hourly_daily_png.read_bytes(), hourly_daily_png.name, "image/png")
        with col2:
            st.subheader("日内距平")
            st.image(str(anomaly_png))
            st.download_button("下载距平图", anomaly_png.read_bytes(), anomaly_png.name, "image/png")

        if variable_key == "temperature":
            st.subheader("温度月平均和月标准差")
            monthly_df = build_temperature_monthly_table(metrics)
            monthly_png = OUTPUT_DIR / "temperature_monthly_stats_streamlit.png"
            plot_temperature_monthly(monthly_df, monthly_png)
            st.dataframe(monthly_df, use_container_width=True)
            st.image(str(monthly_png))
            st.download_button("下载温度月统计图", monthly_png.read_bytes(), monthly_png.name, "image/png")
        else:
            st.subheader("水深每日最大变化幅度")
            depth_range_df = build_depth_daily_range_table(metrics)
            st.dataframe(depth_range_df, use_container_width=True)
            st.metric("整个观测期最大日变化幅度", round(metrics["max_daily_range"], 4))

        all_rows = []
        all_qc = {}
        all_metrics = {}
        for key, upload in {"depth": depth_upload, "temperature": temp_upload}.items():
            path, _ = _source_path(key, upload)
            _, qcs, _, h, d, a, m, row = _run_variable_pipeline(key, path, date_range[0], date_range[1], enable_2std, enable_range)
            all_rows.append(row)
            all_qc[key] = qcs
            all_metrics[key] = m

        summary_buffer = BytesIO()
        with pd.ExcelWriter(summary_buffer) as writer:
            build_basic_statistics_table(all_rows).to_excel(
                writer, sheet_name="basic_statistics", index=False
            )
            build_temperature_monthly_table(all_metrics["temperature"]).to_excel(
                writer, sheet_name="temperature_monthly", index=False
            )
            build_depth_daily_range_table(all_metrics["depth"]).to_excel(
                writer, sheet_name="depth_daily_range", index=False
            )
            build_qc_summary_table(all_qc).to_excel(
                writer, sheet_name="qc_summary", index=False
            )
        st.download_button(
            "下载完整 summary_statistics.xlsx",
            summary_buffer.getvalue(),
            "summary_statistics.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as exc:
        st.error(f"处理失败：{exc}")


if __name__ == "__main__":
    main()
