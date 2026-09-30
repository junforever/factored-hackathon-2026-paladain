"""Public exceptions raised by the Jev transport boundary."""


class JevError(Exception):
    """Base exception for all public Jev adapter failures."""


class JevConfigError(JevError):
    """Raised when the Jev adapter configuration is invalid."""


class JevValidationError(JevError):
    """Raised when Jev input or output violates the transport contract."""


class JevAuthError(JevError):
    """Raised when Jev rejects authentication or authorization."""


class JevRateLimitError(JevError):
    """Raised when Jev rate-limits a request."""


class JevUnavailableError(JevError):
    """Raised when the Jev service cannot complete a request."""
