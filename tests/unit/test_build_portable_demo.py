import importlib.util
from pathlib import Path

import pytest

import duckdb

SCRIPT_PATH = (
    Path(__file__).parents[2]
    / "scripts"
    / "data_preparation"
    / "11_build_portable_demo.py"
)
SPEC = importlib.util.spec_from_file_location("build_portable_demo", SCRIPT_PATH)
assert SPEC and SPEC.loader
portable_demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(portable_demo)


def _sql_string(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def test_builds_filtered_materialized_table_with_source_schema(tmp_path):
    csv_path = tmp_path / "transactions.csv"
    csv_path.write_text(
        "transaction_id,product_id,amount\n"
        "TX-1,PROD-1,10.25\n"
        "TX-2,PROD-2,20.50\n"
        "TX-3,PROD-1,30.75\n",
        encoding="utf-8",
    )
    source_path = tmp_path / "source.duckdb"
    sandbox_path = tmp_path / "sandbox.parquet"
    destination_path = source_path

    with duckdb.connect(str(source_path)) as connection:
        connection.execute(
            "CREATE VIEW raw_transactions AS SELECT * FROM read_csv_auto("
            f"{_sql_string(csv_path)})"
        )
        source_schema = connection.execute(
            "DESCRIBE SELECT * FROM raw_transactions"
        ).fetchall()
    with duckdb.connect() as connection:
        connection.execute(
            "COPY (SELECT * FROM (VALUES ('PROD-1')) AS sandbox(product_id)) "
            f"TO {_sql_string(sandbox_path)} (FORMAT PARQUET)"
        )

    portable_demo.build_portable_demo(source_path, sandbox_path, destination_path)

    with duckdb.connect(str(destination_path), read_only=True) as connection:
        object_type = connection.execute(
            "SELECT table_type FROM information_schema.tables "
            "WHERE table_name = 'raw_transactions'"
        ).fetchone()
        destination_schema = connection.execute(
            "DESCRIBE SELECT * FROM raw_transactions"
        ).fetchall()
        rows = connection.execute(
            "SELECT * FROM raw_transactions ORDER BY transaction_id"
        ).fetchall()

    assert object_type == ("BASE TABLE",)
    assert destination_schema == source_schema
    assert rows == [("TX-1", "PROD-1", 10.25), ("TX-3", "PROD-1", 30.75)]


def test_failure_preserves_same_path_database_and_removes_temporary_output(tmp_path):
    database_path = tmp_path / "source.duckdb"
    invalid_sandbox_path = tmp_path / "invalid.parquet"
    with duckdb.connect(str(database_path)) as connection:
        connection.execute(
            "CREATE TABLE raw_transactions (transaction_id VARCHAR, product_id VARCHAR)"
        )
    with duckdb.connect() as connection:
        connection.execute(
            "COPY (SELECT 1 AS wrong_column) "
            f"TO {_sql_string(invalid_sandbox_path)} (FORMAT PARQUET)"
        )
    original_bytes = database_path.read_bytes()

    with pytest.raises(ValueError, match="sandbox.*product_id"):
        portable_demo.build_portable_demo(
            database_path, invalid_sandbox_path, database_path
        )

    assert database_path.read_bytes() == original_bytes
    assert list(tmp_path.glob(f".{database_path.name}.*")) == []
