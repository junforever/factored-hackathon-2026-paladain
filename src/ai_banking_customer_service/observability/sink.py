"""Audit event sinks."""

import json
from pathlib import Path
from typing import Protocol

from ai_banking_customer_service.observability.contract import validate_event


class AuditSink(Protocol):
    """Destination for validated audit events."""

    def emit(self, event: dict) -> None: ...


class AuditPersistenceError(RuntimeError):
    """Report a failed primary audit write without exposing event data."""

    def __init__(
        self,
        primary_error: Exception,
        fallback_error: Exception | None = None,
    ) -> None:
        self.primary_error = primary_error
        self.fallback_error = fallback_error
        message = f"Primary audit persistence failed ({type(primary_error).__name__})"
        if fallback_error is not None:
            message += f"; diagnostic fallback failed ({type(fallback_error).__name__})"
        super().__init__(message)


class CompositeAuditSink:
    """Persist primarily and use a secondary sink only for diagnostics."""

    def __init__(self, primary_sink: AuditSink, fallback_sink: AuditSink) -> None:
        self._primary_sink = primary_sink
        self._fallback_sink = fallback_sink

    def emit(self, event: dict) -> None:
        """Emit once to primary, falling back once without claiming durability."""
        try:
            self._primary_sink.emit(event)
            return
        except Exception as primary_error:
            fallback_error = None
            try:
                self._fallback_sink.emit(event)
            except Exception as error:
                fallback_error = error
            raise AuditPersistenceError(
                primary_error,
                fallback_error,
            ) from primary_error


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
