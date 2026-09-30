"""Public API for the typed Jev transport boundary."""

from .exceptions import (
    JevAuthError,
    JevConfigError,
    JevError,
    JevRateLimitError,
    JevUnavailableError,
    JevValidationError,
)
from .schemas import ChoiceQuestion, NoulQuestion, ScoreQuestion


class JevClient:
    """Typed Jev transport adapter."""


class JevResponse:
    """Typed Jev response contract."""


__all__ = [
    "ChoiceQuestion",
    "JevAuthError",
    "JevClient",
    "JevConfigError",
    "JevError",
    "JevRateLimitError",
    "JevResponse",
    "JevUnavailableError",
    "JevValidationError",
    "NoulQuestion",
    "ScoreQuestion",
]
