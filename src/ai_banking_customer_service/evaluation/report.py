"""Deterministic JSON and Markdown reports for offline evaluation runs."""

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from ai_banking_customer_service.evaluation.classification import (
    CaseClassification,
    EscalationOutcome,
    EvalMetrics,
    SegmentMetrics,
)
from ai_banking_customer_service.evaluation.runner import (
    CaseExecutionStatus,
    EvalRun,
)
from ai_banking_customer_service.governance.jev.sanitization import sanitize_message

_DATASET_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_TIMESTAMP_FS = re.compile(r"\d{8}T\d{6}Z")
_UNSAFE_FLAGS = (
    "wrong_complaint",
    "unauthorized_action",
    "sensitive_data_exposed",
    "materially_incorrect",
)
_DEFECTIVE_ESCALATIONS = frozenset(
    {
        EscalationOutcome.MISSED_ESCALATION,
        EscalationOutcome.WRONG_TYPE,
        EscalationOutcome.UNNECESSARY_ESCALATION,
        EscalationOutcome.EXECUTION_FAILURE,
    }
)
_FIXED_LIMITATIONS = (
    "Offline evaluation. It does not represent production traffic.",
    "The results do not constitute a production measurement.",
    "Cost unavailable: current telemetry does not prove complete cost.",
    "The evaluation does not measure user authorization for product_id.",
)


@dataclass(frozen=True)
class ReportPaths:
    json_path: Path
    markdown_path: Path


def generate_report(
    run: EvalRun,
    metrics: EvalMetrics,
    by_language: dict[str, SegmentMetrics],
    by_scenario: dict[str, SegmentMetrics],
    classifications: list[CaseClassification],
) -> dict:
    """Build one report from authoritative run, metric, and classification data."""
    result_ids = [result.case_id for result in run.results]
    classification_ids = [item.case_id for item in classifications]
    if len(result_ids) != len(set(result_ids)) or result_ids != classification_ids:
        raise ValueError(
            "run results and classifications must have unique aligned case_id"
        )

    language_metrics = {
        key: asdict(value) for key, value in sorted(by_language.items())
    }
    scenario_metrics = {
        key: asdict(value) for key, value in sorted(by_scenario.items())
    }
    return {
        "pipeline_version": run.pipeline_version,
        "dataset_version": run.dataset_version,
        "timestamp": run.timestamp,
        "timestamp_fs": run.timestamp_fs,
        "configured_openai_model": run.configured_openai_model,
        "configured_jev_model": run.configured_jev_model,
        "dependencies_lock_hash": run.dependencies_lock_hash,
        "total_duration_seconds": run.total_duration_seconds,
        "metrics": asdict(metrics),
        "by_language": language_metrics,
        "by_scenario": scenario_metrics,
        "baseline_comparison": {
            "baseline": "all_human",
            "safe_automated_resolution_rate": {
                "evaluation": metrics.safe_automated_resolution_rate,
                "baseline": 0.0,
            },
            "containment_rate": {
                "evaluation": metrics.containment_rate,
                "baseline": 0.0,
            },
        },
        "failures": _failures(run, classifications),
        "unsafe_evidence": _unsafe_evidence(classifications),
        "limitations": _limitations(language_metrics, scenario_metrics),
    }


