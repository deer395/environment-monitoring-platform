"""Variable metadata registry for the V1/V2 Excel-only workflow."""

from copy import deepcopy


V2_RESERVED_SOURCES = {
    "mat": "MAT file reading is excluded from V1/V2 stage 1 and reserved for later review.",
}


STANDARD_METRICS = [
    "count",
    "valid_count",
    "missing_count",
    "mean",
    "min",
    "max",
    "median",
    "std",
    "monthly_mean",
    "monthly_std",
    "daily_range",
    "max_daily_range",
]

STANDARD_PLOTS = [
    "raw_hourly_with_daily_mean",
    "anomaly_series",
    "monthly_statistics",
    "daily_range",
]

COMMON_DATETIME_ALIASES = [
    "datetime",
    "date_time",
    "timestamp",
    "time",
    "date",
    "日期时间",
    "时间",
    "日期",
    "监测时间",
    "采样时间",
    "观测时间",
]

COMMON_VALUE_ALIASES = ["value", "监测值", "数值", "值"]


def _standard_capabilities():
    return {
        "sampling_type": "high_frequency",
        "aggregation": "mean",
        "supports_hourly": True,
        "supports_daily": True,
        "supports_monthly": True,
        "supports_intraday_anomaly": True,
        "supports_daily_range": True,
        "supports_harmonic_analysis": False,
        "resampling": ["hourly_mean", "daily_mean"],
        "anomaly": "hourly_value_minus_daily_mean",
        "metrics": STANDARD_METRICS.copy(),
        "plots": STANDARD_PLOTS.copy(),
        "has_monthly_statistics": True,
        "has_daily_range": True,
        "special_handling": None,
    }


VARIABLE_REGISTRY = {
    "depth": {
        **_standard_capabilities(),
        "display_name": "Depth",
        "display_name_cn": "水深",
        "display_name_en": "Depth",
        "unit": "m",
        "source": "excel",
        "default_file": "depth.xls",
        "default_file_name": "depth.xls",
        "valid_min": 0,
        "valid_max": 100,
        "y_axis_range": None,
        "qc_profile": "marine_depth_v2_stage1",
        "hampel_window": 25,
        "hampel_sigma": 4.0,
        "hampel_min_abs_deviation": 0.8,
        "rate_change_limit": None,
        "constant_value_window": 12,
        "constant_value_tolerance": 0.0,
        "datetime_column_aliases": COMMON_DATETIME_ALIASES.copy(),
        "value_column_aliases": ["depth", "depth_m", "water_depth", "水深", "深度", "水位"] + COMMON_VALUE_ALIASES,
        "aliases": {
            "datetime": COMMON_DATETIME_ALIASES.copy(),
            "value": ["depth", "depth_m", "water_depth", "水深", "深度", "水位"] + COMMON_VALUE_ALIASES,
        },
        "qc_rules": {
            "required_fields": ["datetime", "value"],
            "valid_min": 0,
            "valid_max": 100,
            "valid_range": [0, 100],
        },
    },
    "temperature": {
        **_standard_capabilities(),
        "display_name": "Temperature",
        "display_name_cn": "温度",
        "display_name_en": "Temperature",
        "unit": "degC",
        "source": "excel",
        "default_file": "temp.xls",
        "default_file_name": "temp.xls",
        "valid_min": -5,
        "valid_max": 45,
        "y_axis_range": None,
        "qc_profile": "marine_temperature_v2_stage1",
        "hampel_window": 49,
        "hampel_sigma": 4.0,
        "hampel_min_abs_deviation": 2.0,
        "rate_change_limit": None,
        "constant_value_window": 12,
        "constant_value_tolerance": 0.0,
        "datetime_column_aliases": COMMON_DATETIME_ALIASES.copy(),
        "value_column_aliases": ["temperature", "temperature_c", "temp", "temp_c", "温度", "水温"] + COMMON_VALUE_ALIASES,
        "aliases": {
            "datetime": COMMON_DATETIME_ALIASES.copy(),
            "value": ["temperature", "temperature_c", "temp", "temp_c", "温度", "水温"] + COMMON_VALUE_ALIASES,
        },
        "qc_rules": {
            "required_fields": ["datetime", "value"],
            "valid_min": -5,
            "valid_max": 45,
            "valid_range": [-5, 45],
        },
    },
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


def list_enabled_variables():
    """Return variable keys enabled for the current local app."""
    return tuple(
        key for key, metadata in VARIABLE_REGISTRY.items()
        if metadata.get("enabled", True)
    )


def get_display_name_cn(variable_key):
    """Return Chinese display name from the registry."""
    return get_variable_metadata(variable_key)["display_name_cn"]
