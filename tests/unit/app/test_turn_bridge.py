import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from ai_banking_customer_service.agent.orchestrator import (
    OrchestratorResult,
    TurnAction,
)
from app import chainlit_app
from app.chainlit_app import ActiveTurn, PendingTurnResult
from app.ui_helpers import get_template


def _result(response_text: str = "safe result") -> OrchestratorResult:
    return OrchestratorResult(
        action=TurnAction.RESPOND,
        response_text=response_text,
        trace_id="trace-123",
        session_id="session-123",
        intent=None,
        escalation_type=None,
        escalation_id=None,
    )


def _message(content: str = "No reconozco este cargo") -> SimpleNamespace:
    return SimpleNamespace(content=content)


def _use_session(monkeypatch: pytest.MonkeyPatch, session_id: object) -> Mock:
    get = Mock(return_value=session_id)
    monkeypatch.setattr(
        chainlit_app,
        "_chainlit_api",
        Mock(return_value=SimpleNamespace(user_session=SimpleNamespace(get=get))),
    )
    return get


async def _wait_until(predicate, attempts: int = 200) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(0.001)
    raise AssertionError("condition was not reached")


@pytest.fixture(autouse=True)
def _reset_process_state(monkeypatch: pytest.MonkeyPatch):
    chainlit_app._active_turns.clear()
    chainlit_app._pending_results.clear()
    chainlit_app._background_monitors.clear()
    monkeypatch.setattr(chainlit_app, "_orchestrator", None)
    yield
    chainlit_app._active_turns.clear()
    chainlit_app._pending_results.clear()
    chainlit_app._background_monitors.clear()


def test_pending_turn_result_enforces_normative_invariant() -> None:
    result = _result()

    valid_result = PendingTurnResult("result", "source", "es", result)
    valid_error = PendingTurnResult("internal_error", "source", "pt", None)

    assert valid_result.delivery_claimed is False
    assert valid_error.delivery_claimed is False
    with pytest.raises(ValueError):
        PendingTurnResult("result", "source", "es", None)
    with pytest.raises(ValueError):
        PendingTurnResult("internal_error", "source", "es", result)


def test_missing_reserved_session_fails_closed_before_state_or_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_session(monkeypatch, None)
    sender = AsyncMock(return_value=True)
    factory = Mock()
    monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)
    monkeypatch.setattr(chainlit_app, "_orchestrator_factory", factory)

    asyncio.run(chainlit_app.on_message(_message("Não reconheço esta cobrança")))

    sender.assert_awaited_once_with(
        get_template("internal_error", "pt"),
        session_id=None,
        trace_id=None,
    )
    factory.assert_not_called()
    assert chainlit_app._active_turns == {}
    assert chainlit_app._pending_results == {}


def test_active_turn_blocks_admission_even_when_worker_task_is_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        _use_session(monkeypatch, "session-123")
        sender = AsyncMock(return_value=True)
        factory = Mock()
        monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)
        monkeypatch.setattr(chainlit_app, "_orchestrator_factory", factory)
        task = asyncio.create_task(asyncio.sleep(0, result=_result()))
        await task
        active = ActiveTurn(task, threading.Event(), "original", "es")
        chainlit_app._active_turns["session-123"] = active

        await chainlit_app.on_message(_message("second message"))

        sender.assert_awaited_once_with(
            get_template("turn_in_progress", "es"),
            session_id="session-123",
            trace_id=None,
        )
        factory.assert_not_called()
        assert chainlit_app._active_turns["session-123"] is active

    asyncio.run(scenario())


def test_two_callbacks_atomically_claim_one_pending_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        _use_session(monkeypatch, "session-123")
        entered = asyncio.Event()
        release = asyncio.Event()
        render_calls: list[PendingTurnResult] = []

        async def render(pending: PendingTurnResult) -> bool:
            render_calls.append(pending)
            entered.set()
            await release.wait()
            return True

        sender = AsyncMock(return_value=True)
        factory = Mock()
        pending = PendingTurnResult("result", "original", "pt", _result())
        chainlit_app._pending_results["session-123"] = pending
        monkeypatch.setattr(chainlit_app, "_render_pending", render)
        monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)
        monkeypatch.setattr(chainlit_app, "_orchestrator_factory", factory)

        owner = asyncio.create_task(chainlit_app.on_message(_message("trigger one")))
        await entered.wait()
        contender = asyncio.create_task(
            chainlit_app.on_message(_message("Não processe isto"))
        )
        await contender
        release.set()
        await owner

        assert render_calls == [pending]
        sender.assert_awaited_once_with(
            get_template("reconciliation_in_progress", "pt"),
            session_id="session-123",
            trace_id=None,
        )
        factory.assert_not_called()
        assert "session-123" not in chainlit_app._pending_results

    asyncio.run(scenario())


