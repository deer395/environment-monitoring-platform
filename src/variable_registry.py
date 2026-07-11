"""Variable metadata registry for the V1/V2 Excel-only workflow."""

from copy import deepcopy


VARIABLE_REGISTRY = {
    "depth": {
        "display_name": "Depth",
        "display_name_cn": "水深",
        "display_name_en": "Depth",
        "unit": "m",
        "source": "excel",
        "default_file_name": "depth.xls",
        "valid_min": 0,
        "valid_max": 100,
        "y_axis_range": None,
        "qc_profile": "marine_depth_v2_stage1",
        "hampel_window": 7,
        "hampel_sigma": 3.0,
        "rate_change_limit": None,
        "constant_value_window": 12,
        "datetime_column_aliases": [
            "datetime", "date_time", "timestamp", "time", "date",
            "日期时间", "时间", "日期", "监测时间", "采样时间", "观测时间",
        ],
        "value_column_aliases": [
            "depth", "depth_m", "water_depth", "value", "水深", "深度", "水位", "测值", "数值", "值",
        ],
        "qc_rules": {
            "required_fields": ["datetime", "value"],
            "valid_min": 0,
            "valid_max": 100,
            "valid_range": [0, 100],
        },
        "resampling": ["hourly_mean", "daily_mean"],
        "anomaly": "hourly_value_minus_daily_mean",
        "metrics": ["mean", "max", "min", "std", "daily_range", "max_daily_range"],
        "plots": ["raw_hourly_with_daily_mean", "anomaly_series"],
        "has_monthly_statistics": False,
        "has_daily_range": True,
        "special_handling": None,
    },
    "temperature": {
        "display_name": "Temperature",
        "display_name_cn": "温度",
        "display_name_en": "Temperature",
        "unit": "degC",
        "source": "excel",
        "default_file_name": "temp.xls",
        "valid_min": -5,
        "valid_max": 45,
        "y_axis_range": None,
        "qc_profile": "marine_temperature_v2_stage1",
        "hampel_window": 7,
        "hampel_sigma": 3.0,
        "rate_change_limit": None,
        "constant_value_window": 12,
        "datetime_column_aliases": [
            "datetime", "date_time", "timestamp", "time", "date",
            "日期时间", "时间", "日期", "监测时间", "采样时间", "观测时间",
        ],
        "value_column_aliases": [
            "temperature", "temperature_c", "temp", "temp_c", "value", "温度", "水温", "测值", "数值", "值",
        ],
        "qc_rules": {
            "required_fields": ["datetime", "value"],
            "valid_min": -5,
            "valid_max": 45,
            "valid_range": [-5, 45],
        },
        "resampling": ["hourly_mean", "daily_mean"],
        "anomaly": "hourly_value_minus_daily_mean",
        "metrics": ["mean", "max", "min", "std", "monthly_mean", "monthly_std"],
        "plots": ["raw_hourly_with_daily_mean", "anomaly_series", "monthly_statistics"],
        "has_monthly_statistics": True,
        "has_daily_range": False,
        "special_handling": None,
    },
}


V2_RESERVED_SOURCES = {
    "mat": "MAT file reading is excluded from V1/V2 stage 1 and reserved for later review.",
}


def get_variable_metadata(variable_key):
    """Return registry metadata for a supported variable."""
    try:
        return deepcopy(VARIABLE_REGISTRY[variable_key])
    except KeyError as exc:
        supported = ", ".join(list_v1_variables())
        raise KeyError(
            f"Unsupported variable: {variable_key!r}. Supported variables: {supported}."
        ) from exc


def list_v1_variables():
    """Return variable keys currently enabled in the app."""
    return tuple(VARIABLE_REGISTRY.keys())


def get_display_name_cn(variable_key):
    """Return Chinese display name from the registry."""
    return get_variable_metadata(variable_key)["display_name_cn"]
