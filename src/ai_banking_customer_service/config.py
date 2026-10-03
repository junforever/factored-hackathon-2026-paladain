"""Configuración central del proyecto: .env (Settings) y policy.yaml (Policy)."""

import math
from pathlib import Path

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_project_root() -> Path:
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise FileNotFoundError("No se encontró la raíz del proyecto")


PROJECT_ROOT = get_project_root()
POLICY_PATH = PROJECT_ROOT / "configs" / "policy.yaml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    # Secretos (obligatorios)
    openai_api_key: SecretStr
    typesafe_api_key: SecretStr

    # Rutas y nombres (obligatorios)
    duckdb_name: str
    sandbox_path: str
    state_path: str

    # Modelos (obligatorios)
    typesafe_default_model: str
    openai_model: str

    # UI and composition
    demo_customer_id: str = "customer-hackathon-demo"
    typesafe_timeout_seconds: float = 10.0
    audit_log_path: str = "data/state/audit/audit.jsonl"
    audit_fallback_path: str = "data/state/audit/audit_fallback.jsonl"
    session_max_messages: int = 50
    session_ttl_seconds: int = 1800

    @field_validator(
        "demo_customer_id",
        "audit_log_path",
        "audit_fallback_path",
    )
    @classmethod
    def _non_empty_ui_string(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("typesafe_timeout_seconds", mode="before")
    @classmethod
    def _timeout_must_not_be_bool(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("must be a finite number greater than zero")
        return value

    @field_validator("typesafe_timeout_seconds")
    @classmethod
    def _positive_finite_timeout(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("must be a finite number greater than zero")
        return value

    @field_validator("session_max_messages", "session_ttl_seconds", mode="before")
    @classmethod
    def _positive_integer_not_bool(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("must be a positive integer")
        return value

    @field_validator("session_max_messages", "session_ttl_seconds")
    @classmethod
    def _positive_integer(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be a positive integer")
        return value

    @property
    def duckdb_path(self) -> Path:
        return PROJECT_ROOT / "duckdb" / self.duckdb_name

    @property
    def sandbox_full_path(self) -> Path:
        return PROJECT_ROOT / self.sandbox_path

    @property
    def state_dir(self) -> Path:
        path = PROJECT_ROOT / self.state_path
        if path.suffix:
            return path.parent
        return path

    @property
    def audit_log_full_path(self) -> Path:
        return PROJECT_ROOT / self.audit_log_path

    @property
    def audit_fallback_full_path(self) -> Path:
        return PROJECT_ROOT / self.audit_fallback_path


class ScreeningThresholdPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block: float
    review: float

    @field_validator("block", "review")
    @classmethod
    def _finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("debe ser un número finito")
        return value

    @model_validator(mode="after")
    def _order(self) -> "ScreeningThresholdPolicy":
        if not (0.0 <= self.review < self.block <= 1.0):
            raise ValueError("se requiere 0 <= review < block <= 1")
        return self


class GovernancePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_injection: ScreeningThresholdPolicy
    social_engineering: ScreeningThresholdPolicy
    min_intent_confidence: float

    @field_validator("min_intent_confidence")
    @classmethod
    def _min_conf(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("min_intent_confidence debe ser finito")
        if not (0.0 <= value <= 1.0):
            raise ValueError("se requiere 0 <= min_intent_confidence <= 1")
        return value


class ToolGatingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_intent_matches_tool: float

    @field_validator("min_intent_matches_tool")
    @classmethod
    def _probability(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("min_intent_matches_tool debe ser finito")
        if not (0.0 <= value <= 1.0):
            raise ValueError("se requiere 0 <= min_intent_matches_tool <= 1")
        return value


class OutputScreeningPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_output_safety_score: float
    min_output_safety_confidence: float

    @field_validator("min_output_safety_score")
    @classmethod
    def _score(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("min_output_safety_score debe ser finito")
        if not (0.0 <= value <= 2.0):
            raise ValueError("se requiere 0 <= min_output_safety_score <= 2")
        return value

    @field_validator("min_output_safety_confidence")
    @classmethod
    def _confidence(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("min_output_safety_confidence debe ser finito")
        if not (0.0 <= value <= 1.0):
            raise ValueError("se requiere 0 <= min_output_safety_confidence <= 1")
        return value


class Policy(BaseModel):
    auto_block: dict = {}
    escalation: dict = {}
    governance: GovernancePolicy
    tool_gating: ToolGatingPolicy
    output_screening: OutputScreeningPolicy

    @property
    def high_amount_threshold_usd(self) -> float:
        return float(self.escalation.get("high_amount_threshold_usd", 500.0))


def load_policy(path: Path = POLICY_PATH) -> Policy:
    if not path.exists():
        raise FileNotFoundError(
            f"policy.yaml no encontrado en {path}; la sección governance es obligatoria"
        )
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Policy(**data)


settings = Settings()
policy = load_policy()
