"""Strict parser for model orchestration signals."""

import json

_SIGNAL_FIELDS = {
    "abstention": frozenset({"orchestration_signal", "reason"}),
    "clarification": frozenset({"orchestration_signal", "question"}),
}


def parse_orchestration_signal(text: str) -> dict[str, str] | None:
    """Parse a complete, exact orchestration signal or return ``None``."""
    candidate = text.lstrip()
    try:
        value, end = json.JSONDecoder().raw_decode(candidate)
    except json.JSONDecodeError:
        return None

    if candidate[end:].strip() or not isinstance(value, dict):
        return None

    signal = value.get("orchestration_signal")
    expected_fields = _SIGNAL_FIELDS.get(signal) if isinstance(signal, str) else None
    if expected_fields is None or set(value) != expected_fields:
        return None

    content_field = "reason" if signal == "abstention" else "question"
    content = value[content_field]
    if not isinstance(content, str) or not content.strip() or len(content) > 500:
        return None
    return value
