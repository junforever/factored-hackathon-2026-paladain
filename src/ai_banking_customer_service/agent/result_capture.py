"""Per-turn capture of normalized Strands tool results."""

import json
from copy import deepcopy
from dataclasses import dataclass
from threading import Lock

from strands.hooks import (
    AfterToolCallEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

from ai_banking_customer_service.governance.jev.sanitization import sanitize_message


@dataclass(frozen=True)
class NormalizedToolResult:
    """Stable subset of one Strands ``AfterToolCallEvent``."""

    tool_use_id: str
    tool_name: str
    tool_args: dict
    status: str
    content: object
    exception: str | None
    cancel_message: str | None
    duration_ms: int | None
    blocked_before_execution: bool
    retry_requested: bool
    authorization_verified: bool


@dataclass(frozen=True)
class _ToolAttempt:
    tool_use_id: str
    tool_name: str
    tool_args: dict
    blocked_before_execution: bool
    authorization_verified: bool


class ResultCaptureHooks(HookProvider):
    """Capture tool attempts and terminal results for one agent turn."""

    def __init__(self) -> None:
        self._attempts: list[_ToolAttempt] = []
        self._attempt_object_ids: list[int] = []
        self._results: list[NormalizedToolResult] = []
        self._matched_attempts: set[int] = set()
        self._lock = Lock()

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeToolCallEvent, self.before_tool_call)
        registry.add_callback(AfterToolCallEvent, self.after_tool_call)

    def before_tool_call(self, event: BeforeToolCallEvent) -> None:
        tool_use_id, tool_name, tool_args = _normalize_tool_use(event.tool_use)
        blocked = _is_governance_block(event, tool_use_id)
        authorized = _is_authorization_verified(event, tool_use_id)
        attempt = _ToolAttempt(tool_use_id, tool_name, tool_args, blocked, authorized)
        with self._lock:
            self._attempts.append(attempt)
            self._attempt_object_ids.append(id(event.tool_use))

    def after_tool_call(self, event: AfterToolCallEvent) -> None:
        tool_use_id, tool_name, tool_args = _normalize_tool_use(event.tool_use)
        with self._lock:
            attempt = self._match_attempt(
                id(event.tool_use), tool_use_id, tool_name, tool_args
            )
            self._results.append(
                NormalizedToolResult(
                    tool_use_id=tool_use_id,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    status=_status(event.result),
                    content=_content(event.result),
                    exception=_exception(event.exception),
                    cancel_message=(
                        event.cancel_message
                        if isinstance(event.cancel_message, str)
                        else None
                    ),
                    duration_ms=_duration_ms(event.duration),
                    blocked_before_execution=(
                        attempt.blocked_before_execution
                        if attempt is not None
                        else False
                    ),
                    retry_requested=event.retry is True,
                    authorization_verified=(
                        attempt.authorization_verified if attempt is not None else False
                    ),
                )
            )

    def snapshot_attempts(self) -> tuple[_ToolAttempt, ...]:
        """Return an isolated point-in-time copy of captured attempts."""
        with self._lock:
            return deepcopy(tuple(self._attempts))

    def snapshot_results(self) -> tuple[NormalizedToolResult, ...]:
        """Return an isolated point-in-time copy of normalized results."""
        with self._lock:
            return deepcopy(tuple(self._results))

    def _match_attempt(
        self,
        tool_use_object_id: int,
        tool_use_id: str,
        tool_name: str,
        tool_args: dict,
    ) -> _ToolAttempt | None:
        unmatched = (
            index
            for index in range(len(self._attempts))
            if index not in self._matched_attempts
        )
        index = next(
            (
                index
                for index in unmatched
                if self._attempt_object_ids[index] == tool_use_object_id
            ),
            None,
        )
        if index is None:
            index = next(
                (
                    index
                    for index, attempt in enumerate(self._attempts)
                    if index not in self._matched_attempts
                    and attempt.tool_use_id == tool_use_id
                    and attempt.tool_name == tool_name
                    and attempt.tool_args == tool_args
                ),
                None,
            )
        if index is None:
            return None
        self._matched_attempts.add(index)
        return self._attempts[index]


def _normalize_tool_use(tool_use: object) -> tuple[str, str, dict]:
    if not isinstance(tool_use, dict):
        return "", "unknown", {}
    tool_use_id = tool_use.get("toolUseId")
    tool_name = tool_use.get("name")
    tool_args = tool_use.get("input")
    return (
        tool_use_id if _is_nonempty_string(tool_use_id) else "",
        tool_name if _is_nonempty_string(tool_name) else "unknown",
        deepcopy(tool_args) if isinstance(tool_args, dict) else {},
    )


def _is_governance_block(event: BeforeToolCallEvent, tool_use_id: str) -> bool:
    if not tool_use_id or not event.cancel_tool:
        return False
    governance = event.invocation_state.get("tool_governance")
    if not isinstance(governance, dict):
        return False
    evidence = governance.get(tool_use_id)
    return isinstance(evidence, dict) and evidence.get("action") == "block"


def _is_authorization_verified(
    event: BeforeToolCallEvent,
    tool_use_id: str,
) -> bool:
    if not tool_use_id:
        return False
    governance = event.invocation_state.get("tool_governance")
    if not isinstance(governance, dict):
        return False
    evidence = governance.get(tool_use_id)
    return (
        isinstance(evidence, dict)
        and evidence.get("authorization_result") == "allowed"
        and evidence.get("authorization_reason_code") == "authorized"
        and evidence.get("authorization_verified") is True
    )


def _status(result: object) -> str:
    if isinstance(result, dict) and result.get("status") in {"success", "error"}:
        return result["status"]
    return "error"


def _content(result: object) -> object:
    if not isinstance(result, dict) or not isinstance(result.get("content"), list):
        return None
    blocks = result["content"]
    for block in blocks:
        if isinstance(block, dict) and "json" in block:
            return deepcopy(block["json"])
    for block in blocks:
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            text = block["text"]
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return text
            return parsed if isinstance(parsed, dict) else text
    return None


def _exception(exception: object) -> str | None:
    if not isinstance(exception, Exception):
        return None
    name = type(exception).__name__
    message = sanitize_message(str(exception))
    return f"{name}: {message}" if message else name


def _duration_ms(duration: object) -> int | None:
    if duration is None:
        return None
    if isinstance(duration, bool) or not isinstance(duration, int | float):
        return None
    return max(0, int(duration * 1000))


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
