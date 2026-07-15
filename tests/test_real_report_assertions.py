from io import BytesIO
from pathlib import Path

from docx import Document

from src.anomaly import calculate_configured_anomaly
from src.loaders import load_excel_variable
from src.manual_qc import apply_review_table_decisions, build_qc_review_table
from src.metrics import calculate_metrics
from src.qc import apply_quality_control
from src.report_context import build_report_context
from src.resampling import resample_configured
from src.variable_registry import get_variable_metadata
from src.word_report import generate_single_variable_report


def _real_report(variable_key, filename):
    metadata = get_variable_metadata(variable_key)
    raw = load_excel_variable(Path("data_private") / filename, variable_key)
    auto, summary, log = apply_quality_control(raw, metadata, enable_hampel=True, enable_constant_value=True)
    review = build_qc_review_table(raw, auto, log)
    final, final_log = apply_review_table_decisions(raw, auto, log, review)
    resampled = resample_configured(final, metadata)
    anomaly = calculate_configured_anomaly(resampled, metadata)
    metrics = calculate_metrics(variable_key, resampled["hourly"], resampled["daily"], anomaly, metadata=metadata, base_data=resampled["hourly"])
    context = build_report_context(variable_key=variable_key, raw_data=raw, final_qc_data=final, final_qc_log=final_log, qc_summary=summary, review_table=review, resampled=resampled, anomaly=anomaly, metrics=metrics, qc_token=variable_key, confirmed_qc_token=variable_key)
    document = Document(BytesIO(generate_single_variable_report(context)))
    return context, "\n".join(paragraph.text for paragraph in document.paragraphs)


def _assert_order(text):
    analysis = text.index("时间变化综合分析")
    assert analysis < text.index("图2", analysis) < text.index("图3", analysis) < text.index("图4", analysis)
    assert text.count("最高小时平均值") == 1
    assert text.count("最低小时平均值") == 1
    for forbidden in ("decrease", "increase", "stable", "change_point", "periodic", "NaN", "2026-05"):
        assert forbidden not in text


def test_pahs_real_report_narrative():
    context, text = _real_report("pahs", "多环芳烃.xls")
    assert context["time_features"]["interpretation"]["primary_mode"] == "change_point"
    _assert_order(text)
    assert "2026年4月至2026年6月持续下降" in text
    assert "未识别出稳定的周期性变化" in text


def test_depth_real_report_narrative():
    context, text = _real_report("depth", "depth.xls")
    assert context["time_features"]["interpretation"]["primary_mode"] == "periodic"
    _assert_order(text)
    assert "主要周期约为" in text


def test_chlorophyll_and_salinity_monthly_wording():
    _, chlorophyll = _real_report("chlorophyll", "叶绿素.xls")
    assert "～3.18" not in chlorophyll
    assert "短暂回升" in chlorophyll
    assert "持续下降" not in chlorophyll
    _, salinity = _real_report("salinity", "盐度.xls")
    assert "6月进一步达到29.72" not in salinity
    assert "短暂回升" in salinity


def test_five_variable_monthly_stage_closure():
    files = {"temperature": "temp.xls", "depth": "depth.xls", "bod": "BOD.xls", "salinity": "盐度.xls", "chlorophyll": "叶绿素.xls"}
    for variable_key, filename in files.items():
        context, text = _real_report(variable_key, filename)
        monthly = context["statistics"]["monthly"]
        stages = context["time_features"]["interpretation"]["monthly_interpretation"]["segments"]
        assert 1 <= len(stages) <= 4
        assert context["variable_info"]["unit"] in text
        assert "NaN" not in text and "～—" not in text
        assert monthly.loc[monthly.monthly_mean.idxmax(), "year_month"].replace("-", "年", 1).split("年")[0] in text


def test_final_four_variable_monthly_and_conclusion_closure():
    temperature_context, temperature = _real_report("temperature", "temp.xls")
    assert temperature_context["variable_info"]["unit"] == "℃"
    assert "2026年2月至2026年6月阶段性回升" in temperature
    assert "2026年3月至2026年6月回升" in temperature
    assert "进一步达到" not in temperature

    _, depth = _real_report("depth", "depth.xls")
    assert "2026年2月至2026年4月阶段性回升" in depth
    assert "约24小时的规律周期" in depth

    _, cod = _real_report("cod", "COD.xls")
    assert "2026年2月达到观测期高值" in cod
    assert "2026年4月降至低值" in cod
    assert "2026年5月至2026年6月回升" in cod

    _, salinity = _real_report("salinity", "盐度.xls")
    assert "短暂回升至30.48 PSU" in salinity
    assert "阶段性回落至29.72 PSU" in salinity
    assert "变化至" not in salinity