def test_reconciliation_consumes_invalid_trigger_without_new_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_session(monkeypatch, "session-123")
    pending = PendingTurnResult("internal_error", "private original", "es", None)
    chainlit_app._pending_results["session-123"] = pending
    renderer = AsyncMock(return_value=True)
    factory = Mock()
    monkeypatch.setattr(chainlit_app, "_render_pending", renderer)
    monkeypatch.setattr(chainlit_app, "_orchestrator_factory", factory)

    asyncio.run(chainlit_app.on_message(_message("   ")))

    renderer.assert_awaited_once_with(pending)
    factory.assert_not_called()
    assert chainlit_app._pending_results == {}


def test_successful_pending_delivery_cannot_remove_newer_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_session(monkeypatch, "session-123")
    original = PendingTurnResult("result", "original", "es", _result())
    replacement = PendingTurnResult("internal_error", "new", "pt", None)

    async def replace_then_succeed(pending: PendingTurnResult) -> bool:
        assert pending is original
        chainlit_app._pending_results["session-123"] = replacement
        return True

    monkeypatch.setattr(chainlit_app, "_render_pending", replace_then_succeed)
    chainlit_app._pending_results["session-123"] = original

    asyncio.run(chainlit_app.on_message(_message("trigger")))

    assert chainlit_app._pending_results["session-123"] is replacement


def test_failed_pending_delivery_releases_claim_for_retry_by_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_session(monkeypatch, "session-123")
    original = PendingTurnResult("result", "original", "es", _result())
    replacement = PendingTurnResult("internal_error", "new", "pt", None)

    async def replace_then_fail(pending: PendingTurnResult) -> bool:
        assert pending is original
        chainlit_app._pending_results["session-123"] = replacement
        return False

    monkeypatch.setattr(chainlit_app, "_render_pending", replace_then_fail)
    chainlit_app._pending_results["session-123"] = original

    asyncio.run(chainlit_app.on_message(_message("trigger")))

    assert chainlit_app._pending_results["session-123"] is replacement
    assert replacement.delivery_claimed is False


def test_cancelled_pending_delivery_releases_claim_and_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_session(monkeypatch, "session-123")
    pending = PendingTurnResult("result", "original", "es", _result())
    chainlit_app._pending_results["session-123"] = pending
    monkeypatch.setattr(
        chainlit_app,
        "_render_pending",
        AsyncMock(side_effect=asyncio.CancelledError),
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(chainlit_app.on_message(_message("trigger")))

    assert chainlit_app._pending_results["session-123"] is pending
    assert pending.delivery_claimed is False


def test_validation_precedes_lazy_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_session(monkeypatch, "session-123")
    sender = AsyncMock(return_value=True)
    factory = Mock()
    monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)
    monkeypatch.setattr(chainlit_app, "_orchestrator_factory", factory)

    asyncio.run(chainlit_app.on_message(_message("x" * 4001)))

    sender.assert_awaited_once_with(
        get_template("too_long_input", "es"),
        session_id="session-123",
        trace_id=None,
    )
    factory.assert_not_called()
    assert chainlit_app._active_turns == {}


def test_lazy_factory_failure_is_safe_and_creates_no_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_session(monkeypatch, "session-123")
    secret = "credential secret"
    sender = AsyncMock(return_value=True)
    logger = Mock()
    monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)
    monkeypatch.setattr(
        chainlit_app,
        "_orchestrator_factory",
        Mock(side_effect=RuntimeError(secret)),
    )
    monkeypatch.setattr(chainlit_app, "logger", logger)

    asyncio.run(chainlit_app.on_message(_message()))

    sender.assert_awaited_once_with(
        get_template("internal_error", "es"),
        session_id="session-123",
        trace_id=None,
    )
    logger.warning.assert_called_once_with(
        "ORCHESTRATOR_ERROR",
        extra={"session_id": "session-123", "exception_type": "RuntimeError"},
    )
    assert secret not in repr(logger.mock_calls)
    assert chainlit_app._active_turns == {}


