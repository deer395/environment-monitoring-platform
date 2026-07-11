# V1 Scope

## Decision

V1 is Excel-only.

The current MATLAB workflow temporarily loads depth, temperature, and salinity from a MAT file because the original temperature-salinity-depth Excel data had quality problems. That is a temporary workaround, not the intended product workflow.

The intended project workflow is that all variables come from Excel files. Therefore, V1 must be designed around Excel input only.

MAT file support is explicitly reserved for V2.

## V1 Variables

V1 supports only two variables:

1. `depth`
2. `temperature`

All variable metadata must be defined in `src/variable_registry.py`.

## V1 Input

V1 accepts Excel files only.

Each variable file must contain at least:

1. A datetime column.
2. A value column.

Column names, units, display names, quality-control rules, and metric requirements are defined by the variable registry.

## V1 Processing Workflow

For each supported variable:

1. Read Excel.
2. Parse datetime and value columns.
3. Sort records by time.
4. Apply quality control.
5. Resample to hourly means.
6. Resample to daily means.
7. Calculate intra-day anomaly as:

   `hourly value - corresponding daily mean`

8. Plot raw hourly series with daily mean.
9. Plot anomaly series.
10. Generate deterministic report tables.

## V1 Metrics

### Temperature

V1 temperature metrics:

1. Mean.
2. Maximum.
3. Minimum.
4. Monthly mean.
5. Monthly standard deviation.

### Depth

V1 depth metrics:

1. Daily maximum variation amplitude.

Definition:

`daily maximum variation amplitude = daily maximum depth - daily minimum depth`

## V1 Exclusions

V1 does not include:

1. MAT file reading.
2. Harmonic analysis.
3. Salinity.
4. Water-quality variables.
5. AI report generation.
6. Database input.
7. Batch report generation.
8. Cloud deployment.

## V2 Candidates

V2 may include:

1. MAT file support for legacy or emergency recovery workflows.
2. Harmonic analysis.
3. Salinity.
4. Water-quality variables.
5. AI-assisted report text generation from computed statistics.
6. Batch processing across stations and variables.
