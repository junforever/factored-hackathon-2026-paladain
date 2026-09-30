import pytest
from pydantic import ValidationError

from ai_banking_customer_service.governance.jev import (
    ChoiceQuestion,
    NoulQuestion,
    ScoreQuestion,
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
def test_noul_question_rejects_blank_criteria(
    field_name: str, value: str
) -> None:
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