def test_accepted_turn_retains_one_to_thread_task_and_exact_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        _use_session(monkeypatch, "session-123")
        started = threading.Event()
        release = threading.Event()
        calls: list[dict[str, object]] = []

        class Orchestrator:
            def handle_turn(self, **kwargs: object) -> OrchestratorResult:
                calls.append(kwargs)
                started.set()
                release.wait(2)
                return _result()

        monkeypatch.setattr(
            chainlit_app, "_orchestrator_factory", Mock(return_value=Orchestrator())
        )
        monkeypatch.setattr(
            chainlit_app, "get_customer_id", Mock(return_value="demo-customer")
        )
        renderer = AsyncMock(return_value=True)
        monkeypatch.setattr(chainlit_app, "_render_pending", renderer)

        handler = asyncio.create_task(chainlit_app.on_message(_message("original")))
        await _wait_until(lambda: started.is_set())
        active = chainlit_app._active_turns["session-123"]
        assert isinstance(active.task, asyncio.Task)
        assert active.source_text == "original"
        assert active.language == "es"
        assert calls == [
            {
                "message": "original",
                "session_id": "session-123",
                "customer_id": "demo-customer",
                "cancel_signal": active.cancel_signal,
            }
        ]

        release.set()
        await handler

        assert len(calls) == 1
        renderer.assert_awaited_once()
        assert chainlit_app._active_turns == {}
        assert chainlit_app._pending_results == {}

    asyncio.run(scenario())


def test_normal_worker_exception_becomes_safe_pending_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_session(monkeypatch, "session-123")
    secret = "private worker failure"

    class Orchestrator:
        def handle_turn(self, **kwargs: object) -> OrchestratorResult:
            raise RuntimeError(secret)

    renderer = AsyncMock(return_value=True)
    logger = Mock()
    monkeypatch.setattr(
        chainlit_app, "_orchestrator_factory", Mock(return_value=Orchestrator())
    )
    monkeypatch.setattr(chainlit_app, "_render_pending", renderer)
    monkeypatch.setattr(chainlit_app, "logger", logger)

    asyncio.run(chainlit_app.on_message(_message()))

    pending = renderer.await_args.args[0]
    assert pending.kind == "internal_error"
    assert pending.result is None
    logger.warning.assert_called_once_with(
        "ORCHESTRATOR_ERROR",
        extra={"session_id": "session-123", "exception_type": "RuntimeError"},
    )
    assert secret not in repr(logger.mock_calls)


def test_worker_timeout_error_is_not_misclassified_as_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_session(monkeypatch, "session-123")

    class Orchestrator:
        def handle_turn(self, **kwargs: object) -> OrchestratorResult:
            raise TimeoutError("worker-owned timeout")

    renderer = AsyncMock(return_value=True)
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(
        chainlit_app, "_orchestrator_factory", Mock(return_value=Orchestrator())
    )
    monkeypatch.setattr(chainlit_app, "_render_pending", renderer)
    monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)

    asyncio.run(chainlit_app.on_message(_message()))

    assert renderer.await_args.args[0].kind == "internal_error"
    assert all(
        call.args[0] != get_template("timeout_exceeded", "es")
        for call in sender.await_args_list
    )


def test_first_deadline_then_grace_completion_uses_same_shielded_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        _use_session(monkeypatch, "session-123")
        shielded: list[asyncio.Future[OrchestratorResult]] = []
        real_shield = asyncio.shield

        def recording_shield(task):
            shielded.append(task)
            return real_shield(task)

        class Orchestrator:
            def handle_turn(self, **kwargs: object) -> OrchestratorResult:
                cancel_signal = kwargs["cancel_signal"]
                assert isinstance(cancel_signal, threading.Event)
                assert cancel_signal.wait(1)
                return _result()

        renderer = AsyncMock(return_value=True)
        sender = AsyncMock(return_value=True)
        monkeypatch.setattr(chainlit_app.asyncio, "shield", recording_shield)
        monkeypatch.setattr(chainlit_app, "TURN_TIMEOUT_SECONDS", 0.01)
        monkeypatch.setattr(chainlit_app, "THREAD_TERMINATION_TIMEOUT_SECONDS", 1)
        monkeypatch.setattr(
            chainlit_app, "_orchestrator_factory", Mock(return_value=Orchestrator())
        )
        monkeypatch.setattr(chainlit_app, "_render_pending", renderer)
        monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)

        await chainlit_app.on_message(_message())

        assert len(shielded) == 2
        assert shielded[0] is shielded[1]
        assert renderer.await_args.args[0].kind == "result"
        assert all(
            call.args[0] != get_template("timeout_exceeded", "es")
            for call in sender.await_args_list
        )

    asyncio.run(scenario())


