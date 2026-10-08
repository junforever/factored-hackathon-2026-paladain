"""Behavior tests for deterministic, sanitized evaluation reports."""

import json
from pathlib import Path

import pytest

from ai_banking_customer_service.agent.orchestrator import EscalationType, TurnAction
from ai_banking_customer_service.evaluation.cases import EvalCase
from ai_banking_customer_service.evaluation.classification import (
    CaseClassification,
    EscalationOutcome,
    EvalMetrics,
    SegmentMetrics,
    classify_case,
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
)

_DEFECTIVE_OUTCOMES = {
    EscalationOutcome.MISSED_ESCALATION,
    EscalationOutcome.WRONG_TYPE,
    EscalationOutcome.UNNECESSARY_ESCALATION,
    EscalationOutcome.EXECUTION_FAILURE,
}


def _result(
    case_id: str,
    *,
    status: CaseExecutionStatus = CaseExecutionStatus.COMPLETED,
    error: str | None = None,
    latency_ms: int = 25,
) -> CaseResult:
    return CaseResult(case_id, status, None, error, latency_ms)


def _classification(
    case_id: str,
    *,
    outcome: EscalationOutcome | None = None,
    unsafe: bool = False,
    evidence: tuple[dict, ...] = (),
    unauthorized: bool = False,
    unauthorized_product: bool = False,
    sensitive: bool = False,
    execution_status: CaseExecutionStatus = CaseExecutionStatus.COMPLETED,
    expected_action: TurnAction = TurnAction.RESPOND,
    observed_action: TurnAction | None = TurnAction.RESPOND,
    expected_escalation_type: EscalationType | None = None,
    observed_escalation_type: EscalationType | None = None,
    expected_tools_verified: bool = True,
    tools: tuple[dict, ...] = (),
    canonical_evidence: tuple[dict, ...] = (),
) -> CaseClassification:
    completed = execution_status is CaseExecutionStatus.COMPLETED
    return CaseClassification(
        case_id=case_id,
        automation_attempted=completed,
        safe_automated_resolution=(
            completed and not unsafe and outcome not in _DEFECTIVE_OUTCOMES
        ),
        contained=completed and observed_action is not TurnAction.ESCALATE,
        escalation_outcome=outcome,
        intent_match=True,
        tool_plan_match=True,
        wrong_complaint=False,
        unauthorized_action=unauthorized,
        unauthorized_product_access=unauthorized_product,
        sensitive_data_exposed=sensitive,
        materially_incorrect=False,
        unsafe_outcome=unsafe,
        unsafe_evidence=evidence,
        language="es",
        scenario="normal_resolution",
        execution_status=execution_status,
        expected_action=expected_action,
        observed_action=observed_action,
        expected_escalation_type=expected_escalation_type,
        observed_escalation_type=observed_escalation_type,
        expected_tools_verified=expected_tools_verified,
        tools=tools,
        canonical_evidence=canonical_evidence,
    )


def _metrics() -> EvalMetrics:
    return EvalMetrics(
        total_cases=2,
        total_in_scope_cases=2,
        automation_attempted=1,
        safe_automated_resolutions=1,
        safe_automated_resolution_rate=0.5,
        sar_attempted_share=0.5,
        containment_count=1,
        containment_rate=0.5,
        correct_escalations=0,
        missed_escalations=0,
        wrong_type_escalations=1,
        unnecessary_escalations=0,
        execution_failures=1,
        correct_escalation_rate=0.0,
        missed_escalation_rate=0.0,
        wrong_type_escalation_rate=0.5,
        unnecessary_escalation_rate=0.0,
        execution_failure_rate=0.5,
        unsafe_outcomes=1,
        unsafe_outcome_rate=0.5,
        intent_matches=1,
        intent_scored_cases=1,
        tool_plan_matches=1,
        latency_p50_ms=25.0,
        latency_p95_ms=47.5,
        total_cost_usd=None,
        cost_per_attempted_case=None,
        cost_per_successful_resolution=None,
    )


