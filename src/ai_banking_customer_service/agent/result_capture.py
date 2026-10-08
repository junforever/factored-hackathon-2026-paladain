"""Per-turn capture of normalized Strands tool results."""

import json
from copy import deepcopy
from dataclasses import dataclass
from threading import Lock

from strands.hooks import (
    AfterToolCallEvent,
    BeforeToolCallEvent,
    HookOrder,
    HookProvider,
    HookRegistry,
)

from ai_banking_customer_service.governance.jev.sanitization import sanitize_message

MISSING_MERCHANT_CANCEL_REASON = "missing_merchant:clarification"
MISSING_MERCHANT_STATE_KEY = "missing_merchant_verified"
_ACTION_TOOLS = frozenset({"block_card", "escalate_case"})
_AUTHORIZATION_EVIDENCE = frozenset(
    {
        ("allowed", "authorized", True),
        ("denied", "not_authenticated", False),
        ("denied", "product_not_authorized", False),
        ("unavailable", "authorization_unavailable", False),
        ("unavailable", "invalid_authorization_result", False),
        ("not_evaluated", None, False),
    }
)


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
    authorization_result: str
    authorization_reason_code: str | None
    authorization_verified: bool
    missing_merchant_blocked: bool


class ResultCaptureHooks(HookProvider):
    """Capture tool attempts and terminal results for one agent turn."""

    def __init__(self) -> None:
        self._attempts: list[_ToolAttempt] = []
        self._attempt_object_ids: list[int] = []
        self._results: list[NormalizedToolResult] = []
        self._matched_attempts: set[int] = set()
        self._lock = Lock()

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(
            BeforeToolCallEvent,
            self.before_tool_call,
            order=HookOrder.SDK_LAST,
        )
        registry.add_callback(AfterToolCallEvent, self.after_tool_call)

    def before_tool_call(self, event: BeforeToolCallEvent) -> None:
        tool_use_id, tool_name, tool_args = _normalize_tool_use(event.tool_use)
        blocked = _is_governance_block(event, tool_use_id)
        authorization_result, authorization_reason, authorized = (
            _authorization_evidence(event, tool_use_id)
        )
        with self._lock:
            self._sync_missing_merchant_state(event.invocation_state)
            if (
                not event.cancel_tool
                and tool_name in _ACTION_TOOLS
                and authorized
                and _has_verified_missing_merchant(self._attempts, self._results)
            ):
                event.cancel_tool = MISSING_MERCHANT_CANCEL_REASON
            attempt = _ToolAttempt(
                tool_use_id,
                tool_name,
                tool_args,
                blocked,
                authorization_result,
                authorization_reason,
                authorized,
                _is_missing_merchant_block(event, tool_use_id, tool_name),
            )
            self._attempts.append(attempt)
            self._attempt_object_ids.append(id(event.tool_use))

    def after_tool_call(self, event: AfterToolCallEvent) -> None:
        tool_use_id, tool_name, tool_args = _normalize_tool_use(event.tool_use)
        with self._lock:
            attempt = self._match_attempt(
                id(event.tool_use), tool_use_id, tool_name, tool_args
            )
            result = NormalizedToolResult(
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
                    attempt.blocked_before_execution if attempt is not None else False
                ),
                retry_requested=event.retry is True,
                authorization_verified=(
                    attempt.authorization_verified if attempt is not None else False
                ),
            )
            self._results.append(result)
            self._sync_missing_merchant_state(event.invocation_state)

    def snapshot_attempts(self) -> tuple[_ToolAttempt, ...]:
        """Return an isolated point-in-time copy of captured attempts."""
        with self._lock:
            return deepcopy(tuple(self._attempts))

    def snapshot_results(self) -> tuple[NormalizedToolResult, ...]:
        """Return an isolated point-in-time copy of normalized results."""
        with self._lock:
            return deepcopy(tuple(self._results))

    def _sync_missing_merchant_state(self, state: dict) -> None:
        state.pop(MISSING_MERCHANT_STATE_KEY, None)

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


def _is_missing_merchant_block(
    event: BeforeToolCallEvent,
    tool_use_id: str,
    tool_name: str,
) -> bool:
    if (
        tool_name not in _ACTION_TOOLS
        or event.cancel_tool != MISSING_MERCHANT_CANCEL_REASON
    ):
        return False
    governance = event.invocation_state.get("tool_governance")
    evidence = governance.get(tool_use_id) if isinstance(governance, dict) else None
    return (
        isinstance(evidence, dict)
        and evidence.get("action") == "allow"
        and evidence.get("authorization_verified") is True
    )


def _has_verified_missing_merchant(
    attempts: list[_ToolAttempt],
    results: list[NormalizedToolResult],
) -> bool:
    for result in results:
        matching_attempts = [
            attempt for attempt in attempts if attempt.tool_use_id == result.tool_use_id
        ]
        matching_results = [
            item for item in results if item.tool_use_id == result.tool_use_id
        ]
        if (
            len(matching_attempts) == 1
            and len(matching_results) == 1
            and matching_attempts[0].tool_name == result.tool_name
            and matching_attempts[0].tool_args == result.tool_args
            and _missing_merchant_state(result) == "verified_missing"
        ):
            return True
    return False


def _missing_merchant_state(result: object) -> str:
    if not isinstance(result, NormalizedToolResult) or not (
        result.tool_name == "get_recent_transactions"
        and result.status == "success"
        and result.exception is None
        and result.cancel_message is None
        and result.blocked_before_execution is False
        and result.retry_requested is False
        and result.authorization_verified is True
        and isinstance(result.content, dict)
        and "error" not in result.content
    ):
        return "unknown"
    transactions = result.content.get("transactions")
    if not (
        isinstance(transactions, list)
        and transactions
        and all(
            isinstance(transaction, dict) and "merchant_name" in transaction
            for transaction in transactions
        )
    ):
        return "unknown"
    if any(transaction["merchant_name"] is None for transaction in transactions):
        return "verified_missing"
    return "verified_present"


def _authorization_evidence(
    event: BeforeToolCallEvent,
    tool_use_id: str,
) -> tuple[str, str | None, bool]:
    fallback = ("not_evaluated", None, False)
    if not tool_use_id:
        return fallback
    governance = event.invocation_state.get("tool_governance")
    if not isinstance(governance, dict):
        return fallback
    evidence = governance.get(tool_use_id)
    if not isinstance(evidence, dict):
        return fallback
    authorization = (
        evidence.get("authorization_result"),
        evidence.get("authorization_reason_code"),
        evidence.get("authorization_verified"),
    )
    if type(authorization[2]) is not bool:
        return fallback
    return authorization if authorization in _AUTHORIZATION_EVIDENCE else fallback


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
