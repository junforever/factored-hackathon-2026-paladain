"""Audit event sinks."""

import json
from pathlib import Path
from typing import Protocol

from ai_banking_customer_service.observability.contract import validate_event


class AuditSink(Protocol):
    """Destination for validated audit events."""

    def emit(self, event: dict) -> None: ...


class JsonlAuditSink:
    """Append validated audit events to a JSON Lines file."""

    def __init__(self, output_path: Path):
        self._output_path = output_path

    def emit(self, event: dict) -> None:
        """Validate and append one event as a single JSON line."""
        validate_event(event)
        line = json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n"
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._output_path.open("a", encoding="utf-8") as output_file:
            output_file.write(line)