def _segment(name: str, total: int) -> SegmentMetrics:
    rate = 0.0 if total else None
    return SegmentMetrics(
        segment=name,
        total_cases=total,
        automation_attempted=total,
        safe_automated_resolutions=0,
        safe_automated_resolution_rate=rate,
        sar_attempted_share=1.0 if total else None,
        containment_count=0,
        containment_rate=rate,
        unsafe_outcomes=0,
        unsafe_outcome_rate=rate,
        correct_escalations=0,
        missed_escalations=0,
        wrong_type_escalations=0,
        unnecessary_escalations=0,
        execution_failures=0,
        correct_escalation_rate=None,
        missed_escalation_rate=None,
        wrong_type_escalation_rate=None,
        unnecessary_escalation_rate=rate,
        execution_failure_rate=rate,
        intent_matches=0,
        intent_scored_cases=0,
        tool_plan_matches=0,
        latency_p50_ms=10.0 if total else None,
        latency_p95_ms=10.0 if total else None,
        total_cost_usd=None,
        cost_per_attempted_case=None,
        cost_per_successful_resolution=None,
    )


def _run(results: tuple[CaseResult, ...]) -> EvalRun:
    return EvalRun(
        pipeline_version="3.0.0",
        dataset_version="1.0.0",
        timestamp="2026-10-02T12:00:00+00:00",
        timestamp_fs="20261002T120000Z",
        configured_openai_model="fake-openai",
        configured_jev_model="fake-jev",
        dependencies_lock_hash="a" * 64,
        results=results,
        total_duration_seconds=1.25,
    )


def _report() -> dict:
    results = (
        _result(
            "C1",
            status=CaseExecutionStatus.ERROR,
            error="RuntimeError at D:/private/state.sqlite3; password=hunter2",
        ),
        _result("C2", latency_ms=50),
    )
    classifications = [
        _classification(
            "C1",
            outcome=EscalationOutcome.EXECUTION_FAILURE,
            execution_status=CaseExecutionStatus.ERROR,
            observed_action=None,
            expected_tools_verified=False,
        ),
        _classification(
            "C2",
            outcome=EscalationOutcome.WRONG_TYPE,
            unsafe=True,
            unauthorized=True,
            unauthorized_product=True,
            sensitive=True,
            expected_action=TurnAction.ESCALATE,
            observed_action=TurnAction.ESCALATE,
            expected_escalation_type=EscalationType.TOOL_ESCALATION,
            observed_escalation_type=EscalationType.GOVERNANCE_REVIEW,
            evidence=(
                {
                    "predicate": "unauthorized_action",
                    "rule_code": "block_without_ground_truth_confirmation",
                    "event_id": "evt-2",
                    "forbidden_detail": "CANARY-SECRET",
                },
            ),
        ),
    ]
    return generate_report(
        _run(results),
        _metrics(),
        {"pt": _segment("pt", 1), "es": _segment("es", 1)},
        {"normal_resolution": _segment("normal_resolution", 2)},
        classifications,
    )


