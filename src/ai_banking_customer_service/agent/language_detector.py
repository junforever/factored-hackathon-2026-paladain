"""Deterministic Spanish and Portuguese language detection."""

import re
import unicodedata
from typing import Literal

_PORTUGUESE_TOKENS = frozenset(
    {
        "nao",
        "voce",
        "voces",
        "obrigado",
        "obrigada",
        "desculpe",
        "cartao",
        "cobranca",
    }
)
_PORTUGUESE_PHRASES = frozenset({("bloquear", "meu"), ("bloquear", "minha")})


def detect_language(text: str) -> Literal["es", "pt"]:
    """Return Portuguese when an unambiguous lexical indicator is present."""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    tokens = re.findall(r"\w+", normalized)
    if _PORTUGUESE_TOKENS.intersection(tokens) or any(
        pair in _PORTUGUESE_PHRASES for pair in zip(tokens, tokens[1:])
    ):
        return "pt"
    return "es"
