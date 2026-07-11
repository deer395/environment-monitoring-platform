"""Report text placeholders for V1.

AI report generation is excluded from V1.

V1 may include simple deterministic text snippets assembled from computed
tables and metadata. Any future AI report generation must be V2 or later and
must use computed structured statistics only, never raw Excel or MAT data.
"""


def build_deterministic_report_notes(variable_key, metrics_result, qc_summary):
    """Build simple non-AI report notes from computed outputs.

    This is a placeholder. Full deterministic text assembly is not implemented
    yet.
    """
    pass


def ai_report_generation_v1_status():
    """Document that AI report generation is out of scope for V1.

    This is a placeholder marker for architecture clarity.
    """
    pass
