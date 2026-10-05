import hashlib
import json
import multiprocessing
import os
import time
from collections import deque
from pathlib import Path
from typing import Any

import pytest

from ai_banking_customer_service import evaluation
from ai_banking_customer_service.agent.orchestrator import TurnAction
from ai_banking_customer_service.config import PROJECT_ROOT, settings
from ai_banking_customer_service.evaluation.cases import (
    EvalCase,
    EvalConfig,
    load_eval_config,
)
from ai_banking_customer_service.evaluation.runner import (
    CaseExecutionStatus,
    EvaluationInfrastructureError,
    run_case,
    run_evaluation,
)


def _case(
    case_id: str = "EVAL-RUNNER-001",
    message: str = "Complaint CMP-RUNNER.",
) -> EvalCase:
    return EvalCase.model_validate(
        {
            "case_id": case_id,
            "language": "es",
            "scenario": "normal_resolution",
            "customer_message": message,
            "expected": {
                "intent": "dispute_charge",
                "action": "respond",
                "is_automatable": True,
                "requires_escalation": False,
                "expected_tools": [],
                "expected_escalation_type": None,
                "complaint_id": "CMP-RUNNER",
                "customer_confirmed_block": False,
                "forbidden_actions": [],
                "response_required_substrings": [],
                "response_forbidden_substrings": [],
                "sensitive_output_forbidden_substrings": ["CANARY-RUNNER"],
            },
            "metadata": {"segment": "Retail", "notes": "Runner contract"},
        }
    )


def _config(
    *,
    timeout: float = 1.0,
    grace: float = 0.0,
    max_result_bytes: int = 1_048_576,
) -> EvalConfig:
    base = load_eval_config(PROJECT_ROOT / "configs" / "eval.yaml")
    return base.model_copy(
        update={
            "case_timeout_seconds": timeout,
            "grace_period_seconds": grace,
            "max_result_bytes": max_result_bytes,
        }
    )


def _envelope(case_id: str = "EVAL-RUNNER-001") -> dict:
    return {
        "schema_version": 1,
        "case_id": case_id,
        "status": "completed",
        "error": None,
        "observation": {
            "action": "respond",
            "response_text": "Safe response",
            "trace_id": "trace-runner",
            "session_id": f"eval:{case_id}",
            "intent": "dispute_charge",
            "escalation_type": None,
            "escalation_id": None,
            "audit_events": [{"event_type": "tool_call", "payload": {}}],
        },
    }


