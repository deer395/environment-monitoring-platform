# Data Schema

## V1 Input Rule

V1 supports Excel input only.

MAT files are not supported in V1. MAT support is reserved for V2.

## File Model

V1 uses one Excel file per variable.

Supported variables:

1. `depth`
2. `temperature`

Each variable file must map to metadata in `src/variable_registry.py`.

Current private V1 files:

| Variable | File | Observed datetime column | Observed value column |
|---|---|---|---|
| `depth` | `data_private/depth.xls` | `时间` | `值` |
| `temperature` | `data_private/temp.xls` | `时间` | `值` |

Both current files are legacy `.xls` workbooks. Reading them with pandas requires
the optional `xlrd` dependency.

## Required Columns

Each Excel file must contain at least:

| Logical field | Required | Type | Description |
|---|---:|---|---|
| `datetime` | Yes | datetime-compatible | Observation timestamp. |
| `value` | Yes | numeric-compatible | Observed variable value. |

The physical Excel column names may differ by file, but V1 must resolve them through the variable registry.

## Recommended Columns

| Logical field | Required | Type | Description |
|---|---:|---|---|
| `station_id` | No | string | Station identifier. |
| `station_name` | No | string | Station display name. |
| `quality_flag` | No | string | Existing source quality flag, if available. |

## Variable Registry Metadata

Each variable entry should define:

1. Variable key.
2. Display name.
3. Unit.
4. Accepted datetime column names.
5. Accepted value column names.
6. Quality-control placeholder rules.
7. Required resampling outputs.
8. Required metrics.
9. Required plots.

## Time Handling

V1 assumes:

1. One local project time zone or timezone-naive timestamps.
2. Timestamps can be parsed by the selected deterministic processing engine.
3. Records are sorted by timestamp after loading.

V1 does not handle:

1. Cross-timezone conversion.
2. Ambiguous daylight-saving time conversion.
3. Mixed timestamp formats that cannot be parsed deterministically.

## Quality-Control Expectations

V1 quality control is a deterministic preprocessing step.

The QC module should eventually support:

1. Missing datetime detection.
2. Missing value detection.
3. Non-numeric value detection.
4. Duplicate timestamp detection.
5. Variable-specific valid range checks from the registry.

This document defines the architecture only. Full QC logic is not implemented yet.
