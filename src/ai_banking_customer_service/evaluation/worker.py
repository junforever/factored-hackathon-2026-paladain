"""Spawn-safe child execution for one offline evaluation case."""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal, Protocol, TypedDict

from pydantic import ValidationError

from ai_banking_customer_service.agent.orchestrator import (
    EscalationType,
    OrchestratorResult,
    TurnAction,
)
from ai_banking_customer_service.evaluation.cases import (
    MAX_CASE_ID_LENGTH,
    MIN_RESULT_BYTES,
    EvalCase,
    EvalConfig,
)
from ai_banking_customer_service.evaluation.factory import (
    build_evaluation_dependencies,
)
from ai_banking_customer_service.governance.jev.sanitization import sanitize_message

SCHEMA_VERSION = 1
_DEFAULT_RESULT_LIMIT = 1024 * 1024
_MAX_RESULT_LIMIT = 16 * 1024 * 1024
_MAX_ERROR_MESSAGE = 500
_REQUEST_FIELDS = frozenset({"schema_version", "case", "config", "state_dir"})


class WorkerRequest(TypedDict):
    """JSON-safe request passed to a fresh child process."""

    schema_version: int
    case: dict
    config: dict
    state_dir: str


class WorkerObservation(TypedDict):
    action: str
    response_text: str
    trace_id: str
    session_id: str
    intent: str | None
    escalation_type: str | None
    escalation_id: str | None
    audit_events: list[dict]


class WorkerResultEnvelope(TypedDict):
    """Only result shape emitted by the child process."""

    schema_version: int
    case_id: str
    status: Literal["completed", "error"]
    error: str | None
    observation: WorkerObservation | None


class _ChildPipe(Protocol):
    def send_bytes(self, payload: bytes) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class _ValidatedRequest:
    case: EvalCase
    config: EvalConfig
    state_dir: Path


def execute_case_child(request: WorkerRequest, child_pipe: _ChildPipe) -> None:
    """Execute one case, emit at most one bounded JSON envelope, and close the pipe."""
    result_limit = _DEFAULT_RESULT_LIMIT
    case_id = "invalid_case"
    payload: bytes | None = None
    try:
        try:
            result_limit = _untrusted_result_limit(request)
            case_id = _untrusted_case_id(request)
            validated = _validate_request(request)
            result_limit = validated.config.max_result_bytes
            case_id = validated.case.case_id
            principal = object()
            dependencies = build_evaluation_dependencies(
                state_dir=validated.state_dir,
                case=validated.case,
                principal=principal,
            )
            result = dependencies.orchestrator.handle_turn(
                validated.case.customer_message,
                f"eval:{case_id}",
                f"evaluation:{case_id}",
            )
            envelope = _completed_envelope(
                case_id,
                result,
                dependencies.recording_sink.get_events(),
            )
            payload = _encode(envelope)
            if len(payload) > result_limit:
                payload = _bounded_error_payload(
                    case_id,
                    "result_envelope_too_large",
                    result_limit,
                )
        except Exception as error:
            payload = _bounded_error_payload(
                case_id,
                _safe_error(error),
                result_limit,
            )
        if payload is not None:
            child_pipe.send_bytes(payload)
    finally:
        child_pipe.close()


def _validate_request(request: object) -> _ValidatedRequest:
    if not isinstance(request, dict) or set(request) != _REQUEST_FIELDS:
        raise ValueError("invalid worker request envelope")
    if request.get("schema_version") != SCHEMA_VERSION or isinstance(
        request.get("schema_version"), bool
    ):
        raise ValueError("unsupported worker request schema")
    case_payload = request.get("case")
    config_payload = request.get("config")
    state_dir_value = request.get("state_dir")
    if not isinstance(case_payload, dict) or not isinstance(config_payload, dict):
        raise ValueError("invalid worker request payload")
    if not isinstance(state_dir_value, str) or not state_dir_value.strip():
        raise ValueError("invalid worker state directory")

    # Reject non-JSON or non-UTF-8 values before constructing live dependencies.
    json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8")
    case = EvalCase.model_validate(case_payload)
    config = EvalConfig.model_validate(config_payload)
    state_dir = Path(state_dir_value).resolve()
    if not state_dir.is_dir():
        raise ValueError("worker state directory must already exist")
    return _ValidatedRequest(case, config, state_dir)


def _completed_envelope(
    case_id: str,
    result: OrchestratorResult,
    audit_events: list[dict],
) -> WorkerResultEnvelope:
    if not isinstance(result, OrchestratorResult):
        raise TypeError("orchestrator returned an invalid result")
    observation: WorkerObservation = {
        "action": _enum_value(result.action, TurnAction, "action"),
        "response_text": _required_string(result.response_text, "response_text"),
        "trace_id": _required_string(result.trace_id, "trace_id"),
        "session_id": _required_string(result.session_id, "session_id"),
        "intent": _optional_string(result.intent, "intent"),
        "escalation_type": (
            None
            if result.escalation_type is None
            else _enum_value(
                result.escalation_type,
                EscalationType,
                "escalation_type",
            )
        ),
        "escalation_id": _optional_string(result.escalation_id, "escalation_id"),
        "audit_events": audit_events,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "status": "completed",
        "error": None,
        "observation": observation,
    }


def _error_envelope(case_id: str, error: str) -> WorkerResultEnvelope:
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "status": "error",
        "error": error,
        "observation": None,
    }


def _bounded_error_payload(case_id: str, error: str, limit: int) -> bytes:
    payload = _encode(_error_envelope(case_id, error))
    if len(payload) <= limit:
        return payload
    minimal = _encode(_error_envelope(case_id, "child_error"))
    if len(minimal) > limit:  # Protected by EvalConfig and _untrusted_result_limit.
        raise AssertionError("bounded worker error envelope exceeds validated limit")
    return minimal


def _encode(envelope: WorkerResultEnvelope) -> bytes:
    return json.dumps(
        envelope,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _safe_error(error: Exception) -> str:
    error_type = type(error).__name__
    if isinstance(error, ValidationError):
        return f"{error_type}: invalid child request"
    message = sanitize_message(str(error))
    if "/" in message or "\\" in message:
        message = "child case execution failed"
    message = " ".join(message.split())[:_MAX_ERROR_MESSAGE]
    return f"{error_type}: {message}" if message else error_type


def _untrusted_result_limit(request: object) -> int:
    if not isinstance(request, dict) or not isinstance(request.get("config"), dict):
        return _DEFAULT_RESULT_LIMIT
    value = request["config"].get("max_result_bytes")
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and MIN_RESULT_BYTES <= value <= _MAX_RESULT_LIMIT
    ):
        return value
    return _DEFAULT_RESULT_LIMIT


def _untrusted_case_id(request: object) -> str:
    if not isinstance(request, dict) or not isinstance(request.get("case"), dict):
        return "invalid_case"
    value = request["case"].get("case_id")
    if not isinstance(value, str) or not value.strip():
        return "invalid_case"
    return _sanitize_untrusted_case_id(value)


def _sanitize_untrusted_case_id(value: str) -> str:
    sanitized = sanitize_message(value.strip())
    if "/" in sanitized or "\\" in sanitized:
        return "invalid_case"
    utf8_safe = sanitized.encode("utf-8", errors="replace").decode("utf-8")
    return utf8_safe[:MAX_CASE_ID_LENGTH] or "invalid_case"


def _enum_value(value: object, enum_type: type[Enum], field: str) -> str:
    if not isinstance(value, enum_type):
        raise TypeError(f"invalid {field}")
    return str(value.value)


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"invalid {field}")
    return value


def _optional_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, field)
