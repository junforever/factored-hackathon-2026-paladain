"""Typed client boundary for Jev requests."""

import json
from typing import Any, Mapping

from pydantic import SecretStr, ValidationError

from ai_banking_customer_service.config import settings

from .exceptions import JevConfigError, JevValidationError
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
        resolved_api_key = (
            api_key if api_key is not None else settings.typesafe_api_key
        )
        if not resolved_api_key.get_secret_value().strip():
            raise JevConfigError("TypeSafe API key must not be empty")
        if timeout_seconds <= 0:
            raise JevConfigError("timeout_seconds must be greater than zero")

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
            response = JevResponse.model_validate(self._invoke(request))
        except ValidationError:
            raise JevValidationError("Jev returned a malformed response") from None

        if set(response.answers) != set(questions):
            raise JevValidationError(
                "Jev response question IDs do not match the request"
            )
        return response

    def _invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        """Invoke the Jev transport; real SDK integration is intentionally pending."""
        raise NotImplementedError
