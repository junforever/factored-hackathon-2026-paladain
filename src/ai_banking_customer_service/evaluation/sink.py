"""In-memory audit recording for one isolated evaluation case."""

import re
from copy import deepcopy
from threading import Lock

from ai_banking_customer_service.governance.jev.sanitization import sanitize_message
from ai_banking_customer_service.observability.contract import validate_event

_ENVELOPE_FIELDS = (
    "trace_id",
    "event_id",
    "parent_event_id",
    "timestamp",
    "component",
    "event_type",
    "customer_id",
    "session_id",
    "outcome",
    "latency_ms",
    "tokens",
    "cost_usd",
    "payload",
)
_TOOL_PAYLOAD_FIELDS = (
    "tool_name",
    "tool_use_id",
    "args",
    "result_status",
    "result_summary",
    "verified",
    "correlation",
    "orphaned",
)
_INTERNAL_PATH_KEYS = frozenset(
    {
        "state_dir",
        "state_path",
        "db_path",
        "card_db_path",
        "escalation_db_path",
    }
)
_WINDOWS_PATH = re.compile(r"(?i)\b[a-z]:[\\/][^\"'\r\n,;|]+")
_POSIX_PATH = re.compile(r"(?<![\w:])/(?:[^/\"'\r\n,;|]+/)*[^\"'\r\n,;|]+")
_SENSITIVE_KEYS = frozenset(
    {
        "accesstoken",
        "apikey",
        "authorization",
        "cardnumber",
        "chavedeapi",
        "clientsecret",
        "contraseña",
        "credential",
        "credentials",
        "credencial",
        "cvv",
        "cvc",
        "password",
        "pan",
        "pin",
        "privatekey",
        "refreshtoken",
        "secret",
        "securitycode",
        "segredo",
        "senha",
        "token",
    }
)
_KEY_SEPARATOR = re.compile(r"[\s_-]+")


class RecordingAuditSink:
    """Record safe audit snapshots and expose canonical filtering helpers."""

    def __init__(self) -> None:
        self._events: list[dict] = []
        self._lock = Lock()

    def emit(self, event: dict) -> None:
        """Validate and record a defensive, path-scrubbed event copy."""
        snapshot = deepcopy(event)
        validate_event(snapshot)
        filtered = _filter_event(snapshot)
        with self._lock:
            self._events.append(filtered)

    def get_events(self) -> list[dict]:
        """Return a defensive snapshot of all events in emission order."""
        with self._lock:
            return deepcopy(self._events)

    def get_events_by_type(self, event_type: str) -> list[dict]:
        """Return events whose canonical envelope type matches exactly."""
        return [
            event
            for event in self.get_events()
            if event.get("event_type") == event_type
        ]

    def get_tool_calls(self) -> list[dict]:
        """Return tool calls with a valid canonical ``tool_call.payload``."""
        return [
            event
            for event in self.get_events_by_type("tool_call")
            if _valid_tool_call_payload(event.get("payload"))
        ]

    def get_tool_calls_by_name(self, tool_name: str) -> list[dict]:
        """Filter valid tool calls by canonical payload tool name."""
        return [
            event
            for event in self.get_tool_calls()
            if event["payload"]["tool_name"] == tool_name
        ]


def _filter_event(event: dict) -> dict:
    filtered = {
        field: _sanitize_value(event[field])
        for field in _ENVELOPE_FIELDS
        if field in event
    }
    payload = filtered.get("payload")
    if event.get("event_type") == "tool_call" and isinstance(payload, dict):
        filtered["payload"] = {
            field: payload[field] for field in _TOOL_PAYLOAD_FIELDS if field in payload
        }
    return filtered


def _sanitize_value(value: object) -> object:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if isinstance(key, str) and key.casefold() in _INTERNAL_PATH_KEYS:
                continue
            if isinstance(key, str) and _sensitive_key(key):
                sanitized[key] = "[REDACTED_SECRET]"
            else:
                sanitized[key] = _sanitize_value(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_value(item) for item in value)
    if isinstance(value, str):
        value = sanitize_message(value)
        value = _WINDOWS_PATH.sub("[REDACTED_INTERNAL_PATH]", value)
        return _POSIX_PATH.sub("[REDACTED_INTERNAL_PATH]", value)
    return value


def _sensitive_key(key: str) -> bool:
    return _KEY_SEPARATOR.sub("", key.casefold()) in _SENSITIVE_KEYS


def _valid_tool_call_payload(payload: object) -> bool:
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("tool_name"), str)
        and bool(payload["tool_name"].strip())
        and isinstance(payload.get("tool_use_id"), str)
        and isinstance(payload.get("args"), dict)
        and payload.get("result_status") in {"success", "error", "blocked"}
        and isinstance(payload.get("result_summary"), str)
        and isinstance(payload.get("verified"), bool)
    )
