"""Validation for audit event envelopes and runtime evidence blocks."""

import json
from math import isfinite

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
AUTHORIZATION_RESULTS = frozenset({"allowed", "denied", "unavailable", "not_evaluated"})
AUTHORIZATION_REASON_CODES = frozenset(
    {
        "authorized",
        "not_authenticated",
        "product_not_authorized",
        "authorization_unavailable",
        "invalid_authorization_result",
    }
)
SENSITIVE_TOOL_NAMES = frozenset(
    {
        "get_dispute_context",
        "get_recent_transactions",
        "block_card",
        "escalate_case",
    }
)

# fmt: off
GOVERNANCE_ACTIONS = frozenset({"allow", "block"})
GOVERNANCE_EVIDENCE_REASON_CODES = frozenset({
    "invalid_tool_name", "invalid_tool_input", "invalid_complaint_id", "invalid_invocation_state",  # noqa: E501
    "missing_merchant:clarification", "TOOL_GATING_VALIDATION_ERROR", "JEV_ERROR",
    "TOOL_GATING_DETERMINISTIC_BLOCK", "INVALID_METADATA", "INVALID_SIGNAL",
    "TOOL_GATING_ALLOW", "TOOL_GATING_BLOCK_LOW_INTENT_MATCH",
})
MISSING_DATA_STATES = frozenset({"verified_missing", "verified_present", "unknown", "invalid"})  # noqa: E501
EXECUTION_STATES = frozenset({"success", "failure", "blocked", "unknown", "invalid"})
VERIFICATION_OUTCOMES = frozenset({"verified", "unverified", "not_applicable", "invalid"})  # noqa: E501
EVIDENCE_REQUIRED_KEYS = frozenset({"ordinal", "authorization", "missing_data", "governance", "execution", "verification"})  # noqa: E501
EVIDENCE_OPTIONAL_KEYS = frozenset({"truncated", "invalid"})
_MAX_CODE_POINTS = 64
_MAX_SERIALIZED_BYTES = 8192

_EVIDENCE_SUBSCHEMAS = {
    "authorization": ({"state", "reason_code", "verified"}, {"state": AUTHORIZATION_RESULTS | {"invalid"}, "reason_code": AUTHORIZATION_REASON_CODES}, {"reason_code"}, {"verified"}),  # noqa: E501
    "missing_data": ({"state", "detected"}, {"state": MISSING_DATA_STATES}, set(), {"detected"}),  # noqa: E501
    "governance": ({"stage", "action", "reason_code"}, {"stage": {"tool_gating"}, "action": GOVERNANCE_ACTIONS, "reason_code": GOVERNANCE_EVIDENCE_REASON_CODES}, {"reason_code"}, set()),  # noqa: E501
    "execution": ({"state"}, {"state": EXECUTION_STATES}, set(), set()),
    "verification": ({"outcome", "verified"}, {"outcome": VERIFICATION_OUTCOMES}, set(), {"verified"}),  # noqa: E501
}
# fmt: on

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
    if cost_usd is not None and (
        not isinstance(cost_usd, float) or not isfinite(cost_usd) or cost_usd < 0
    ):
        raise ValueError("cost_usd must be a non-negative float or None")

    payload = event.get("payload")
    if payload is not None and not isinstance(payload, dict):
        raise ValueError("payload must be a dict or None")
    if (
        event["event_type"] == "tool_call"
        and isinstance(payload, dict)
        and payload.get("tool_name") in SENSITIVE_TOOL_NAMES
        and type(payload.get("authorization_verified")) is not bool
    ):
        raise ValueError("authorization_verified must be a bool for sensitive tools")
    if (
        event["event_type"] == "tool_call"
        and isinstance(payload, dict)
        and "evidence" in payload
    ):
        validate_evidence(payload["evidence"])