def test_grace_period_exception_becomes_safe_error_not_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_session(monkeypatch, "session-123")

    class Orchestrator:
        def handle_turn(self, **kwargs: object) -> OrchestratorResult:
            cancel_signal = kwargs["cancel_signal"]
            assert isinstance(cancel_signal, threading.Event)
            assert cancel_signal.wait(1)
            raise RuntimeError("late private failure")

    renderer = AsyncMock(return_value=True)
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(chainlit_app, "TURN_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(chainlit_app, "THREAD_TERMINATION_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(
        chainlit_app, "_orchestrator_factory", Mock(return_value=Orchestrator())
    )
    monkeypatch.setattr(chainlit_app, "_render_pending", renderer)
    monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)

    asyncio.run(chainlit_app.on_message(_message()))

    assert renderer.await_args.args[0].kind == "internal_error"
    assert all(
        call.args[0] != get_template("timeout_exceeded", "es")
        for call in sender.await_args_list
    )


def test_dual_timeout_retains_active_and_one_strong_monitor_until_late_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        _use_session(monkeypatch, "session-123")
        release = threading.Event()
        calls = 0

        class Orchestrator:
            def handle_turn(self, **kwargs: object) -> OrchestratorResult:
                nonlocal calls
                calls += 1
                release.wait(2)
                return _result("late result")

        sender = AsyncMock(return_value=True)
        monkeypatch.setattr(chainlit_app, "TURN_TIMEOUT_SECONDS", 0.01)
        monkeypatch.setattr(chainlit_app, "THREAD_TERMINATION_TIMEOUT_SECONDS", 0.01)
        monkeypatch.setattr(
            chainlit_app, "_orchestrator_factory", Mock(return_value=Orchestrator())
        )
        monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)

        await chainlit_app.on_message(_message())

        active = chainlit_app._active_turns["session-123"]
        assert active.cancel_signal.is_set()
        assert active.monitor is not None
        assert active.monitor in chainlit_app._background_monitors
        assert calls == 1
        sender.assert_awaited_once_with(
            get_template("timeout_exceeded", "es"),
            session_id="session-123",
            trace_id=None,
        )

        chainlit_app._ensure_monitor("session-123", active)
        assert len(chainlit_app._background_monitors) == 1
        release.set()
        await _wait_until(lambda: "session-123" not in chainlit_app._active_turns)
        await asyncio.sleep(0)

        pending = chainlit_app._pending_results["session-123"]
        assert pending.kind == "result"
        assert pending.result == _result("late result")
        assert active.monitor not in chainlit_app._background_monitors
        assert calls == 1

    asyncio.run(scenario())


def test_handler_cancellation_signals_worker_monitors_and_preserves_late_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        _use_session(monkeypatch, "session-123")
        started = threading.Event()
        release = threading.Event()
        calls = 0

        class Orchestrator:
            def handle_turn(self, **kwargs: object) -> OrchestratorResult:
                nonlocal calls
                calls += 1
                started.set()
                release.wait(2)
                return _result("after cancellation")

        monkeypatch.setattr(
            chainlit_app, "_orchestrator_factory", Mock(return_value=Orchestrator())
        )
        handler = asyncio.create_task(chainlit_app.on_message(_message("original")))
        await _wait_until(lambda: started.is_set())
        active = chainlit_app._active_turns["session-123"]

        handler.cancel()
        with pytest.raises(asyncio.CancelledError):
            await handler

        assert active.cancel_signal.is_set()
        assert chainlit_app._active_turns["session-123"] is active
        assert active.monitor in chainlit_app._background_monitors
        release.set()
        await _wait_until(lambda: "session-123" not in chainlit_app._active_turns)

        pending = chainlit_app._pending_results["session-123"]
        assert pending.kind == "result"
        assert pending.source_text == "original"
        assert calls == 1

        renderer = AsyncMock(return_value=True)
        monkeypatch.setattr(chainlit_app, "_render_pending", renderer)
        await chainlit_app.on_message(_message("must only reconcile"))
        renderer.assert_awaited_once_with(pending)
        assert calls == 1

    asyncio.run(scenario())


