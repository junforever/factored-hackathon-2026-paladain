"""Pydantic schemas for Jev question contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


def _require_non_blank(value: str, field_name: str) -> str:
    """Reject strings that are empty or contain only whitespace."""
    if not value.strip():
        raise ValueError(
            f"{field_name} no puede estar vacío ni contener solo espacios"
        )
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
