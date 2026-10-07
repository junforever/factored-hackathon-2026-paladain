import pytest

from ai_banking_customer_service.observability.contract import (
    AUTHORIZATION_REASON_CODES,
    AUTHORIZATION_RESULTS,
    EVIDENCE_OPTIONAL_KEYS,
    EVIDENCE_REQUIRED_KEYS,
    REQUIRED_ENVELOPE_FIELDS,
    SENSITIVE_TOOL_NAMES,
    VALID_COMPONENTS,
    VALID_EVENT_TYPES,
    VALID_OUTCOMES,
    validate_event,
    validate_evidence,
)


def _valid_event() -> dict:
    return {
        "trace_id": "trace-1",
        "event_id": "event-1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "component": "governance",
        "event_type": "governance",
        "customer_id": "********1234",
        "session_id": "session-1",
        "outcome": "success",
        "latency_ms": 10,
        "tokens": 20,
        "cost_usd": 0.01,
        "payload": {"decision": "allow"},
    }


def test_validate_event_accepts_valid_event() -> None:
    validate_event(_valid_event())


@pytest.mark.parametrize("field", sorted(REQUIRED_ENVELOPE_FIELDS))
def test_validate_event_rejects_missing_required_field(field: str) -> None:
    event = _valid_event()
    del event[field]

    with pytest.raises(ValueError):
        validate_event(event)


@pytest.mark.parametrize(
    "field", ["trace_id", "event_id", "timestamp", "customer_id", "session_id"]
)
@pytest.mark.parametrize("invalid_value", [None, "", 1])
def test_validate_event_rejects_invalid_string_fields(
    field: str, invalid_value: object
) -> None:
    event = _valid_event()
    event[field] = invalid_value

    with pytest.raises(ValueError):
        validate_event(event)


@pytest.mark.parametrize(
    ("field", "valid_values"),
    [
        ("component", VALID_COMPONENTS),
        ("event_type", VALID_EVENT_TYPES),
        ("outcome", VALID_OUTCOMES),
    ],
)
def test_validate_event_accepts_every_domain_value(
    field: str, valid_values: frozenset[str]
) -> None:
    for value in valid_values:
        event = _valid_event()
        event[field] = value
        validate_event(event)


@pytest.mark.parametrize("field", ["component", "event_type", "outcome"])
@pytest.mark.parametrize("invalid_value", [None, "", "unknown", 1])
def test_validate_event_rejects_values_outside_domains(
    field: str, invalid_value: object
) -> None:
    event = _valid_event()
    event[field] = invalid_value

    with pytest.raises(ValueError):
        validate_event(event)


@pytest.mark.parametrize("valid_value", [0, 10])
def test_validate_event_accepts_non_negative_integer_latency(valid_value: int) -> None:
    event = _valid_event()
    event["latency_ms"] = valid_value

    validate_event(event)


@pytest.mark.parametrize("invalid_value", [True, False, -1, 1.0, None])
def test_validate_event_rejects_invalid_latency(invalid_value: object) -> None:
    event = _valid_event()
    event["latency_ms"] = invalid_value

    with pytest.raises(ValueError):
        validate_event(event)


@pytest.mark.parametrize("valid_value", [None, 0, 10])
def test_validate_event_accepts_optional_non_negative_integer_tokens(
    valid_value: int | None,
) -> None:
    event = _valid_event()
    event["tokens"] = valid_value

    validate_event(event)


@pytest.mark.parametrize("invalid_value", [True, False, -1, 1.0, "1"])
def test_validate_event_rejects_invalid_tokens(invalid_value: object) -> None:
    event = _valid_event()
    event["tokens"] = invalid_value

    with pytest.raises(ValueError):
        validate_event(event)


@pytest.mark.parametrize("valid_value", [None, 0.0, 1.5])
def test_validate_event_accepts_optional_non_negative_float_cost(
    valid_value: float | None,
) -> None:
    event = _valid_event()
    event["cost_usd"] = valid_value

    validate_event(event)


