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
