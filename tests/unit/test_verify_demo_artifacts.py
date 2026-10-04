import hashlib
import importlib.util
from pathlib import Path

import pytest

import duckdb

SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "verify_demo_artifacts.py"
SPEC = importlib.util.spec_from_file_location("verify_demo_artifacts", SCRIPT_PATH)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def _sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def _write_manifest(root: Path, database_hash: str | None = None) -> Path:
    database_path = root / "duckdb" / "ai_banking.duckdb"
    sandbox_path = root / "data" / "sandbox" / "agent_sandbox_final.parquet"
    manifest_path = root / "demo-artifacts.sha256"
    manifest_path.write_text(
        f"{database_hash or _sha256(database_path)}  duckdb/ai_banking.duckdb\n"
        f"{_sha256(sandbox_path)}  data/sandbox/agent_sandbox_final.parquet\n",
        encoding="utf-8",
    )
    return manifest_path


def _artifacts(
    tmp_path: Path,
    database_sql: str = (
        "CREATE TABLE raw_transactions AS "
        "SELECT * FROM (VALUES ('TX-1', 'PROD-1')) "
        "AS transactions(transaction_id, product_id)"
    ),
) -> Path:
    database_path = tmp_path / "duckdb" / "ai_banking.duckdb"
    sandbox_path = tmp_path / "data" / "sandbox" / "agent_sandbox_final.parquet"
    database_path.parent.mkdir(parents=True)
    sandbox_path.parent.mkdir(parents=True)
    with duckdb.connect(str(database_path)) as connection:
        connection.execute(database_sql)
    with duckdb.connect() as connection:
        connection.execute(
            "COPY (SELECT 'PROD-1' AS product_id) TO ? (FORMAT PARQUET)",
            [str(sandbox_path)],
        )
    return _write_manifest(tmp_path)


def test_verifies_hashes_and_portable_database(tmp_path):
    manifest_path = _artifacts(tmp_path)

    result = verifier.verify_demo_artifacts(tmp_path, manifest_path)

    assert result == 1


def test_rejects_missing_artifact(tmp_path):
    manifest_path = tmp_path / "demo-artifacts.sha256"
    manifest_path.write_text(
        f"{'0' * 64}  duckdb/ai_banking.duckdb\n"
        f"{'0' * 64}  data/sandbox/agent_sandbox_final.parquet\n",
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="duckdb/ai_banking.duckdb"):
        verifier.verify_demo_artifacts(tmp_path, manifest_path)


def test_rejects_checksum_mismatch(tmp_path):
    manifest_path = _artifacts(tmp_path)
    _write_manifest(tmp_path, database_hash="0" * 64)

    with pytest.raises(ValueError, match="Checksum mismatch.*ai_banking.duckdb"):
        verifier.verify_demo_artifacts(tmp_path, manifest_path)


def test_rejects_malformed_manifest_entry(tmp_path):
    manifest_path = tmp_path / "demo-artifacts.sha256"
    manifest_path.write_text("not a checksum entry\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed manifest entry on line 1"):
        verifier.verify_demo_artifacts(tmp_path, manifest_path)


@pytest.mark.parametrize(
    ("database_sql", "message"),
    [
        (
            "CREATE TABLE other_table (value INTEGER)",
            "raw_transactions must be a BASE TABLE.*missing",
        ),
        (
            "CREATE VIEW raw_transactions AS "
            "SELECT 'TX-1' AS transaction_id, 'PROD-1' AS product_id",
            "raw_transactions must be a BASE TABLE.*VIEW",
        ),
        (
            "CREATE TABLE raw_transactions (transaction_id VARCHAR)",
            "raw_transactions must contain product_id",
        ),
        (
            "CREATE TABLE raw_transactions "
            "(transaction_id VARCHAR, product_id VARCHAR)",
            "raw_transactions must not be empty",
        ),
        (
            "CREATE TABLE raw_transactions AS "
            "SELECT 'TX-1' AS transaction_id, 'PROD-ABSENT' AS product_id",
            "product_id is absent from the sandbox",
        ),
    ],
)
def test_rejects_invalid_duckdb_structure(tmp_path, database_sql, message):
    manifest_path = _artifacts(tmp_path, database_sql)

    with pytest.raises(ValueError, match=message):
        verifier.verify_demo_artifacts(tmp_path, manifest_path)
