import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from ai_banking_customer_service.agent.orchestrator import EscalationType, TurnAction
from ai_banking_customer_service.config import PROJECT_ROOT
from ai_banking_customer_service.evaluation import cases as cases_module
from ai_banking_customer_service.evaluation.cases import (
    EvalCase,
    EvalConfig,
    EvalManifest,
    load_eval_cases,
    load_eval_config,
    validate_coverage,
    validate_held_out_independence,
)


def _config_payload() -> dict:
    return {
        "pipeline_version": "3.0.0",
        "dataset_version": "1.0.0",
        "held_out_manifest": "evals/held_out_manifest.json",
        "development_manifest": "evals/development_manifest.json",
        "output_dir": "evals/reports",
        "baseline": "all_human",
        "case_timeout_seconds": 120,
        "grace_period_seconds": 5,
        "max_result_bytes": 1048576,
        "min_coverage": {
            "total_cases": 50,
            "min_portuguese_cases": 10,
            "min_cases_per_scenario": 5,
        },
    }


def test_load_eval_config_resolves_normative_paths_inside_project() -> None:
    config = load_eval_config(PROJECT_ROOT / "configs" / "eval.yaml")

    assert config.pipeline_version == "3.0.0"
    assert config.dataset_version == "1.0.0"
    assert config.held_out_manifest == PROJECT_ROOT / "evals/held_out_manifest.json"
    assert config.development_manifest == (
        PROJECT_ROOT / "evals/development_manifest.json"
    )
    assert config.output_dir == PROJECT_ROOT / "evals/reports"
    assert config.baseline == "all_human"
    assert config.case_timeout_seconds == 120.0
    assert config.grace_period_seconds == 5.0
    assert config.max_result_bytes == 1048576


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("case_timeout_seconds", True),
        ("grace_period_seconds", False),
        ("max_result_bytes", True),
    ],
)
def test_eval_config_rejects_bool_for_numeric_fields(field: str, value: bool) -> None:
    payload = _config_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        EvalConfig.model_validate(payload)


def test_eval_config_rejects_project_escape() -> None:
    payload = _config_payload()
    payload["output_dir"] = "../outside"

    with pytest.raises(ValidationError, match="project root"):
        EvalConfig.model_validate(payload)


def test_eval_config_requires_room_for_the_canonical_error_envelope() -> None:
    payload = _config_payload()
    payload["max_result_bytes"] = cases_module.MIN_RESULT_BYTES

    config = EvalConfig.model_validate(payload)

    assert config.max_result_bytes == cases_module.MIN_RESULT_BYTES

    payload["max_result_bytes"] -= 1
    with pytest.raises(ValidationError, match="canonical error envelope"):
        EvalConfig.model_validate(payload)


def test_eval_case_rejects_case_id_above_the_bounded_envelope_maximum() -> None:
    payload = _case_payload("C" * cases_module.MAX_CASE_ID_LENGTH)
    assert EvalCase.model_validate(payload).case_id == payload["case_id"]

    payload["case_id"] += "C"
    with pytest.raises(ValidationError, match="case_id"):
        EvalCase.model_validate(payload)


def test_eval_config_forbids_unknown_fields() -> None:
    payload = _config_payload()
    payload["cost"] = {"input": 1}

    with pytest.raises(ValidationError):
        EvalConfig.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pipeline_version", ""),
        ("dataset_version", "   "),
        ("held_out_manifest", ""),
        ("case_timeout_seconds", 0),
        ("case_timeout_seconds", float("inf")),
        ("grace_period_seconds", -1),
        ("grace_period_seconds", float("nan")),
        ("max_result_bytes", 0),
        ("max_result_bytes", 16 * 1024 * 1024 + 1),
        ("baseline", "model_only"),
    ],
)
def test_eval_config_rejects_invalid_values(field: str, value: object) -> None:
    payload = _config_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        EvalConfig.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("total_cases", True),
        ("min_portuguese_cases", 0),
        ("min_cases_per_scenario", 1.5),
    ],
)
def test_eval_config_rejects_invalid_coverage_minimums(
    field: str, value: object
) -> None:
    payload = _config_payload()
    payload["min_coverage"][field] = value

    with pytest.raises(ValidationError):
        EvalConfig.model_validate(payload)


