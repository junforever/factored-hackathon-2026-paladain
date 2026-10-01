import logging

import pytest
import typesafe_sdk
from pydantic import SecretStr

from ai_banking_customer_service.governance.jev import (
    ChoiceQuestion,
    JevAuthError,
    JevClient,
    JevConfigError,
    JevRateLimitError,
    JevResponse,
    JevUnavailableError,
    JevValidationError,
    NoulQuestion,
    ScoreQuestion,
)


def _noul_question() -> NoulQuestion:
    return NoulQuestion(
        instructions="Is the request authorized?",
        criteria={"true": "Authorized.", "false": "Not authorized."},
    )


@pytest.mark.parametrize("api_key", [SecretStr(""), SecretStr("   ")])
def test_constructor_rejects_empty_api_key(api_key: SecretStr) -> None:
    with pytest.raises(JevConfigError):
        JevClient(api_key=api_key)


@pytest.mark.parametrize("timeout_seconds", [0.0, -0.1])
def test_constructor_rejects_non_positive_timeout(timeout_seconds: float) -> None:
    with pytest.raises(JevConfigError):
        JevClient(timeout_seconds=timeout_seconds)


def test_constructor_raises_sdk_logger_level_from_debug() -> None:
    sdk_logger = logging.getLogger("typesafe_sdk")
    previous_level = sdk_logger.level
    try:
        sdk_logger.setLevel(logging.DEBUG)

        JevClient()

        assert sdk_logger.getEffectiveLevel() >= logging.INFO
    finally:
        sdk_logger.setLevel(previous_level)


