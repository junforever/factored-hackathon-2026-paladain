"""Validation for audit event envelopes."""

REQUIRED_ENVELOPE_FIELDS = frozenset(
    {
        "trace_id",
        "event_id",
        "timestamp",
        "component",
        "event_type",
        "customer_id",
        "session_id",
        "outcome",
        "latency_ms",
    }
)
VALID_COMPONENTS = frozenset({"governance", "orchestrator", "tool", "service"})
VALID_EVENT_TYPES = frozenset(
    {
        "input",
        "governance",
        "tool_call",
        "policy",
        "action",
        "escalation",
        "response",
    }
)
VALID_OUTCOMES = frozenset({"success", "blocked", "escalated", "failure", "abstained"})

_STRING_FIELDS = ("trace_id", "event_id", "timestamp", "customer_id", "session_id")
_DOMAIN_FIELDS = {
    "component": VALID_COMPONENTS,
    "event_type": VALID_EVENT_TYPES,
    "outcome": VALID_OUTCOMES,
}


def validate_event(event: dict) -> None:
    """Raise ``ValueError`` when an audit event envelope is invalid."""
    missing = REQUIRED_ENVELOPE_FIELDS - event.keys()
    if missing:
        raise ValueError(f"Missing required event fields: {sorted(missing)}")

    for field in _STRING_FIELDS:
        if not isinstance(event[field], str) or not event[field]:
            raise ValueError(f"{field} must be a non-empty string")

    for field, valid_values in _DOMAIN_FIELDS.items():
        if not isinstance(event[field], str) or event[field] not in valid_values:
            raise ValueError(f"Invalid {field}: {event[field]!r}")

    latency_ms = event["latency_ms"]
    if (
        not isinstance(latency_ms, int)
        or isinstance(latency_ms, bool)
        or latency_ms < 0
    ):
        raise ValueError("latency_ms must be a non-negative integer")

    tokens = event.get("tokens")
    if tokens is not None and (
        not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0
    ):
        raise ValueError("tokens must be a non-negative integer or None")

    cost_usd = event.get("cost_usd")
    if cost_usd is not None and (not isinstance(cost_usd, float) or cost_usd < 0):
        raise ValueError("cost_usd must be a non-negative float or None")

    payload = event.get("payload")
    if payload is not None and not isinstance(payload, dict):
        raise ValueError("payload must be a dict or None")
