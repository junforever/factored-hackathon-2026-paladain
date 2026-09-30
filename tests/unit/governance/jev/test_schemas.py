import pytest
from pydantic import TypeAdapter, ValidationError

from ai_banking_customer_service.governance.jev import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    JevResponse,
    JevValidationError,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
    Usage,
)


def test_noul_question_accepts_valid_instructions_and_criteria() -> None:
    question = NoulQuestion(
        instructions="Is the request authorized?",
        criteria={
            "true": "The request is explicitly authorized.",
            "false": "Authorization is missing.",
        },
    )

    assert question.model_dump() == {
        "type": "noul",
        "instructions": "Is the request authorized?",
        "criteria": {
            "true": "The request is explicitly authorized.",
            "false": "Authorization is missing.",
        },
    }


@pytest.mark.parametrize("instructions", ["", "   "])
def test_noul_question_rejects_blank_instructions(instructions: str) -> None:
    with pytest.raises(ValidationError):
        NoulQuestion(
            instructions=instructions,
            criteria={"true": "Authorized.", "false": "Not authorized."},
        )


@pytest.mark.parametrize("field_name", ["true", "false"])
@pytest.mark.parametrize("value", ["", "   "])
def test_noul_question_rejects_blank_criteria(field_name: str, value: str) -> None:
    criteria = {"true": "Authorized.", "false": "Not authorized."}
    criteria[field_name] = value

    with pytest.raises(ValidationError):
        NoulQuestion(instructions="Is it authorized?", criteria=criteria)


def test_choice_question_rejects_fewer_than_two_options() -> None:
    with pytest.raises(ValidationError):
        ChoiceQuestion(
            instructions="Choose the request type.",
            criteria={"one": "The only option."},
        )


def test_choice_question_rejects_more_than_255_options() -> None:
    with pytest.raises(ValidationError):
        ChoiceQuestion(
            instructions="Choose the request type.",
            criteria={str(index): f"Option {index}" for index in range(256)},
        )


@pytest.mark.parametrize(
    ("option_id", "description"),
    [
        ("fraud", ""),
        ("fraud", "   "),
        ("", "A blank option identifier."),
        ("   ", "A blank option identifier."),
    ],
)
def test_choice_question_rejects_empty_option_parts(
    option_id: str, description: str
) -> None:
    with pytest.raises(ValidationError):
        ChoiceQuestion(
            instructions="Choose the request type.",
            criteria={option_id: description, "other": "Another option."},
        )


def test_score_question_rejects_fewer_than_two_levels() -> None:
    with pytest.raises(ValidationError):
        ScoreQuestion(
            instructions="How safe is the request?",
            criteria=["Unsafe."],
        )


def test_score_question_rejects_more_than_ten_levels() -> None:
    with pytest.raises(ValidationError):
        ScoreQuestion(
            instructions="How safe is the request?",
            criteria=[f"Level {index}." for index in range(11)],
        )


@pytest.mark.parametrize("level", ["", "   "])
def test_score_question_rejects_empty_level(level: str) -> None:
    with pytest.raises(ValidationError):
        ScoreQuestion(
            instructions="How safe is the request?",
            criteria=["Unsafe.", level],
        )


@pytest.mark.parametrize("probability", [-0.01, 1.01])
def test_noul_answer_rejects_probability_outside_unit_interval(
    probability: float,
) -> None:
    with pytest.raises(ValidationError):
        NoulAnswer(noul=probability)


def test_choice_answer_rejects_choice_absent_from_probabilities() -> None:
    with pytest.raises(ValidationError):
        ChoiceAnswer(
            choice="fraud",
            probabilities={"card_issue": 1.0},
            confidence=1.0,
        )


def test_score_answer_normalizes_legend_and_probability_keys_to_int() -> None:
    answer = ScoreAnswer(
        score=1.75,
        legend={"0": "Unsafe", "1": "Review", "2": "Safe"},
        probabilities={"0": 0.05, "1": 0.15, "2": 0.8},
        confidence=0.75,
    )

    assert answer.legend == {0: "Unsafe", 1: "Review", 2: "Safe"}
    assert answer.probabilities == {0: 0.05, 1: 0.15, 2: 0.8}


@pytest.mark.parametrize(
    "structured_description",
    [
        {"label": "Unsafe", "examples": ["Unauthorized action"]},
        ["Safe", {"requires": "Explicit authorization"}],
    ],
)
def test_score_answer_accepts_structured_legend_content(
    structured_description: dict[str, object] | list[object],
) -> None:
    answer = ScoreAnswer(
        score=0.0,
        legend={"0": structured_description, "1": "Safe"},
        probabilities={"0": 1.0, "1": 0.0},
        confidence=1.0,
    )

    assert answer.legend[0] == structured_description
    assert all(isinstance(key, int) for key in answer.legend)


@pytest.mark.parametrize(
    ("payload", "expected_type"),
    [
        ({"type": "noul", "noul": 0.8}, NoulAnswer),
        (
            {
                "type": "choice",
                "choice": "fraud",
                "probabilities": {"fraud": 0.9, "other": 0.1},
                "confidence": 0.8,
            },
            ChoiceAnswer,
        ),
        (
            {
                "type": "score",
                "score": 1.5,
                "legend": {"0": "Unsafe", "1": "Review", "2": "Safe"},
                "probabilities": {"0": 0.1, "1": 0.3, "2": 0.6},
                "confidence": 0.7,
            },
            ScoreAnswer,
        ),
    ],
)
def test_answer_union_parses_by_discriminator(
    payload: dict[str, object],
    expected_type: type,
) -> None:
    answer = TypeAdapter(Answer).validate_python(payload)

    assert isinstance(answer, expected_type)


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "unknown", "value": 0.5},
        {"noul": 0.5},
    ],
)
def test_answer_union_rejects_unknown_or_missing_type(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(Answer).validate_python(payload)


def test_jev_response_parses_answers_usage_and_future_fields() -> None:
    response = JevResponse.model_validate(
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
                    "score": 1.8,
                    "legend": {"0": "Unsafe", "1": "Review", "2": "Safe"},
                    "probabilities": {"0": 0.0, "1": 0.2, "2": 0.8},
                    "confidence": 0.75,
                },
            },
            "usage": {
                "input_tokens": 42,
                "output_tokens": 10,
                "cached_tokens": 5,
            },
            "request_id": "req-123",
        }
    )

    assert isinstance(response.usage, Usage)
    assert response.usage.input_tokens == 42
    assert response.usage.model_extra == {"cached_tokens": 5}
    assert response.model_extra == {"request_id": "req-123"}
    assert response.get_noul("authorized").noul == 0.9
    assert response.get_choice("intent").choice == "fraud"
    assert response.get_score("safety").legend[2] == "Safe"


@pytest.mark.parametrize(
    ("helper_name", "question_id"),
    [
        ("get_noul", "intent"),
        ("get_choice", "safety"),
        ("get_score", "missing"),
    ],
)
def test_jev_response_helpers_reject_wrong_type_or_missing_question(
    helper_name: str,
    question_id: str,
) -> None:
    response = JevResponse(
        model="jev-1.13.0",
        answers={
            "intent": {
                "type": "choice",
                "choice": "fraud",
                "probabilities": {"fraud": 1.0},
                "confidence": 1.0,
            },
            "safety": {
                "type": "score",
                "score": 0.0,
                "legend": {"0": "Unsafe", "1": "Safe"},
                "probabilities": {"0": 1.0, "1": 0.0},
                "confidence": 1.0,
            },
        },
        usage={},
    )

    with pytest.raises(JevValidationError):
        getattr(response, helper_name)(question_id)
