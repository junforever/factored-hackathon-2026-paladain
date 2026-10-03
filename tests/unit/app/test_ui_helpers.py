import asyncio
from dataclasses import replace
from types import SimpleNamespace
from typing import cast, get_args
from unittest.mock import AsyncMock, Mock

import pytest

from ai_banking_customer_service.agent.orchestrator import (
    OrchestratorResult,
    TurnAction,
)
from app import chainlit_app
from app.ui_helpers import (
    MAX_MESSAGE_CHARS,
    UI_TEMPLATES,
    Language,
    detect_language,
    get_template,
    validate_input,
)


def _result(action: TurnAction = TurnAction.RESPOND) -> OrchestratorResult:
    return OrchestratorResult(
        action=action,
        response_text="approved response",
        trace_id="trace-123",
        session_id="session-123",
        intent=None,
        escalation_type=None,
        escalation_id=None,
    )


def test_language_contract_and_detection_are_spanish_portuguese_only() -> None:
    assert get_args(Language) == ("es", "pt")
    assert detect_language("No reconozco este cargo") == "es"
    assert detect_language("Não reconheço esta cobrança") == "pt"


def test_ui_templates_preserve_exact_normative_copy() -> None:
    assert UI_TEMPLATES == {
        "empty_input": {
            "es": "Por favor ingresa un mensaje.",
            "pt": "Por favor insira uma mensagem.",
        },
        "too_long_input": {
            "es": "El mensaje es demasiado largo. Por favor acórtalo.",
            "pt": "A mensagem é muito longa. Por favor encurte-a.",
        },
        "internal_error": {
            "es": "Ocurrió un error interno. Por favor intenta de nuevo.",
            "pt": "Ocorreu um erro interno. Por favor tente novamente.",
        },
        "timeout_exceeded": {
            "es": (
                "La solicitud superó el tiempo de espera. La operación todavía está "
                "finalizando. Por favor espera el resultado antes de reintentar."
            ),
            "pt": (
                "A solicitação excedeu o tempo de espera. A operação ainda está "
                "finalizando. Por favor aguarde o resultado antes de tentar novamente."
            ),
        },
        "turn_in_progress": {
            "es": "Hay una solicitud en curso. Por favor espera a que termine.",
            "pt": "Há uma solicitação em andamento. Por favor aguarde até que termine.",
        },
        "reconciliation_in_progress": {
            "es": "El resultado anterior se está mostrando. Por favor espera.",
            "pt": "O resultado anterior está sendo exibido. Por favor aguarde.",
        },
        "render_error": {
            "es": "Error al mostrar el mensaje.",
            "pt": "Erro ao exibir a mensagem.",
        },
        "escalation_prefix": {
            "es": "🔴 Escalamiento: ",
            "pt": "🔴 Escalonamento: ",
        },
    }
    assert get_template("internal_error", "pt") == UI_TEMPLATES["internal_error"]["pt"]


@pytest.mark.parametrize("text", ["", "   \t\n"])
@pytest.mark.parametrize("language", ["es", "pt"])
def test_validate_input_localizes_empty_or_whitespace_input(
    text: str,
    language: Language,
) -> None:
    assert validate_input(text, language) == get_template("empty_input", language)


@pytest.mark.parametrize("language", ["es", "pt"])
def test_validate_input_accepts_limit_and_rejects_over_limit_without_truncation(
    language: Language,
) -> None:
    at_limit = "x" * MAX_MESSAGE_CHARS
    over_limit = at_limit + "y"

    assert validate_input(at_limit, language) is None
    assert validate_input(over_limit, language) == get_template(
        "too_long_input", language
    )
    assert over_limit.endswith("y")


def test_validate_input_logs_only_static_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = Mock()
    monkeypatch.setattr("app.ui_helpers.logger", logger)

    validate_input("private PAN 4111111111111111" * 1000, "es")

    logger.warning.assert_called_once_with("TOO_LONG_INPUT")


