from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "data_preparation" / "12_build_demo_cases.py"
SANDBOX_PATH = PROJECT_ROOT / "data" / "sandbox" / "agent_sandbox_final.parquet"
CATALOG_PATH = PROJECT_ROOT / "configs" / "demo_cases.yaml"
SCENARIOS = {
    "normal_resolution",
    "ambiguous",
    "human_required",
    "attack",
    "missing_data",
    "edge_case",
}
REQUIRED_CASE_FIELDS = {
    "scenario",
    "complaint_id",
    "language",
    "purpose",
    "starter_prompt",
    "expected_behavior",
    "selection_criteria",
}


def _load_generator():
    spec = importlib.util.spec_from_file_location("build_demo_cases", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generator_builds_versioned_catalog_with_real_unique_cases(tmp_path):
    generator = _load_generator()
    output_path = tmp_path / "demo_cases.yaml"

    catalog = generator.generate_catalog(SANDBOX_PATH, output_path)

    assert catalog["catalog_version"] == "1.0.0"
    assert catalog["source"] == "data/sandbox/agent_sandbox_final.parquet"
    cases = catalog["cases"]
    assert len(cases) == 6
    assert {case["scenario"] for case in cases} == SCENARIOS
    assert all(set(case) == REQUIRED_CASE_FIELDS for case in cases)

    complaint_ids = [case["complaint_id"] for case in cases]
    assert len(complaint_ids) == len(set(complaint_ids))
    assert all(case["language"] in {"es", "pt"} for case in cases)
    assert all(case["complaint_id"] in case["starter_prompt"] for case in cases)
    assert all(
        case[field].strip()
        for case in cases
        for field in ("purpose", "starter_prompt", "expected_behavior")
    )

    with duckdb.connect() as connection:
        sandbox_rows = connection.execute(
            "SELECT complaint_id, product_id FROM read_parquet(?)",
            [str(SANDBOX_PATH)],
        ).fetchall()
    sandbox_by_id = {
        complaint_id: product_id for complaint_id, product_id in sandbox_rows
    }
    assert set(complaint_ids) <= sandbox_by_id.keys()
    assert all(sandbox_by_id[complaint_id] for complaint_id in complaint_ids)


def test_generation_is_deterministic_and_matches_versioned_artifact(tmp_path):
    generator = _load_generator()
    first_path = tmp_path / "first.yaml"
    second_path = tmp_path / "second.yaml"

    generator.generate_catalog(SANDBOX_PATH, first_path)
    generator.generate_catalog(SANDBOX_PATH, second_path)

    assert first_path.read_bytes() == second_path.read_bytes()
    assert first_path.read_bytes() == CATALOG_PATH.read_bytes()
    assert yaml.safe_load(first_path.read_text(encoding="utf-8"))["cases"]


def test_generator_fails_without_a_candidate_and_writes_nothing(tmp_path, monkeypatch):
    generator = _load_generator()
    impossible_specs = list(generator._CASE_SPECS)
    impossible_specs[0] = {**impossible_specs[0], "where": "1 = 0"}
    monkeypatch.setattr(generator, "_CASE_SPECS", tuple(impossible_specs))
    output_path = tmp_path / "demo_cases.yaml"

    with pytest.raises(ValueError, match="No sandbox candidate for normal_resolution"):
        generator.generate_catalog(SANDBOX_PATH, output_path)

    assert not output_path.exists()
