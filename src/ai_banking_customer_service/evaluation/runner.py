"""Parent-owned sequential process runner for offline evaluation cases."""

import hashlib
import json
import math
import multiprocessing
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from time import monotonic
from typing import Any, Protocol

from ai_banking_customer_service.agent.orchestrator import EscalationType, TurnAction
from ai_banking_customer_service.config import PROJECT_ROOT, settings
from ai_banking_customer_service.evaluation.cases import EvalCase, EvalConfig
from ai_banking_customer_service.evaluation.worker import (
    SCHEMA_VERSION,
    WorkerRequest,
    execute_case_child,
)
from ai_banking_customer_service.governance.jev.sanitization import sanitize_message

_POLL_INTERVAL_SECONDS = 0.01
_STOP_JOIN_SECONDS = 1.0
_RESULT_FIELDS = frozenset(
    {"schema_version", "case_id", "status", "error", "observation"}
)
_OBSERVATION_FIELDS = frozenset(
    {
        "action",
        "response_text",
        "trace_id",
        "session_id",
        "intent",
        "escalation_type",
        "escalation_id",
        "audit_events",
    }
)
_CHILD_TARGET = execute_case_child


class CaseExecutionStatus(str, Enum):  # noqa: UP042 - exact public contract
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class CaseObservation:
    action: TurnAction
    response_text: str
    trace_id: str
    session_id: str
    intent: str | None
    escalation_type: EscalationType | None
    escalation_id: str | None
    audit_events: tuple[dict, ...]


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    execution_status: CaseExecutionStatus
    observation: CaseObservation | None
    error: str | None
    latency_ms: int


@dataclass(frozen=True)
class EvalRun:
    pipeline_version: str
    dataset_version: str
    timestamp: str
    timestamp_fs: str
    configured_openai_model: str
    configured_jev_model: str
    dependencies_lock_hash: str
    results: tuple[CaseResult, ...]
    total_duration_seconds: float


class EvaluationInfrastructureError(RuntimeError):
    """Abort a run when process isolation or parent cleanup cannot be proven."""


class _ReceivePipe(Protocol):
    def poll(self, timeout: float = 0.0) -> bool: ...

    def recv_bytes(self, maxlength: int | None = None) -> bytes: ...

    def close(self) -> None: ...


class _SendPipe(Protocol):
    def close(self) -> None: ...


@dataclass
class _ReceivedFrames:
    payloads: list[bytes]
    oversize: bool = False


def run_case(case: EvalCase, config: EvalConfig) -> CaseResult:
    """Run one case in a fresh spawn child and clean its state after final join."""
    case_started = monotonic()
    state_dir = _create_state_dir()
    parent_pipe: _ReceivePipe | None = None
    child_pipe: _SendPipe | None = None
    process: Any | None = None
    cleanup_allowed = True
    result_parts: (
        tuple[CaseExecutionStatus, CaseObservation | None, str | None] | None
    ) = None
    pending_error: EvaluationInfrastructureError | None = None

    try:
        context = multiprocessing.get_context("spawn")
        parent_pipe, child_pipe = context.Pipe(duplex=False)
        request: WorkerRequest = {
            "schema_version": SCHEMA_VERSION,
            "case": case.model_dump(mode="json"),
            "config": config.model_dump(mode="json"),
            "state_dir": str(state_dir),
        }
        process = context.Process(
            target=_CHILD_TARGET,
            args=(request, child_pipe),
            daemon=False,
        )
        try:
            process.start()
        except Exception:
            if _process_may_be_alive(process):
                cleanup_allowed = False
                _force_stop(process)
                cleanup_allowed = True
            raise EvaluationInfrastructureError("child_process_start_failed") from None

        cleanup_allowed = False
        received = _ReceivedFrames([])
        deadline = case_started + config.case_timeout_seconds
        timed_out = False

        while True:
            _drain_nonblocking(parent_pipe, received, config.max_result_bytes)
            if not process.is_alive():
                break
            remaining = deadline - monotonic()
            if remaining <= 0:
                timed_out = True
                break
            parent_pipe.poll(min(_POLL_INTERVAL_SECONDS, remaining))

        if timed_out:
            _stop_after_timeout(
                process,
                config.grace_period_seconds,
                parent_pipe,
                received,
                config.max_result_bytes,
            )
        else:
            _final_join(process)
        cleanup_allowed = True

        # The child is gone and joined. Only now can the final pipe snapshot be fixed.
        _drain_nonblocking(parent_pipe, received, config.max_result_bytes)
        if timed_out:
            result_parts = (CaseExecutionStatus.TIMEOUT, None, "case_timeout")
        else:
            result_parts = _materialize_result(
                case.case_id,
                process.exitcode,
                received,
            )
    except EvaluationInfrastructureError as error:
        pending_error = error
    except Exception:
        pending_error = EvaluationInfrastructureError("runner_infrastructure_failure")
    finally:
        pipe_close_failed = False
        for pipe in (parent_pipe, child_pipe):
            if pipe is None:
                continue
            try:
                pipe.close()
            except Exception:
                pipe_close_failed = True

        if cleanup_allowed:
            try:
                _remove_state_dir(state_dir)
            except Exception:
                pending_error = EvaluationInfrastructureError("state_cleanup_failed")
        if pipe_close_failed and pending_error is None:
            pending_error = EvaluationInfrastructureError("pipe_close_failed")

    if pending_error is not None:
        raise pending_error
    if result_parts is None:  # Defensive: every successful lifecycle fixes one result.
        raise EvaluationInfrastructureError("runner_infrastructure_failure")

    status, observation, error = result_parts
    latency_ms = max(0, int((monotonic() - case_started) * 1000))
    return CaseResult(case.case_id, status, observation, error, latency_ms)


