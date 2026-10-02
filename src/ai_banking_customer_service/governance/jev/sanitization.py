"""Deterministic sanitization for governance inputs and outputs."""

import re

_PAN_PATTERN = re.compile(r"\b\d(?:[ .-]?\d){12,18}\b")
_ASSIGN = r"(?:(?:es|is|é)\b|[:=])"
_CVV_PATTERN = re.compile(
    r"\b(?:cvv|cvc|security\s+code|c[oó]digo\s+de\s+seguridad|"
    r"c[oó]digo\s+de\s+seguran[cç]a)\b"
    r"\s*(?:" + _ASSIGN + r")?\s*\d{3,4}\b",
    re.IGNORECASE,
)
_CREDENTIAL_PATTERN = re.compile(
    r"\b(?:password|contrase[nñ]a|senha|pin|token|"
    r"api[\s_-]*key|chave\s+de\s+api|secret|segredo|credential|credencial)\b"
    r"\s*" + _ASSIGN + r"\s*\S+",
    re.IGNORECASE,
)

SECRET_TYPES = ("PAN", "CVV", "CREDENTIAL")
SENSITIVE_KEYS = frozenset(
    {
        "card_number",
        "cvv",
        "cvc",
        "password",
        "token",
        "secret",
        "credential",
        "pan",
        "security_code",
        "pin",
    }
)


def sanitize_message(message: str) -> str:
    """Redact prohibited secrets covered by the governance contract."""
    result = _PAN_PATTERN.sub("[REDACTED_PAN]", message)
    result = _CVV_PATTERN.sub("[REDACTED_SECRET]", result)
    return _CREDENTIAL_PATTERN.sub("[REDACTED_SECRET]", result)


def detect_secrets(text: str) -> tuple[str, ...]:
    """Return secret types found in the original text in deterministic order."""
    detected = []
    if _PAN_PATTERN.search(text):
        detected.append("PAN")
    if _CVV_PATTERN.search(text):
        detected.append("CVV")
    if _CREDENTIAL_PATTERN.search(text):
        detected.append("CREDENTIAL")
    return tuple(detected)


def sanitize_json_structure(value: object) -> object:
    """Recursively sanitize strings in JSON-compatible structures."""
    if isinstance(value, str):
        return sanitize_message(value)
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"clave no-string en estructura JSON: {type(key)}")
            result[key] = (
                "[REDACTED]"
                if key.lower() in SENSITIVE_KEYS
                else sanitize_json_structure(item)
            )
        return result
    if isinstance(value, tuple):
        return tuple(sanitize_json_structure(item) for item in value)
    if isinstance(value, list):
        return [sanitize_json_structure(item) for item in value]
    return value