def _case_payload(
    case_id: str = "CASE-001",
    *,
    language: str = "es",
    scenario: str = "normal_resolution",
    customer_message: str = "I do not recognize this charge and confirm blocking.",
    complaint_id: str | None = "CMP-001",
    action: str = "respond",
    requires_escalation: bool = False,
    expected_escalation_type: str | None = None,
) -> dict:
    return {
        "case_id": case_id,
        "language": language,
        "scenario": scenario,
        "customer_message": customer_message,
        "expected": {
            "intent": "dispute_charge",
            "action": action,
            "is_automatable": not requires_escalation,
            "requires_escalation": requires_escalation,
            "expected_tools": ["get_dispute_context"],
            "expected_escalation_type": expected_escalation_type,
            "complaint_id": complaint_id,
            "customer_confirmed_block": False,
            "forbidden_actions": [],
            "response_required_substrings": [],
            "response_forbidden_substrings": [],
            "sensitive_output_forbidden_substrings": [f"CANARY-{case_id}"],
        },
        "metadata": {"segment": "Retail", "notes": "Synthetic evaluation case"},
    }


def _case(*args: object, **kwargs: object) -> EvalCase:
    return EvalCase.model_validate(_case_payload(*args, **kwargs))


def test_eval_case_parses_the_exact_ground_truth_contract() -> None:
    case = EvalCase.model_validate(
        _case_payload(
            action="escalate",
            requires_escalation=True,
            expected_escalation_type="tool_escalation",
        )
    )

    assert case.expected.action is TurnAction.ESCALATE
    assert case.expected.expected_escalation_type is EscalationType.TOOL_ESCALATION
    assert case.metadata.segment == "Retail"


@pytest.mark.parametrize(
    ("action", "requires_escalation", "escalation_type"),
    [
        ("escalate", False, None),
        ("respond", True, "tool_escalation"),
        ("escalate", True, None),
        ("respond", False, "tool_escalation"),
    ],
)
def test_eval_case_rejects_inconsistent_escalation_ground_truth(
    action: str,
    requires_escalation: bool,
    escalation_type: str | None,
) -> None:
    payload = _case_payload(
        action=action,
        requires_escalation=requires_escalation,
        expected_escalation_type=escalation_type,
    )

    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("expected_tools", ["unknown_tool"]),
        ("forbidden_actions", ["block", "block"]),
        ("response_required_substrings", ["   "]),
        ("response_forbidden_substrings", [""]),
        ("sensitive_output_forbidden_substrings", ["\t"]),
    ],
)
def test_eval_case_rejects_invalid_ground_truth_lists(
    field: str, value: object
) -> None:
    payload = _case_payload()
    payload["expected"][field] = value

    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)


def test_eval_case_rejects_unknown_and_removed_fields() -> None:
    payload = _case_payload()
    payload["expected"]["is_sensitive"] = True

    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)


def test_validate_coverage_accepts_all_six_scenarios_and_portuguese_minimum() -> None:
    scenarios = [
        "normal_resolution",
        "ambiguous",
        "human_required",
        "attack",
        "missing_data",
        "edge_case",
    ]
    cases = [
        _case(
            f"CASE-{index}",
            language="pt" if index == 0 else "es",
            scenario=scenario,
            customer_message=f"Unique synthetic message number {index}",
            complaint_id=f"CMP-{index}",
        )
        for index, scenario in enumerate(scenarios)
    ]
    payload = _config_payload()
    payload["min_coverage"] = {
        "total_cases": 6,
        "min_portuguese_cases": 1,
        "min_cases_per_scenario": 1,
    }
    config = EvalConfig.model_validate(payload)

    validate_coverage(cases, config)


@pytest.mark.parametrize("failure", ["total", "portuguese", "scenario", "duplicate"])
def test_validate_coverage_fails_closed(failure: str) -> None:
    scenarios = [
        "normal_resolution",
        "ambiguous",
        "human_required",
        "attack",
        "missing_data",
        "edge_case",
    ]
    cases = [
        _case(
            f"CASE-{index}",
            language="pt" if index == 0 else "es",
            scenario=scenario,
            customer_message=f"Unique synthetic message number {index}",
            complaint_id=f"CMP-{index}",
        )
        for index, scenario in enumerate(scenarios)
    ]
    payload = _config_payload()
    payload["min_coverage"] = {
        "total_cases": 7 if failure == "total" else 6,
        "min_portuguese_cases": 2 if failure == "portuguese" else 1,
        "min_cases_per_scenario": 2 if failure == "scenario" else 1,
    }
    if failure == "duplicate":
        cases[-1] = cases[0]
    config = EvalConfig.model_validate(payload)

    with pytest.raises(ValueError):
        validate_coverage(cases, config)


