"""Typed client boundary for Jev requests."""

import json
import logging
from collections.abc import Mapping
from typing import Any

import typesafe_sdk
from pydantic import SecretStr, ValidationError

from ai_banking_customer_service.config import settings

from .exceptions import (
    JevAuthError,
    JevConfigError,
    JevRateLimitError,
    JevUnavailableError,
    JevValidationError,
)
from .schemas import ChoiceQuestion, JevResponse, Question


def _question_to_wire(question: Question) -> dict[str, Any]:
    wire = question.model_dump(exclude={"include_other"})
    if isinstance(question, ChoiceQuestion) and question.include_other:
        criteria = wire["criteria"]
        if "other" not in criteria:
            if len(criteria) >= 255:
                raise JevValidationError(
                    "include_other would exceed the 255-option limit"
                )
            criteria["other"] = "None of the above options fit."
    return wire


class JevClient:
    """Validate and prepare Jev requests behind a replaceable transport seam."""

    def __init__(
        self,
        api_key: SecretStr | None = None,
        model: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        resolved_api_key = api_key if api_key is not None else settings.typesafe_api_key
        if not resolved_api_key.get_secret_value().strip():
            raise JevConfigError("TypeSafe API key must not be empty")
        if timeout_seconds <= 0:
            raise JevConfigError("timeout_seconds must be greater than zero")

        sdk_logger = logging.getLogger("typesafe_sdk")
        if sdk_logger.getEffectiveLevel() < logging.INFO:
            sdk_logger.setLevel(logging.INFO)

        self._api_key = resolved_api_key
        self._model = model if model is not None else settings.typesafe_default_model
        self._timeout_seconds = timeout_seconds

    def evaluate(
        self,
        *,
        state: Mapping[str, Any],
        questions: Mapping[str, Question],
    ) -> JevResponse:
        """Validate inputs and evaluate typed questions against shared state."""
        if not questions:
            raise JevValidationError("questions must not be empty")
        try:
            json.dumps(state)
        except (TypeError, ValueError) as exc:
            raise JevValidationError("state must be JSON-serializable") from exc

        wire_questions = {
            question_id: _question_to_wire(question)
            for question_id, question in questions.items()
        }
        request = {
            "state": state,
            "model": self._model,
            "questions": wire_questions,
        }
        try:
            raw_response = self._invoke(request)
        except (
            typesafe_sdk.TypeSafeAuthenticationError,
            typesafe_sdk.TypeSafePermissionDeniedError,
        ):
            raise JevAuthError("Jev authentication or authorization failed") from None
        except typesafe_sdk.TypeSafeRateLimitError:
            raise JevRateLimitError("Jev rate limit exceeded") from None
        except (
            typesafe_sdk.TypeSafeUnprocessableEntityError,
            typesafe_sdk.TypeSafeAPIResponseValidationError,
            typesafe_sdk.TypeSafeBadRequestError,
            typesafe_sdk.TypeSafeNotFoundError,
        ):
            raise JevValidationError("Jev rejected or malformed the request") from None
        except typesafe_sdk.TypeSafeError:
            raise JevUnavailableError("Jev is unavailable") from None

        try:
            response = JevResponse.model_validate(raw_response)
        except ValidationError:
            raise JevValidationError("Jev returned a malformed response") from None

        if set(response.answers) != set(questions):
            raise JevValidationError(
                "Jev response question IDs do not match the request"
            )
        return response

    def _invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        """Invoke Jev through the SDK and return its JSON-compatible wire form."""
        with typesafe_sdk.TypeSafeClient(
            api_key=self._api_key.get_secret_value(),
            model=self._model,
            timeout=self._timeout_seconds,
        ) as client:
            response = client.system_one(
                state=request["state"],
                questions=request["questions"],
            )
            return response.model_dump(mode="json")