def _encoded(envelope: dict) -> bytes:
    return json.dumps(
        envelope,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


class _FakeClock:
    def __init__(self, step: float = 0.01) -> None:
        self.value = -step
        self.step = step

    def __call__(self) -> float:
        self.value += self.step
        return self.value


class _FakeReceivePipe:
    def __init__(self, frames: list[bytes], events: list[str]) -> None:
        self.frames = deque(frames)
        self.events = events
        self.closed = False

    def poll(self, _timeout: float = 0.0) -> bool:
        return bool(self.frames)

    def recv_bytes(self, maxlength: int | None = None) -> bytes:
        payload = self.frames.popleft()
        if maxlength is not None and len(payload) > maxlength:
            raise OSError("bad message length")
        self.events.append("receive")
        return payload

    def close(self) -> None:
        self.closed = True
        self.events.append("parent_pipe_closed")


class _FakeSendPipe:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.closed = False

    def close(self) -> None:
        self.closed = True
        self.events.append("child_pipe_closed_in_parent")


class _FakeProcess:
    def __init__(
        self,
        events: list[str],
        *,
        natural_checks: int = 0,
        exitcode: int = 0,
        exit_during_grace: bool = False,
        wait_for_late_drain: bool = False,
        terminate_stops: bool = True,
        kill_stops: bool = True,
        late_frame: tuple[_FakeReceivePipe, bytes] | None = None,
        start_error: Exception | None = None,
    ) -> None:
        self.events = events
        self._remaining_checks = natural_checks
        self._configured_exitcode = exitcode
        self._exit_during_grace = exit_during_grace
        self._wait_for_late_drain = wait_for_late_drain
        self._late_sent = False
        self._terminate_stops = terminate_stops
        self._kill_stops = kill_stops
        self._late_frame = late_frame
        self._start_error = start_error
        self._alive = False
        self.started = False
        self.joined = False
        self.daemon = False
        self.exitcode: int | None = None

    def start(self) -> None:
        self.events.append("start")
        if self._start_error is not None:
            raise self._start_error
        self.started = True
        self._alive = True

    def is_alive(self) -> bool:
        if (
            self._alive
            and self._wait_for_late_drain
            and self._late_sent
            and self._late_frame is not None
            and not self._late_frame[0].frames
        ):
            self._alive = False
            self.exitcode = self._configured_exitcode
        if self._alive and self._remaining_checks <= 0:
            self._alive = False
            self.exitcode = self._configured_exitcode
        elif self._alive:
            self._remaining_checks -= 1
        return self._alive

    def join(self, timeout: float | None = None) -> None:
        self.events.append("join")
        if self._exit_during_grace and self._alive and timeout is not None:
            if self._late_frame is not None and not self._late_sent:
                pipe, payload = self._late_frame
                pipe.frames.append(payload)
                self._late_sent = True
            waiting_for_drain = (
                self._wait_for_late_drain
                and self._late_frame is not None
                and bool(self._late_frame[0].frames)
            )
            if not waiting_for_drain:
                self._alive = False
                self.exitcode = self._configured_exitcode
        if not self._alive:
            self.joined = True
            if self.exitcode is None:
                self.exitcode = self._configured_exitcode

    def terminate(self) -> None:
        self.events.append("terminate")
        if self._terminate_stops:
            self._alive = False
            self.exitcode = -15

    def kill(self) -> None:
        self.events.append("kill")
        if self._kill_stops:
            self._alive = False
            self.exitcode = -9


class _FakeContext:
    def __init__(
        self,
        process: _FakeProcess,
        parent_pipe: _FakeReceivePipe,
        child_pipe: _FakeSendPipe,
    ) -> None:
        self.process = process
        self.parent_pipe = parent_pipe
        self.child_pipe = child_pipe
        self.process_calls: list[dict[str, Any]] = []

    def Pipe(self, *, duplex: bool):
        assert duplex is False
        return self.parent_pipe, self.child_pipe

    def Process(self, **kwargs):
        self.process_calls.append(kwargs)
        self.process.daemon = kwargs.get("daemon", False)
        return self.process


def _install_fake_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    frames: list[bytes] | None = None,
    process_kwargs: dict[str, Any] | None = None,
    clock_step: float = 0.01,
):
    events: list[str] = []
    parent_pipe = _FakeReceivePipe(frames or [], events)
    child_pipe = _FakeSendPipe(events)
    kwargs = dict(process_kwargs or {})
    late_payload = kwargs.pop("late_payload", None)
    if late_payload is not None:
        kwargs["late_frame"] = (parent_pipe, late_payload)
    process = _FakeProcess(events, **kwargs)
    context = _FakeContext(process, parent_pipe, child_pipe)
    state_dir = tmp_path / "case-state"

    def create_state_dir() -> Path:
        state_dir.mkdir()
        events.append("state_created")
        return state_dir

    def remove_state_dir(path: Path) -> None:
        assert path == state_dir
        if process.started:
            assert process.joined is True
            assert process.is_alive() is False
        events.append("cleanup")

    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.runner.multiprocessing.get_context",
        lambda method: context if method == "spawn" else pytest.fail(method),
    )
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.runner._create_state_dir",
        create_state_dir,
    )
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.runner._remove_state_dir",
        remove_state_dir,
    )
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.runner.monotonic",
        _FakeClock(clock_step),
    )
    return context, process, parent_pipe, child_pipe, events, state_dir