@pytest.mark.parametrize(
    ("reserved_id", "expected"),
    [("chainlit-session", "chainlit-session"), ("  stable  ", "  stable  ")],
)
def test_get_session_id_reuses_chainlit_reserved_id(
    monkeypatch: pytest.MonkeyPatch,
    reserved_id: str,
    expected: str,
) -> None:
    get = Mock(return_value=reserved_id)
    monkeypatch.setattr(
        chainlit_app,
        "_chainlit_api",
        Mock(return_value=SimpleNamespace(user_session=SimpleNamespace(get=get))),
    )

    assert chainlit_app.get_session_id() == expected
    get.assert_called_once_with("id")


@pytest.mark.parametrize("reserved_id", [None, "", "  ", 123, False])
def test_get_session_id_fails_closed_without_synthesizing(
    monkeypatch: pytest.MonkeyPatch,
    reserved_id: object,
) -> None:
    get = Mock(return_value=reserved_id)
    monkeypatch.setattr(
        chainlit_app,
        "_chainlit_api",
        Mock(return_value=SimpleNamespace(user_session=SimpleNamespace(get=get))),
    )

    assert chainlit_app.get_session_id() is None
    get.assert_called_once_with("id")


def test_get_session_id_returns_none_when_chainlit_access_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        chainlit_app,
        "_chainlit_api",
        Mock(side_effect=RuntimeError("private runtime failure")),
    )

    assert chainlit_app.get_session_id() is None


def test_get_customer_id_comes_only_from_typed_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        chainlit_app,
        "settings",
        SimpleNamespace(demo_customer_id="configured-customer"),
    )

    assert chainlit_app.get_customer_id() == "configured-customer"


def test_send_ui_message_is_the_single_chainlit_delivery_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivered: list[str] = []

    class FakeMessage:
        def __init__(self, *, content: str) -> None:
            self.content = content

        async def send(self) -> None:
            delivered.append(self.content)

    monkeypatch.setattr(
        chainlit_app,
        "_chainlit_api",
        Mock(return_value=SimpleNamespace(Message=FakeMessage)),
    )

    sent = asyncio.run(
        chainlit_app._send_ui_message(
            "safe content",
            session_id="session-123",
            trace_id="trace-123",
        )
    )

    assert sent is True
    assert delivered == ["safe content"]


def test_send_ui_message_returns_false_and_logs_only_allowlisted_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "PAN 4111111111111111 raw exception"
    logger = Mock()

    class FailingMessage:
        def __init__(self, *, content: str) -> None:
            self.content = content

        async def send(self) -> None:
            raise RuntimeError(secret)

    monkeypatch.setattr(
        chainlit_app,
        "_chainlit_api",
        Mock(return_value=SimpleNamespace(Message=FailingMessage)),
    )
    monkeypatch.setattr(chainlit_app, "logger", logger)

    sent = asyncio.run(
        chainlit_app._send_ui_message(
            "private response text",
            session_id=None,
            trace_id="trace-123",
        )
    )

    assert sent is False
    logger.warning.assert_called_once_with(
        "UI_SEND_FAILED",
        extra={"trace_id": "trace-123", "exception_type": "RuntimeError"},
    )
    assert secret not in repr(logger.mock_calls)
    assert "private response text" not in repr(logger.mock_calls)


def test_send_ui_message_propagates_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CancelledMessage:
        def __init__(self, *, content: str) -> None:
            self.content = content

        async def send(self) -> None:
            raise asyncio.CancelledError

    monkeypatch.setattr(
        chainlit_app,
        "_chainlit_api",
        Mock(return_value=SimpleNamespace(Message=CancelledMessage)),
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            chainlit_app._send_ui_message(
                "safe content",
                session_id="session-123",
                trace_id=None,
            )
        )