@pytest.mark.parametrize(
    ("mutation", "rule"),
    [
        ("case_id", "case_id"),
        ("complaint_id", "complaint_id"),
        ("normalized_message", "normalized_message"),
        ("near_duplicate", "message_jaccard"),
    ],
)
def test_independence_rejects_identity_and_message_leakage(
    mutation: str, rule: str
) -> None:
    held = _case(
        "HELD-001",
        customer_message=(
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu "
            "nu xi omicron pi rho sigma tau upsilon phi chi psi omega one two "
            "three four five held"
        ),
        complaint_id="CMP-HELD",
    )
    development_payload = _case_payload(
        "DEV-001",
        customer_message="separate development wording for a banking request",
        complaint_id="CMP-DEV",
    )
    if mutation == "case_id":
        development_payload["case_id"] = held.case_id
    elif mutation == "complaint_id":
        development_payload["expected"]["complaint_id"] = held.expected.complaint_id
    elif mutation == "normalized_message":
        development_payload["customer_message"] = (
            "  ALPHA beta gamma delta epsilon zeta eta theta iota kappa lambda mu "
            "nu xi omicron pi rho sigma tau upsilon phi chi psi omega one two "
            "three four five held  "
        )
    elif mutation == "near_duplicate":
        development_payload["customer_message"] = (
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu "
            "nu xi omicron pi rho sigma tau upsilon phi chi psi omega one two "
            "three four five changed"
        )
    development = EvalCase.model_validate(development_payload)

    with pytest.raises(ValueError, match=rule) as error:
        validate_held_out_independence(
            [held], [development], b"held bytes", b"development bytes"
        )

    assert "HELD-001" in str(error.value)
    assert development.case_id in str(error.value)
    assert held.customer_message not in str(error.value)


def test_independence_rejects_identical_bytes_and_hashes() -> None:
    held = _case("HELD-001", complaint_id="CMP-HELD")
    development = _case(
        "DEV-001",
        customer_message="Different development case wording",
        complaint_id="CMP-DEV",
    )

    with pytest.raises(ValueError, match="dataset_bytes"):
        validate_held_out_independence([held], [development], b"same", b"same")


def test_short_messages_use_the_complete_token_sequence_as_one_shingle() -> None:
    held = _case("HELD-001", customer_message="same short text", complaint_id=None)
    development = _case(
        "DEV-001", customer_message="SAME   short text", complaint_id=None
    )

    with pytest.raises(ValueError, match="normalized_message"):
        validate_held_out_independence([held], [development], b"held", b"development")


def _write_dataset(root: Path) -> tuple[EvalConfig, Path, Path]:
    cases_dir = root / "evals" / "cases"
    cases_dir.mkdir(parents=True)
    scenarios = [
        "normal_resolution",
        "ambiguous",
        "human_required",
        "attack",
        "missing_data",
        "edge_case",
    ]
    held_payload = [
        _case_payload(
            f"HELD-{index}",
            language="pt" if index == 0 else "es",
            scenario=scenario,
            customer_message=(
                f"Held message with unique marker {index} scenario {scenario}"
            ),
            complaint_id=f"CMP-H-{index}",
        )
        for index, scenario in enumerate(scenarios)
    ]
    development_payload = [
        _case_payload(
            "DEV-001",
            customer_message="Development-only request with distinct vocabulary",
            complaint_id="CMP-D-001",
        )
    ]
    held_file = cases_dir / "custom-held.yaml"
    development_file = cases_dir / "custom-development.yaml"
    held_file.write_text(
        yaml.safe_dump(held_payload, sort_keys=False), encoding="utf-8"
    )
    development_file.write_text(
        yaml.safe_dump(development_payload, sort_keys=False), encoding="utf-8"
    )
    held_manifest = root / "evals" / "held.json"
    development_manifest = root / "evals" / "development.json"
    held_manifest.write_text(
        json.dumps(
            {
                "dataset_version": "1.0.0",
                "pipeline_version": "3.0.0",
                "cases_file": "evals/cases/custom-held.yaml",
                "sha256": hashlib.sha256(held_file.read_bytes()).hexdigest(),
                "frozen_at": "2026-10-02T12:00:00Z",
                "owner": "evaluation-team",
                "total_cases": 6,
                "coverage": {
                    "total_cases": 6,
                    "portuguese_cases": 1,
                    "cases_per_scenario": dict.fromkeys(scenarios, 1),
                },
            }
        ),
        encoding="utf-8",
    )
    development_manifest.write_text(
        json.dumps(
            {
                "dataset_version": "development-1.0.0",
                "cases_file": "evals/cases/custom-development.yaml",
                "sha256": hashlib.sha256(development_file.read_bytes()).hexdigest(),
                "frozen_at": "2026-10-02T12:00:00Z",
                "owner": "evaluation-team",
                "total_cases": 1,
            }
        ),
        encoding="utf-8",
    )
    config_payload = _config_payload()
    config_payload["held_out_manifest"] = "evals/held.json"
    config_payload["development_manifest"] = "evals/development.json"
    config_payload["min_coverage"] = {
        "total_cases": 6,
        "min_portuguese_cases": 1,
        "min_cases_per_scenario": 1,
    }
    config = EvalConfig.model_validate(config_payload)
    return config, held_manifest, development_manifest


