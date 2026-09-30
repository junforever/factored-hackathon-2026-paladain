def test_public_api_importable() -> None:
    from ai_banking_customer_service.governance.jev import (
        ChoiceQuestion,
        JevAuthError,
        JevClient,
        JevConfigError,
        JevError,
        JevRateLimitError,
        JevResponse,
        JevUnavailableError,
        JevValidationError,
        NoulQuestion,
        ScoreQuestion,
    )

    public_types = (
        JevClient,
        NoulQuestion,
        ChoiceQuestion,
        ScoreQuestion,
        JevResponse,
        JevError,
        JevConfigError,
        JevValidationError,
        JevAuthError,
        JevRateLimitError,
        JevUnavailableError,
    )
    assert all(isinstance(public_type, type) for public_type in public_types)
    assert all(
        issubclass(error_type, JevError)
        for error_type in (
            JevConfigError,
            JevValidationError,
            JevAuthError,
            JevRateLimitError,
            JevUnavailableError,
        )
    )
