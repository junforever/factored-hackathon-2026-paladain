import json
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from ai_banking_customer_service.observability import sink as sink_module
from ai_banking_customer_service.observability.sink import AuditSink, JsonlAuditSink


def _valid_event(event_id: str = "event-1") -> dict:
    return {
        "trace_id": "trace-1",
        "event_id": event_id,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "component": "governance",
        "event_type": "governance",
        "customer_id": "********1234",
        "session_id": "session-1",
        "outcome": "success",
        "latency_ms": 10,
        "tokens": None,
        "cost_usd": None,
        "payload": {"reason": "revisión completada"},
    }


def test_audit_sink_is_a_protocol() -> None:
    assert AuditSink._is_protocol is True


def test_jsonl_audit_sink_writes_one_json_line_without_ascii_escaping(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit.jsonl"

    JsonlAuditSink(output_path).emit(_valid_event())

    content = output_path.read_text(encoding="utf-8")
    assert content.endswith("\n")
    assert "revisión completada" in content
    assert json.loads(content) == _valid_event()


def test_jsonl_audit_sink_creates_parent_directory(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "audit" / "audit.jsonl"

    JsonlAuditSink(output_path).emit(_valid_event())

    assert output_path.is_file()


def test_jsonl_audit_sink_validates_before_serializing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dumps = Mock()
    monkeypatch.setattr(sink_module.json, "dumps", dumps)
    event = _valid_event()
    del event["trace_id"]

    with pytest.raises(ValueError):
        JsonlAuditSink(tmp_path / "audit.jsonl").emit(event)

    dumps.assert_not_called()


def test_jsonl_audit_sink_rejects_nan_before_creating_directory(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "missing" / "audit.jsonl"
    event = _valid_event()
    event["payload"] = {"score": float("nan")}

    with pytest.raises(ValueError):
        JsonlAuditSink(output_path).emit(event)

    assert not output_path.parent.exists()


def test_jsonl_audit_sink_rejects_non_serializable_object(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "missing" / "audit.jsonl"
    event = _valid_event()
    event["payload"] = {"value": object()}

    with pytest.raises(TypeError):
        JsonlAuditSink(output_path).emit(event)

    assert not output_path.parent.exists()


def test_jsonl_audit_sink_appends_multiple_events_as_separate_lines(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "audit.jsonl"
    sink = JsonlAuditSink(output_path)

    sink.emit(_valid_event("event-1"))
    sink.emit(_valid_event("event-2"))

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["event_id"] for line in lines] == [
        "event-1",
        "event-2",
    ]


def test_jsonl_audit_sink_uses_one_append_write_per_event(tmp_path: Path) -> None:
    output_path = tmp_path / "audit.jsonl"
    opened_file = mock_open()

    with patch.object(Path, "open", opened_file):
        JsonlAuditSink(output_path).emit(_valid_event())

    opened_file.assert_called_once_with("a", encoding="utf-8")
    opened_file().write.assert_called_once()
