from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from ai_banking_customer_service.config import PROJECT_ROOT, Settings, load_policy


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "openai_api_key": "test-openai-key",
        "typesafe_api_key": "test-typesafe-key",
        "duckdb_name": "test.duckdb",
        "sandbox_path": "data/test.parquet",
        "state_path": "data/state",
        "typesafe_default_model": "test-jev",
        "openai_model": "test-openai",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_settings_ui_defaults_and_resolved_audit_paths() -> None:
    configured = _settings()

    assert configured.demo_customer_id == "customer-hackathon-demo"
    assert configured.typesafe_timeout_seconds == 10.0
    assert configured.audit_log_path == "data/state/audit/audit.jsonl"
    assert configured.audit_fallback_path == "data/state/audit/audit_fallback.jsonl"
    assert configured.session_max_messages == 50
    assert configured.session_ttl_seconds == 1800
    assert configured.audit_log_full_path == PROJECT_ROOT / configured.audit_log_path
    assert (
        configured.audit_fallback_full_path
        == PROJECT_ROOT / configured.audit_fallback_path
    )


@pytest.mark.parametrize(
    "field",
    ["demo_customer_id", "audit_log_path", "audit_fallback_path"],
)
def test_settings_rejects_blank_ui_strings(field: str) -> None:
    with pytest.raises(ValidationError):
        _settings(**{field: " \t "})


@pytest.mark.parametrize(
    "value",
    [0, -0.1, float("nan"), float("inf"), float("-inf"), True, False],
    ids=["zero", "negative", "nan", "infinity", "negative-infinity", "true", "false"],
)
def test_settings_rejects_invalid_typesafe_timeout(value: object) -> None:
    with pytest.raises(ValidationError):
        _settings(typesafe_timeout_seconds=value)


@pytest.mark.parametrize("field", ["session_max_messages", "session_ttl_seconds"])
@pytest.mark.parametrize(
    "value",
    [0, -1, True, False],
    ids=["zero", "negative", "true", "false"],
)
def test_settings_rejects_invalid_positive_integers(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        _settings(**{field: value})


def test_env_example_documents_ui_defaults() -> None:
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    for entry in (
        "DEMO_CUSTOMER_ID=customer-hackathon-demo",
        "TYPESAFE_TIMEOUT_SECONDS=10.0",
        "AUDIT_LOG_PATH=data/state/audit/audit.jsonl",
        "AUDIT_FALLBACK_PATH=data/state/audit/audit_fallback.jsonl",
        "SESSION_MAX_MESSAGES=50",
        "SESSION_TTL_SECONDS=1800",
    ):
        assert entry in env_example.splitlines()


def _valid_policy_data() -> dict[str, object]:
    return {
        "auto_block": {"enabled": True},
        "escalation": {"high_amount_threshold_usd": 750},
        "governance": {
            "prompt_injection": {"block": 0.8, "review": 0.35},
            "social_engineering": {"block": 0.8, "review": 0.35},
            "min_intent_confidence": 0.5,
        },
        "tool_gating": {"min_intent_matches_tool": 0.7},
        "output_screening": {
            "min_output_safety_score": 1.5,
            "min_output_safety_confidence": 0.5,
        },
    }


def _write_policy(path: Path, data: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_load_policy_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_policy(tmp_path / "missing-policy.yaml")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.pop("governance"),
        lambda data: data["governance"].pop("social_engineering"),
    ],
    ids=["missing-governance", "incomplete-governance"],
)
def test_load_policy_requires_complete_governance(
    tmp_path: Path,
    mutate: Callable[[dict[str, object]], object],
) -> None:
    data = _valid_policy_data()
    mutate(data)
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, data)

    with pytest.raises(ValidationError):
        load_policy(policy_path)


@pytest.mark.parametrize(
    "section",
    ["tool_gating", "output_screening"],
    ids=["tool-gating", "output-screening"],
)
def test_load_policy_requires_new_governance_sections(
    tmp_path: Path,
    section: str,
) -> None:
    data = _valid_policy_data()
    data.pop(section)
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, data)

    with pytest.raises(ValidationError):
        load_policy(policy_path)