@pytest.mark.parametrize(
    "invalid_value",
    [True, False, -0.1, 1, "1.0", float("nan"), float("inf"), float("-inf")],
)
def test_validate_event_rejects_invalid_cost(invalid_value: object) -> None:
    event = _valid_event()
    event["cost_usd"] = invalid_value

    with pytest.raises(ValueError):
        validate_event(event)


@pytest.mark.parametrize("valid_value", [None, {}, {"stage": "input_screening"}])
def test_validate_event_accepts_optional_dict_payload(valid_value: dict | None) -> None:
    event = _valid_event()
    event["payload"] = valid_value

    validate_event(event)


@pytest.mark.parametrize("invalid_value", [[], "payload", 1, True])
def test_validate_event_rejects_invalid_payload(invalid_value: object) -> None:
    event = _valid_event()
    event["payload"] = invalid_value

    with pytest.raises(ValueError):
        validate_event(event)


def test_validate_event_accepts_omitted_optional_fields() -> None:
    event = _valid_event()
    del event["tokens"]
    del event["cost_usd"]
    del event["payload"]

    validate_event(event)


def test_authorization_observability_domains_are_closed() -> None:
    assert AUTHORIZATION_RESULTS == frozenset(
        {"allowed", "denied", "unavailable", "not_evaluated"}
    )
    assert AUTHORIZATION_REASON_CODES == frozenset(
        {
            "authorized",
            "not_authenticated",
            "product_not_authorized",
            "authorization_unavailable",
            "invalid_authorization_result",
        }
    )
    assert SENSITIVE_TOOL_NAMES == frozenset(
        {
            "get_dispute_context",
            "get_recent_transactions",
            "block_card",
            "escalate_case",
        }
    )


@pytest.mark.parametrize("authorization_verified", [None, 0, 1, "true", []])
def test_sensitive_tool_event_requires_strict_authorization_boolean(
    authorization_verified: object,
) -> None:
    event = _valid_event()
    event.update(component="orchestrator", event_type="tool_call")
    event["payload"] = {
        "tool_name": "get_recent_transactions",
        "authorization_verified": authorization_verified,
    }

    with pytest.raises(ValueError, match="authorization_verified"):
        validate_event(event)


@pytest.mark.parametrize("tool_name", sorted(SENSITIVE_TOOL_NAMES))
def test_sensitive_tool_event_accepts_canonical_authorization_boolean(
    tool_name: str,
) -> None:
    event = _valid_event()
    event.update(component="orchestrator", event_type="tool_call")
    event["payload"] = {
        "tool_name": tool_name,
        "authorization_verified": False,
    }

    validate_event(event)


# fmt: off
def _evidence(a="allowed", r="authorized", v=True, m="verified_present", d=False, g="allow", gr="TOOL_GATING_ALLOW", e="success", o="verified", ov=True):  # noqa: E501
    return {
        "ordinal": 0,
        "authorization": {"state": a, "reason_code": r, "verified": v},
        "missing_data": {"state": m, "detected": d},
        "governance": {"stage": "tool_gating", "action": g, "reason_code": gr},
        "execution": {"state": e},
        "verification": {"outcome": o, "verified": ov},
    }


def _set(evidence, path, value):
    *head, tail = path.split(".")
    target = evidence
    for key in head:
        target = target[key]
    target[tail] = value
    return evidence
# fmt: on


