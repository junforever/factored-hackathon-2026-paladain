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
    load_eval_case_set,
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
        "sandbox_file": "data/sandbox/agent_sandbox_final.parquet",
        "sandbox_sha256": "0" * 64,
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
    assert config.dataset_version == "1.0.2"
    assert config.held_out_manifest == PROJECT_ROOT / "evals/held_out_manifest.json"
    assert config.development_manifest == (
        PROJECT_ROOT / "evals/development_manifest.json"
    )
    assert config.sandbox_file == (
        PROJECT_ROOT / "data/sandbox/agent_sandbox_final.parquet"
    )
    assert (
        config.sandbox_sha256
        == "5b80c6e487a9333f9045632aa66d6636c1d7b896689b85a4f2180289e56a8dd1"
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
        ("sandbox_sha256", "not-a-hash"),
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
    if complaint_id is not None and complaint_id not in customer_message:
        customer_message = f"{customer_message} {complaint_id}"
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
            "authorization": {
                "authenticated": True,
                "product_authorized": True,
            },
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


def test_eval_case_rejects_hidden_expected_complaint_identity() -> None:
    payload = _case_payload(complaint_id="CMP-001")
    payload["customer_message"] = "I do not recognize this charge and confirm blocking."

    with pytest.raises(ValidationError, match="customer_message"):
        EvalCase.model_validate(payload)


def test_eval_case_allows_null_expected_complaint_identity() -> None:
    payload = _case_payload(complaint_id=None)

    assert EvalCase.model_validate(payload).expected.complaint_id is None


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


@pytest.mark.parametrize("field", ["authenticated", "product_authorized"])
@pytest.mark.parametrize("value", [0, 1, "true", None])
def test_authorization_expectation_requires_strict_booleans(
    field: str, value: object
) -> None:
    payload = _case_payload()
    payload["expected"]["authorization"][field] = value

    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)


def test_authorization_rejects_authorized_product_without_principal() -> None:
    payload = _case_payload()
    payload["expected"]["authorization"] = {
        "authenticated": False,
        "product_authorized": True,
    }

    with pytest.raises(ValidationError, match="product_authorized"):
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
        development_payload["customer_message"] += f" {held.expected.complaint_id}"
    elif mutation == "normalized_message":
        development_payload["expected"]["complaint_id"] = None
        development_payload["customer_message"] = f"  {held.customer_message.upper()}  "
    elif mutation == "near_duplicate":
        development_payload["expected"]["complaint_id"] = None
        development_payload["customer_message"] = held.customer_message.replace(
            "CMP-HELD", "CMP-CHANGED"
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


def _write_dataset(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[EvalConfig, Path, Path]:
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
    sandbox_file = root / "data" / "sandbox" / "sandbox.parquet"
    sandbox_file.parent.mkdir(parents=True)
    sandbox_file.write_bytes(b"validated sandbox identity")
    monkeypatch.setattr(cases_module, "_RUNTIME_SANDBOX_PATH", sandbox_file)
    sandbox_sha256 = hashlib.sha256(sandbox_file.read_bytes()).hexdigest()
    held_manifest = root / "evals" / "held.json"
    development_manifest = root / "evals" / "development.json"
    held_manifest.write_text(
        json.dumps(
            {
                "dataset_version": "1.0.0",
                "pipeline_version": "3.0.0",
                "cases_file": "evals/cases/custom-held.yaml",
                "sha256": hashlib.sha256(held_file.read_bytes()).hexdigest(),
                "sandbox_sha256": sandbox_sha256,
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
                "sandbox_sha256": sandbox_sha256,
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
    config_payload["sandbox_file"] = "data/sandbox/sandbox.parquet"
    config_payload["sandbox_sha256"] = sandbox_sha256
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
    config, held_manifest, development_manifest = _write_dataset(tmp_path, monkeypatch)

    cases = load_eval_cases(held_manifest, development_manifest, config)

    assert [case.case_id for case in cases] == [f"HELD-{index}" for index in range(6)]
    assert all(case.expected.authorization.authenticated for case in cases)
    assert all(case.expected.authorization.product_authorized for case in cases)


def test_loader_selects_development_and_preserves_its_dataset_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cases_module, "PROJECT_ROOT", tmp_path)
    config, held_manifest, development_manifest = _write_dataset(tmp_path, monkeypatch)

    selected = load_eval_case_set(
        held_manifest,
        development_manifest,
        config,
        "development",
    )

    assert [case.case_id for case in selected.cases] == ["DEV-001"]
    assert selected.dataset_version == "development-1.0.0"


def test_loader_rejects_missing_development_authorization_expectation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cases_module, "PROJECT_ROOT", tmp_path)
    config, held_manifest, development_manifest = _write_dataset(tmp_path, monkeypatch)
    manifest = json.loads(development_manifest.read_text(encoding="utf-8"))
    fixture = tmp_path / manifest["cases_file"]
    payload = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    payload[0]["expected"].pop("authorization")
    fixture.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    manifest["sha256"] = hashlib.sha256(fixture.read_bytes()).hexdigest()
    development_manifest.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="development authorization"):
        load_eval_case_set(
            held_manifest,
            development_manifest,
            config,
            "development",
        )


def test_loader_resolves_relative_manifest_arguments_from_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cases_module, "PROJECT_ROOT", tmp_path)
    config, _, _ = _write_dataset(tmp_path, monkeypatch)

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
    config, held_manifest, development_manifest = _write_dataset(tmp_path, monkeypatch)
    manifest_path = held_manifest if dataset == "held" else development_manifest
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="sha256"):
        load_eval_cases(held_manifest, development_manifest, config)


