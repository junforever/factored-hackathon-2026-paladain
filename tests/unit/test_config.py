from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from ai_banking_customer_service.config import load_policy


def _valid_policy_data() -> dict[str, object]:
    return {
        "auto_block": {"enabled": True},
        "escalation": {"high_amount_threshold_usd": 750},
        "governance": {
            "prompt_injection": {"block": 0.8, "review": 0.35},
            "social_engineering": {"block": 0.8, "review": 0.35},
            "min_intent_confidence": 0.5,
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
    assert loaded.high_amount_threshold_usd == 750.0
