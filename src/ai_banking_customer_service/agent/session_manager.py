"""In-memory conversation history with per-session turn locking."""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager as ContextManager
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Literal

from strands.types.content import Message

from ai_banking_customer_service.governance.jev.sanitization import sanitize_message


@dataclass(frozen=True)
class TurnPersistence:
    action: Literal["respond", "abstain", "block", "escalate"]
    user_text: str
    assistant_text: str | None


class SessionTurn:
    def __init__(
        self,
        history_snapshot: list[Message],
        persist_once: Callable[[TurnPersistence], None],
    ) -> None:
        self._history_snapshot = history_snapshot
        self._persist_once = persist_once
        self._persist_attempted = False

    @property
    def history(self) -> list[Message]:
        return deepcopy(self._history_snapshot)

    def persist(self, request: TurnPersistence) -> None:
        if self._persist_attempted:
            raise RuntimeError("persist may be called at most once per turn")
        self._persist_attempted = True
        self._persist_once(request)


class SessionManager:
    def __init__(
        self,
        max_messages_per_session: int = 50,
        ttl_seconds: int = 1800,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if not _is_positive_int(max_messages_per_session):
            raise ValueError("max_messages_per_session must be a positive integer")
        if not _is_positive_int(ttl_seconds):
            raise ValueError("ttl_seconds must be a positive integer")
        if not callable(clock):
            raise ValueError("clock must be callable")

        self._max_messages_per_session = max_messages_per_session
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._histories: dict[str, list[Message]] = {}
        self._last_activity: dict[str, float] = {}
        self._locks: dict[str, Lock] = {}
        self._locks_guard = Lock()

    def turn(self, session_id: str) -> ContextManager[SessionTurn]:
        _validate_session_id(session_id)
        return self._turn(session_id)

    @contextmanager
    def _turn(self, session_id: str) -> Iterator[SessionTurn]:
        session_lock = self._session_lock(session_id)
        session_lock.acquire()
        try:
            now = self._clock()
            last_activity = self._last_activity.get(session_id)
            if last_activity is not None and now - last_activity >= self._ttl_seconds:
                self._histories.pop(session_id, None)
                self._last_activity.pop(session_id, None)

            snapshot = deepcopy(self._histories.get(session_id, []))

            def persist_once(request: TurnPersistence) -> None:
                messages = _messages_for(request)
                candidate = deepcopy(self._histories.get(session_id, []))
                candidate.extend(messages)
                if len(candidate) > self._max_messages_per_session:
                    candidate = candidate[-self._max_messages_per_session :]
                persisted_at = self._clock()
                self._histories[session_id] = candidate
                self._last_activity[session_id] = persisted_at

            yield SessionTurn(snapshot, persist_once)
        finally:
            session_lock.release()

    def clear_session(self, session_id: str) -> None:
        _validate_session_id(session_id)
        with self._session_lock(session_id):
            self._histories.pop(session_id, None)
            self._last_activity.pop(session_id, None)

    def _session_lock(self, session_id: str) -> Lock:
        with self._locks_guard:
            return self._locks.setdefault(session_id, Lock())


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validate_session_id(session_id: object) -> None:
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id must be a non-empty string")


def _messages_for(request: TurnPersistence) -> list[Message]:
    if not isinstance(request, TurnPersistence):
        raise TypeError("request must be TurnPersistence")
    if request.action not in {"respond", "abstain", "block", "escalate"}:
        raise ValueError("invalid persistence action")
    if not isinstance(request.user_text, str) or not request.user_text.strip():
        raise ValueError("user_text must be a non-empty string")

    requires_assistant = request.action in {"respond", "abstain"}
    if requires_assistant:
        if (
            not isinstance(request.assistant_text, str)
            or not request.assistant_text.strip()
        ):
            raise ValueError("assistant_text is required for this action")
    elif request.assistant_text is not None:
        raise ValueError("assistant_text must be None for this action")

    messages: list[Message] = [
        {
            "role": "user",
            "content": [{"text": sanitize_message(request.user_text)}],
        }
    ]
    if requires_assistant:
        messages.append(
            {
                "role": "assistant",
                "content": [{"text": sanitize_message(request.assistant_text)}],
            }
        )
    return messages
