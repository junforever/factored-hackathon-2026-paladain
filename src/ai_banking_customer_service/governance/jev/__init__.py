"""Public API for the typed Jev transport boundary."""

from .exceptions import (
    JevAuthError,
    JevConfigError,
    JevError,
    JevRateLimitError,
    JevUnavailableError,
    JevValidationError,
)
from .schemas import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    JevResponse,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
    Usage,
)


class JevClient:
    """Typed Jev transport adapter."""


__all__ = [
    "Answer",
    "ChoiceAnswer",
    "ChoiceQuestion",
    "JevAuthError",
    "JevClient",
    "JevConfigError",
    "JevError",
    "JevRateLimitError",
    "JevResponse",
    "JevUnavailableError",
    "JevValidationError",
    "NoulAnswer",
    "NoulQuestion",
    "ScoreAnswer",
    "ScoreQuestion",
    "Usage",
]
