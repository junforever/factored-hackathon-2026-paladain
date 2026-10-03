from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from threading import Event

import pytest

from ai_banking_customer_service.agent import session_manager as session_manager_module
from ai_banking_customer_service.agent.session_manager import (
    SessionManager,
    SessionTurn,
    TurnPersistence,
)


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _persist_block(manager: SessionManager, session_id: str, text: str) -> None:
    with manager.turn(session_id) as turn:
        turn.persist(
            TurnPersistence(action="block", user_text=text, assistant_text=None)
        )


def test_persisted_respond_turn_is_available_to_the_next_turn() -> None:
    manager = SessionManager(clock=lambda: 10.0)

    with manager.turn("session-1") as turn:
        assert isinstance(turn, SessionTurn)
        assert turn.history == []
        turn.persist(
            TurnPersistence(
                action="respond",
                user_text="Unrecognized charge",
                assistant_text="I can help.",
            )
        )

    with manager.turn("session-1") as turn:
        assert turn.history == [
            {"role": "user", "content": [{"text": "Unrecognized charge"}]},
            {"role": "assistant", "content": [{"text": "I can help."}]},
        ]


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("max_messages_per_session", True),
        ("max_messages_per_session", 0),
        ("max_messages_per_session", -1),
        ("max_messages_per_session", 1.5),
        ("ttl_seconds", False),
        ("ttl_seconds", 0),
        ("ttl_seconds", -1),
        ("ttl_seconds", "10"),
        ("clock", None),
        ("clock", 10),
    ],
)
def test_constructor_rejects_invalid_configuration(keyword: str, value: object) -> None:
    with pytest.raises(ValueError):
        SessionManager(**{keyword: value})  # type: ignore[arg-type]


@pytest.mark.parametrize("session_id", [None, 1, "", "   "])
def test_session_operations_reject_invalid_ids_before_returning_a_context(
    session_id: object,
) -> None:
    manager = SessionManager()

    with pytest.raises(ValueError):
        manager.turn(session_id)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        manager.clear_session(session_id)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("action", "assistant_text", "expected_roles"),
    [
        ("respond", "Approved response", ["user", "assistant"]),
        ("abstain", "Safe abstention", ["user", "assistant"]),
        ("block", None, ["user"]),
        ("escalate", None, ["user"]),
    ],
)
def test_persistence_action_matrix(
    action: str,
    assistant_text: str | None,
    expected_roles: list[str],
) -> None:
    manager = SessionManager(clock=lambda: 1.0)

    with manager.turn("matrix") as turn:
        turn.persist(
            TurnPersistence(
                action=action,  # type: ignore[arg-type]
                user_text="Customer text",
                assistant_text=assistant_text,
            )
        )

    with manager.turn("matrix") as turn:
        assert [message["role"] for message in turn.history] == expected_roles


@pytest.mark.parametrize(
    "persistence",
    [
        TurnPersistence(
            action="invalid",  # type: ignore[arg-type]
            user_text="Customer text",
            assistant_text=None,
        ),
        TurnPersistence(action="respond", user_text="", assistant_text="Answer"),
        TurnPersistence(action="respond", user_text="   ", assistant_text="Answer"),
        TurnPersistence(
            action="respond",
            user_text=1,  # type: ignore[arg-type]
            assistant_text="Answer",
        ),
        TurnPersistence(action="respond", user_text="Question", assistant_text=None),
        TurnPersistence(action="respond", user_text="Question", assistant_text=" "),
        TurnPersistence(action="abstain", user_text="Question", assistant_text=None),
        TurnPersistence(action="block", user_text="Question", assistant_text="No"),
        TurnPersistence(action="escalate", user_text="Question", assistant_text="No"),
    ],
)
def test_invalid_persistence_request_is_atomic_and_consumes_the_one_attempt(
    persistence: TurnPersistence,
) -> None:
    manager = SessionManager(clock=lambda: 1.0)

    with manager.turn("invalid") as turn:
        with pytest.raises(ValueError):
            turn.persist(persistence)
        with pytest.raises(RuntimeError, match="at most once"):
            turn.persist(
                TurnPersistence(action="block", user_text="Valid", assistant_text=None)
            )

    with manager.turn("invalid") as turn:
        assert turn.history == []