@pytest.mark.parametrize(
    "value",
    [-0.01, 1.01, float("nan"), float("inf")],
    ids=["below-zero", "above-one", "nan", "infinity"],
)
def test_load_policy_rejects_invalid_tool_gating_threshold(
    tmp_path: Path,
    value: float,
) -> None:
    data = _valid_policy_data()
    tool_gating = data["tool_gating"]
    assert isinstance(tool_gating, dict)
    tool_gating["min_intent_matches_tool"] = value
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, data)

    with pytest.raises(ValidationError):
        load_policy(policy_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_output_safety_score", -0.01),
        ("min_output_safety_score", 2.01),
        ("min_output_safety_score", float("nan")),
        ("min_output_safety_score", float("inf")),
        ("min_output_safety_confidence", -0.01),
        ("min_output_safety_confidence", 1.01),
        ("min_output_safety_confidence", float("nan")),
        ("min_output_safety_confidence", float("inf")),
    ],
    ids=[
        "score-below-zero",
        "score-above-two",
        "score-nan",
        "score-infinity",
        "confidence-below-zero",
        "confidence-above-one",
        "confidence-nan",
        "confidence-infinity",
    ],
)
def test_load_policy_rejects_invalid_output_screening_thresholds(
    tmp_path: Path,
    field: str,
    value: float,
) -> None:
    data = _valid_policy_data()
    output_screening = data["output_screening"]
    assert isinstance(output_screening, dict)
    output_screening[field] = value
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, data)

    with pytest.raises(ValidationError):
        load_policy(policy_path)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("prompt_injection", "review", 0.8),
        ("prompt_injection", "block", 1.01),
        ("social_engineering", "review", -0.01),
        ("social_engineering", "block", float("nan")),
        ("prompt_injection", "review", float("inf")),
        ("governance", "min_intent_confidence", 1.01),
        ("governance", "min_intent_confidence", float("-inf")),
    ],
    ids=[
        "review-not-below-block",
        "block-above-one",
        "review-below-zero",
        "non-finite-block",
        "non-finite-review",
        "confidence-above-one",
        "non-finite-confidence",
    ],
)
def test_load_policy_rejects_invalid_governance_values(
    tmp_path: Path,
    section: str,
    field: str,
    value: float,
) -> None:
    data = _valid_policy_data()
    governance = data["governance"]
    assert isinstance(governance, dict)
    target = governance if section == "governance" else governance[section]
    assert isinstance(target, dict)
    target[field] = value
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, data)

    with pytest.raises(ValidationError):
        load_policy(policy_path)


@pytest.mark.parametrize(
    "section",
    ["governance", "prompt_injection"],
    ids=["governance", "threshold-block"],
)
def test_load_policy_rejects_unknown_governance_fields(
    tmp_path: Path,
    section: str,
) -> None:
    data = _valid_policy_data()
    governance = data["governance"]
    assert isinstance(governance, dict)
    target = governance if section == "governance" else governance[section]
    assert isinstance(target, dict)
    target["unexpected"] = True
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, data)

    with pytest.raises(ValidationError):
        load_policy(policy_path)


@pytest.mark.parametrize("section", ["tool_gating", "output_screening"])
def test_load_policy_rejects_unknown_new_governance_fields(
    tmp_path: Path,
    section: str,
) -> None:
    data = _valid_policy_data()
    target = data[section]
    assert isinstance(target, dict)
    target["unexpected"] = True
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, data)

    with pytest.raises(ValidationError):
        load_policy(policy_path)


def test_load_policy_returns_typed_governance_and_preserves_escalation(
    tmp_path: Path,
) -> None:
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, _valid_policy_data())

    loaded = load_policy(policy_path)

    assert loaded.governance.prompt_injection.block == 0.8
    assert loaded.governance.prompt_injection.review == 0.35
    assert loaded.governance.social_engineering.block == 0.8
    assert loaded.governance.social_engineering.review == 0.35
    assert loaded.governance.min_intent_confidence == 0.5
    assert loaded.tool_gating.min_intent_matches_tool == 0.7
    assert loaded.output_screening.min_output_safety_score == 1.5
    assert loaded.output_screening.min_output_safety_confidence == 0.5
    assert loaded.high_amount_threshold_usd == 750.0


@pytest.mark.parametrize(
    ("tool_threshold", "output_score", "output_confidence"),
    [(0.0, 0.0, 0.0), (1.0, 2.0, 1.0)],
    ids=["lower-boundaries", "upper-boundaries"],
)
def test_load_policy_accepts_new_threshold_boundaries(
    tmp_path: Path,
    tool_threshold: float,
    output_score: float,
    output_confidence: float,
) -> None:
    data = _valid_policy_data()
    tool_gating = data["tool_gating"]
    output_screening = data["output_screening"]
    assert isinstance(tool_gating, dict)
    assert isinstance(output_screening, dict)
    tool_gating["min_intent_matches_tool"] = tool_threshold
    output_screening["min_output_safety_score"] = output_score
    output_screening["min_output_safety_confidence"] = output_confidence
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, data)

    loaded = load_policy(policy_path)

    assert loaded.tool_gating.min_intent_matches_tool == tool_threshold
    assert loaded.output_screening.min_output_safety_score == output_score
    assert loaded.output_screening.min_output_safety_confidence == output_confidence
