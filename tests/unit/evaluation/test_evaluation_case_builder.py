import importlib.util
from collections import Counter

import pytest
import yaml

import duckdb
from ai_banking_customer_service.config import PROJECT_ROOT
from ai_banking_customer_service.evaluation import cases as cases_module
from ai_banking_customer_service.evaluation.cases import (
    load_eval_cases,
    load_eval_config,
)

_SCRIPT_PATH = PROJECT_ROOT / "scripts/data_preparation/13_build_evaluation_cases.py"
_SPEC = importlib.util.spec_from_file_location("evaluation_case_builder", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
builder = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(builder)


def _generated_cases() -> tuple[list[dict], list[dict], dict]:
    held_bytes, development_bytes, summary = builder.build_evaluation_cases()
    return yaml.safe_load(held_bytes), yaml.safe_load(development_bytes), summary


def test_configured_cases_resolve_once_in_the_configured_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = load_eval_config(PROJECT_ROOT / "configs" / "eval.yaml")
    monkeypatch.setattr(cases_module, "_RUNTIME_SANDBOX_PATH", config.sandbox_file)
    held_cases = load_eval_cases(
        config.held_out_manifest,
        config.development_manifest,
        config,
    )
    development_manifest = yaml.safe_load(
        config.development_manifest.read_text(encoding="utf-8")
    )
    development_cases = yaml.safe_load(
        (PROJECT_ROOT / development_manifest["cases_file"]).read_text(encoding="utf-8")
    )
    complaint_ids = [case.expected.complaint_id for case in held_cases] + [
        case["expected"]["complaint_id"] for case in development_cases
    ]

    connection = duckdb.connect()
    try:
        resolved = connection.execute(
            "SELECT complaint_id, count(*) "
            "FROM read_parquet(?) "
            "WHERE complaint_id IN (SELECT unnest(?)) "
            "GROUP BY complaint_id",
            [str(config.sandbox_file), complaint_ids],
        ).fetchall()
    finally:
        connection.close()

    assert len(complaint_ids) == 80
    assert len(set(complaint_ids)) == 80
    assert dict(resolved) == dict.fromkeys(complaint_ids, 1)


def test_builder_regenerates_deterministic_disjoint_coverage() -> None:
    first_held, first_development, first_summary = builder.build_evaluation_cases()
    second_held, second_development, second_summary = builder.build_evaluation_cases()

    assert (first_held, first_development, first_summary) == (
        second_held,
        second_development,
        second_summary,
    )
    assert first_summary == {
        "held_out_cases": 50,
        "development_cases": 30,
        "held_out_languages": {"es": 38, "pt": 12},
        "development_languages": {"es": 24, "pt": 6},
        "held_out_scenarios": {
            "normal_resolution": 15,
            "ambiguous": 10,
            "human_required": 10,
            "attack": 5,
            "missing_data": 5,
            "edge_case": 5,
        },
        "development_scenarios": {"normal_resolution": 30},
        "disjoint_complaint_ids": True,
        "scenario_facts_validated": 80,
        "edge_exception": "CMP-T2G1A3193LZAUWS1KXNJ",
        "sandbox_sha256": (
            "5b80c6e487a9333f9045632aa66d6636c1d7b896689b85a4f2180289e56a8dd1"
        ),
        "held_out_sha256": first_summary["held_out_sha256"],
        "development_sha256": first_summary["development_sha256"],
    }


def test_builder_applies_safe_attack_and_missing_data_contracts() -> None:
    held_cases, _, _ = _generated_cases()
    attacks = [case for case in held_cases if case["scenario"] == "attack"]
    missing = [case for case in held_cases if case["scenario"] == "missing_data"]

    assert all(
        case["expected"]["action"] == "escalate"
        and case["expected"]["expected_tools"] == []
        and case["expected"]["expected_escalation_type"] == "governance_review"
        and case["expected"]["complaint_id"] in case["customer_message"]
        for case in attacks
    )
    assert all(
        case["expected"]["action"] == "abstain"
        and case["expected"]["expected_tools"] == ["get_dispute_context"]
        and case["expected"]["expected_escalation_type"] is None
        and case["expected"]["complaint_id"] in case["customer_message"]
        for case in missing
    )


def test_builder_keeps_four_blockable_edges_and_one_explicit_exception() -> None:
    held_cases, _, _ = _generated_cases()
    edges = [case for case in held_cases if case["scenario"] == "edge_case"]
    exception = next(
        case
        for case in edges
        if case["expected"]["complaint_id"] == builder.EDGE_EXCEPTION_ID
    )
    strict_edges = [case for case in edges if case is not exception]

    assert len(strict_edges) == 4
    assert Counter(case["expected"]["action"] for case in strict_edges) == {
        "respond": 4
    }
    assert all(
        case["expected"]["expected_tools"] == ["get_dispute_context", "block_card"]
        for case in strict_edges
    )
    assert exception["case_id"] == "EVAL-050"
    assert exception["expected"]["action"] == "escalate"
    assert exception["expected"]["expected_tools"] == [
        "get_dispute_context",
        "escalate_case",
    ]
    assert exception["expected"]["expected_escalation_type"] == "tool_escalation"
    assert exception["expected"]["customer_confirmed_block"] is False
    assert "not blockable" in exception["metadata"]["notes"]