def test_completed_envelope_remains_provisional_until_join_then_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context, process, parent_pipe, child_pipe, events, state_dir = (
        _install_fake_runtime(
            monkeypatch,
            tmp_path,
            frames=[_encoded(_envelope())],
        )
    )

    result = run_case(_case(), _config())

    assert result.execution_status is CaseExecutionStatus.COMPLETED
    assert result.error is None
    assert result.observation is not None
    assert result.observation.action is TurnAction.RESPOND
    assert result.observation.audit_events == (
        {"event_type": "tool_call", "payload": {}},
    )
    assert result.latency_ms >= 0
    assert context.process_calls[0]["daemon"] is False
    request, passed_pipe = context.process_calls[0]["args"]
    assert request["state_dir"] == str(state_dir)
    assert passed_pipe is child_pipe
    assert events.index("receive") < events.index("join") < events.index("cleanup")
    assert events.index("join") < events.index("parent_pipe_closed")
    assert process.joined is True
    assert parent_pipe.closed is True
    assert child_pipe.closed is True


def test_child_error_envelope_is_materialized_only_after_clean_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    envelope = {
        "schema_version": 1,
        "case_id": "EVAL-RUNNER-001",
        "status": "error",
        "error": "RuntimeError: safe failure",
        "observation": None,
    }
    _install_fake_runtime(monkeypatch, tmp_path, frames=[_encoded(envelope)])

    result = run_case(_case(), _config())

    assert result.execution_status is CaseExecutionStatus.ERROR
    assert result.observation is None
    assert result.error == "RuntimeError: safe failure"


def test_child_error_is_sanitized_again_at_the_parent_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    envelope = {
        "schema_version": 1,
        "case_id": "EVAL-RUNNER-001",
        "status": "error",
        "error": "RuntimeError at D:/private/state.sqlite3; password=hunter2",
        "observation": None,
    }
    _install_fake_runtime(monkeypatch, tmp_path, frames=[_encoded(envelope)])

    result = run_case(_case(), _config())

    assert result.execution_status is CaseExecutionStatus.ERROR
    assert result.error == "child_error"
    assert "private" not in result.error
    assert "hunter2" not in result.error


def test_clean_exit_without_envelope_is_deterministic_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_runtime(monkeypatch, tmp_path)

    result = run_case(_case(), _config())

    assert result.execution_status is CaseExecutionStatus.ERROR
    assert result.error == "child_exited_without_envelope"


def test_abnormal_exit_discards_even_a_valid_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_runtime(
        monkeypatch,
        tmp_path,
        frames=[_encoded(_envelope())],
        process_kwargs={"exitcode": 7},
    )

    result = run_case(_case(), _config())

    assert result.execution_status is CaseExecutionStatus.ERROR
    assert result.observation is None
    assert result.error == "child_abnormal_exit"


@pytest.mark.parametrize(
    ("frames", "expected_error"),
    [
        ([b"not-json"], "invalid_result_envelope"),
        (
            [_encoded({**_envelope(), "unexpected": True})],
            "invalid_result_envelope",
        ),
        (
            [
                json.dumps(_envelope())
                .replace('"intent": "dispute_charge"', '"intent": NaN')
                .encode("utf-8")
            ],
            "invalid_result_envelope",
        ),
        (
            [_encoded(_envelope("OTHER-CASE"))],
            "mismatched_case_id",
        ),
        (
            [_encoded(_envelope()), _encoded(_envelope())],
            "duplicate_result_envelope",
        ),
    ],
)
def test_invalid_duplicate_and_mismatched_envelopes_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    frames: list[bytes],
    expected_error: str,
) -> None:
    _install_fake_runtime(monkeypatch, tmp_path, frames=frames)

    result = run_case(_case(), _config())

    assert result.execution_status is CaseExecutionStatus.ERROR
    assert result.observation is None
    assert result.error == expected_error