def test_cancellation_after_worker_completion_publishes_before_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        _use_session(monkeypatch, "session-123")
        real_wait_for = asyncio.wait_for

        async def cancel_after_completion(awaitable, timeout):
            await real_wait_for(awaitable, timeout)
            raise asyncio.CancelledError

        class Orchestrator:
            def handle_turn(self, **kwargs: object) -> OrchestratorResult:
                return _result("completed before cancellation")

        monkeypatch.setattr(chainlit_app.asyncio, "wait_for", cancel_after_completion)
        monkeypatch.setattr(
            chainlit_app, "_orchestrator_factory", Mock(return_value=Orchestrator())
        )

        with pytest.raises(asyncio.CancelledError):
            await chainlit_app.on_message(_message("original"))

        assert "session-123" not in chainlit_app._active_turns
        pending = chainlit_app._pending_results["session-123"]
        assert pending.kind == "result"
        assert pending.result == _result("completed before cancellation")

    asyncio.run(scenario())


def test_cancellation_during_immediate_render_preserves_unclaimed_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        _use_session(monkeypatch, "session-123")
        render_started = asyncio.Event()
        render_release = asyncio.Event()

        class Orchestrator:
            def handle_turn(self, **kwargs: object) -> OrchestratorResult:
                return _result()

        async def render(pending: PendingTurnResult) -> bool:
            render_started.set()
            await render_release.wait()
            return True

        monkeypatch.setattr(
            chainlit_app, "_orchestrator_factory", Mock(return_value=Orchestrator())
        )
        monkeypatch.setattr(chainlit_app, "_render_pending", render)
        handler = asyncio.create_task(chainlit_app.on_message(_message("original")))
        await render_started.wait()
        pending = chainlit_app._pending_results["session-123"]
        assert pending.delivery_claimed is True

        handler.cancel()
        with pytest.raises(asyncio.CancelledError):
            await handler

        assert "session-123" not in chainlit_app._active_turns
        assert chainlit_app._pending_results["session-123"] is pending
        assert pending.delivery_claimed is False

    asyncio.run(scenario())


def test_immediate_delivery_failure_preserves_pending_without_duplicate_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_session(monkeypatch, "session-123")
    calls = 0

    class Orchestrator:
        def handle_turn(self, **kwargs: object) -> OrchestratorResult:
            nonlocal calls
            calls += 1
            return _result()

    renderer = AsyncMock(side_effect=[False, True])
    monkeypatch.setattr(
        chainlit_app, "_orchestrator_factory", Mock(return_value=Orchestrator())
    )
    monkeypatch.setattr(chainlit_app, "_render_pending", renderer)

    asyncio.run(chainlit_app.on_message(_message("original")))

    pending = chainlit_app._pending_results["session-123"]
    assert pending.delivery_claimed is False
    assert "session-123" not in chainlit_app._active_turns
    assert calls == 1

    asyncio.run(chainlit_app.on_message(_message("reconcile only")))

    assert calls == 1
    assert renderer.await_args_list[1].args == (pending,)
    assert "session-123" not in chainlit_app._pending_results


def test_monitor_converts_cancelled_worker_to_internal_error_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        logger = Mock()
        monkeypatch.setattr(chainlit_app, "logger", logger)
        task = asyncio.create_task(asyncio.sleep(10, result=_result()))
        active = ActiveTurn(task, threading.Event(), "private source", "pt")
        chainlit_app._active_turns["session-123"] = active
        task.cancel()

        await chainlit_app._monitor_turn("session-123", active)

        assert "session-123" not in chainlit_app._active_turns
        pending = chainlit_app._pending_results["session-123"]
        assert pending.kind == "internal_error"
        assert pending.result is None
        logger.warning.assert_called_once_with(
            "ORCHESTRATOR_ERROR",
            extra={"session_id": "session-123", "exception_type": "CancelledError"},
        )
        assert "private source" not in repr(logger.mock_calls)

    asyncio.run(scenario())


