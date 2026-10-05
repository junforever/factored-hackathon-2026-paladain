import json
import multiprocessing
import pickle
from pathlib import Path
from types import SimpleNamespace
from typing import is_typeddict

import pytest

from ai_banking_customer_service.agent.orchestrator import (
    EscalationType,
    OrchestratorResult,
    TurnAction,
)
from ai_banking_customer_service.config import PROJECT_ROOT
from ai_banking_customer_service.evaluation import cases as cases_module
from ai_banking_customer_service.evaluation import worker
from ai_banking_customer_service.evaluation.cases import load_eval_config
from ai_banking_customer_service.evaluation.factory import build_evaluation_dependencies
from ai_banking_customer_service.evaluation.sink import RecordingAuditSink
from ai_banking_customer_service.evaluation.worker import (
    SCHEMA_VERSION,
    WorkerRequest,
    execute_case_child,
)


def _case_payload() -> dict:
    return {
        "case_id": "EVAL-WORKER-001",
        "language": "es",
        "scenario": "normal_resolution",
        "customer_message": "Complaint CMP-EVAL; block card.",
        "expected": {
            "intent": "dispute_charge",
            "action": "respond",
            "is_automatable": True,
            "requires_escalation": False,
            "expected_tools": ["block_card"],
            "expected_escalation_type": None,
            "complaint_id": "CMP-EVAL",
            "customer_confirmed_block": True,
            "forbidden_actions": [],
            "response_required_substrings": [],
            "response_forbidden_substrings": [],
            "sensitive_output_forbidden_substrings": ["CANARY-EVAL-WORKER-001"],
        },
        "metadata": {"segment": "Retail", "notes": "Worker contract case"},
    }


def _config_payload(*, max_result_bytes: int = 1_048_576) -> dict:
    config = load_eval_config(PROJECT_ROOT / "configs" / "eval.yaml")
    payload = config.model_dump(mode="json")
    payload["max_result_bytes"] = max_result_bytes
    return payload


def _request(tmp_path: Path, *, max_result_bytes: int = 1_048_576) -> WorkerRequest:
    return {
        "schema_version": SCHEMA_VERSION,
        "case": _case_payload(),
        "config": _config_payload(max_result_bytes=max_result_bytes),
        "state_dir": str(tmp_path),
    }


def _tool_call_event() -> dict:
    return {
        "trace_id": "trace-worker",
        "event_id": "event-tool",
        "parent_event_id": "event-governance",
        "timestamp": "2026-10-03T12:00:00+00:00",
        "component": "orchestrator",
        "event_type": "tool_call",
        "customer_id": "********-001",
        "session_id": "eval:EVAL-WORKER-001",
        "outcome": "success",
        "latency_ms": 2,
        "tokens": None,
        "cost_usd": None,
        "payload": {
            "tool_name": "block_card",
            "tool_use_id": "tool-1",
            "args": {
                "complaint_id": "CMP-EVAL",
                "confirmed_by_customer": True,
            },
            "result_status": "success",
            "result_summary": "success",
            "verified": True,
        },
    }


class _Pipe:
    def __init__(self) -> None:
        self.messages: list[bytes] = []
        self.closed = False

    def send_bytes(self, payload: bytes) -> None:
        self.messages.append(payload)

    def close(self) -> None:
        self.closed = True


class _Orchestrator:
    def __init__(self, result: OrchestratorResult | Exception) -> None:
        self.result = result
        self.calls: list[tuple[str, str, str]] = []

    def handle_turn(self, message: str, session_id: str, customer_id: str):
        self.calls.append((message, session_id, customer_id))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _dependencies(
    result: OrchestratorResult | Exception, events: list[dict] | None = None
):
    sink = RecordingAuditSink()
    for event in events or []:
        sink.emit(event)
    return SimpleNamespace(orchestrator=_Orchestrator(result), recording_sink=sink)


def _decode(pipe: _Pipe) -> dict:
    assert len(pipe.messages) == 1
    return json.loads(pipe.messages[0].decode("utf-8"))


def test_worker_request_is_json_serializable_and_target_is_top_level_picklable(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)

    assert is_typeddict(WorkerRequest)
    assert json.loads(json.dumps(request, allow_nan=False)) == request
    assert pickle.loads(pickle.dumps(execute_case_child)) is execute_case_child
    assert execute_case_child.__module__ == worker.__name__
    assert "<locals>" not in execute_case_child.__qualname__


