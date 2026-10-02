import pytest

from ai_banking_customer_service.governance.jev.evaluations import _sanitize_message
from ai_banking_customer_service.governance.jev.sanitization import (
    detect_secrets,
    sanitize_json_structure,
    sanitize_message,
)


def test_sanitize_message_compatibility_alias() -> None:
    assert _sanitize_message is sanitize_message


def test_sanitize_message_redacts_pan() -> None:
    assert sanitize_message("Card 4111 1111 1111 1111") == "Card [REDACTED_PAN]"


def test_sanitize_message_redacts_cvv() -> None:
    assert sanitize_message("CVV 123") == "[REDACTED_SECRET]"


def test_sanitize_message_redacts_credential() -> None:
    assert sanitize_message("token=abc123") == "[REDACTED_SECRET]"


def test_detect_secrets_returns_types_in_deterministic_order() -> None:
    text = "token=abc123, CVV 123, card 4111 1111 1111 1111"

    assert detect_secrets(text) == ("PAN", "CVV", "CREDENTIAL")


def test_detect_secrets_returns_empty_tuple_without_secrets() -> None:
    assert detect_secrets("Necesito ayuda con mi tarjeta") == ()


def test_sanitize_json_structure_sanitizes_nested_dict_strings() -> None:
    value = {"outer": {"message": "Card 4111 1111 1111 1111"}}

    assert sanitize_json_structure(value) == {
        "outer": {"message": "Card [REDACTED_PAN]"}
    }


def test_sanitize_json_structure_sanitizes_nested_list_strings() -> None:
    value = ["CVV 123", ["token=abc123"]]

    assert sanitize_json_structure(value) == [
        "[REDACTED_SECRET]",
        ["[REDACTED_SECRET]"],
    ]


def test_sanitize_json_structure_sanitizes_nested_tuple_strings() -> None:
    value = {"outer": ("token=abc123",)}

    assert sanitize_json_structure(value) == {"outer": ("[REDACTED_SECRET]",)}


@pytest.mark.parametrize(
    "key",
    [
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
    ],
)
def test_sanitize_json_structure_redacts_sensitive_keys(key: str) -> None:
    assert sanitize_json_structure({key: "safe-looking"}) == {key: "[REDACTED]"}


def test_sanitize_json_structure_redacts_sensitive_keys_case_insensitively() -> None:
    assert sanitize_json_structure({"PaSsWoRd": "safe-looking"}) == {
        "PaSsWoRd": "[REDACTED]"
    }


def test_sanitize_json_structure_uses_exact_sensitive_key_matching() -> None:
    assert sanitize_json_structure({"token_count": 3}) == {"token_count": 3}


def test_sanitize_json_structure_rejects_non_string_dict_keys() -> None:
    with pytest.raises(ValueError, match="clave no-string en estructura JSON"):
        sanitize_json_structure({1: "value"})