def test_late_monitor_exception_publishes_safe_error_and_releases_strong_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        logger = Mock()
        monkeypatch.setattr(chainlit_app, "logger", logger)

        async def fail_late() -> OrchestratorResult:
            await asyncio.sleep(0)
            raise RuntimeError("private late failure")

        task = asyncio.create_task(fail_late())
        active = ActiveTurn(task, threading.Event(), "private source", "pt")
        chainlit_app._active_turns["session-123"] = active

        chainlit_app._ensure_monitor("session-123", active)
        monitor = active.monitor
        assert monitor is not None
        assert monitor in chainlit_app._background_monitors
        await monitor
        await asyncio.sleep(0)

        assert "session-123" not in chainlit_app._active_turns
        assert chainlit_app._pending_results["session-123"].kind == "internal_error"
        assert monitor not in chainlit_app._background_monitors
        logger.warning.assert_called_once_with(
            "ORCHESTRATOR_ERROR",
            extra={"session_id": "session-123", "exception_type": "RuntimeError"},
        )
        assert "private late failure" not in repr(logger.mock_calls)
        assert "private source" not in repr(logger.mock_calls)

    asyncio.run(scenario())


def test_stale_monitor_cannot_replace_or_clean_newer_session_state() -> None:
    async def scenario() -> None:
        old_task = asyncio.create_task(asyncio.sleep(0, result=_result("old")))
        new_task = asyncio.create_task(asyncio.sleep(0, result=_result("new")))
        old = ActiveTurn(old_task, threading.Event(), "old", "es")
        new = ActiveTurn(new_task, threading.Event(), "new", "pt")
        existing_pending = PendingTurnResult(
            "result", "existing", "es", _result("existing")
        )
        chainlit_app._active_turns["session-123"] = new
        chainlit_app._pending_results["session-123"] = existing_pending

        await chainlit_app._monitor_turn("session-123", old)
        await new_task

        assert chainlit_app._active_turns["session-123"] is new
        assert chainlit_app._pending_results["session-123"] is existing_pending

    asyncio.run(scenario())


def test_stale_immediate_cleanup_cannot_remove_newer_active_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        _use_session(monkeypatch, "session-123")

        class Orchestrator:
            def handle_turn(self, **kwargs: object) -> OrchestratorResult:
                return _result("old")

        replacement_task = asyncio.create_task(asyncio.sleep(0, result=_result("new")))
        replacement = ActiveTurn(replacement_task, threading.Event(), "new", "pt")

        async def replace_active(pending: PendingTurnResult) -> bool:
            chainlit_app._active_turns["session-123"] = replacement
            return True

        monkeypatch.setattr(
            chainlit_app, "_orchestrator_factory", Mock(return_value=Orchestrator())
        )
        monkeypatch.setattr(chainlit_app, "_render_pending", replace_active)

        await chainlit_app.on_message(_message("old"))
        await replacement_task

        assert chainlit_app._active_turns["session-123"] is replacement

    asyncio.run(scenario())


def test_on_stop_uses_reserved_id_and_only_sets_current_signal_idempotently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        get = _use_session(monkeypatch, "session-123")
        task = asyncio.create_task(asyncio.sleep(0, result=_result()))
        active = ActiveTurn(task, threading.Event(), "source", "es")
        chainlit_app._active_turns["session-123"] = active

        await chainlit_app.on_stop()
        await chainlit_app.on_stop()
        await task

        assert active.cancel_signal.is_set()
        assert chainlit_app._active_turns["session-123"] is active
        assert chainlit_app._pending_results == {}
        assert [call.args for call in get.call_args_list] == [("id",), ("id",)]

    asyncio.run(scenario())


def test_handlers_register_with_chainlit_when_runtime_is_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_chainlit = SimpleNamespace(on_message=Mock(), on_stop=Mock())
    monkeypatch.setitem(chainlit_app.sys.modules, "chainlit", fake_chainlit)

    chainlit_app._register_chainlit_handlers()

    fake_chainlit.on_message.assert_called_once_with(chainlit_app.on_message)
    fake_chainlit.on_stop.assert_called_once_with(chainlit_app.on_stop)


def test_on_stop_with_invalid_reserved_id_does_not_touch_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        _use_session(monkeypatch, None)
        task = asyncio.create_task(asyncio.sleep(0, result=_result()))
        active = ActiveTurn(task, threading.Event(), "source", "es")
        chainlit_app._active_turns["session-123"] = active

        await chainlit_app.on_stop()
        await task

        assert active.cancel_signal.is_set() is False
        assert chainlit_app._active_turns["session-123"] is active

    asyncio.run(scenario())