def validate_evidence(evidence: dict) -> None:
    if not isinstance(evidence, dict):
        raise ValueError("evidence_invalid:not_dict")
    keys = set(evidence.keys())
    if not EVIDENCE_REQUIRED_KEYS <= keys:
        raise ValueError("evidence_invalid:missing_required_keys")
    if keys - (EVIDENCE_REQUIRED_KEYS | EVIDENCE_OPTIONAL_KEYS):
        raise ValueError("evidence_invalid:extra_keys")
    _validate_size(evidence)

    ordinal = evidence["ordinal"]
    if type(ordinal) is not int or ordinal < 0:
        raise ValueError("evidence_invalid:ordinal")

    for name, (shape, codes, nullable, bools) in _EVIDENCE_SUBSCHEMAS.items():
        _validate_subdict(evidence[name], name, shape, codes, nullable, bools)

    for marker in EVIDENCE_OPTIONAL_KEYS:
        if marker in evidence and type(evidence[marker]) is not bool:
            raise ValueError(f"evidence_invalid:{marker}.type")
        if evidence.get(marker) is False:
            raise ValueError(f"evidence_invalid:{marker}.value")

    _validate_impossibilities(evidence)


def _validate_subdict(value, name, shape, codes, nullable, bools):
    if not isinstance(value, dict) or set(value) != shape:
        raise ValueError(f"evidence_invalid:{name}")
    for field, allowlist in codes.items():
        field_value = value[field]
        if field in nullable and field_value is None:
            continue
        path = f"{name}.{field}"
        if not isinstance(field_value, str):
            raise ValueError(f"evidence_invalid:{path}")
        if len(field_value) > _MAX_CODE_POINTS:
            raise ValueError(f"evidence_invalid:{path}.length")
        if field_value not in allowlist:
            raise ValueError(f"evidence_invalid:{path}")
    for field in bools:
        if type(value[field]) is not bool:
            raise ValueError(f"evidence_invalid:{name}.{field}")


def _validate_impossibilities(evidence):
    auth = evidence["authorization"]
    auth_rules = {
        "allowed": ("authorized", True),
        "denied": (("not_authenticated", "product_not_authorized"), False),
        "unavailable": (
            ("authorization_unavailable", "invalid_authorization_result"),
            False,
        ),
    }
    if auth["state"] in auth_rules:
        reasons, verified = auth_rules[auth["state"]]
        if auth["reason_code"] not in reasons or auth["verified"] is not verified:
            raise ValueError(
                f"evidence_invalid:authorization.{auth['state']}_inconsistent"
            )
    if auth["state"] == "not_evaluated" and (
        auth["reason_code"] is not None or auth["verified"] is not False
    ):
        raise ValueError("evidence_invalid:authorization.not_evaluated_inconsistent")

    checks = [
        (
            "missing_data",
            "state",
            "detected",
            (
                ("verified_missing", True),
                ("verified_present", False),
                ("unknown", False),
            ),
        ),
        (
            "verification",
            "outcome",
            "verified",
            (("verified", True), ("unverified", False), ("not_applicable", False)),
        ),
    ]
    for name, key, bool_key, rules in checks:
        section = evidence[name]
        for value, expected in rules:
            if section[key] == value and section[bool_key] is not expected:
                raise ValueError(f"evidence_invalid:{name}.{value}_inconsistent")

    has_invalid = any(
        evidence[n][k] == "invalid"
        for n, k in (
            ("authorization", "state"),
            ("missing_data", "state"),
            ("execution", "state"),
            ("verification", "outcome"),
        )
    )
    if has_invalid and evidence.get("invalid") is not True:
        raise ValueError("evidence_invalid:invalid_marker_missing")


def _validate_size(evidence):
    try:
        serialized = json.dumps(
            evidence,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        raise ValueError("evidence_invalid:serialization")
    if len(serialized.encode("utf-8")) > _MAX_SERIALIZED_BYTES:
        raise ValueError("evidence_invalid:oversized")
