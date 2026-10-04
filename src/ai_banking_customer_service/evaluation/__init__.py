"""Offline held-out evaluation contracts."""

from ai_banking_customer_service.evaluation.cases import (
    EvalCase,
    EvalConfig,
    EvalManifest,
    load_eval_cases,
    load_eval_config,
    validate_coverage,
    validate_held_out_independence,
)
from ai_banking_customer_service.evaluation.classification import (
    CaseClassification,
    EscalationOutcome,
    EvalMetrics,
    SegmentMetrics,
    calculate_metrics,
    calculate_segment_metrics,
    classify_case,
)
from ai_banking_customer_service.evaluation.factory import (
    EvaluationDependencies,
    build_evaluation_dependencies,
)
from ai_banking_customer_service.evaluation.report import (
    ReportPaths,
    generate_report,
    render_markdown_report,
    save_report,
)
from ai_banking_customer_service.evaluation.runner import (
    CaseExecutionStatus,
    CaseObservation,
    CaseResult,
    EvalRun,
    run_case,
    run_evaluation,
)
from ai_banking_customer_service.evaluation.sink import RecordingAuditSink

__all__ = [
    "CaseClassification",
    "CaseExecutionStatus",
    "CaseObservation",
    "CaseResult",
    "EscalationOutcome",
    "EvalCase",
    "EvalConfig",
    "EvalManifest",
    "EvalMetrics",
    "EvalRun",
    "EvaluationDependencies",
    "RecordingAuditSink",
    "ReportPaths",
    "SegmentMetrics",
    "build_evaluation_dependencies",
    "calculate_metrics",
    "calculate_segment_metrics",
    "classify_case",
    "generate_report",
    "load_eval_cases",
    "load_eval_config",
    "render_markdown_report",
    "run_case",
    "run_evaluation",
    "save_report",
    "validate_coverage",
    "validate_held_out_independence",
]