def test_child_builds_dependencies_handles_one_turn_and_sends_one_typed_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = OrchestratorResult(
        action=TurnAction.RESPOND,
        response_text="El cargo fue revisado.",
        trace_id="trace-worker",
        session_id="eval:EVAL-WORKER-001",
        intent="dispute_charge",
        escalation_type=None,
        escalation_id=None,
    )
    dependencies = _dependencies(result, [_tool_call_event()])
    built_for: list[Path] = []

    def build(*, state_dir: Path, model_factory=None):
        assert model_factory is None
        built_for.append(state_dir)
        return dependencies

    monkeypatch.setattr(worker, "build_evaluation_dependencies", build)
    pipe = _Pipe()

    execute_case_child(_request(tmp_path), pipe)

    envelope = _decode(pipe)
    assert pipe.closed is True
    assert built_for == [tmp_path.resolve()]
    assert dependencies.orchestrator.calls == [
        (
            "Complaint CMP-EVAL; block card.",
            "eval:EVAL-WORKER-001",
            "evaluation:EVAL-WORKER-001",
        )
    ]
    assert set(envelope) == {
        "schema_version",
        "case_id",
        "status",
        "error",
        "observation",
    }
    assert envelope["schema_version"] == SCHEMA_VERSION
    assert envelope["case_id"] == "EVAL-WORKER-001"
    assert envelope["status"] == "completed"
    assert envelope["error"] is None
    assert envelope["observation"] == {
        "action": "respond",
        "response_text": "El cargo fue revisado.",
        "trace_id": "trace-worker",
        "session_id": "eval:EVAL-WORKER-001",
        "intent": "dispute_charge",
        "escalation_type": None,
        "escalation_id": None,
        "audit_events": [_tool_call_event()],
    }


def test_valid_unicode_slash_case_id_round_trips_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = "caso/ação-ñ"
    request = _request(tmp_path)
    request["case"]["case_id"] = case_id
    result = OrchestratorResult(
        action=TurnAction.RESPOND,
        response_text="El cargo fue revisado.",
        trace_id="trace-worker",
        session_id=f"eval:{case_id}",
        intent="dispute_charge",
        escalation_type=None,
        escalation_id=None,
    )
    dependencies = _dependencies(result)
    monkeypatch.setattr(
        worker,
        "build_evaluation_dependencies",
        lambda *, state_dir, model_factory=None: dependencies,
    )
    pipe = _Pipe()

    execute_case_child(request, pipe)

    envelope = _decode(pipe)
    assert envelope["status"] == "completed"
    assert envelope["case_id"] == case_id
    assert dependencies.orchestrator.calls == [
        (
            request["case"]["customer_message"],
            f"eval:{case_id}",
            f"evaluation:{case_id}",
        )
    ]


def test_child_serializes_enum_values_for_escalation_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = OrchestratorResult(
        action=TurnAction.ESCALATE,
        response_text="Caso derivado.",
        trace_id="trace-worker",
        session_id="eval:EVAL-WORKER-001",
        intent=None,
        escalation_type=EscalationType.TOOL_ESCALATION,
        escalation_id="ESC-EVAL",
    )
    monkeypatch.setattr(
        worker,
        "build_evaluation_dependencies",
        lambda *, state_dir, model_factory=None: _dependencies(result),
    )
    pipe = _Pipe()

    execute_case_child(_request(tmp_path), pipe)

    observation = _decode(pipe)["observation"]
    assert observation["action"] == "escalate"
    assert observation["escalation_type"] == "tool_escalation"
    assert observation["escalation_id"] == "ESC-EVAL"


def test_child_sanitizes_exception_secrets_and_internal_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_path = str(tmp_path / "card_service.sqlite3")
    failure = RuntimeError(
        f"failed at {raw_path}; password=private; PAN 4111-1111-1111-1111; CVV=123"
    )
    monkeypatch.setattr(
        worker,
        "build_evaluation_dependencies",
        lambda *, state_dir, model_factory=None: _dependencies(failure),
    )
    pipe = _Pipe()

    execute_case_child(_request(tmp_path), pipe)

    envelope = _decode(pipe)
    serialized = json.dumps(envelope)
    assert envelope["status"] == "error"
    assert envelope["observation"] is None
    assert envelope["error"].startswith("RuntimeError:")
    assert raw_path not in serialized
    assert "private" not in serialized
    assert "4111" not in serialized
    assert "123" not in serialized