def test_frozen_held_out_hash_cannot_be_redefined_by_its_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cases_module, "PROJECT_ROOT", tmp_path)
    config, held_manifest, development_manifest = _write_dataset(tmp_path, monkeypatch)
    manifest = json.loads(held_manifest.read_text(encoding="utf-8"))
    manifest["dataset_version"] = "1.0.2"
    held_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    config = config.model_copy(update={"dataset_version": "1.0.2"})

    with pytest.raises(ValueError, match="frozen held-out v1.0.2"):
        load_eval_cases(held_manifest, development_manifest, config)


def test_loader_rejects_sandbox_path_that_differs_from_runtime_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cases_module, "PROJECT_ROOT", tmp_path)
    config, held_manifest, development_manifest = _write_dataset(tmp_path, monkeypatch)
    monkeypatch.setattr(
        cases_module, "_RUNTIME_SANDBOX_PATH", tmp_path / "different.parquet"
    )

    with pytest.raises(ValueError, match="runtime settings"):
        load_eval_cases(held_manifest, development_manifest, config)


def test_loader_rejects_configured_sandbox_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cases_module, "PROJECT_ROOT", tmp_path)
    config, held_manifest, development_manifest = _write_dataset(tmp_path, monkeypatch)
    config.sandbox_file.write_bytes(b"different sandbox bytes")

    with pytest.raises(ValueError, match="sandbox sha256"):
        load_eval_cases(held_manifest, development_manifest, config)


def test_loader_rejects_unavailable_configured_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cases_module, "PROJECT_ROOT", tmp_path)
    config, held_manifest, development_manifest = _write_dataset(tmp_path, monkeypatch)
    config = config.model_copy(update={"sandbox_file": tmp_path / "missing.parquet"})
    monkeypatch.setattr(cases_module, "_RUNTIME_SANDBOX_PATH", config.sandbox_file)

    with pytest.raises(ValueError, match="sandbox file is unavailable"):
        load_eval_cases(held_manifest, development_manifest, config)


def test_loader_rejects_manifest_sandbox_identity_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cases_module, "PROJECT_ROOT", tmp_path)
    config, held_manifest, development_manifest = _write_dataset(tmp_path, monkeypatch)
    payload = json.loads(development_manifest.read_text(encoding="utf-8"))
    payload["sandbox_sha256"] = "0" * 64
    development_manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="sandbox identity"):
        load_eval_cases(held_manifest, development_manifest, config)


@pytest.mark.parametrize("count_field", ["total_cases", "coverage.total_cases"])
def test_loader_rejects_declared_count_mismatch(
    count_field: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cases_module, "PROJECT_ROOT", tmp_path)
    config, held_manifest, development_manifest = _write_dataset(tmp_path, monkeypatch)
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
        "sandbox_sha256": "also-not-a-hash",
        "frozen_at": "2026-10-02T12:00:00Z",
        "owner": "evaluation-team",
        "total_cases": True,
        "unexpected": "field",
    }

    with pytest.raises(ValidationError):
        EvalManifest.model_validate(payload)


