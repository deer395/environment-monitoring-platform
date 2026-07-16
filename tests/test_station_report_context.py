import pandas as pd
from docx import Document
from io import BytesIO

from src.station_report_context import build_station_report_context
from src.station_task import build_station_task_status
from src.variable_registry import get_variable_metadata, list_enabled_variables
from src.station_word_report import generate_station_word_report


def test_station_context_uses_all_confirmed_assets_and_registered_order():
    keys = list_enabled_variables()
    timestamps = pd.date_range("2026-01-01", periods=72, freq="h")
    assets, sources, statuses = {}, {}, {}
    for index, key in enumerate(keys):
        raw = pd.DataFrame({"datetime": timestamps, "value": [index + 1.0] * len(timestamps)})
        assets[key] = {"raw_data": raw, "final_qc_data": raw.copy(), "final_qc_log": pd.DataFrame(), "qc_summary": {"raw_count": len(raw), "missing_before_qc": 0}, "review_table": pd.DataFrame(), "analysis_start": timestamps.min(), "analysis_end": timestamps.max(), "qc_token": key}
        sources[key] = {"provided": True, "read_success": True, "start_time": timestamps.min(), "end_time": timestamps.max(), "raw_count": len(raw)}
        statuses[key] = "已人工确认"
    info = {"site_name": "测试站", "project_name": "测试项目", "department": "部门", "author": "甲", "report_title": "测试站综合报告"}
    _, progress = build_station_task_status(keys, {key: get_variable_metadata(key) for key in keys}, sources, assets, statuses, info)
    context = build_station_report_context(keys, assets, progress, info)
    assert [item["key"] for item in context["variables"]] == list(keys)
    assert len(context["overview_rows"]) == 9
    assert context["overview_rows"][0][3] == f"{len(timestamps):,}"
    assert context["overview_rows"][0][4] == f"{len(timestamps):,}"


def test_station_word_uses_compact_structure_and_two_overview_figures():
    keys = list_enabled_variables(); timestamps = pd.date_range("2026-01-01", periods=72, freq="h")
    assets = {key: {"raw_data": pd.DataFrame({"datetime": timestamps, "value": [i + 1.0] * len(timestamps)}), "final_qc_data": pd.DataFrame({"datetime": timestamps, "value": [i + 1.0] * len(timestamps)}), "final_qc_log": pd.DataFrame(), "qc_summary": {"raw_count": len(timestamps)}, "review_table": pd.DataFrame(), "analysis_start": timestamps.min(), "analysis_end": timestamps.max(), "qc_token": key} for i, key in enumerate(keys)}
    sources = {key: {"provided": True, "read_success": True} for key in keys}; info = {"site_name": "站", "report_title": "综合报告"}
    _, progress = build_station_task_status(keys, {key: get_variable_metadata(key) for key in keys}, sources, assets, {key: "已人工确认" for key in keys}, info)
    text = "\n".join(p.text for p in Document(BytesIO(generate_station_word_report(build_station_report_context(keys, assets, progress, info)))).paragraphs)
    assert "3. 各监测要素质控与统计分析" in text and "3.1 水深" in text and "3.9 多环芳烃" in text
    assert "图2-1" in text and "图2-2" in text
    assert "数据摘要：" not in text and "站点任务总结" not in text and "附录" not in text and "Git标签" not in text
