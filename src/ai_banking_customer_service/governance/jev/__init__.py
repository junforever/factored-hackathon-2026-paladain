"""Public API for the typed Jev transport boundary."""

from .exceptions import (
    JevAuthError,
    JevConfigError,
    JevError,
    JevRateLimitError,
    JevUnavailableError,
    JevValidationError,
)


class JevClient:
    """Typed Jev transport adapter."""


class NoulQuestion:
    """Typed Noul question contract."""


class ChoiceQuestion:
    """Typed Choice question contract."""


class ScoreQuestion:
    """Typed Score question contract."""


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
