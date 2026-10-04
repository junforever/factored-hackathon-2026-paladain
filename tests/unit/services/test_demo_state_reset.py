from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest
import yaml

import duckdb
from ai_banking_customer_service.services import card_service, escalation_service

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "reset_demo_state.py"


def _load_reset_module():
    spec = importlib.util.spec_from_file_location("reset_demo_state", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    sandbox_path = tmp_path / "sandbox.parquet"
    with duckdb.connect() as connection:
        connection.execute(
            "COPY (SELECT * FROM VALUES "
            "('CMP-DEMO', 'PROD-DEMO'), ('CMP-OTHER', 'PROD-OTHER') "
            "AS cases(complaint_id, product_id)) TO ? (FORMAT PARQUET)",
            [str(sandbox_path)],
        )
    catalog_path = tmp_path / "demo_cases.yaml"
    catalog_path.write_text(
        yaml.safe_dump({"cases": [{"complaint_id": "CMP-DEMO"}]}),
        encoding="utf-8",
    )
    return catalog_path, sandbox_path


def test_reset_removes_only_catalog_case_state_and_preserves_files(tmp_path: Path):
    reset = _load_reset_module()
    catalog_path, sandbox_path = _write_inputs(tmp_path)
    card_db = tmp_path / "state" / "card_service.sqlite3"
    escalation_db = tmp_path / "state" / "escalation_service.sqlite3"
    preserved = {
        tmp_path / "audit.jsonl": b'{"event":"keep"}\n',
        tmp_path / "bank.duckdb": b"keep-duckdb",
        tmp_path / "source.parquet": b"keep-parquet",
    }
    for path, content in preserved.items():
        path.write_bytes(content)

    card_service.block_card("PROD-DEMO", "CMP-DEMO", "demo", db_path=card_db)
    card_service.block_card("PROD-OTHER", "CMP-OTHER", "other", db_path=card_db)
    escalation_service.create_escalation(
        "CMP-DEMO", "CUS-WRONG", "PROD-DEMO", "demo", "Medium", {},
        db_path=escalation_db,
    )
    other = escalation_service.create_escalation(
        "CMP-OTHER", "CUS-OTHER", "PROD-OTHER", "other", "Medium", {},
        db_path=escalation_db,
    )
    same_product_other_case = escalation_service.create_escalation(
        "CMP-OTHER-SAME-PRODUCT",
        "CUS-OTHER",
        "PROD-DEMO",
        "other",
        "Medium",
        {},
        db_path=escalation_db,
    )

    result = reset.reset_demo_state(
        catalog_path=catalog_path,
        sandbox_path=sandbox_path,
        card_db_path=card_db,
        escalation_db_path=escalation_db,
    )

    assert result["complaint_ids"] == ["CMP-DEMO"]
    assert result["product_ids"] == ["PROD-DEMO"]
    assert result["card_service"]["affected"] == {
        "blocked_cards": 1,
        "actions_log": 1,
    }
    assert result["escalation_service"]["affected"] == {"escalations": 1}
    assert card_service.is_card_blocked("PROD-DEMO", db_path=card_db) is False
    assert card_service.is_card_blocked("PROD-OTHER", db_path=card_db) is True
    assert escalation_service.get_escalation(
        other["escalation_id"], db_path=escalation_db
    ) is not None
    assert escalation_service.get_escalation(
        same_product_other_case["escalation_id"], db_path=escalation_db
    ) is not None
    for path, content in preserved.items():
        assert path.read_bytes() == content

    with sqlite3.connect(card_db) as connection:
        assert connection.execute(
            "SELECT complaint_id FROM actions_log"
        ).fetchall() == [("CMP-OTHER",)]


def test_dry_run_case_selection_and_repeated_reset_are_safe(tmp_path: Path):
    reset = _load_reset_module()
    sandbox_path = tmp_path / "sandbox.parquet"
    with duckdb.connect() as connection:
        connection.execute(
            "COPY (SELECT * FROM VALUES "
            "('CMP-ONE', 'PROD-ONE'), ('CMP-TWO', 'PROD-TWO') "
            "AS cases(complaint_id, product_id)) TO ? (FORMAT PARQUET)",
            [str(sandbox_path)],
        )
    catalog_path = tmp_path / "demo_cases.yaml"
    catalog_path.write_text(
        yaml.safe_dump(
            {"cases": [{"complaint_id": "CMP-ONE"}, {"complaint_id": "CMP-TWO"}]}
        ),
        encoding="utf-8",
    )
    card_db = tmp_path / "card.sqlite3"
    escalation_db = tmp_path / "escalation.sqlite3"
    for complaint_id, product_id in (("CMP-ONE", "PROD-ONE"), ("CMP-TWO", "PROD-TWO")):
        card_service.block_card(product_id, complaint_id, "demo", db_path=card_db)
        escalation_service.create_escalation(
            complaint_id,
            "CUS-IGNORED",
            product_id,
            "demo",
            "Medium",
            {},
            db_path=escalation_db,
        )

    dry_run = reset.reset_demo_state(
        catalog_path=catalog_path,
        sandbox_path=sandbox_path,
        card_db_path=card_db,
        escalation_db_path=escalation_db,
        complaint_id="CMP-ONE",
        dry_run=True,
    )

    assert dry_run["product_ids"] == ["PROD-ONE"]
    assert dry_run["card_service"]["affected"]["blocked_cards"] == 1
    assert dry_run["escalation_service"]["affected"]["escalations"] == 1
    assert card_service.is_card_blocked("PROD-ONE", db_path=card_db) is True

    first = reset.reset_demo_state(
        catalog_path=catalog_path,
        sandbox_path=sandbox_path,
        card_db_path=card_db,
        escalation_db_path=escalation_db,
        complaint_id="CMP-ONE",
    )
    second = reset.reset_demo_state(
        catalog_path=catalog_path,
        sandbox_path=sandbox_path,
        card_db_path=card_db,
        escalation_db_path=escalation_db,
        complaint_id="CMP-ONE",
    )

    assert first["card_service"]["affected"]["blocked_cards"] == 1
    assert second["card_service"]["affected"] == {
        "blocked_cards": 0,
        "actions_log": 0,
    }
    assert second["escalation_service"]["affected"] == {"escalations": 0}
    assert card_service.is_card_blocked("PROD-TWO", db_path=card_db) is True


def test_invalid_selection_fails_before_mutating_state(tmp_path: Path):
    reset = _load_reset_module()
    catalog_path, sandbox_path = _write_inputs(tmp_path)
    card_db = tmp_path / "card.sqlite3"
    card_service.block_card("PROD-DEMO", "CMP-DEMO", "demo", db_path=card_db)

    with pytest.raises(ValueError, match="not in the demo catalog"):
        reset.reset_demo_state(
            catalog_path=catalog_path,
            sandbox_path=sandbox_path,
            card_db_path=card_db,
            escalation_db_path=tmp_path / "escalation.sqlite3",
            complaint_id="CMP-NOT-CATALOGED",
        )

    assert card_service.is_card_blocked("PROD-DEMO", db_path=card_db) is True


def test_locked_and_invalid_databases_fail_without_deleting_files(tmp_path: Path):
    card_db = tmp_path / "card.sqlite3"
    card_service.block_card("PROD-DEMO", "CMP-DEMO", "demo", db_path=card_db)
    lock = sqlite3.connect(card_db, timeout=0, isolation_level=None)
    lock.execute("BEGIN IMMEDIATE")
    try:
        locked = card_service.reset_demo_state(["PROD-DEMO"], db_path=card_db)
        assert locked["success"] is False
        assert "locked" in locked["error"]
        assert card_db.is_file()
    finally:
        lock.execute("ROLLBACK")
        lock.close()
    assert card_service.is_card_blocked("PROD-DEMO", db_path=card_db) is True

    invalid_db = tmp_path / "invalid.sqlite3"
    original = b"not a sqlite database"
    invalid_db.write_bytes(original)
    invalid = escalation_service.reset_demo_state(
        ["CMP-DEMO"], db_path=invalid_db
    )

    assert invalid["success"] is False
    assert invalid["verification"] == "reset_failed_db_error"
    assert invalid_db.read_bytes() == original


def test_cli_returns_nonzero_for_controlled_reset_error(monkeypatch, capsys):
    reset = _load_reset_module()

    def fail(**_kwargs):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(reset, "reset_demo_state", fail)

    assert reset.main(["--dry-run"]) == 1
    assert "Reset failed: database is locked" in capsys.readouterr().err