def test_oversize_envelope_is_rejected_without_materializing_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    limit = 873
    _install_fake_runtime(monkeypatch, tmp_path, frames=[b"x" * (limit + 1)])

    result = run_case(_case(), _config(max_result_bytes=limit))

    assert result.execution_status is CaseExecutionStatus.ERROR
    assert result.error == "result_envelope_too_large"


def test_timeout_discards_provisional_envelope_then_terminates_and_joins(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, process, _, _, events, _ = _install_fake_runtime(
        monkeypatch,
        tmp_path,
        frames=[_encoded(_envelope())],
        process_kwargs={"natural_checks": 10_000, "terminate_stops": True},
        clock_step=0.02,
    )

    result = run_case(_case(), _config(timeout=0.05, grace=0.0))

    assert result.execution_status is CaseExecutionStatus.TIMEOUT
    assert result.observation is None
    assert result.error == "case_timeout"
    assert "terminate" in events
    assert "kill" not in events
    assert events.index("terminate") < events.index("join") < events.index("cleanup")
    assert process.joined is True


def test_child_exiting_during_grace_is_still_timeout_and_late_result_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    late = _encoded(_envelope())
    _install_fake_runtime(
        monkeypatch,
        tmp_path,
        process_kwargs={
            "natural_checks": 10_000,
            "exit_during_grace": True,
            "late_payload": late,
        },
        clock_step=0.02,
    )

    result = run_case(_case(), _config(timeout=0.05, grace=0.2))

    assert result.execution_status is CaseExecutionStatus.TIMEOUT
    assert result.observation is None
    assert result.error == "case_timeout"


def test_timeout_grace_drains_late_bytes_so_child_can_exit_naturally(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    late = _encoded(_envelope())
    _, _, _, _, events, _ = _install_fake_runtime(
        monkeypatch,
        tmp_path,
        process_kwargs={
            "natural_checks": 10_000,
            "exit_during_grace": True,
            "wait_for_late_drain": True,
            "late_payload": late,
        },
        clock_step=0.02,
    )

    result = run_case(_case(), _config(timeout=0.05, grace=0.2))

    assert result.execution_status is CaseExecutionStatus.TIMEOUT
    assert "receive" in events
    assert "terminate" not in events


def test_resistant_child_is_killed_joined_and_only_then_cleaned(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, process, _, _, events, _ = _install_fake_runtime(
        monkeypatch,
        tmp_path,
        process_kwargs={
            "natural_checks": 10_000,
            "terminate_stops": False,
            "kill_stops": True,
        },
        clock_step=0.02,
    )

    result = run_case(_case(), _config(timeout=0.05, grace=0.0))

    assert result.execution_status is CaseExecutionStatus.TIMEOUT
    assert events.index("terminate") < events.index("kill")
    assert events.index("kill") < events.index("cleanup")
    assert process.joined is True


def test_unstoppable_child_aborts_run_before_cleanup_or_next_case(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context, _, _, _, events, _ = _install_fake_runtime(
        monkeypatch,
        tmp_path,
        process_kwargs={
            "natural_checks": 10_000,
            "terminate_stops": False,
            "kill_stops": False,
        },
        clock_step=0.02,
    )

    with pytest.raises(
        EvaluationInfrastructureError, match="child_process_not_stopped"
    ):
        run_evaluation([_case(), _case("EVAL-RUNNER-002")], _config(timeout=0.05))

    assert len(context.process_calls) == 1
    assert "cleanup" not in events


def test_cleanup_failure_is_an_infrastructure_error_not_a_case_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_runtime(
        monkeypatch,
        tmp_path,
        frames=[_encoded(_envelope())],
    )

    def fail_cleanup(_path: Path) -> None:
        raise OSError("D:/secret/path cannot be removed")

    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.runner._remove_state_dir",
        fail_cleanup,
    )

    with pytest.raises(EvaluationInfrastructureError) as raised:
        run_case(_case(), _config())

    assert str(raised.value) == "state_cleanup_failed"
    assert "secret" not in str(raised.value)


def test_cleanup_failure_aborts_sequential_run_before_next_case(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context, _, _, _, _, _ = _install_fake_runtime(
        monkeypatch,
        tmp_path,
        frames=[_encoded(_envelope())],
    )
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.runner._remove_state_dir",
        lambda _path: (_ for _ in ()).throw(OSError("cleanup failed")),
    )

    with pytest.raises(EvaluationInfrastructureError, match="state_cleanup_failed"):
        run_evaluation([_case(), _case("EVAL-RUNNER-002")], _config())

    assert len(context.process_calls) == 1


def test_process_start_failure_closes_pipes_and_cleans_owned_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, _, parent_pipe, child_pipe, events, _ = _install_fake_runtime(
        monkeypatch,
        tmp_path,
        process_kwargs={"start_error": OSError("spawn failed at D:/secret")},
    )

    with pytest.raises(EvaluationInfrastructureError) as raised:
        run_case(_case(), _config())

    assert str(raised.value) == "child_process_start_failed"
    assert parent_pipe.closed is True
    assert child_pipe.closed is True
    assert "cleanup" in events


def _spawn_runtime_child(request: dict, child_pipe: Any) -> None:
    """Top-level spawn harness; it uses no model, Jev client, or network."""
    state_dir = Path(request["state_dir"])
    envelope = _envelope(request["case"]["case_id"])
    envelope["observation"]["response_text"] = json.dumps(
        {
            "pid": os.getpid(),
            "state_dir": str(state_dir),
            "daemon": multiprocessing.current_process().daemon,
            "start_method": multiprocessing.get_start_method(),
            "pipe_readable": child_pipe.readable,
        },
        sort_keys=True,
    )
    child_pipe.send_bytes(_encoded(envelope))
    time.sleep(0.08)
    child_pipe.close()


def test_runtime_spawn_uses_fresh_non_daemon_children_and_exclusive_cleaned_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.runner._CHILD_TARGET",
        _spawn_runtime_child,
    )
    cases = [_case("EVAL-SPAWN-001"), _case("EVAL-SPAWN-002")]

    run = run_evaluation(cases, _config(timeout=10.0, grace=0.2))

    details = [
        json.loads(result.observation.response_text)  # type: ignore[union-attr]
        for result in run.results
    ]
    assert [result.execution_status for result in run.results] == [
        CaseExecutionStatus.COMPLETED,
        CaseExecutionStatus.COMPLETED,
    ]
    assert len({detail["pid"] for detail in details}) == 2
    assert len({detail["state_dir"] for detail in details}) == 2
    assert all(detail["daemon"] is False for detail in details)
    assert all(detail["start_method"] == "spawn" for detail in details)
    assert all(detail["pipe_readable"] is False for detail in details)
    assert all(not Path(detail["state_dir"]).exists() for detail in details)
    assert run.total_duration_seconds >= 0.12
    assert not (
        {detail["pid"] for detail in details}
        & {p.pid for p in multiprocessing.active_children()}
    )


def test_runner_contracts_are_exported_from_evaluation_package() -> None:
    assert evaluation.CaseExecutionStatus is CaseExecutionStatus
    assert evaluation.run_case is run_case
    assert evaluation.run_evaluation is run_evaluation


def test_run_metadata_is_single_timestamped_ordered_and_lock_identified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.runner._CHILD_TARGET",
        _spawn_runtime_child,
    )
    cases = [_case("EVAL-ORDER-001"), _case("EVAL-ORDER-002")]

    run = run_evaluation(cases, _config(timeout=10.0, grace=0.2))

    assert [result.case_id for result in run.results] == [
        case.case_id for case in cases
    ]
    assert (
        run.timestamp_fs == run.timestamp[:19].replace("-", "").replace(":", "") + "Z"
    )
    assert run.configured_openai_model == settings.openai_model
    assert run.configured_jev_model == settings.typesafe_default_model
    assert (
        run.dependencies_lock_hash
        == hashlib.sha256((PROJECT_ROOT / "uv.lock").read_bytes()).hexdigest()
    )
    assert run.total_duration_seconds >= 0.12