def test_committed_fixtures_match_hash_identity_coverage_and_independence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = load_eval_config(PROJECT_ROOT / "configs" / "eval.yaml")
    monkeypatch.setattr(cases_module, "_RUNTIME_SANDBOX_PATH", config.sandbox_file)

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
    assert all(
        case.expected.complaint_id is None
        or case.expected.complaint_id in case.customer_message
        for case in cases
    )
    held_manifest = json.loads(config.held_out_manifest.read_text(encoding="utf-8"))
    development_manifest = json.loads(
        config.development_manifest.read_text(encoding="utf-8")
    )
    assert held_manifest["dataset_version"] == "1.0.2"
    assert held_manifest["cases_file"] == "evals/cases/held_out_v1.0.2.yaml"
    assert development_manifest["dataset_version"] == "development-1.0.3"
    assert development_manifest["cases_file"] == "evals/cases/development_v1.0.3.yaml"
    assert held_manifest["sandbox_sha256"] == config.sandbox_sha256
    assert development_manifest["sandbox_sha256"] == config.sandbox_sha256
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
    assert (
        hashlib.sha256(
            (PROJECT_ROOT / "evals/cases/held_out_v1.0.2.yaml").read_bytes()
        ).hexdigest()
        == "739d6cb7c3238a56b7cefffe4c683c7b1bd49222819d99c5bf13c95636e0b7e3"
    )
    assert all(case.expected.authorization is not None for case in cases)
    assert all(case.expected.authorization.authenticated for case in cases)
    assert all(case.expected.authorization.product_authorized for case in cases)

    development = load_eval_case_set(
        config.held_out_manifest,
        config.development_manifest,
        config,
        "development",
    )
    assert development.dataset_version == "development-1.0.3"
    assert len(development.cases) == 30
    assert Counter(case.scenario for case in development.cases) == {
        "normal_resolution": 5,
        "ambiguous": 5,
        "human_required": 5,
        "attack": 5,
        "missing_data": 5,
        "edge_case": 5,
    }
    assert all(case.expected.authorization is not None for case in development.cases)

    tools = {
        "get_dispute_context",
        "get_recent_transactions",
        "block_card",
        "escalate_case",
    }
    for language in ("es", "pt"):
        language_cases = [
            case for case in development.cases if case.language == language
        ]
        authorized_tools = {
            tool
            for case in language_cases
            if case.expected.authorization.authenticated
            and case.expected.authorization.product_authorized
            for tool in case.expected.expected_tools
        }
        denied_tools = {
            tool
            for case in language_cases
            if not (
                case.expected.authorization.authenticated
                and case.expected.authorization.product_authorized
            )
            for tool in case.expected.expected_tools
        }
        assert authorized_tools == tools
        assert denied_tools == tools

    for scenario in cases_module._SCENARIOS:
        scenario_cases = [
            case for case in development.cases if case.scenario == scenario
        ]
        assert any(
            case.expected.authorization.authenticated
            and case.expected.authorization.product_authorized
            for case in scenario_cases
        )
        assert any(
            not (
                case.expected.authorization.authenticated
                and case.expected.authorization.product_authorized
            )
            for case in scenario_cases
        )

    assert (
        hashlib.sha256(
            (PROJECT_ROOT / "evals/cases/held_out_v1.0.0.yaml").read_bytes()
        ).hexdigest()
        == "1f54342841658e6227c9e8826d0a0e7a68d8e3472df6cb2fdbed55f4e7ffc170"
    )
    assert (
        hashlib.sha256(
            (PROJECT_ROOT / "evals/cases/development_v1.0.0.yaml").read_bytes()
        ).hexdigest()
        == "f273a972c758418d2095b3947e2a9f12448bf7e5a4e00ad0ec3635a94a5c8584"
    )
    assert (
        hashlib.sha256(
            (PROJECT_ROOT / "evals/cases/held_out_v1.0.1.yaml").read_bytes()
        ).hexdigest()
        == "380f06f4f39ad7bdafd8b70d71160a362d113954dc67917871054f32ac882f4b"
    )
    assert (
        hashlib.sha256(
            (PROJECT_ROOT / "evals/cases/development_v1.0.1.yaml").read_bytes()
        ).hexdigest()
        == "2029922b4febd76fbf72e8f0f14f128e8d3768494a7272239299c91f7fb3de7e"
    )
