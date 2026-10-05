import json
from copy import deepcopy

import pytest

from ai_banking_customer_service.evaluation.sink import RecordingAuditSink


def _event(event_type: str = "tool_call", payload: dict | None = None) -> dict:
    return {
        "trace_id": "trace-1",
        "event_id": "event-1",
        "parent_event_id": None,
        "timestamp": "2026-10-03T12:00:00+00:00",
        "component": "orchestrator",
        "event_type": event_type,
        "customer_id": "****EVAL",
        "session_id": "session-1",
        "outcome": "success",
        "latency_ms": 1,
        "tokens": None,
        "cost_usd": None,
        "payload": payload
        if payload is not None
        else {
            "tool_name": "block_card",
            "tool_use_id": "tool-1",
            "args": {
                "complaint_id": "CMP-EVAL",
                "confirmed_by_customer": True,
            },
            "result_status": "success",
            "result_summary": "success",
            "verified": True,
            "authorization_verified": True,
        },
    }


def test_recording_sink_keeps_defensive_copies_on_write_and_read() -> None:
    sink = RecordingAuditSink()
    original = _event()
    expected = deepcopy(original)
    expected["payload"].pop("authorization_verified")

    sink.emit(original)
    original["payload"]["args"]["complaint_id"] = "MUTATED"
    first_read = sink.get_events()
    first_read[0]["payload"]["args"]["complaint_id"] = "ALSO-MUTATED"

    assert sink.get_events() == [expected]


def test_tool_call_filters_use_only_the_canonical_payload() -> None:
    sink = RecordingAuditSink()
    canonical = _event()
    canonical["tool_name"] = "escalate_case"
    canonical["args"] = {"complaint_id": "WRONG-TOP-LEVEL"}
    action = _event("action")
    action["event_id"] = "event-action"
    malformed = _event(
        payload={
            "tool_name": "block_card",
            "args": {},
            "authorization_verified": False,
        }
    )
    malformed["event_id"] = "event-malformed"

    sink.emit(canonical)
    sink.emit(action)
    sink.emit(malformed)

    tool_calls = sink.get_tool_calls()

    assert len(tool_calls) == 1
    assert tool_calls[0]["payload"]["tool_name"] == "block_card"
    assert tool_calls[0]["payload"]["args"]["complaint_id"] == "CMP-EVAL"
    assert sink.get_tool_calls_by_name("block_card") == tool_calls
    assert sink.get_tool_calls_by_name("escalate_case") == []
    assert sink.get_events_by_type("action")[0]["event_id"] == "event-action"


def test_recorded_events_drop_internal_paths_and_noncanonical_tool_payload_fields() -> (
    None
):
    sink = RecordingAuditSink()
    internal_path = r"D:\private folder\case 1\card_service.sqlite3"
    posix_path = "/private folder/case 1/escalation_service.sqlite3"
    event = _event()
    event["db_path"] = internal_path
    event["payload"]["state_dir"] = internal_path
    event["payload"]["debug_detail"] = {"location": internal_path}
    event["payload"]["result_summary"] = (
        f"database failed at {internal_path}; fallback {posix_path}"
    )

    sink.emit(event)

    serialized = json.dumps(sink.get_events(), sort_keys=True)
    payload = sink.get_tool_calls()[0]["payload"]
    assert internal_path not in serialized
    assert posix_path not in serialized
    assert "card_service.sqlite3" not in serialized
    assert "escalation_service.sqlite3" not in serialized
    assert "case 1" not in serialized
    assert "db_path" not in serialized
    assert "state_dir" not in serialized
    assert set(payload) == {
        "tool_name",
        "tool_use_id",
        "args",
        "result_status",
        "result_summary",
        "verified",
    }


def test_recording_sink_redacts_direct_and_malformed_secrets_independently() -> None:
    sink = RecordingAuditSink()
    canonical = _event()
    canonical["payload"]["args"].update(
        {
            "pan": "4111-1111-1111-1111",
            "cvv": "123",
            "api_key": "top-secret-key",
        }
    )
    malformed = _event(
        payload={
            "tool_name": "block_card",
            "args": {"credential": "credential-value"},
            "result_summary": "password=direct-secret",
            "authorization_verified": False,
        }
    )
    malformed["event_id"] = "event-malformed-secret"

    sink.emit(canonical)
    sink.emit(malformed)

    serialized = json.dumps(sink.get_events(), sort_keys=True)
    tool_call = sink.get_tool_calls()[0]
    assert "4111-1111-1111-1111" not in serialized
    assert '"cvv": "123"' not in serialized
    assert "top-secret-key" not in serialized
    assert "credential-value" not in serialized
    assert "direct-secret" not in serialized
    assert tool_call["payload"]["tool_name"] == "block_card"
    assert tool_call["payload"]["args"]["complaint_id"] == "CMP-EVAL"
    assert tool_call["payload"]["result_status"] == "success"
    assert tool_call["payload"]["verified"] is True
    assert len(sink.get_events()) == 2


def test_emit_rejects_a_malformed_audit_envelope() -> None:
    sink = RecordingAuditSink()

    with pytest.raises(ValueError, match="event fields"):
        sink.emit({"event_type": "tool_call"})