def test_persist_requires_a_turn_persistence_instance() -> None:
    manager = SessionManager()

    with manager.turn("typed") as turn:
        with pytest.raises(TypeError):
            turn.persist(  # type: ignore[arg-type]
                {
                    "action": "block",
                    "user_text": "Customer text",
                    "assistant_text": None,
                }
            )


def test_successful_persistence_can_only_happen_once() -> None:
    manager = SessionManager(clock=lambda: 1.0)

    with manager.turn("once") as turn:
        turn.persist(
            TurnPersistence(action="block", user_text="First", assistant_text=None)
        )
        with pytest.raises(RuntimeError, match="at most once"):
            turn.persist(
                TurnPersistence(action="block", user_text="Second", assistant_text=None)
            )

    with manager.turn("once") as turn:
        assert turn.history == [{"role": "user", "content": [{"text": "First"}]}]


def test_turn_persistence_is_frozen() -> None:
    request = TurnPersistence(action="block", user_text="Text", assistant_text=None)

    with pytest.raises(FrozenInstanceError):
        request.user_text = "Changed"  # type: ignore[misc]


def test_memory_contains_only_exact_sanitized_message_schema() -> None:
    manager = SessionManager(clock=lambda: 1.0)

    with manager.turn("secrets") as turn:
        turn.persist(
            TurnPersistence(
                action="respond",
                user_text="card 4111 1111 1111 1111 cvv: 123",
                assistant_text="password: hunter2",
            )
        )

    with manager.turn("secrets") as turn:
        assert turn.history == [
            {
                "role": "user",
                "content": [{"text": "card [REDACTED_PAN] [REDACTED_SECRET]"}],
            },
            {
                "role": "assistant",
                "content": [{"text": "[REDACTED_SECRET]"}],
            },
        ]


def test_history_snapshots_are_deep_copies() -> None:
    manager = SessionManager(clock=lambda: 1.0)
    _persist_block(manager, "isolated", "Original")

    with manager.turn("isolated") as turn:
        first = turn.history
        second = turn.history
        first[0]["content"][0]["text"] = "Mutated"
        first.append({"role": "assistant", "content": [{"text": "Injected"}]})
        assert second == [{"role": "user", "content": [{"text": "Original"}]}]

    with manager.turn("isolated") as turn:
        assert turn.history == [{"role": "user", "content": [{"text": "Original"}]}]


def test_ttl_expires_at_boundary_and_unpersisted_turn_does_not_refresh_it() -> None:
    clock = FakeClock()
    manager = SessionManager(ttl_seconds=10, clock=clock)
    _persist_block(manager, "ttl", "Original")

    clock.now = 9
    with manager.turn("ttl") as turn:
        assert turn.history

    clock.now = 10
    with manager.turn("ttl") as turn:
        assert turn.history == []


def test_fifo_limit_counts_messages_instead_of_turns() -> None:
    manager = SessionManager(max_messages_per_session=3, clock=lambda: 1.0)

    turns = [("User 1", "Assistant 1"), ("User 2", "Assistant 2")]
    for user_text, assistant_text in turns:
        with manager.turn("fifo") as turn:
            turn.persist(
                TurnPersistence(
                    action="respond",
                    user_text=user_text,
                    assistant_text=assistant_text,
                )
            )

    with manager.turn("fifo") as turn:
        assert turn.history == [
            {"role": "assistant", "content": [{"text": "Assistant 1"}]},
            {"role": "user", "content": [{"text": "User 2"}]},
            {"role": "assistant", "content": [{"text": "Assistant 2"}]},
        ]