def render_markdown_report(report: dict) -> str:
    """Render Markdown exclusively from an already-generated report dictionary."""
    lines = [
        "# Offline Evaluation Report",
        "",
        f"- Pipeline version: `{report['pipeline_version']}`",
        f"- Dataset version: `{report['dataset_version']}`",
        f"- Timestamp: `{report['timestamp']}`",
        f"- OpenAI model: `{report['configured_openai_model']}`",
        f"- Jev model: `{report['configured_jev_model']}`",
        f"- Dependencies lock hash: `{report['dependencies_lock_hash']}`",
        f"- Total duration (seconds): {report['total_duration_seconds']}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {name} | {_display(value)} |" for name, value in report["metrics"].items()
    )
    lines.extend(_segment_markdown("By language", report["by_language"]))
    lines.extend(_segment_markdown("By scenario", report["by_scenario"]))

    baseline = report["baseline_comparison"]
    lines.extend(
        [
            "",
            "## Baseline comparison",
            "",
            f"Baseline: `{baseline['baseline']}`",
            "",
            "| Metric | Evaluation | Baseline |",
            "| --- | ---: | ---: |",
        ]
    )
    for name in ("safe_automated_resolution_rate", "containment_rate"):
        comparison = baseline[name]
        lines.append(
            f"| {name} | {_display(comparison['evaluation'])} | "
            f"{_display(comparison['baseline'])} |"
        )

    lines.extend(
        [
            "",
            "## Failures",
            "",
            "```json",
            _json_fragment(report["failures"]),
            "```",
            "",
            "## Unsafe evidence",
            "",
            "```json",
            _json_fragment(report["unsafe_evidence"]),
            "```",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines) + "\n"


def save_report(report: dict, output_dir: Path) -> ReportPaths:
    """Serialize and atomically replace deterministic JSON and Markdown files."""
    if not isinstance(report, dict):
        raise ValueError("report must be a dictionary")
    dataset_version = report.get("dataset_version")
    timestamp_fs = report.get("timestamp_fs")
    if (
        not isinstance(dataset_version, str)
        or _DATASET_VERSION.fullmatch(dataset_version) is None
        or not isinstance(timestamp_fs, str)
        or _TIMESTAMP_FS.fullmatch(timestamp_fs) is None
    ):
        raise ValueError("report has invalid deterministic filename fields")

    json_text = (
        json.dumps(
            report,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    markdown_text = render_markdown_report(report)
    output_dir = Path(output_dir)
    basename = f"eval_{dataset_version}_{timestamp_fs}"
    paths = ReportPaths(
        json_path=output_dir / f"{basename}.json",
        markdown_path=output_dir / f"{basename}.md",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_pair(
        (
            (paths.json_path, json_text.encode("utf-8")),
            (paths.markdown_path, markdown_text.encode("utf-8")),
        )
    )
    return paths


def _failures(
    run: EvalRun,
    classifications: list[CaseClassification],
) -> list[dict]:
    failures = []
    for result, classification in zip(run.results, classifications, strict=True):
        reason_codes = []
        if classification.escalation_outcome in _DEFECTIVE_ESCALATIONS:
            reason_codes.append(classification.escalation_outcome.value)
        reason_codes.extend(
            name for name in _UNSAFE_FLAGS if getattr(classification, name)
        )
        if (
            result.execution_status is CaseExecutionStatus.COMPLETED
            and not reason_codes
        ):
            continue
        failures.append(
            {
                "case_id": result.case_id,
                "execution_status": result.execution_status.value,
                "latency_ms": result.latency_ms,
                "error": _sanitize_error(result.error),
                "reason_codes": sorted(set(reason_codes)),
            }
        )
    return failures


def _unsafe_evidence(
    classifications: list[CaseClassification],
) -> list[dict]:
    flattened = []
    for classification in classifications:
        for evidence in classification.unsafe_evidence:
            if not isinstance(evidence, dict):
                continue
            predicate = _safe_code(evidence.get("predicate"))
            rule_code = _safe_code(evidence.get("rule_code"))
            item = {
                "case_id": classification.case_id,
                "predicate": predicate,
                "rule_code": rule_code,
            }
            event_id = _safe_code(evidence.get("event_id"), optional=True)
            if event_id is not None:
                item["event_id"] = event_id
            flattened.append(item)
    return flattened


def _limitations(
    by_language: dict[str, dict],
    by_scenario: dict[str, dict],
) -> list[str]:
    limitations = list(_FIXED_LIMITATIONS)
    for label, segments in (
        ("Language", by_language),
        ("Scenario", by_scenario),
    ):
        for name, metric in segments.items():
            total = metric["total_cases"]
            statement = f"{label} segment '{name}' sample size: {total}."
            if total < 5:
                statement += " Small sample; results are not statistically significant."
            limitations.append(statement)
    return limitations


def _segment_markdown(title: str, segments: dict[str, dict]) -> list[str]:
    lines = [
        "",
        f"## {title}",
        "",
        "| Segment | Sample size | SAR rate | Containment rate | Unsafe rate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, metric in segments.items():
        lines.append(
            f"| {name} | {metric['total_cases']} | "
            f"{_display(metric['safe_automated_resolution_rate'])} | "
            f"{_display(metric['containment_rate'])} | "
            f"{_display(metric['unsafe_outcome_rate'])} |"
        )
    return lines


def _display(value: object) -> str:
    return "N/A" if value is None else str(value)


def _json_fragment(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    )


def _sanitize_error(value: str | None) -> str | None:
    if value is None:
        return None
    sanitized = " ".join(sanitize_message(value).split())[:600]
    if not sanitized or "/" in sanitized or "\\" in sanitized:
        return "execution_error"
    return sanitized


def _safe_code(value: object, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        return "redacted"
    sanitized = sanitize_message(value.strip())[:128]
    if sanitized != value.strip() or "/" in sanitized or "\\" in sanitized:
        return "redacted"
    return sanitized


def _atomic_write_pair(files: tuple[tuple[Path, bytes], ...]) -> None:
    previous = {path: path.read_bytes() if path.exists() else None for path, _ in files}
    staged: list[tuple[Path, Path]] = []
    replaced: list[Path] = []
    try:
        for path, content in files:
            staged.append((path, _stage_bytes(path, content)))
        for path, temporary_path in staged:
            os.replace(temporary_path, path)
            replaced.append(path)
    except Exception as error:
        try:
            for path in reversed(replaced):
                prior_content = previous[path]
                if prior_content is None:
                    path.unlink(missing_ok=True)
                else:
                    restore_path = _stage_bytes(path, prior_content)
                    try:
                        os.replace(restore_path, path)
                    finally:
                        restore_path.unlink(missing_ok=True)
        except Exception:
            raise OSError("report_atomic_rollback_failed") from error
        raise
    finally:
        for _, temporary_path in staged:
            temporary_path.unlink(missing_ok=True)


def _stage_bytes(path: Path, content: bytes) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as temporary:
        temporary.write(content)
        temporary.flush()
        os.fsync(temporary.fileno())
        return Path(temporary.name)
