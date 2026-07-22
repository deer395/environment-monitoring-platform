import pandas as pd

from src.station_task import (
    build_station_task_status,
    clear_all_variable_report_caches,
    clear_report_caches,
    clear_station_export_caches,
    clear_variable_result_caches,
    default_station_report_title,
    invalidate_report_template_cache,
    require_station_export,
)
from src.variable_registry import get_variable_metadata, list_enabled_variables


VARIABLES = ("depth", "temperature", "salinity")
METADATA = {key: {"display_name_cn": name} for key, name in zip(VARIABLES, ("水深", "温度", "盐度"))}
INFO = {"site_name": "示例站", "project_name": "项目", "department": "部门", "author": "甲", "report_title": "示例站点环境监测综合报告"}


def _source_states():
    return {
        key: {"provided": True, "read_success": True, "start_time": "2026-01-01", "end_time": "2026-01-02", "raw_count": 12}
        for key in VARIABLES
    }


def _assets():
    return {
        key: {
            "analysis_start": pd.Timestamp("2026-01-02"),
            "analysis_end": pd.Timestamp("2026-01-03 23:59:59"),
            "qc_summary": {"raw_count": 8},
            "final_qc_data": pd.DataFrame({"datetime": pd.to_datetime(["2026-01-02", "2026-01-03"]), "value": [1.0, None]}),
        }
        for key in VARIABLES
    }


def test_default_title_and_station_metadata_cache_clear_do_not_touch_qc_assets():
    state = {
        "depth:word_report_bytes": b"old", "depth:word_report_filename": "old.docx",
        "depth:confirmed_qc_assets": {"final_qc_data": "keep"},
    }
    clear_report_caches(state, ["depth"])
    assert default_station_report_title("A站") == "A站站点环境监测综合报告"
    assert "depth:word_report_bytes" not in state
    assert state["depth:confirmed_qc_assets"]["final_qc_data"] == "keep"


def test_station_information_change_clears_every_report_and_station_export_cache_only():
    state = {
        "depth:word_report_bytes": b"old", "temperature:word_report_bytes": b"old",
        "station_task:summary_excel_bytes": b"old-summary",
        "station_task:station_word_report_bytes": b"future-word",
        "depth:confirmed_qc_assets": {"final_qc_data": "keep"},
    }
    clear_all_variable_report_caches(state, ["depth", "temperature"])
    clear_station_export_caches(state)
    assert not any(key.endswith("report_bytes") or key == "station_task:summary_excel_bytes" for key in state)
    assert state["depth:confirmed_qc_assets"]["final_qc_data"] == "keep"


def test_station_word_template_change_clears_only_station_word_cache():
    state = {
        "station_task:station_word_report_bytes": b"old-word",
        "station_task:station_word_report_filename": "old.docx",
        "station_task:summary_excel_bytes": b"keep-excel",
        "depth:confirmed_qc_assets": {"final_qc_data": "keep"},
    }
    changed = invalidate_report_template_cache(
        state,
        "station_task:station_word_report_template_version",
        "station-template-test-v2",
        ("station_task:station_word_report_bytes", "station_task:station_word_report_filename"),
    )
    assert changed
    assert "station_task:station_word_report_bytes" not in state
    assert "station_task:station_word_report_filename" not in state
    assert state["station_task:summary_excel_bytes"] == b"keep-excel"
    assert state["depth:confirmed_qc_assets"]["final_qc_data"] == "keep"
    assert state["station_task:station_word_report_template_version"] == "station-template-test-v2"

    state["station_task:station_word_report_bytes"] = b"new-word"
    assert not invalidate_report_template_cache(
        state,
        "station_task:station_word_report_template_version",
        "station-template-test-v2",
        ("station_task:station_word_report_bytes", "station_task:station_word_report_filename"),
    )
    assert state["station_task:station_word_report_bytes"] == b"new-word"

def test_one_variable_result_change_clears_its_word_and_station_export_only():
    state = {
        "depth:word_report_bytes": b"old-depth", "depth:word_report_filename": "depth.docx",
        "temperature:word_report_bytes": b"keep-temperature", "temperature:word_report_filename": "temperature.docx",
        "station_task:summary_excel_bytes": b"old-summary",
        "depth:confirmed_qc_assets": {"final_qc_data": "keep"},
    }
    clear_variable_result_caches(state, "depth")
    assert "depth:word_report_bytes" not in state
    assert "station_task:summary_excel_bytes" not in state
    assert state["temperature:word_report_bytes"] == b"keep-temperature"
    assert state["depth:confirmed_qc_assets"]["final_qc_data"] == "keep"


