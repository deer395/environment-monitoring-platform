# Implementation Plan

## Goal

Build a 2-3 week local V1 demo that processes Excel-based depth and temperature data through a deterministic analysis pipeline.

No full logic is implemented in the current architecture pass. The source files contain placeholders and docstrings only.

## V1 Pipeline

1. `src/variable_registry.py`
   - Define supported variables and metadata.
   - V1 variables: `depth`, `temperature`.
   - Mark MAT support as V2.

2. `src/loaders.py`
   - Placeholder for Excel loading.
   - Must not include MAT loading in V1.
   - Future MAT loader belongs to V2.

3. `src/qc.py`
   - Placeholder for deterministic quality-control checks.
   - Should use metadata from the variable registry.

4. `src/resampling.py`
   - Placeholder for hourly and daily mean resampling.

5. `src/anomaly.py`
   - Placeholder for intra-day anomaly calculation:
     `hourly value - corresponding daily mean`.

6. `src/metrics.py`
   - Placeholder for deterministic metric calculation.
   - Temperature: mean, max, min, monthly mean, monthly standard deviation.
   - Depth: daily maximum variation amplitude.

7. `src/plotting.py`
   - Placeholder for raw hourly series with daily mean plot.
   - Placeholder for anomaly series plot.

8. `src/report_tables.py`
   - Placeholder for deterministic tables derived from computed data.

9. `src/report_text.py`
   - Placeholder for non-AI deterministic text snippets only.
   - AI report generation is excluded from V1.

## Suggested Build Order

1. Finalize Excel schema examples for depth and temperature.
2. Finalize `variable_registry.py` metadata.
3. Implement Excel loader.
4. Implement deterministic QC.
5. Implement hourly and daily resampling.
6. Implement anomaly calculation.
7. Implement metrics.
8. Implement plots.
9. Implement report tables.
10. Add a minimal Streamlit interface.
11. Add tests for deterministic calculations.

## V1 Acceptance Checkpoints

1. The app accepts Excel files only.
2. MAT files are rejected or not exposed.
3. Depth and temperature are the only selectable variables.
4. Hourly and daily means are generated deterministically.
5. Intra-day anomaly is calculated as hourly value minus daily mean.
6. Temperature metrics are generated deterministically.
7. Depth daily maximum variation amplitude is generated deterministically.
8. Report tables contain only computed values.
9. No AI report generation is present in V1.

## V2 Notes

V2 may add:

1. MAT file reading.
2. Harmonic analysis.
3. Additional variables.
4. AI report generation based only on computed statistics.