def run_evaluation(cases: list[EvalCase], config: EvalConfig) -> EvalRun:
    """Run held-out cases strictly in file order with no overlapping children."""
    captured_at = datetime.now(UTC)
    lock_hash = hashlib.sha256((PROJECT_ROOT / "uv.lock").read_bytes()).hexdigest()
    run_started = monotonic()
    results = tuple(run_case(case, config) for case in cases)
    total_duration = max(0.0, monotonic() - run_started)
    return EvalRun(
        pipeline_version=config.pipeline_version,
        dataset_version=config.dataset_version,
        timestamp=captured_at.isoformat(),
        timestamp_fs=captured_at.strftime("%Y%m%dT%H%M%SZ"),
        configured_openai_model=settings.openai_model,
        configured_jev_model=settings.typesafe_default_model,
        dependencies_lock_hash=lock_hash,
        results=results,
        total_duration_seconds=total_duration,
    )


def _create_state_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="ai-banking-eval-"))


def _remove_state_dir(state_dir: Path) -> None:
    shutil.rmtree(state_dir)


def _process_may_be_alive(process: Any) -> bool:
    try:
        return bool(process.is_alive())
    except Exception:
        return False


def _stop_after_timeout(
    process: Any,
    grace_period_seconds: float,
    parent_pipe: _ReceivePipe,
    received: _ReceivedFrames,
    max_result_bytes: int,
) -> None:
    grace_deadline = monotonic() + grace_period_seconds
    while process.is_alive():
        _drain_nonblocking(parent_pipe, received, max_result_bytes)
        if not process.is_alive():
            break
        remaining = grace_deadline - monotonic()
        if remaining <= 0:
            break
        process.join(timeout=min(_POLL_INTERVAL_SECONDS, remaining))

    if process.is_alive():
        try:
            process.terminate()
        except Exception:
            pass
        try:
            process.join(timeout=_STOP_JOIN_SECONDS)
        except Exception:
            pass

    if process.is_alive():
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.join(timeout=_STOP_JOIN_SECONDS)
        except Exception:
            pass

    if process.is_alive():
        raise EvaluationInfrastructureError("child_process_not_stopped")
    _final_join(process)


def _force_stop(process: Any) -> None:
    try:
        process.terminate()
    except Exception:
        pass
    try:
        process.join(timeout=_STOP_JOIN_SECONDS)
    except Exception:
        pass
    if _process_may_be_alive(process):
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.join(timeout=_STOP_JOIN_SECONDS)
        except Exception:
            pass
    if _process_may_be_alive(process):
        raise EvaluationInfrastructureError("child_process_not_stopped")


def _final_join(process: Any) -> None:
    try:
        process.join(timeout=_STOP_JOIN_SECONDS)
    except Exception:
        raise EvaluationInfrastructureError("child_process_join_failed") from None
    if process.is_alive() or process.exitcode is None:
        raise EvaluationInfrastructureError("child_process_not_joined")


