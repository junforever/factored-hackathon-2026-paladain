"""Configuración central del proyecto: .env (Settings) y policy.yaml (Policy)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, SecretStr
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
    jev_api_key: SecretStr

    # Rutas y nombres (obligatorios)
    duckdb_name: str
    sandbox_path: str
    state_path: str

    # Modelos (obligatorios)
    jev_model: str
    openai_model: str

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


class Policy(BaseModel):
    auto_block: dict = {}
    escalation: dict = {}

    @property
    def high_amount_threshold_usd(self) -> float:
        return float(self.escalation.get("high_amount_threshold_usd", 500.0))


def load_policy(path: Path = POLICY_PATH) -> Policy:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return Policy(**(yaml.safe_load(f) or {}))
    return Policy()


settings = Settings()
policy = load_policy()
