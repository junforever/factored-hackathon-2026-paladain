"""Pydantic schemas for Jev question contracts."""

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from .exceptions import JevValidationError

Probability = Annotated[float, Field(ge=0.0, le=1.0)]
JSONContent = str | dict[str, Any] | list[Any]


def _require_non_blank(value: str, field_name: str) -> str:
    """Reject strings that are empty or contain only whitespace."""
    if not value.strip():
        raise ValueError(f"{field_name} no puede estar vacío ni contener solo espacios")
    return value


class NoulCriteria(BaseModel):
    """Descriptions for the true and false outcomes of a Noul question."""

    model_config = ConfigDict(extra="forbid")

    true: str = Field(min_length=1)
    false: str = Field(min_length=1)

    @field_validator("true", "false")
    @classmethod
    def _no_blank(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_blank(value, info.field_name)


class NoulQuestion(BaseModel):
    """A binary Jev question."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["noul"] = "noul"
    instructions: str = Field(min_length=1)
    criteria: NoulCriteria

    @field_validator("instructions")
    @classmethod
    def _no_blank_instructions(cls, value: str) -> str:
        return _require_non_blank(value, "instructions")


class ChoiceQuestion(BaseModel):
    """A Jev question that selects one option from a closed set."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["choice"] = "choice"
    instructions: str = Field(min_length=1)
    criteria: dict[str, str] = Field(min_length=2, max_length=255)
    include_other: bool = False

    @field_validator("instructions")
    @classmethod
    def _no_blank_instructions(cls, value: str) -> str:
        return _require_non_blank(value, "instructions")

    @field_validator("criteria")
    @classmethod
    def _no_empty(cls, value: dict[str, str]) -> dict[str, str]:
        for option_id, description in value.items():
            if not option_id.strip():
                raise ValueError("option_id vacío o compuesto solo por espacios")
            if not description.strip():
                raise ValueError(
                    "descripción vacía o compuesta solo por espacios "
                    f"para '{option_id}'"
                )
        return value


class ScoreQuestion(BaseModel):
    """A Jev question scored across ordered levels."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["score"] = "score"
    instructions: str = Field(min_length=1)
    criteria: list[str] = Field(min_length=2, max_length=10)

    @field_validator("instructions")
    @classmethod
    def _no_blank_instructions(cls, value: str) -> str:
        return _require_non_blank(value, "instructions")

    @field_validator("criteria")
    @classmethod
    def _no_empty_levels(cls, value: list[str]) -> list[str]:
        for level in value:
            if not level.strip():
                raise ValueError("nivel de Score vacío o compuesto solo por espacios")
        return value


Question = NoulQuestion | ChoiceQuestion | ScoreQuestion


class NoulAnswer(BaseModel):
    """A binary Jev answer represented as the probability of true."""

    model_config = ConfigDict(extra="allow")

    type: Literal["noul"] = "noul"
    noul: Probability


class ChoiceAnswer(BaseModel):
    """A Jev choice answer and its probability distribution."""

    model_config = ConfigDict(extra="allow")

    type: Literal["choice"] = "choice"
    choice: str
    probabilities: dict[str, Probability]
    confidence: Probability

    @model_validator(mode="after")
    def _choice_present(self) -> "ChoiceAnswer":
        if self.choice not in self.probabilities:
            raise ValueError("choice no está en probabilities")
        return self


class ScoreAnswer(BaseModel):
    """A Jev score answer over ordered levels."""

    model_config = ConfigDict(extra="allow")

    type: Literal["score"] = "score"
    score: float
    legend: dict[int, JSONContent]
    probabilities: dict[int, Probability]
    confidence: Probability

    @field_validator("legend", "probabilities", mode="before")
    @classmethod
    def _int_keys(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {int(key): item for key, item in value.items()}
        return value


Answer = Annotated[
    NoulAnswer | ChoiceAnswer | ScoreAnswer,
    Field(discriminator="type"),
]


class Usage(BaseModel):
    """Token usage reported by Jev."""

    model_config = ConfigDict(extra="allow")

    input_tokens: int | None = None
    output_tokens: int | None = None


class JevResponse(BaseModel):
    """Typed response returned by Jev."""

    model_config = ConfigDict(extra="allow")

    model: str
    answers: dict[str, Answer]
    usage: Usage

    def _get(self, question_id: str, expected: str) -> Answer:
        if question_id not in self.answers:
            raise JevValidationError(f"question_id '{question_id}' no existe")
        answer = self.answers[question_id]
        if answer.type != expected:
            raise JevValidationError(
                f"answer '{question_id}' es '{answer.type}', se esperaba '{expected}'"
            )
        return answer

    def get_noul(self, question_id: str) -> NoulAnswer:
        answer = self._get(question_id, "noul")
        assert isinstance(answer, NoulAnswer)
        return answer

    def get_choice(self, question_id: str) -> ChoiceAnswer:
        answer = self._get(question_id, "choice")
        assert isinstance(answer, ChoiceAnswer)
        return answer

    def get_score(self, question_id: str) -> ScoreAnswer:
        answer = self._get(question_id, "score")
        assert isinstance(answer, ScoreAnswer)
        return answer