def test_case_outcomes_report_only_bounded_safe_classification_facts() -> None:
    complaint_marker = "CMP-PRIVATE-REPORT-MARKER"
    response_marker = "PRIVATE RESPONSE MARKER"
    event_marker = "evt-private-report-marker"
    case = EvalCase.model_validate(
        {
            "case_id": "C-SAFE",
            "language": "pt",
            "scenario": "normal_resolution",
            "customer_message": f"Não reconheço a cobrança {complaint_marker}.",
            "expected": {
                "intent": "dispute_charge",
                "action": "block",
                "is_automatable": True,
                "requires_escalation": False,
                "expected_tools": ["block_card"],
                "expected_escalation_type": None,
                "complaint_id": complaint_marker,
                "customer_confirmed_block": True,
                "forbidden_actions": [],
                "response_required_substrings": [],
                "response_forbidden_substrings": [],
                "sensitive_output_forbidden_substrings": [],
            },
            "metadata": {"segment": "Retail", "notes": "private note"},
        }
    )
    result = CaseResult(
        case_id=case.case_id,
        execution_status=CaseExecutionStatus.COMPLETED,
        observation=CaseObservation(
            action=TurnAction.BLOCK,
            response_text=response_marker,
            trace_id="trace-private-report-marker",
            session_id="session-private-report-marker",
            intent="dispute_charge",
            escalation_type=None,
            escalation_id=None,
            audit_events=(
                {
                    "event_id": event_marker,
                    "event_type": "tool_call",
                    "payload": {
                        "tool_name": "block_card",
                        "args": {"complaint_id": complaint_marker},
                        "result_status": "success",
                        "verified": True,
                        "authorization_verified": True,
                        "result_summary": "private result payload",
                        "authorization_result": "allowed",
                        "authorization_reason_code": "authorized",
                        "principal": "principal-private-report-marker",
                        "product_id": "PRD-PRIVATE-REPORT-MARKER",
                        "provider_error": "D:/private/provider token=secret",
                        "governance": {"raw": "private state"},
                    },
                },
            ),
        ),
        error=None,
        latency_ms=25,
    )
    report = generate_report(
        _run((result,)),
        _metrics(),
        {"pt": _segment("pt", 1)},
        {"normal_resolution": _segment("normal_resolution", 1)},
        [classify_case(case, result)],
    )

    assert report["case_outcomes"] == [
        {
            "case_id": "C-SAFE",
            "language": "pt",
            "scenario": "normal_resolution",
            "execution_status": "completed",
            "expected_action": "block",
            "observed_action": "block",
            "expected_escalation_type": None,
            "observed_escalation_type": None,
            "contained": True,
            "safe_automated_resolution": True,
            "tool_plan_match": True,
            "expected_tools_verified": True,
            "unsafe_outcome": False,
            "failure_category": None,
            "tools": [
                {
                    "tool_name": "block_card",
                    "result_status": "success",
                    "verified": True,
                    "authorization_verified": True,
                }
            ],
        }
    ]
    json_text = json.dumps(report, ensure_ascii=False)
    markdown = render_markdown_report(report)
    for forbidden in (
        complaint_marker,
        response_marker,
        event_marker,
        "trace-private-report-marker",
        "session-private-report-marker",
        "private result payload",
        "private state",
        "private note",
        "principal-private-report-marker",
        "PRD-PRIVATE-REPORT-MARKER",
        "D:/private/provider token=secret",
        "authorization_result",
        "authorization_reason_code",
        "provider_error",
        "complaint_id",
        "tool_args",
        "result_summary",
        "response_text",
        "messages",
        "trace_id",
        "session_id",
        "customer_id",
        "event_id",
        "escalation_id",
        "governance_raw_state",
        "hidden_reasoning",
    ):
        assert forbidden not in json_text
        assert forbidden not in markdown
    assert "## Case outcomes" in markdown
    assert "| C-SAFE | pt | normal_resolution | completed | block | block |" in markdown
    assert "block_card:success:true:true" in markdown


def test_report_projects_canonical_evidence_with_json_markdown_parity() -> None:
    evidence = (
        {
            "tool_name": "block_card",
            "ordinal": 3,
            "authorization": {
                "state": "allowed",
                "reason_code": "authorized",
                "verified": True,
            },
            "missing_data": {"state": "unknown", "detected": False},
            "governance": {
                "stage": "tool_gating",
                "action": "allow",
                "reason_code": None,
            },
            "execution": {"state": "success"},
            "verification": {"outcome": "verified", "verified": True},
            "provider_error": "CANARY-PRIVATE-EVIDENCE",
        },
    )
    report = generate_report(
        _run((_result("C1"),)),
        _metrics(),
        {},
        {},
        [_classification("C1", canonical_evidence=evidence)],
    )

    expected = [dict(evidence[0])]
    expected[0].pop("provider_error")
    assert report["case_outcomes"][0]["canonical_evidence"] == expected
    markdown = render_markdown_report(report)
    assert _canonical_evidence_from_markdown(markdown) == [
        {"case_id": "C1", "canonical_evidence": expected}
    ]
    assert "CANARY-PRIVATE-EVIDENCE" not in json.dumps(report) + markdown


def test_case_outcome_tools_keep_stable_order_and_exact_bounded_fields() -> None:
    tools = (
        {
            "tool_name": "get_dispute_context",
            "result_status": "success",
            "verified": True,
            "authorization_verified": True,
            "private": "must-not-copy",
        },
        {
            "tool_name": "block_card",
            "result_status": "error",
            "verified": False,
            "authorization_verified": False,
            "path": "D:/private/state.sqlite3",
        },
    )
    report = generate_report(
        _run((_result("C1"),)),
        _metrics(),
        {},
        {},
        [_classification("C1", tools=tools)],
    )

    assert report["case_outcomes"][0]["tools"] == [
        {
            "tool_name": "get_dispute_context",
            "result_status": "success",
            "verified": True,
            "authorization_verified": True,
        },
        {
            "tool_name": "block_card",
            "result_status": "error",
            "verified": False,
            "authorization_verified": False,
        },
    ]
    markdown = render_markdown_report(report)
    assert (
        "get_dispute_context:success:true:true, block_card:error:false:false"
        in markdown
    )
    assert "must-not-copy" not in markdown
    assert "D:/private/state.sqlite3" not in markdown


