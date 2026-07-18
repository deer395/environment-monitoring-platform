"""Build reproducible monthly-report evaluation samples from station workbooks."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

from .report_context import _build_narratives
from .time_series_interpretation import extract_time_series_features
from .variable_registry import get_variable_metadata, list_enabled_variables

ALGORITHM_VERSION = "v4.2-frozen"
REQUIRED_MONTHLY_COLUMNS = ("year_month", "monthly_mean", "monthly_std")


def stable_sample_id(station_name: str, variable_key: str, start_month: str, end_month: str) -> str:
    """Return a deterministic, filesystem-safe identifier (never a random UUID)."""
    source = "|".join((station_name, variable_key, start_month, end_month))
    return f"monthly-{sha256(source.encode('utf-8')).hexdigest()[:16]}"


def _normalise(value: object) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def identify_monthly_sheet(sheet_names: list[str], variable_key: str) -> str | None:
    """Find a monthly sheet, including Excel's 31-character truncation."""
    key = _normalise(variable_key)
    matches = [name for name in sheet_names if "monthly" in _normalise(name) and _normalise(name).startswith(key)]
    return matches[0] if len(matches) == 1 else None


def _read_monthly(workbook: Path, sheet_name: str) -> pd.DataFrame:
    frame = pd.read_excel(workbook, sheet_name=sheet_name)
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    missing = [column for column in REQUIRED_MONTHLY_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
    frame = frame.loc[:, list(REQUIRED_MONTHLY_COLUMNS)].copy()
    frame["year_month"] = frame["year_month"].astype(str).str.slice(0, 7)
    frame["monthly_mean"] = pd.to_numeric(frame["monthly_mean"], errors="coerce")
    frame["monthly_std"] = pd.to_numeric(frame["monthly_std"], errors="coerce")
    frame = frame.sort_values("year_month", kind="stable").reset_index(drop=True)
    if frame["monthly_mean"].notna().sum() == 0:
        raise ValueError("monthly_mean contains no numeric values")
    return frame


def _json_value(value: Any) -> Any:
    if isinstance(value, dict): return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [_json_value(item) for item in value]
    if isinstance(value, pd.Timestamp): return value.isoformat()
    if pd.isna(value): return None
    if hasattr(value, "item"): return value.item()
    return value


def build_baseline(monthly: pd.DataFrame, variable_key: str) -> dict[str, Any]:
    """Call the frozen V4.2 feature and narrative functions for a monthly series."""
    metadata = get_variable_metadata(variable_key)
    # The baseline deliberately supplies no hourly/daily data: this evaluation is
    # restricted to the monthly input, while the existing monthly logic is reused.
    empty_hourly = pd.DataFrame({"datetime": pd.Series(dtype="datetime64[ns]"), "value": pd.Series(dtype=float)})
    empty_daily = pd.DataFrame({"value": pd.Series(dtype=float)})
    empty_ranges = pd.DataFrame({"daily_range": pd.Series(dtype=float)})
    features = extract_time_series_features(empty_hourly, empty_daily, monthly, empty_ranges, None)
    narratives = _build_narratives(
        metadata["display_name_cn"], metadata["unit"], {"monthly": monthly}, {"interpretation": features}
    )
    info = features.get("monthly_interpretation", {})
    stages = info.get("segments", [])
    directions = [stage.get("direction") for stage in stages]
    return _json_value({
        "current_primary_pattern": features.get("primary_mode"),
        "current_trend_direction": features.get("narrative_mode"),
        "current_change_point": info.get("change_month"),
        "current_stages": stages,
        "current_highest_month": features.get("monthly_high_month"),
        "current_lowest_month": features.get("monthly_low_month"),
        "current_max_std_month": features.get("highest_variability_month"),
        "current_monthly_narrative": narratives.get("monthly", ""),
        "current_stage_count": len(stages),
        "current_direction_change_count": sum(a != b for a, b in zip(directions, directions[1:])),
    })


def scan_monthly_workbooks(input_dir: str | Path) -> tuple[list[dict[str, Any]], list[dict[str, str]], int]:
    """Scan every workbook; a bad file or variable never stops the remaining scan."""
    input_path = Path(input_dir)
    samples: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    # Excel creates ``~$`` lock files beside an open workbook; these are not
    # station workbooks and cannot be read as valid data.
    workbooks = sorted(path for path in input_path.glob("*.xlsx") if not path.name.startswith("~$"))
    for workbook in workbooks:
        station_name = workbook.stem
        try:
            sheet_names = pd.ExcelFile(workbook).sheet_names
        except Exception as exc:  # pragma: no cover - engine error varies by platform
            warnings.append({"workbook_name": workbook.name, "variable_key": "", "reason": f"unable to read workbook: {exc}"})
            continue
        for variable_key in list_enabled_variables():
            sheet_name = identify_monthly_sheet(sheet_names, variable_key)
            if not sheet_name:
                warnings.append({"workbook_name": workbook.name, "variable_key": variable_key, "reason": "monthly_statistics sheet not found"})
                continue
            try:
                monthly = _read_monthly(workbook, sheet_name)
                valid = monthly.dropna(subset=["monthly_mean"])
                start, end = valid.iloc[0]["year_month"], valid.iloc[-1]["year_month"]
                metadata = get_variable_metadata(variable_key)
                baseline = build_baseline(monthly, variable_key)
                sample = {
                    "sample_id": stable_sample_id(station_name, variable_key, start, end),
                    "station_name": station_name, "workbook_name": workbook.name,
                    "variable_key": variable_key, "variable_name": metadata["display_name_cn"], "unit": metadata["unit"],
                    "analysis_start_month": start, "analysis_end_month": end, "month_count": len(monthly),
                    "monthly_mean_min": valid["monthly_mean"].min(), "monthly_mean_max": valid["monthly_mean"].max(),
                    "monthly_mean_range": valid["monthly_mean"].max() - valid["monthly_mean"].min(),
                    "monthly_std_mean": monthly["monthly_std"].mean(), "monthly_std_max": monthly["monthly_std"].max(),
                    "selected_for_annotation": "yes", "dataset_split": "development", "data_status": "valid", "notes": "",
                    "monthly": monthly, "baseline": baseline,
                }
                sample.update({key: baseline[key] for key in ("current_stage_count", "current_direction_change_count", "current_primary_pattern")})
                samples.append(sample)
            except Exception as exc:
                warnings.append({"workbook_name": workbook.name, "variable_key": variable_key, "reason": str(exc)})
    return samples, warnings, len(workbooks)