def test_loader_uses_declared_files_and_validates_both_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cases_module, "PROJECT_ROOT", tmp_path)
    config, held_manifest, development_manifest = _write_dataset(tmp_path)

    cases = load_eval_cases(held_manifest, development_manifest, config)

    assert [case.case_id for case in cases] == [f"HELD-{index}" for index in range(6)]


def test_loader_resolves_relative_manifest_arguments_from_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cases_module, "PROJECT_ROOT", tmp_path)
    config, _, _ = _write_dataset(tmp_path)

    cases = load_eval_cases(
        Path("evals/held.json"),
        Path("evals/development.json"),
        config,
    )

    assert len(cases) == 6


@pytest.mark.parametrize("dataset", ["held", "development"])
def test_loader_rejects_hash_mismatch(
    dataset: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cases_module, "PROJECT_ROOT", tmp_path)
    config, held_manifest, development_manifest = _write_dataset(tmp_path)
    manifest_path = held_manifest if dataset == "held" else development_manifest
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="sha256"):
        load_eval_cases(held_manifest, development_manifest, config)


@pytest.mark.parametrize("count_field", ["total_cases", "coverage.total_cases"])
def test_loader_rejects_declared_count_mismatch(
    count_field: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cases_module, "PROJECT_ROOT", tmp_path)
    config, held_manifest, development_manifest = _write_dataset(tmp_path)
    payload = json.loads(held_manifest.read_text(encoding="utf-8"))
    if count_field == "total_cases":
        payload["total_cases"] = 7
    else:
        payload["coverage"]["total_cases"] = 7
    held_manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="total_cases"):
        load_eval_cases(held_manifest, development_manifest, config)


def test_manifest_rejects_invalid_identity_and_unknown_fields() -> None:
    payload = {
        "dataset_version": "1.0.0",
        "cases_file": "evals/cases/file.yaml",
        "sha256": "not-a-hash",
        "frozen_at": "2026-10-02T12:00:00Z",
        "owner": "evaluation-team",
        "total_cases": True,
        "unexpected": "field",
    }

    with pytest.raises(ValidationError):
        EvalManifest.model_validate(payload)


def test_committed_fixtures_match_hash_identity_coverage_and_independence() -> None:
    config = load_eval_config(PROJECT_ROOT / "configs" / "eval.yaml")

    cases = load_eval_cases(
        config.held_out_manifest,
        config.development_manifest,
        config,
    )

    assert len(cases) == 50
    assert len({case.case_id for case in cases}) == 50
    assert sum(case.language == "pt" for case in cases) == 12
    assert Counter(case.scenario for case in cases) == {
        "normal_resolution": 15,
        "ambiguous": 10,
        "human_required": 10,
        "attack": 5,
        "missing_data": 5,
        "edge_case": 5,
    }
    held_manifest = json.loads(config.held_out_manifest.read_text(encoding="utf-8"))
    development_manifest = json.loads(
        config.development_manifest.read_text(encoding="utf-8")
    )
    assert (
        held_manifest["sha256"]
        == hashlib.sha256(
            Path(held_manifest["cases_file"]).resolve().read_bytes()
        ).hexdigest()
    )
    assert (
        development_manifest["sha256"]
        == hashlib.sha256(
            Path(development_manifest["cases_file"]).resolve().read_bytes()
        ).hexdigest()
    )