@pytest.mark.parametrize(
    ("action", "language", "expected"),
    [
        (TurnAction.RESPOND, "es", "approved response"),
        (TurnAction.ESCALATE, "es", "🔴 Escalamiento: approved response"),
        (TurnAction.ESCALATE, "pt", "🔴 Escalonamento: approved response"),
        (TurnAction.BLOCK, "pt", "approved response"),
        (TurnAction.ABSTAIN, "es", "approved response"),
    ],
)
def test_render_result_exhaustively_maps_turn_actions_through_safe_sender(
    monkeypatch: pytest.MonkeyPatch,
    action: TurnAction,
    language: Language,
    expected: str,
) -> None:
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)

    rendered = asyncio.run(
        chainlit_app._render_result(_result(action), "never log this source", language)
    )

    assert rendered is True
    sender.assert_awaited_once_with(
        expected,
        session_id="session-123",
        trace_id="trace-123",
    )


def test_render_result_fails_closed_for_unknown_action_without_response_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = AsyncMock(return_value=True)
    logger = Mock()
    unknown = replace(_result(), action=cast(TurnAction, "future-action"))
    monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)
    monkeypatch.setattr(chainlit_app, "logger", logger)

    rendered = asyncio.run(chainlit_app._render_result(unknown, "private source", "pt"))

    assert rendered is True
    sender.assert_awaited_once_with(
        get_template("internal_error", "pt"),
        session_id="session-123",
        trace_id="trace-123",
    )
    logger.warning.assert_called_once_with(
        "UNKNOWN_ACTION",
        extra={"session_id": "session-123", "trace_id": "trace-123"},
    )
    assert "approved response" not in repr(sender.await_args_list)
    assert "future-action" not in repr(logger.mock_calls)
    assert "private source" not in repr(logger.mock_calls)


def test_render_result_attempts_one_safe_fallback_and_reports_original_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = AsyncMock(side_effect=[False, True])
    logger = Mock()
    monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)
    monkeypatch.setattr(chainlit_app, "logger", logger)

    rendered = asyncio.run(
        chainlit_app._render_result(_result(), "private source", "es")
    )

    assert rendered is False
    assert sender.await_args_list[0].args == ("approved response",)
    assert sender.await_args_list[1].args == (get_template("render_error", "es"),)
    logger.warning.assert_called_once_with(
        "RENDER_FAILED",
        extra={"session_id": "session-123", "trace_id": "trace-123"},
    )


def test_render_result_propagates_cancellation_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(chainlit_app._render_result(_result(), "private source", "es"))

    assert sender.await_count == 1


def test_render_pending_delegates_preserved_result_source_and_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    renderer = AsyncMock(return_value=True)
    pending = SimpleNamespace(
        kind="result",
        source_text="texto original",
        language="pt",
        result=_result(),
    )
    monkeypatch.setattr(chainlit_app, "_render_result", renderer)

    rendered = asyncio.run(chainlit_app._render_pending(pending))

    assert rendered is True
    renderer.assert_awaited_once_with(
        pending.result,
        pending.source_text,
        pending.language,
    )


def test_render_pending_fails_closed_for_invalid_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = AsyncMock(return_value=True)
    logger = Mock()
    pending = SimpleNamespace(
        kind="result",
        source_text="private source",
        language="pt",
        result=None,
    )
    monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)
    monkeypatch.setattr(chainlit_app, "logger", logger)

    rendered = asyncio.run(chainlit_app._render_pending(pending))

    assert rendered is False
    sender.assert_awaited_once_with(
        get_template("internal_error", "pt"),
        session_id=None,
        trace_id=None,
    )
    logger.warning.assert_called_once_with("RENDER_FAILED")
    assert "private source" not in repr(logger.mock_calls)


def test_render_pending_internal_error_uses_safe_sender_without_raw_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = AsyncMock(return_value=True)
    pending = SimpleNamespace(
        kind="internal_error",
        source_text="private source",
        language="es",
        result=None,
    )
    monkeypatch.setattr(chainlit_app, "_send_ui_message", sender)

    rendered = asyncio.run(chainlit_app._render_pending(pending))

    assert rendered is True
    sender.assert_awaited_once_with(
        get_template("internal_error", "es"),
        session_id=None,
        trace_id=None,
    )
    assert "private source" not in repr(sender.await_args_list)