def test_adapter_does_not_log_request_or_response_bodies(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sdk_logger = logging.getLogger("typesafe_sdk")
    previous_level = sdk_logger.level
    request_secret = "sensitive-request-body"
    response_secret = "sensitive-response-body"

    class FakeResponse:
        def model_dump(self, *, mode: str) -> dict[str, object]:
            sdk_logger.debug("response=%s", response_secret)
            return {
                "model": "jev-test",
                "answers": {"authorized": {"type": "noul", "noul": 0.9}},
                "usage": {},
            }

    class FakeTypeSafeClient:
        def __init__(self, **kwargs: object) -> None:
            sdk_logger.debug("client=%r", kwargs)

        def __enter__(self) -> "FakeTypeSafeClient":
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def system_one(self, *, state: object, questions: object) -> FakeResponse:
            sdk_logger.debug("request=%r questions=%r", state, questions)
            return FakeResponse()

    monkeypatch.setattr(typesafe_sdk, "TypeSafeClient", FakeTypeSafeClient)
    caplog.set_level(logging.DEBUG)
    try:
        sdk_logger.setLevel(logging.DEBUG)
        client = JevClient(api_key=SecretStr("secret-api-key"), model="jev-test")

        client._invoke(
            {
                "state": {"message": request_secret},
                "model": "jev-test",
                "questions": {"authorized": {}},
            }
        )
    finally:
        sdk_logger.setLevel(previous_level)

    assert "secret-api-key" not in caplog.text
    assert request_secret not in caplog.text
    assert response_secret not in caplog.text


def test_evaluate_rejects_empty_questions() -> None:
    client = JevClient()

    with pytest.raises(JevValidationError):
        client.evaluate(state={"message": "hello"}, questions={})


@pytest.mark.parametrize("unsupported", [{1, 2}, object()])
def test_evaluate_rejects_non_json_serializable_state(unsupported: object) -> None:
    client = JevClient()

    with pytest.raises(JevValidationError):
        client.evaluate(
            state={"unsupported": unsupported},
            questions={"authorized": _noul_question()},
        )


def test_evaluate_builds_wire_request(monkeypatch: pytest.MonkeyPatch) -> None:
    client = JevClient(model="jev-test")
    state = {"message": "Report an unknown charge."}
    questions = {
        "authorized": _noul_question(),
        "intent": ChoiceQuestion(
            instructions="Choose the intent.",
            criteria={"fraud": "Unknown charge.", "other": "Another request."},
        ),
        "safety": ScoreQuestion(
            instructions="How safe is the action?",
            criteria=["Unsafe.", "Safe."],
        ),
    }
    captured: dict[str, object] = {}

    def fake_invoke(request: dict[str, object]) -> dict[str, object]:
        captured.update(request)
        return {
            "model": "jev-test",
            "answers": {
                "authorized": {"type": "noul", "noul": 0.9},
                "intent": {
                    "type": "choice",
                    "choice": "fraud",
                    "probabilities": {"fraud": 0.9, "other": 0.1},
                    "confidence": 0.8,
                },
                "safety": {
                    "type": "score",
                    "score": 1.0,
                    "legend": {"0": "Unsafe.", "1": "Safe."},
                    "probabilities": {"0": 0.0, "1": 1.0},
                    "confidence": 1.0,
                },
            },
            "usage": {"input_tokens": 10, "output_tokens": 3},
        }

    monkeypatch.setattr(client, "_invoke", fake_invoke)

    client.evaluate(state=state, questions=questions)

    assert captured == {
        "state": state,
        "model": "jev-test",
        "questions": {
            "authorized": {
                "type": "noul",
                "instructions": "Is the request authorized?",
                "criteria": {
                    "true": "Authorized.",
                    "false": "Not authorized.",
                },
            },
            "intent": {
                "type": "choice",
                "instructions": "Choose the intent.",
                "criteria": {
                    "fraud": "Unknown charge.",
                    "other": "Another request.",
                },
            },
            "safety": {
                "type": "score",
                "instructions": "How safe is the action?",
                "criteria": ["Unsafe.", "Safe."],
            },
        },
    }


def test_include_other_adds_default_wire_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = JevClient()
    question = ChoiceQuestion(
        instructions="Choose the intent.",
        criteria={"fraud": "Unknown charge.", "support": "Account help."},
        include_other=True,
    )
    captured: dict[str, object] = {}

    def fake_invoke(request: dict[str, object]) -> dict[str, object]:
        captured.update(request)
        return {
            "model": "jev-1.13.0",
            "answers": {
                "intent": {
                    "type": "choice",
                    "choice": "other",
                    "probabilities": {
                        "fraud": 0.1,
                        "support": 0.1,
                        "other": 0.8,
                    },
                    "confidence": 0.7,
                }
            },
            "usage": {},
        }

    monkeypatch.setattr(client, "_invoke", fake_invoke)

    client.evaluate(
        state={"message": "Something else."}, questions={"intent": question}
    )

    wire_questions = captured["questions"]
    assert isinstance(wire_questions, dict)
    assert wire_questions["intent"]["criteria"] == {
        "fraud": "Unknown charge.",
        "support": "Account help.",
        "other": "None of the above options fit.",
    }
    assert "include_other" not in wire_questions["intent"]
    assert "other" not in question.criteria


def test_include_other_preserves_existing_other_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = JevClient()
    question = ChoiceQuestion(
        instructions="Choose the intent.",
        criteria={"fraud": "Unknown charge.", "other": "Custom fallback."},
        include_other=True,
    )
    captured: dict[str, object] = {}

    def fake_invoke(request: dict[str, object]) -> dict[str, object]:
        captured.update(request)
        return {
            "model": "jev-1.13.0",
            "answers": {
                "intent": {
                    "type": "choice",
                    "choice": "other",
                    "probabilities": {"fraud": 0.1, "other": 0.9},
                    "confidence": 0.8,
                }
            },
            "usage": {},
        }

    monkeypatch.setattr(client, "_invoke", fake_invoke)

    client.evaluate(
        state={"message": "Something else."}, questions={"intent": question}
    )

    wire_questions = captured["questions"]
    assert isinstance(wire_questions, dict)
    assert wire_questions["intent"]["criteria"]["other"] == "Custom fallback."


def test_include_other_rejects_255_options_without_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = JevClient()
    question = ChoiceQuestion(
        instructions="Choose one option.",
        criteria={str(index): f"Option {index}." for index in range(255)},
        include_other=True,
    )

    def forbidden_invoke(request: dict[str, object]) -> dict[str, object]:
        raise AssertionError(f"transport must not be called: {request.keys()}")

    monkeypatch.setattr(client, "_invoke", forbidden_invoke)

    with pytest.raises(JevValidationError):
        client.evaluate(state={"message": "Choose."}, questions={"choice": question})


def test_evaluate_returns_typed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = JevClient()
    monkeypatch.setattr(
        client,
        "_invoke",
        lambda request: {
            "model": request["model"],
            "answers": {"authorized": {"type": "noul", "noul": 0.75}},
            "usage": {"input_tokens": 5, "output_tokens": 1},
        },
    )

    response = client.evaluate(
        state={"message": "Please block my card."},
        questions={"authorized": _noul_question()},
    )

    assert isinstance(response, JevResponse)
    assert response.model == "jev-1.13.0"
    assert response.get_noul("authorized").noul == 0.75
    assert response.usage.input_tokens == 5


def _response_with_all_answer_types() -> JevResponse:
    return JevResponse.model_validate(
        {
            "model": "jev-1.13.0",
            "answers": {
                "authorized": {"type": "noul", "noul": 0.9},
                "intent": {
                    "type": "choice",
                    "choice": "fraud",
                    "probabilities": {"fraud": 0.9, "other": 0.1},
                    "confidence": 0.8,
                },
                "safety": {
                    "type": "score",
                    "score": 1.5,
                    "legend": {"0": "Unsafe.", "1": "Safe."},
                    "probabilities": {"0": 0.1, "1": 0.9},
                    "confidence": 0.8,
                },
            },
            "usage": {},
        }
    )


def test_typed_response_helpers_return_matching_answers() -> None:
    response = _response_with_all_answer_types()

    assert response.get_noul("authorized").noul == 0.9
    assert response.get_choice("intent").choice == "fraud"
    assert response.get_score("safety").score == 1.5


def test_typed_response_helper_rejects_wrong_answer_type() -> None:
    response = _response_with_all_answer_types()

    with pytest.raises(JevValidationError):
        response.get_noul("intent")


@pytest.mark.parametrize("helper", ["get_noul", "get_choice", "get_score"])
def test_typed_response_helpers_reject_missing_question(helper: str) -> None:
    response = _response_with_all_answer_types()

    with pytest.raises(JevValidationError):
        getattr(response, helper)("missing")


@pytest.mark.parametrize(
    ("sdk_error", "expected_error"),
    [
        (
            typesafe_sdk.TypeSafeAuthenticationError(
                401, {"message": "secret-api-key"}, {}
            ),
            JevAuthError,
        ),
        (
            typesafe_sdk.TypeSafePermissionDeniedError(
                403, {"message": "secret-api-key"}, {}
            ),
            JevAuthError,
        ),
        (
            typesafe_sdk.TypeSafeUnprocessableEntityError(
                422, {"message": "secret-api-key"}, {}
            ),
            JevValidationError,
        ),
        (
            typesafe_sdk.TypeSafeAPIResponseValidationError(
                200,
                {"message": "secret-api-key"},
                {},
                "answers.authorized",
            ),
            JevValidationError,
        ),
        (
            typesafe_sdk.TypeSafeBadRequestError(
                400, {"message": "secret-api-key"}, {}
            ),
            JevValidationError,
        ),
        (
            typesafe_sdk.TypeSafeNotFoundError(404, {"message": "secret-api-key"}, {}),
            JevValidationError,
        ),
        (
            typesafe_sdk.TypeSafeRateLimitError(429, {"message": "secret-api-key"}, {}),
            JevRateLimitError,
        ),
        (
            typesafe_sdk.TypeSafeInternalServerError(
                529, {"message": "secret-api-key"}, {}
            ),
            JevUnavailableError,
        ),
        (typesafe_sdk.TypeSafeAPITimeoutError(2.5), JevUnavailableError),
        (
            typesafe_sdk.TypeSafeAPIConnectionError("secret-api-key"),
            JevUnavailableError,
        ),
        (typesafe_sdk.TypeSafeError("secret-api-key"), JevUnavailableError),
    ],
    ids=[
        "authentication",
        "permission-denied",
        "unprocessable-entity",
        "response-validation",
        "bad-request",
        "not-found",
        "rate-limit",
        "internal-server",
        "timeout",
        "connection",
        "catch-all",
    ],
)
def test_evaluate_maps_sdk_errors_without_exposing_secrets(
    monkeypatch: pytest.MonkeyPatch,
    sdk_error: typesafe_sdk.TypeSafeError,
    expected_error: type[Exception],
) -> None:
    client = JevClient(api_key=SecretStr("secret-api-key"))

    def fail_invoke(request: dict[str, object]) -> dict[str, object]:
        raise sdk_error

    monkeypatch.setattr(client, "_invoke", fail_invoke)

    with pytest.raises(expected_error) as raised:
        client.evaluate(
            state={"message": "Please block my card."},
            questions={"authorized": _noul_question()},
        )

    assert not isinstance(raised.value, typesafe_sdk.TypeSafeError)
    assert "secret-api-key" not in str(raised.value)


def test_evaluate_wraps_malformed_response_as_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = JevClient()
    monkeypatch.setattr(
        client,
        "_invoke",
        lambda request: {
            "model": request["model"],
            "answers": {"authorized": {"type": "noul", "noul": "not-a-probability"}},
            "usage": {},
        },
    )

    with pytest.raises(JevValidationError):
        client.evaluate(
            state={"message": "Please block my card."},
            questions={"authorized": _noul_question()},
        )


def test_evaluate_rejects_response_without_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = JevClient()
    monkeypatch.setattr(
        client,
        "_invoke",
        lambda request: {
            "model": request["model"],
            "answers": {"authorized": {"type": "noul", "noul": 0.75}},
        },
    )

    with pytest.raises(JevValidationError):
        client.evaluate(
            state={"message": "Please block my card."},
            questions={"authorized": _noul_question()},
        )


@pytest.mark.parametrize(
    ("question_ids", "answer_ids"),
    [
        (("first", "second"), ("first",)),
        (("first",), ("first", "unexpected")),
    ],
)
def test_evaluate_rejects_incomplete_or_surplus_answers(
    monkeypatch: pytest.MonkeyPatch,
    question_ids: tuple[str, ...],
    answer_ids: tuple[str, ...],
) -> None:
    client = JevClient()
    monkeypatch.setattr(
        client,
        "_invoke",
        lambda request: {
            "model": request["model"],
            "answers": {
                answer_id: {"type": "noul", "noul": 0.5} for answer_id in answer_ids
            },
            "usage": {},
        },
    )

    with pytest.raises(JevValidationError):
        client.evaluate(
            state={"message": "Check completeness."},
            questions={question_id: _noul_question() for question_id in question_ids},
        )


def test_invoke_uses_sdk_context_manager_and_returns_wire_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []
    constructor_arguments: dict[str, object] = {}
    state = {"message": "Report an unknown charge."}
    questions = {
        "authorized": {
            "type": "noul",
            "instructions": "Is the request authorized?",
            "criteria": {"true": "Authorized.", "false": "Not authorized."},
        }
    }
    wire_response = {
        "model": "jev-test",
        "answers": {"authorized": {"type": "noul", "noul": 0.9}},
        "usage": {"input_tokens": 5, "output_tokens": 1},
    }

    class FakeResponse:
        def model_dump(self, *, mode: str) -> dict[str, object]:
            events.append(("model_dump", mode))
            return wire_response

    class FakeTypeSafeClient:
        def __init__(self, **kwargs: object) -> None:
            constructor_arguments.update(kwargs)

        def __enter__(self) -> "FakeTypeSafeClient":
            events.append("enter")
            return self

        def __exit__(self, *args: object) -> None:
            events.append("exit")

        def system_one(self, *, state: object, questions: object) -> FakeResponse:
            events.append(("system_one", state, questions))
            return FakeResponse()

    monkeypatch.setattr(typesafe_sdk, "TypeSafeClient", FakeTypeSafeClient)
    client = JevClient(
        api_key=SecretStr("plain-api-key"),
        model="jev-test",
        timeout_seconds=2.5,
    )

    result = client._invoke(
        {"state": state, "model": "jev-test", "questions": questions}
    )

    assert constructor_arguments == {
        "api_key": "plain-api-key",
        "model": "jev-test",
        "timeout": 2.5,
    }
    assert events == [
        "enter",
        ("system_one", state, questions),
        ("model_dump", "json"),
        "exit",
    ]
    assert result == wire_response


def test_invoke_closes_sdk_client_when_system_one_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []

    class FakeTypeSafeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        def __enter__(self) -> "FakeTypeSafeClient":
            events.append("enter")
            return self

        def __exit__(self, *args: object) -> None:
            events.append(("exit", args[0]))

        def system_one(self, *, state: object, questions: object) -> object:
            raise RuntimeError("transport failed")

    monkeypatch.setattr(typesafe_sdk, "TypeSafeClient", FakeTypeSafeClient)
    client = JevClient()

    with pytest.raises(RuntimeError, match="transport failed"):
        client._invoke(
            {
                "state": {"message": "Report an unknown charge."},
                "model": "jev-test",
                "questions": {"authorized": {}},
            }
        )

    assert events == ["enter", ("exit", RuntimeError)]