@pytest.mark.parametrize(
    ("evidence",),
    [
        (_evidence(),),
        (_evidence(a="denied", r="not_authenticated", v=False),),
        (_evidence(a="unavailable", r="authorization_unavailable", v=False),),
        (_evidence(a="not_evaluated", r=None, v=False),),
        (_evidence(m="verified_missing", d=True),),
        (_evidence(m="unknown", d=False),),
        (_evidence(g="block", gr="invalid_tool_name"),),
        (_evidence(e="blocked"),),
        (_evidence(o="unverified", ov=False),),
        (_evidence(o="not_applicable", ov=False),),
    ],
)
def test_validate_evidence_accepts_canonical_dimensions(evidence: dict) -> None:
    validate_evidence(evidence)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("authorization.state", "bad"),
        ("authorization.reason_code", "bad"),
        ("governance.stage", "bad"),
        ("governance.action", "bad"),
        ("governance.reason_code", "bad"),
        ("execution.state", "bad"),
        ("verification.outcome", "bad"),
        ("missing_data.state", "bad"),
        ("authorization.verified", 0),
        ("authorization.verified", 1),
        ("authorization.verified", "true"),
        ("authorization.verified", None),
        ("missing_data.detected", 0),
        ("missing_data.detected", 1),
        ("missing_data.detected", "true"),
        ("missing_data.detected", None),
        ("verification.verified", 0),
        ("verification.verified", 1),
        ("verification.verified", "true"),
        ("verification.verified", None),
    ],
)
def test_validate_evidence_rejects_invalid_values(path: str, value: object) -> None:
    with pytest.raises(ValueError, match=path):
        validate_evidence(_set(_evidence(), path, value))


@pytest.mark.parametrize("key", sorted(EVIDENCE_REQUIRED_KEYS))
def test_validate_evidence_rejects_missing_key(key: str) -> None:
    evidence = _evidence()
    del evidence[key]
    with pytest.raises(ValueError, match="missing_required_keys"):
        validate_evidence(evidence)


def test_validate_evidence_rejects_extra_key() -> None:
    evidence = _evidence()
    evidence["extra"] = 1
    with pytest.raises(ValueError, match="extra_keys"):
        validate_evidence(evidence)


@pytest.mark.parametrize(
    ("evidence", "match"),
    [
        # fmt: off
        (_evidence(v=False), "allowed_inconsistent"),
        (_evidence(a="allowed", r="not_authenticated", v=True), "allowed_inconsistent"),
        (_evidence(a="denied", r="authorized", v=False), "denied_inconsistent"),
        (
            _evidence(a="unavailable", r="authorized", v=False),
            "unavailable_inconsistent",
        ),
        (
            _evidence(a="not_evaluated", r="authorized", v=False),
            "not_evaluated_inconsistent",
        ),
        (_evidence(a="not_evaluated", r=None, v=True), "not_evaluated_inconsistent"),
        (_evidence(m="verified_missing", d=False), "verified_missing_inconsistent"),
        (_evidence(m="verified_present", d=True), "verified_present_inconsistent"),
        (_evidence(m="unknown", d=True), "unknown_inconsistent"),
        (_evidence(o="verified", ov=False), "verified_inconsistent"),
        (_evidence(o="unverified", ov=True), "unverified_inconsistent"),
        (_evidence(o="not_applicable", ov=True), "not_applicable_inconsistent"),
        # fmt: on
    ],
)
def test_validate_evidence_rejects_impossible_combinations(
    evidence: dict, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        validate_evidence(evidence)


def test_validate_evidence_invalid_state_marker() -> None:
    evidence = _evidence()
    evidence["execution"] = {"state": "invalid"}
    with pytest.raises(ValueError, match="invalid_marker_missing"):
        validate_evidence(evidence)
    evidence["invalid"] = True
    validate_evidence(evidence)


@pytest.mark.parametrize("marker", sorted(EVIDENCE_OPTIONAL_KEYS))
def test_validate_evidence_optional_marker_only_true_allowed(marker: str) -> None:
    with pytest.raises(ValueError, match=marker):
        validate_evidence(_set(_evidence(), marker, False))
    validate_evidence(_set(_evidence(), marker, True))


def test_validate_evidence_rejects_code_longer_than_64_code_points() -> None:
    with pytest.raises(ValueError, match="length"):
        validate_evidence(_set(_evidence(), "governance.reason_code", "x" * 65))


def test_validate_evidence_rejects_oversized_serialized_block() -> None:
    evidence = _evidence()
    evidence["authorization"] = {
        "state": "invalid",
        "reason_code": "x" * 8200,
        "verified": False,
    }
    evidence["invalid"] = True
    with pytest.raises(ValueError, match="oversized"):
        validate_evidence(evidence)
