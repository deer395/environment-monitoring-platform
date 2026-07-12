"""Input loading for the V1 Excel-only workflow.

V1 supports Excel input only. MAT files are intentionally excluded from V1
because MAT usage in the current MATLAB workflow is a temporary workaround for
problematic source spreadsheets.

MAT file support is reserved for V2.
"""

from pathlib import Path

import pandas as pd

try:
    from .variable_registry import VARIABLE_REGISTRY, get_variable_metadata
except ImportError:  # pragma: no cover - allows direct script-style imports.
    from variable_registry import VARIABLE_REGISTRY, get_variable_metadata


EXCEL_SUFFIXES = {".xls", ".xlsx", ".xlsm"}


def _normalize_column_name(name):
    """Normalize an Excel column name for alias matching."""
    return str(name).strip().lower().replace(" ", "").replace("_", "")


def _find_column(columns, aliases, logical_name):
    """Find the first column matching one of the configured aliases."""
    normalized_aliases = {_normalize_column_name(alias) for alias in aliases}
    for column in columns:
        if _normalize_column_name(column) in normalized_aliases:
            return column

    available = ", ".join(str(column) for column in columns)
    expected = ", ".join(str(alias) for alias in aliases)
    raise ValueError(
        f"Could not find {logical_name!r} column. "
        f"Expected one of: {expected}. Available columns: {available}."
    )


def _excel_engine_for(path):
    """Return the pandas engine for a V1 Excel file."""
    suffix = path.suffix.lower()
    if suffix == ".xls":
        return "xlrd"
    if suffix in {".xlsx", ".xlsm"}:
        return "openpyxl"
    raise ValueError(
        f"V1 supports Excel files only ({', '.join(sorted(EXCEL_SUFFIXES))}). "
        f"Got: {path.name}"
    )


def _read_excel(path, sheet_name=0):
    """Read an Excel file with a clear message for missing optional engines."""
    engine = _excel_engine_for(path)
    try:
        return pd.read_excel(path, sheet_name=sheet_name, engine=engine)
    except ImportError as exc:
        if engine == "xlrd":
            raise ImportError(
                "Reading .xls files requires the optional dependency 'xlrd'. "
                "Install it with: pip install xlrd"
            ) from exc
        raise


def load_excel_variable(file_path, variable_key, registry=None, sheet_name=0):
    """Load one variable from one Excel file.

    V1 behavior:
    - Read an Excel file only.
    - Resolve datetime and value columns using registry metadata.
    - Return a normalized DataFrame with ``datetime`` and ``value`` fields.
    - Coerce datetime and numeric values deterministically.
    - Drop rows where datetime or value cannot be parsed.
    - Sort records by datetime.

    MAT files are not supported in V1.
    """
    path = Path(file_path)
    reject_mat_input(path)
    if path.suffix.lower() not in EXCEL_SUFFIXES:
        raise ValueError(f"V1 supports Excel input only. Got: {path.name}")

    registry = registry or VARIABLE_REGISTRY
    metadata = registry.get(variable_key) or get_variable_metadata(variable_key)
    raw = _read_excel(path, sheet_name=sheet_name)

    aliases = metadata.get("aliases", {})
    datetime_aliases = aliases.get("datetime", metadata["datetime_column_aliases"])
    value_aliases = aliases.get("value", metadata["value_column_aliases"])
    datetime_column = _find_column(raw.columns, datetime_aliases, "datetime")
    value_column = _find_column(raw.columns, value_aliases, "value")

    data = raw[[datetime_column, value_column]].copy()
    data = data.rename(columns={datetime_column: "datetime", value_column: "value"})
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data = data.dropna(subset=["datetime", "value"]).sort_values("datetime")
    data = data.reset_index(drop=True)
    data.insert(0, "record_id", [f"{variable_key}_{idx}" for idx in range(len(data))])
    data["variable"] = variable_key
    data["unit"] = metadata["unit"]

    data.attrs["variable_key"] = variable_key
    data.attrs["display_name"] = metadata["display_name"]
    data.attrs["unit"] = metadata["unit"]
    data.attrs["source_file"] = str(path)
    data.attrs["source_datetime_column"] = str(datetime_column)
    data.attrs["source_value_column"] = str(value_column)
    return data


def load_default_variable(data_dir, variable_key, registry=None):
    """Load one configured variable from its registry default Excel file."""
    registry = registry or VARIABLE_REGISTRY
    metadata = registry.get(variable_key) or get_variable_metadata(variable_key)
    default_file = metadata.get("default_file") or metadata.get("default_file_name")
    if not default_file:
        raise ValueError(f"No default file configured for variable: {variable_key!r}")
    return load_excel_variable(Path(data_dir) / default_file, variable_key, registry=registry)


def load_variables(data_dir, variable_keys=None, registry=None):
    """Load configured variables without adding variable-specific loader code."""
    registry = registry or VARIABLE_REGISTRY
    keys = tuple(variable_keys) if variable_keys is not None else tuple(registry.keys())
    return {
        variable_key: load_default_variable(data_dir, variable_key, registry=registry)
        for variable_key in keys
    }


def reject_mat_input(file_path):
    """Reject MAT files because they are out of scope for V1.

    V1 must not read MAT files. A future V2 implementation may add a separate
    MAT loader for legacy or emergency recovery workflows.
    """
    path = Path(file_path)
    if path.suffix.lower() == ".mat":
        raise ValueError("MAT file reading is excluded from V1 and reserved for V2.")


def load_depth_and_temperature(data_dir):
    """Load the default V1 private depth and temperature Excel files.

    Expected files:
    - ``depth.xls``
    - ``temp.xls``

    Args:
        data_dir: Directory containing the V1 Excel files.

    Returns:
        A dictionary with ``depth`` and ``temperature`` DataFrames.
    """
    return load_variables(data_dir, ("depth", "temperature"))
