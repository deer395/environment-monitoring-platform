# Environment Monitoring Data QC & Analysis Platform

> AI-assisted environmental monitoring data quality control, statistical analysis, and automated Word report generation — built with Streamlit and Python.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B)](https://streamlit.io/)

## Overview

This is a **local desktop tool** designed for environmental researchers and analysts to process time-series monitoring data efficiently. It automates the repetitive parts of data QC, analysis, and report drafting — without replacing scientific judgment.

**Key principle**: All numerical computations are deterministic Python code. AI is used **only** for generating report narrative text based on computed statistics — never for calculating values or inventing causal explanations.

## Features

### Data Loading
- Excel file ingestion with flexible column-name matching (supports aliases like `datetime`, `time`, `监测时间`)
- Read-only source files — raw data is never modified
- Unified internal structure: `datetime`, `value`, `variable`, `unit`, `record_id`

### Three-Stage QC Pipeline

| Stage | Description |
|-------|-------------|
| **1. Auto QC** | Sensor-zero detection, hard-range filtering — automatically masked as missing and irreversible |
| **2. Manual Review** | Hampel outlier & constant-value flagging; interactive single-point, box, or lasso selection to delete/keep/restore |
| **3. Confirmation & Analysis** | Final QC dataset locked, then used for all downstream computation |

### Analysis & Output
- **Basic statistics**: max, min, mean, median, std, valid/missing counts
- **Time-series results**: hourly means, daily means, diurnal anomalies, daily range, monthly means, monthly std
- **Visualizations**: QC summary charts, candidate anomaly plots, final QC data plots
- **Exports**:
  - Per-variable results
  - Multi-variable comprehensive workbook with `processing_status` sheet
  - `.docx` Word reports with project metadata

### Supported Variables (9 total)
`depth`, `temperature`, `salinity`, `dissolved_oxygen`, `cod`, `bod`, `nitrate`, `chlorophyll`, `pahs`

All metadata (display names, units, default files, ranges, QC parameters) is centralized in `src/variable_registry.py`.

## Architecture

```
environment-monitoring-platform/
├── app.py                         # Streamlit entry point
├── src/
│   ├── loaders.py                 # Excel file loading & validation
│   ├── anomaly.py                 # Anomaly detection algorithms
│   ├── metrics.py                 # Statistical computation
│   ├── qc.py                      # QC pipeline orchestration
│   ├── manual_qc.py              # Interactive QC UI components
│   ├── plotting.py               # Time-series & QC visualizations
│   ├── report_text.py            # AI-assisted report narrative
│   ├── report_tables.py          # Statistical table generation
│   ├── report_context.py         # Report data context assembly
│   ├── word_report.py            # Legacy Word report export
│   ├── station_word_report.py    # Per-station report generation
│   ├── station_report_context.py # Station-level report data
│   ├── station_task.py           # Station analysis task runner
│   ├── variable_registry.py      # Centralized variable config
│   ├── output_paths.py           # Output path management
│   ├── resampling.py             # Time-series resampling
│   ├── time_series_interpretation.py # Time-series mode analysis
│   ├── export_preview.py         # Export preview components
│   └── version.py               # Version information
├── tests/                        # Unit & integration tests
├── evaluation/                   # Evaluation datasets & annotation
│   └── monthly/                  # Monthly evaluation framework
├── docs/                         # Architecture & design documents
├── scripts/                      # Utility scripts
├── requirements.txt
└── LICENSE
```

## Quick Start

### Prerequisites
- Python 3.10 or higher
- pip

### Installation

```bash
git clone https://github.com/deer395/environment-monitoring-platform.git
cd environment-monitoring-platform
pip install -r requirements.txt
```

### Run

```bash
streamlit run app.py
```

Open the local URL displayed by Streamlit in your browser. Select a variable, upload an Excel file (or use the default sample file configured in the variable registry), and follow the QC pipeline.

## Input Format

Each Excel file should contain at minimum a time column and a value column. The loader recognizes common column name aliases:
- Time columns: `datetime`, `time`, `日期时间`, `监测时间`
- Value columns: configured per variable in `variable_registry.py`

## Current Limitations

- PAHs unit confirmed as `ppb` (project-specific)
- `hard_max=100` for BOD, nitrate, PAHs, and chlorophyll are project-level operational bounds, not universal physical limits
- Harmonic analysis and automated reporting are planned for future versions

## Version History

Key version tags (accessible via `git tag`):

| Tag | Description |
|-----|-------------|
| `v2-qc-complete` | Full QC pipeline complete |
| `v3.1-generic-architecture` | Generalized multi-variable architecture |
| `v3.2.1-qc-interaction-complete` | Interactive QC UI finalized |
| `v3.3-all-variables-complete` | All 9 variables supported |

To checkout a historical version:

```bash
git checkout v3.3-all-variables-complete
```

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