def _drain_nonblocking(
    pipe: _ReceivePipe,
    received: _ReceivedFrames,
    max_result_bytes: int,
) -> None:
    if received.oversize:
        return
    while pipe.poll(0):
        try:
            payload = pipe.recv_bytes(max_result_bytes)
        except EOFError:
            return
        except (OSError, ValueError):
            received.oversize = True
            return
        if len(payload) > max_result_bytes:
            received.oversize = True
            return
        received.payloads.append(payload)


def _materialize_result(
    case_id: str,
    exitcode: int | None,
    received: _ReceivedFrames,
) -> tuple[CaseExecutionStatus, CaseObservation | None, str | None]:
    if exitcode != 0:
        return CaseExecutionStatus.ERROR, None, "child_abnormal_exit"
    if received.oversize:
        return CaseExecutionStatus.ERROR, None, "result_envelope_too_large"
    if not received.payloads:
        return CaseExecutionStatus.ERROR, None, "child_exited_without_envelope"
    if len(received.payloads) != 1:
        return CaseExecutionStatus.ERROR, None, "duplicate_result_envelope"

    try:
        envelope = json.loads(
            received.payloads[0].decode("utf-8"),
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return CaseExecutionStatus.ERROR, None, "invalid_result_envelope"
    if not _all_numbers_finite(envelope):
        return CaseExecutionStatus.ERROR, None, "invalid_result_envelope"
    if not isinstance(envelope, dict) or set(envelope) != _RESULT_FIELDS:
        return CaseExecutionStatus.ERROR, None, "invalid_result_envelope"
    schema_version = envelope.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != SCHEMA_VERSION
    ):
        return CaseExecutionStatus.ERROR, None, "invalid_result_envelope"
    if envelope.get("case_id") != case_id:
        return CaseExecutionStatus.ERROR, None, "mismatched_case_id"

    status = envelope.get("status")
    if status == "error":
        if envelope.get("observation") is not None:
            return CaseExecutionStatus.ERROR, None, "invalid_result_envelope"
        error = envelope.get("error")
        if not isinstance(error, str) or not error.strip():
            return CaseExecutionStatus.ERROR, None, "invalid_result_envelope"
        return CaseExecutionStatus.ERROR, None, _sanitize_child_error(error)
    if status != "completed" or envelope.get("error") is not None:
        return CaseExecutionStatus.ERROR, None, "invalid_result_envelope"

    observation = _parse_observation(envelope.get("observation"))
    if observation is None:
        return CaseExecutionStatus.ERROR, None, "invalid_result_envelope"
    return CaseExecutionStatus.COMPLETED, observation, None


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _all_numbers_finite(value: object) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _all_numbers_finite(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return all(_all_numbers_finite(item) for item in value)
    return True


def _parse_observation(value: object) -> CaseObservation | None:
    if not isinstance(value, dict) or set(value) != _OBSERVATION_FIELDS:
        return None
    try:
        action = TurnAction(value["action"])
    except (TypeError, ValueError):
        return None
    response_text = _required_string(value.get("response_text"))
    trace_id = _required_string(value.get("trace_id"))
    session_id = _required_string(value.get("session_id"))
    intent = _optional_string(value.get("intent"))
    escalation_id = _optional_string(value.get("escalation_id"))
    if response_text is None or trace_id is None or session_id is None:
        return None
    if value.get("intent") is not None and intent is None:
        return None
    if value.get("escalation_id") is not None and escalation_id is None:
        return None

    escalation_value = value.get("escalation_type")
    if escalation_value is None:
        escalation_type = None
    else:
        try:
            escalation_type = EscalationType(escalation_value)
        except (TypeError, ValueError):
            return None
    audit_events = value.get("audit_events")
    if not isinstance(audit_events, list) or not all(
        isinstance(event, dict) for event in audit_events
    ):
        return None
    return CaseObservation(
        action=action,
        response_text=response_text,
        trace_id=trace_id,
        session_id=session_id,
        intent=intent,
        escalation_type=escalation_type,
        escalation_id=escalation_id,
        audit_events=tuple(audit_events),
    )


def _required_string(value: object) -> str | None:
    return value if isinstance(value, str) and bool(value.strip()) else None


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return _required_string(value)


def _sanitize_child_error(value: str) -> str:
    sanitized = " ".join(sanitize_message(value).split())[:600]
    if not sanitized or "/" in sanitized or "\\" in sanitized:
        return "child_error"
    return sanitized