def test_report_omits_event_ids_and_arbitrary_unsafe_evidence_details() -> None:
    report = _report()

    assert report["unsafe_evidence"] == [
        {
            "case_id": "C2",
            "predicate": "unauthorized_action",
            "rule_code": "block_without_ground_truth_confirmation",
        }
    ]
    json_text = json.dumps(report, ensure_ascii=False)
    markdown = render_markdown_report(report)
    for forbidden in ("event_id", "evt-2", "forbidden_detail", "CANARY-SECRET"):
        assert forbidden not in json_text
        assert forbidden not in markdown


@pytest.mark.parametrize(
    "status", [CaseExecutionStatus.ERROR, CaseExecutionStatus.TIMEOUT]
)
def test_report_replaces_arbitrary_worker_error_with_stable_failure_code(
    status: CaseExecutionStatus,
) -> None:
    markers = (
        "CMP-PRIVATE-WORKER-ERROR",
        "please block the card now",
        "UNKNOWN-SECRET-TOKEN-9472",
        "trace-private-worker-error",
    )
    result = _result(
        "C1",
        status=status,
        error=" | ".join(markers),
    )
    report = generate_report(
        _run((result,)),
        _metrics(),
        {},
        {},
        [
            _classification(
                "C1",
                outcome=EscalationOutcome.EXECUTION_FAILURE,
                execution_status=status,
                observed_action=None,
                expected_tools_verified=False,
            )
        ],
    )

    assert report["failures"] == [
        {
            "case_id": "C1",
            "execution_status": status.value,
            "latency_ms": 25,
            "error": "execution_failed",
            "reason_codes": ["execution_failure"],
        }
    ]
    json_text = json.dumps(report, ensure_ascii=False)
    markdown = render_markdown_report(report)
    for forbidden in markers:
        assert forbidden not in json_text
        assert forbidden not in markdown


def test_generate_report_uses_authoritative_inputs_and_sanitized_failures() -> None:
    report = _report()

    assert report["pipeline_version"] == "3.0.0"
    assert report["dataset_version"] == "1.0.0"
    assert report["timestamp_fs"] == "20261002T120000Z"
    assert report["metrics"]["safe_automated_resolution_rate"] == 0.5
    assert list(report["by_language"]) == ["es", "pt"]
    assert report["baseline_comparison"] == {
        "baseline": "all_human",
        "safe_automated_resolution_rate": {"evaluation": 0.5, "baseline": 0.0},
        "containment_rate": {"evaluation": 0.5, "baseline": 0.0},
    }
    assert report["failures"] == [
        {
            "case_id": "C1",
            "execution_status": "error",
            "latency_ms": 25,
            "error": "execution_failed",
            "reason_codes": ["execution_failure"],
        },
        {
            "case_id": "C2",
            "execution_status": "completed",
            "latency_ms": 50,
            "error": None,
            "reason_codes": [
                "sensitive_data_exposed",
                "unauthorized_action",
                "unauthorized_product_access",
                "wrong_type",
            ],
        },
    ]
    assert report["unsafe_evidence"] == [
        {
            "case_id": "C2",
            "predicate": "unauthorized_action",
            "rule_code": "block_without_ground_truth_confirmation",
        }
    ]
    assert [item["failure_category"] for item in report["case_outcomes"]] == [
        "execution_failure",
        "wrong_type",
    ]
    assert report["case_outcomes"][0]["observed_action"] is None
    assert report["case_outcomes"][1]["observed_escalation_type"] == (
        "governance_review"
    )
    serialized = json.dumps(report)
    assert "private" not in serialized
    assert "hunter2" not in serialized
    assert "CANARY-SECRET" not in serialized
    assert any("sample size: 1" in item for item in report["limitations"])
    assert any(
        "not statistically significant" in item for item in report["limitations"]
    )
    assert any("complete cost" in item for item in report["limitations"])
    assert any("canonical adapter evidence" in item for item in report["limitations"])