def test_unprovided_variable_is_shown_and_blocks_export_without_default_source():
    sources = _source_states()
    sources["temperature"] = {"provided": False}
    table, progress = build_station_task_status(VARIABLES, METADATA, sources, _assets(), {key: "已人工确认" for key in VARIABLES}, INFO)
    row = table.loc[table["中文变量名称"].eq("温度")].iloc[0]
    assert row["文件状态"] == "未提供"
    assert row["阻断原因"] == "未上传文件"
    assert not progress["可生成站点综合 Excel"]


def test_read_failure_and_automatic_only_are_independent_blockers():
    sources = _source_states()
    sources["salinity"] = {"provided": True, "read_error": "列名不匹配"}
    assets = _assets()
    assets.pop("temperature")
    table, progress = build_station_task_status(
        VARIABLES, METADATA, sources, assets,
        {"depth": "已人工确认", "temperature": "仅自动质控", "salinity": "未处理"}, INFO,
    )
    assert table.loc[table["中文变量名称"].eq("盐度"), "文件状态"].item() == "读取失败"
    assert table.loc[table["中文变量名称"].eq("温度"), "人工确认状态"].item() == "仅自动质控"
    assert not progress["可生成站点综合 Excel"]


def test_unconfirmed_status_has_file_metadata_but_no_analysis_metadata():
    assets = _assets()
    assets.pop("temperature")
    table, _ = build_station_task_status(
        VARIABLES, METADATA, _source_states(), assets,
        {"depth": "已人工确认", "temperature": "仅自动质控", "salinity": "已人工确认"}, INFO,
    )
    row = table.loc[table["中文变量名称"].eq("温度")].iloc[0]
    assert row["文件时间范围"] == "2026-01-01 至 2026-01-02"
    assert row["文件记录数"] == 12
    assert row["分析时间范围"] == ""
    assert row["分析范围原始记录数"] == ""
    assert row["最终有效记录数"] == ""


def test_confirmed_status_uses_saved_analysis_range_qc_count_and_final_valid_count():
    table, _ = build_station_task_status(
        VARIABLES, METADATA, _source_states(), _assets(),
        {key: "已人工确认" for key in VARIABLES}, INFO,
    )
    row = table.loc[table["中文变量名称"].eq("水深")].iloc[0]
    assert row["文件时间范围"] == "2026-01-01 至 2026-01-02"
    assert "2026-01-02" in row["分析时间范围"]
    assert row["分析范围原始记录数"] == 8
    assert row["最终有效记录数"] == 1


def test_invalid_confirmation_blocks_only_that_variable():
    assets = _assets()
    table, progress = build_station_task_status(
        VARIABLES, METADATA, _source_states(), assets,
        {"depth": "已人工确认", "temperature": "数据源已变化，需重新确认", "salinity": "已人工确认"}, INFO,
    )
    invalid = table.loc[table["中文变量名称"].eq("温度")].iloc[0]
    assert invalid["人工确认状态"] == "确认结果已失效"
    assert invalid["是否可纳入站点综合导出"] == "否"
    assert progress["已确认变量数"] == 2


def test_all_confirmed_final_assets_allow_strict_station_export():
    assets = _assets()
    _, progress = build_station_task_status(
        VARIABLES, METADATA, _source_states(), assets,
        {key: "已人工确认" for key in VARIABLES}, INFO,
    )
    assert progress["可生成站点综合 Excel"]
    require_station_export(progress, assets, VARIABLES)


def test_all_nine_registered_variables_must_be_confirmed_for_station_export():
    variable_keys = list_enabled_variables()
    assert len(variable_keys) == 9
    metadata = {key: get_variable_metadata(key) for key in variable_keys}
    sources = {key: {"provided": True, "read_success": True, "raw_count": 1} for key in variable_keys}
    assets = {key: {"final_qc_data": pd.DataFrame({"datetime": pd.to_datetime(["2026-01-01"]), "value": [1.0]})} for key in variable_keys}
    statuses = {key: "已人工确认" for key in variable_keys}
    _, progress = build_station_task_status(variable_keys, metadata, sources, assets, statuses, INFO)
    assert progress["可生成站点综合 Excel"]
    assets.pop(variable_keys[-1])
    _, blocked = build_station_task_status(variable_keys, metadata, sources, assets, statuses, INFO)
    assert not blocked["可生成站点综合 Excel"]


def test_missing_station_name_or_final_data_blocks_strict_export():
    assets = _assets()
    no_site = {**INFO, "site_name": ""}
    _, progress = build_station_task_status(
        VARIABLES, METADATA, _source_states(), assets,
        {key: "已人工确认" for key in VARIABLES}, no_site,
    )
    assert not progress["可生成站点综合 Excel"]
    try:
        require_station_export(progress, assets, VARIABLES)
    except ValueError as exc:
        assert "站点名称" in str(exc)
    else:
        raise AssertionError("expected strict export gate to fail")
