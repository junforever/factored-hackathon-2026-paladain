"""Chainlit startup safety boundary and lazy orchestrator access."""

import asyncio
import logging
import sys
import threading
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ai_banking_customer_service.agent.orchestrator import (
    BankingOrchestrator,
    OrchestratorResult,
    TurnAction,
)
from ai_banking_customer_service.config import PROJECT_ROOT, settings
from app.bootstrap import build_orchestrator
from app.ui_helpers import Language, detect_language, get_template, validate_input

CHAINLIT_CONFIG_PATH = PROJECT_ROOT / ".chainlit" / "config.toml"

logger = logging.getLogger(__name__)

TURN_TIMEOUT_SECONDS = 60
THREAD_TERMINATION_TIMEOUT_SECONDS = 5

_orchestrator_factory: Callable[[], BankingOrchestrator] = build_orchestrator
_orchestrator: BankingOrchestrator | None = None


@dataclass
class ActiveTurn:
    task: asyncio.Task[OrchestratorResult]
    cancel_signal: threading.Event
    source_text: str
    language: Language
    monitor: asyncio.Task[None] | None = None


@dataclass
class PendingTurnResult:
    kind: Literal["result", "internal_error"]
    source_text: str
    language: Language
    result: OrchestratorResult | None
    delivery_claimed: bool = False

    def __post_init__(self) -> None:
        valid = (self.kind == "result" and self.result is not None) or (
            self.kind == "internal_error" and self.result is None
        )
        if not valid:
            raise ValueError("Invalid pending turn result")


_active_turns: dict[str, ActiveTurn] = {}
_pending_results: dict[str, PendingTurnResult] = {}
_background_monitors: set[asyncio.Task[None]] = set()


def _chainlit_api():
    import chainlit as cl

    return cl


def _validate_startup_config(config_path: Path) -> None:
    """Require Chainlit's unsafe HTML feature to be explicitly disabled."""
    try:
        with config_path.open("rb") as config_file:
            config = tomllib.load(config_file)
    except (OSError, tomllib.TOMLDecodeError):
        raise RuntimeError("Unsafe Chainlit configuration") from None

    features = config.get("features")
    if not isinstance(features, dict) or features.get("unsafe_allow_html") is not False:
        raise RuntimeError("Unsafe Chainlit configuration")


def _get_orchestrator() -> BankingOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = _orchestrator_factory()
    return _orchestrator


def get_session_id() -> str | None:
    """Return Chainlit's reserved conversation ID without synthesizing one."""
    try:
        cl = _chainlit_api()
        session_id = cl.user_session.get("id")
    except Exception:
        return None
    return (
        session_id if isinstance(session_id, str) and bool(session_id.strip()) else None
    )


def get_customer_id() -> str:
    """Return the configured demo customer identity."""
    return settings.demo_customer_id


def _log_metadata(
    *,
    session_id: str | None,
    trace_id: str | None,
    exception_type: str | None = None,
) -> dict[str, str]:
    metadata = {}
    if session_id is not None:
        metadata["session_id"] = session_id
    if trace_id is not None:
        metadata["trace_id"] = trace_id
    if exception_type is not None:
        metadata["exception_type"] = exception_type
    return metadata


async def _send_ui_message(
    content: str,
    *,
    session_id: str | None,
    trace_id: str | None,
) -> bool:
    """Deliver one UI-owned message without exposing delivery failures."""
    try:
        cl = _chainlit_api()
        await cl.Message(content=content).send()
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.warning(
            "UI_SEND_FAILED",
            extra=_log_metadata(
                session_id=session_id,
                trace_id=trace_id,
                exception_type=type(error).__name__,
            ),
        )
        return False
    return True


async def _render_result(
    result: OrchestratorResult,
    source_text: str,
    language: Language,
) -> bool:
    """Render every known turn action and fail closed for future actions."""
    if result.action is TurnAction.ESCALATE:
        content = get_template("escalation_prefix", language) + result.response_text
    elif result.action in {
        TurnAction.RESPOND,
        TurnAction.BLOCK,
        TurnAction.ABSTAIN,
    }:
        content = result.response_text
    else:
        logger.warning(
            "UNKNOWN_ACTION",
            extra=_log_metadata(
                session_id=result.session_id,
                trace_id=result.trace_id,
            ),
        )
        content = get_template("internal_error", language)

    delivered = await _send_ui_message(
        content,
        session_id=result.session_id,
        trace_id=result.trace_id,
    )
    if delivered:
        return True

    logger.warning(
        "RENDER_FAILED",
        extra=_log_metadata(
            session_id=result.session_id,
            trace_id=result.trace_id,
        ),
    )
    await _send_ui_message(
        get_template("render_error", language),
        session_id=result.session_id,
        trace_id=result.trace_id,
    )
    return False


