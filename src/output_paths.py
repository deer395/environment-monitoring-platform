"""Centralized output paths for the current development stage."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGE_NAME = "v2_stage4_1_qc_workflow"
STAGE_ROOT = PROJECT_ROOT / "outputs" / STAGE_NAME
FIGURES_DIR = STAGE_ROOT / "figures"
TABLES_DIR = STAGE_ROOT / "tables"
LOGS_DIR = STAGE_ROOT / "logs"


def ensure_stage_dirs():
    """Create the stage output directory tree and return key paths."""
    for path in (STAGE_ROOT, FIGURES_DIR, TABLES_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)
    return {"root": STAGE_ROOT, "figures": FIGURES_DIR, "tables": TABLES_DIR, "logs": LOGS_DIR}


def figure_path(file_name):
    ensure_stage_dirs()
    return FIGURES_DIR / file_name


def table_path(file_name):
    ensure_stage_dirs()
    return TABLES_DIR / file_name


def log_path(file_name):
    ensure_stage_dirs()
    return LOGS_DIR / file_name