def test_child_replaces_oversize_result_with_bounded_error_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = OrchestratorResult(
        action=TurnAction.RESPOND,
        response_text="x" * 10_000,
        trace_id="trace-worker",
        session_id="eval:EVAL-WORKER-001",
        intent="dispute_charge",
        escalation_type=None,
        escalation_id=None,
    )
    monkeypatch.setattr(
        worker,
        "build_evaluation_dependencies",
        lambda *, state_dir, model_factory=None: _dependencies(result),
    )
    pipe = _Pipe()
    limit = cases_module.MIN_RESULT_BYTES

    execute_case_child(_request(tmp_path, max_result_bytes=limit), pipe)

    envelope = _decode(pipe)
    assert len(pipe.messages[0]) <= limit
    assert envelope == {
        "schema_version": SCHEMA_VERSION,
        "case_id": "EVAL-WORKER-001",
        "status": "error",
        "error": "result_envelope_too_large",
        "observation": None,
    }


def test_calculated_minimum_fits_the_canonical_error_for_the_largest_case_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = OrchestratorResult(
        action=TurnAction.RESPOND,
        response_text="x" * 10_000,
        trace_id="trace-worker",
        session_id="eval:max-case-id",
        intent=None,
        escalation_type=None,
        escalation_id=None,
    )
    monkeypatch.setattr(
        worker,
        "build_evaluation_dependencies",
        lambda *, state_dir, model_factory=None: _dependencies(result),
    )
    request = _request(
        tmp_path,
        max_result_bytes=cases_module.MIN_RESULT_BYTES,
    )
    request["case"]["case_id"] = "\x00" * cases_module.MAX_CASE_ID_LENGTH
    pipe = _Pipe()

    execute_case_child(request, pipe)

    envelope = _decode(pipe)
    assert len(pipe.messages[0]) <= cases_module.MIN_RESULT_BYTES
    assert envelope["status"] == "error"
    assert envelope["error"] == "result_envelope_too_large"
    assert envelope["case_id"] == request["case"]["case_id"]


def test_child_turns_non_json_audit_data_into_a_sanitized_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = OrchestratorResult(
        action=TurnAction.RESPOND,
        response_text="safe",
        trace_id="trace-worker",
        session_id="eval:EVAL-WORKER-001",
        intent=None,
        escalation_type=None,
        escalation_id=None,
    )
    malformed = _tool_call_event()
    malformed["payload"]["args"]["invalid_number"] = float("nan")
    monkeypatch.setattr(
        worker,
        "build_evaluation_dependencies",
        lambda *, state_dir, model_factory=None: _dependencies(result, [malformed]),
    )
    pipe = _Pipe()

    execute_case_child(_request(tmp_path), pipe)

    envelope = _decode(pipe)
    assert envelope["status"] == "error"
    assert envelope["observation"] is None
    assert "NaN" not in pipe.messages[0].decode("utf-8")


def test_malformed_unvalidated_request_uses_sanitized_fallback_case_id(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    secret_path_id = "D:/internal/state.sqlite3/password=hunter2"
    request["case"] = {"case_id": secret_path_id}
    pipe = _Pipe()

    execute_case_child(request, pipe)

    envelope = _decode(pipe)
    serialized = pipe.messages[0].decode("utf-8")
    assert envelope == {
        "schema_version": SCHEMA_VERSION,
        "case_id": "invalid_case",
        "status": "error",
        "error": "ValidationError: invalid child request",
        "observation": None,
    }
    assert secret_path_id not in serialized
    assert "internal" not in serialized
    assert "hunter2" not in serialized


def test_child_closes_pipe_when_malformed_unicode_cannot_be_serialized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    request["case"]["case_id"] = "\ud800"
    result = OrchestratorResult(
        action=TurnAction.RESPOND,
        response_text="safe",
        trace_id="trace-worker",
        session_id="eval:invalid",
        intent=None,
        escalation_type=None,
        escalation_id=None,
    )
    monkeypatch.setattr(
        worker,
        "build_evaluation_dependencies",
        lambda *, state_dir, model_factory=None: _dependencies(result),
    )
    pipe = _Pipe()

    execute_case_child(request, pipe)

    assert pipe.closed is True
    assert len(pipe.messages) <= 1


def test_child_is_spawn_compatible_without_building_real_dependencies(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    request["case"] = {}
    context = multiprocessing.get_context("spawn")
    parent_pipe, child_pipe = context.Pipe(duplex=False)
    process = context.Process(target=execute_case_child, args=(request, child_pipe))

    process.start()
    child_pipe.close()
    assert parent_pipe.poll(15)
    envelope = json.loads(parent_pipe.recv_bytes().decode("utf-8"))
    process.join(15)
    parent_pipe.close()

    assert process.exitcode == 0
    assert envelope["status"] == "error"
    assert envelope["observation"] is None


def test_child_worker_uses_public_factory_without_duplicate_builder() -> None:
    assert worker.build_evaluation_dependencies is build_evaluation_dependencies
    assert not hasattr(worker, "_build_child_dependencies")