async def _render_pending(pending: PendingTurnResult) -> bool:
    """Render the safe outcome retained for later reconciliation."""
    if pending.kind == "result" and pending.result is not None:
        return await _render_result(
            pending.result,
            pending.source_text,
            pending.language,
        )
    if pending.kind == "internal_error" and pending.result is None:
        return await _send_ui_message(
            get_template("internal_error", pending.language),
            session_id=None,
            trace_id=None,
        )

    logger.warning("RENDER_FAILED")
    await _send_ui_message(
        get_template("internal_error", pending.language),
        session_id=None,
        trace_id=None,
    )
    return False


def _log_orchestrator_error(session_id: str, error: BaseException) -> None:
    logger.warning(
        "ORCHESTRATOR_ERROR",
        extra=_log_metadata(
            session_id=session_id,
            trace_id=None,
            exception_type=type(error).__name__,
        ),
    )


def _pending_from_task(active: ActiveTurn, session_id: str) -> PendingTurnResult:
    try:
        result = active.task.result()
    except asyncio.CancelledError as error:
        _log_orchestrator_error(session_id, error)
        return PendingTurnResult(
            "internal_error", active.source_text, active.language, None
        )
    except Exception as error:
        _log_orchestrator_error(session_id, error)
        return PendingTurnResult(
            "internal_error", active.source_text, active.language, None
        )
    return PendingTurnResult("result", active.source_text, active.language, result)


def _claim_pending(session_id: str, pending: PendingTurnResult) -> bool:
    if _pending_results.get(session_id) is not pending or pending.delivery_claimed:
        return False
    pending.delivery_claimed = True
    return True


def _release_pending_claim(session_id: str, pending: PendingTurnResult) -> None:
    if _pending_results.get(session_id) is pending:
        pending.delivery_claimed = False


def _remove_pending(session_id: str, pending: PendingTurnResult) -> None:
    if _pending_results.get(session_id) is pending:
        del _pending_results[session_id]


def _remove_active(session_id: str, active: ActiveTurn) -> None:
    if _active_turns.get(session_id) is active:
        del _active_turns[session_id]


async def _monitor_turn(session_id: str, active: ActiveTurn) -> None:
    try:
        result = await asyncio.shield(active.task)
    except asyncio.CancelledError as error:
        if not active.task.done():
            raise
        _log_orchestrator_error(session_id, error)
        pending = PendingTurnResult(
            "internal_error", active.source_text, active.language, None
        )
    except Exception as error:
        _log_orchestrator_error(session_id, error)
        pending = PendingTurnResult(
            "internal_error", active.source_text, active.language, None
        )
    else:
        pending = PendingTurnResult(
            "result", active.source_text, active.language, result
        )

    if _active_turns.get(session_id) is active:
        _pending_results[session_id] = pending
        del _active_turns[session_id]


def _ensure_monitor(session_id: str, active: ActiveTurn) -> None:
    if (
        _active_turns.get(session_id) is not active
        or active.task.done()
        or active.monitor is not None
    ):
        return
    monitor = asyncio.create_task(_monitor_turn(session_id, active))
    active.monitor = monitor
    _background_monitors.add(monitor)
    monitor.add_done_callback(_background_monitors.discard)


async def _await_worker(
    session_id: str,
    active: ActiveTurn,
) -> OrchestratorResult | None:
    try:
        return await asyncio.wait_for(asyncio.shield(active.task), TURN_TIMEOUT_SECONDS)
    except TimeoutError:
        if active.task.done():
            return active.task.result()

    active.cancel_signal.set()
    try:
        return await asyncio.wait_for(
            asyncio.shield(active.task), THREAD_TERMINATION_TIMEOUT_SECONDS
        )
    except TimeoutError:
        if active.task.done():
            return active.task.result()

    _ensure_monitor(session_id, active)
    logger.warning(
        "TIMEOUT_EXCEEDED",
        extra=_log_metadata(session_id=session_id, trace_id=None),
    )
    await _send_ui_message(
        get_template("timeout_exceeded", active.language),
        session_id=session_id,
        trace_id=None,
    )
    return None