@pytest.mark.parametrize(
    "classifications",
    [
        [_classification("C2"), _classification("C1")],
        [_classification("C1"), _classification("OTHER")],
        [_classification("C1")],
    ],
)
def test_generate_report_rejects_mismatched_classification_order_and_ids(
    classifications: list[CaseClassification],
) -> None:
    run = _run((_result("C1"), _result("C2")))

    with pytest.raises(ValueError, match="aligned"):
        generate_report(run, _metrics(), {}, {}, classifications)


def test_save_report_uses_exact_filenames_utf8_strict_json_and_same_markdown(
    tmp_path: Path,
) -> None:
    report = _report()
    report["label"] = "avaliação"

    paths = save_report(report, tmp_path)

    assert paths.json_path == tmp_path / "eval_1.0.0_20261002T120000Z.json"
    assert paths.markdown_path == tmp_path / "eval_1.0.0_20261002T120000Z.md"
    json_text = paths.json_path.read_text(encoding="utf-8")
    assert "avaliação" in json_text
    assert "\\u00e7" not in json_text
    assert json.loads(json_text) == report
    assert paths.markdown_path.read_text(encoding="utf-8") == (
        render_markdown_report(report)
    )
    assert not list(tmp_path.glob("*.tmp"))


def test_save_report_rejects_nan_before_creating_artifacts(tmp_path: Path) -> None:
    report = _report()
    report["metrics"]["latency_p50_ms"] = float("nan")

    with pytest.raises(ValueError):
        save_report(report, tmp_path)

    assert not list(tmp_path.iterdir())


def test_atomic_replace_failure_preserves_existing_report_and_removes_temp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report = _report()
    json_path = tmp_path / "eval_1.0.0_20261002T120000Z.json"
    markdown_path = tmp_path / "eval_1.0.0_20261002T120000Z.md"
    json_path.write_text("old-json", encoding="utf-8")
    markdown_path.write_text("old-markdown", encoding="utf-8")

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("D:/private/report replacement failed")

    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.report.os.replace", fail_replace
    )

    with pytest.raises(OSError):
        save_report(report, tmp_path)

    assert json_path.read_text(encoding="utf-8") == "old-json"
    assert markdown_path.read_text(encoding="utf-8") == "old-markdown"
    assert not list(tmp_path.glob("*.tmp"))


def test_second_atomic_replace_failure_rolls_back_json_and_markdown_pair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report = _report()
    json_path = tmp_path / "eval_1.0.0_20261002T120000Z.json"
    markdown_path = tmp_path / "eval_1.0.0_20261002T120000Z.md"
    json_path.write_text("old-json", encoding="utf-8")
    markdown_path.write_text("old-markdown", encoding="utf-8")
    real_replace = __import__("os").replace
    calls = 0

    def fail_second_replace(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("D:/private/markdown replacement failed")
        real_replace(source, destination)

    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.report.os.replace",
        fail_second_replace,
    )

    with pytest.raises(OSError):
        save_report(report, tmp_path)

    assert json_path.read_text(encoding="utf-8") == "old-json"
    assert markdown_path.read_text(encoding="utf-8") == "old-markdown"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dataset_version", None),
        ("dataset_version", "../escape"),
        ("timestamp_fs", None),
        ("timestamp_fs", "2026/10/02"),
    ],
)
def test_save_report_validates_safe_filename_fields(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    report = _report()
    report[field] = value

    with pytest.raises(ValueError):
        save_report(report, tmp_path)


def _canonical_evidence_from_markdown(markdown: str) -> list[dict]:
    section = markdown.split("## Canonical evidence\n\n```json\n", 1)[1]
    return json.loads(section.split("\n```", 1)[0])


def test_markdown_is_a_pure_rendering_of_the_supplied_report() -> None:
    report = _report()
    report["metrics"]["safe_automated_resolution_rate"] = 0.321
    report["baseline_comparison"]["containment_rate"]["evaluation"] = 0.654

    markdown = render_markdown_report(report)

    assert "0.321" in markdown
    assert "0.654" in markdown
    assert "C1" in markdown
    assert "unauthorized_action" in markdown


def test_report_contracts_are_exported_from_evaluation_package() -> None:
    from ai_banking_customer_service import evaluation

    assert evaluation.ReportPaths is ReportPaths
    assert evaluation.generate_report is generate_report
    assert evaluation.render_markdown_report is render_markdown_report
    assert evaluation.save_report is save_report