def test_sanitization_failure_preserves_history_and_last_activity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    manager = SessionManager(ttl_seconds=10, clock=clock)
    _persist_block(manager, "atomic", "Original")
    original_sanitizer = session_manager_module.sanitize_message

    def fail_for_assistant(text: str) -> str:
        if text == "Sanitizer failure":
            raise RuntimeError("sanitizer failed")
        return original_sanitizer(text)

    monkeypatch.setattr(session_manager_module, "sanitize_message", fail_for_assistant)
    clock.now = 5
    with manager.turn("atomic") as turn:
        with pytest.raises(RuntimeError, match="sanitizer failed"):
            turn.persist(
                TurnPersistence(
                    action="respond",
                    user_text="New user text",
                    assistant_text="Sanitizer failure",
                )
            )

    with manager.turn("atomic") as turn:
        assert turn.history == [{"role": "user", "content": [{"text": "Original"}]}]

    clock.now = 10
    with manager.turn("atomic") as turn:
        assert turn.history == []


def test_same_session_is_serialized_until_the_first_context_exits() -> None:
    manager = SessionManager(clock=lambda: 1.0)
    first_entered = Event()
    first_persisted = Event()
    allow_first_exit = Event()
    second_started = Event()
    second_entered = Event()

    def first_turn() -> None:
        with manager.turn("shared") as turn:
            first_entered.set()
            turn.persist(
                TurnPersistence(action="block", user_text="First", assistant_text=None)
            )
            first_persisted.set()
            assert allow_first_exit.wait(timeout=2)

    def second_turn() -> list[dict]:
        assert first_entered.wait(timeout=2)
        second_started.set()
        with manager.turn("shared") as turn:
            second_entered.set()
            return turn.history

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(first_turn)
        assert first_entered.wait(timeout=2)
        second_future = executor.submit(second_turn)
        assert second_started.wait(timeout=2)
        assert first_persisted.wait(timeout=2)
        assert not second_entered.wait(timeout=0.05)
        allow_first_exit.set()
        first_future.result(timeout=2)
        assert second_future.result(timeout=2) == [
            {"role": "user", "content": [{"text": "First"}]}
        ]


def test_distinct_sessions_can_overlap() -> None:
    manager = SessionManager(clock=lambda: 1.0)
    first_entered = Event()
    allow_first_exit = Event()

    def held_turn() -> None:
        with manager.turn("session-a"):
            first_entered.set()
            assert allow_first_exit.wait(timeout=2)

    def independent_turn() -> list[dict]:
        assert first_entered.wait(timeout=2)
        with manager.turn("session-b") as turn:
            return turn.history

    with ThreadPoolExecutor(max_workers=2) as executor:
        held_future = executor.submit(held_turn)
        assert first_entered.wait(timeout=2)
        independent_future = executor.submit(independent_turn)
        assert independent_future.result(timeout=2) == []
        allow_first_exit.set()
        held_future.result(timeout=2)


def test_lock_is_released_when_turn_body_raises() -> None:
    manager = SessionManager(clock=lambda: 1.0)

    with pytest.raises(LookupError, match="agent failed"):
        with manager.turn("failure"):
            raise LookupError("agent failed")

    with manager.turn("failure") as turn:
        assert turn.history == []


def test_clear_session_waits_for_active_turn_then_removes_state() -> None:
    manager = SessionManager(clock=lambda: 1.0)
    _persist_block(manager, "clear", "Old")
    active_turn_entered = Event()
    allow_active_turn_exit = Event()
    clear_started = Event()
    clear_finished = Event()

    def active_turn() -> None:
        with manager.turn("clear") as turn:
            assert turn.history
            active_turn_entered.set()
            assert allow_active_turn_exit.wait(timeout=2)

    def clear() -> None:
        clear_started.set()
        manager.clear_session("clear")
        clear_finished.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        active_future = executor.submit(active_turn)
        assert active_turn_entered.wait(timeout=2)
        clear_future = executor.submit(clear)
        assert clear_started.wait(timeout=2)
        assert not clear_finished.wait(timeout=0.05)
        allow_active_turn_exit.set()
        active_future.result(timeout=2)
        clear_future.result(timeout=2)

    with manager.turn("clear") as turn:
        assert turn.history == []