async def _reconcile_pending(
    session_id: str,
    pending: PendingTurnResult,
) -> None:
    if not _claim_pending(session_id, pending):
        await _send_ui_message(
            get_template("reconciliation_in_progress", pending.language),
            session_id=session_id,
            trace_id=None,
        )
        return

    try:
        delivered = await _render_pending(pending)
    except asyncio.CancelledError:
        _release_pending_claim(session_id, pending)
        raise
    except Exception as error:
        _release_pending_claim(session_id, pending)
        logger.warning(
            "TURN_RECONCILE_ERROR",
            extra=_log_metadata(
                session_id=session_id,
                trace_id=None,
                exception_type=type(error).__name__,
            ),
        )
        return

    if delivered:
        _remove_pending(session_id, pending)
        logger.info(
            "TURN_RECONCILED",
            extra=_log_metadata(session_id=session_id, trace_id=None),
        )
    else:
        _release_pending_claim(session_id, pending)
        logger.warning(
            "TURN_RECONCILE_ERROR",
            extra=_log_metadata(session_id=session_id, trace_id=None),
        )


async def _handle_message(message: object) -> None:
    source_text = getattr(message, "content", "")
    if not isinstance(source_text, str):
        source_text = ""
    language = detect_language(source_text)
    session_id = get_session_id()
    if session_id is None:
        await _send_ui_message(
            get_template("internal_error", language),
            session_id=None,
            trace_id=None,
        )
        return

    if session_id in _active_turns:
        await _send_ui_message(
            get_template("turn_in_progress", language),
            session_id=session_id,
            trace_id=None,
        )
        return

    pending = _pending_results.get(session_id)
    if pending is not None:
        await _reconcile_pending(session_id, pending)
        return

    validation_error = validate_input(source_text, language)
    if validation_error is not None:
        await _send_ui_message(
            validation_error,
            session_id=session_id,
            trace_id=None,
        )
        return

    try:
        orchestrator = _get_orchestrator()
    except Exception as error:
        _log_orchestrator_error(session_id, error)
        await _send_ui_message(
            get_template("internal_error", language),
            session_id=session_id,
            trace_id=None,
        )
        return

    cancel_signal = threading.Event()
    task = asyncio.create_task(
        asyncio.to_thread(
            orchestrator.handle_turn,
            message=source_text,
            session_id=session_id,
            customer_id=get_customer_id(),
            cancel_signal=cancel_signal,
        )
    )
    active = ActiveTurn(task, cancel_signal, source_text, language)
    _active_turns[session_id] = active

    try:
        result = await _await_worker(session_id, active)
    except asyncio.CancelledError:
        active.cancel_signal.set()
        if active.task.done():
            pending = _pending_from_task(active, session_id)
            if _active_turns.get(session_id) is active:
                _pending_results[session_id] = pending
                del _active_turns[session_id]
        else:
            _ensure_monitor(session_id, active)
        raise
    except Exception as error:
        _log_orchestrator_error(session_id, error)
        pending = PendingTurnResult(
            "internal_error", active.source_text, active.language, None
        )
    else:
        if result is None:
            return
        pending = PendingTurnResult(
            "result", active.source_text, active.language, result
        )

    if _active_turns.get(session_id) is not active:
        return
    _pending_results[session_id] = pending
    pending.delivery_claimed = True
    try:
        delivered = await _render_pending(pending)
    except asyncio.CancelledError:
        active.cancel_signal.set()
        _release_pending_claim(session_id, pending)
        _remove_active(session_id, active)
        raise
    except Exception as error:
        _release_pending_claim(session_id, pending)
        _remove_active(session_id, active)
        logger.warning(
            "RENDER_FAILED",
            extra=_log_metadata(
                session_id=session_id,
                trace_id=None,
                exception_type=type(error).__name__,
            ),
        )
        return

    if delivered:
        _remove_pending(session_id, pending)
    else:
        _release_pending_claim(session_id, pending)
    _remove_active(session_id, active)


async def _handle_stop() -> None:
    session_id = get_session_id()
    if session_id is None:
        return
    active = _active_turns.get(session_id)
    if active is not None:
        active.cancel_signal.set()


async def on_message(message: object) -> None:
    await _handle_message(message)


async def on_stop() -> None:
    await _handle_stop()


def _register_chainlit_handlers() -> None:
    cl = sys.modules.get("chainlit")
    if cl is not None:
        cl.on_message(on_message)
        cl.on_stop(on_stop)


_validate_startup_config(CHAINLIT_CONFIG_PATH)
_register_chainlit_handlers()
