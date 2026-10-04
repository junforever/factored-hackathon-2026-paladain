"""Build a portable DuckDB containing sandbox-relevant transactions only."""

import argparse
import os
import sys
import tempfile
from pathlib import Path

import duckdb

DEFAULT_DATABASE = Path("duckdb/ai_banking.duckdb")
DEFAULT_SANDBOX = Path("data/sandbox/agent_sandbox_final.parquet")


def _sql_string(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def _schema(
    connection: duckdb.DuckDBPyConnection, relation: str
) -> list[tuple[str, str]]:
    return [
        (row[0], row[1])
        for row in connection.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()
    ]


def build_portable_demo(
    source: str | Path, sandbox: str | Path, destination: str | Path
) -> int:
    """Build and atomically install a validated portable database."""
    source_path = Path(source).resolve()
    sandbox_path = Path(sandbox).resolve()
    destination_path = Path(destination).resolve()

    if not source_path.is_file():
        raise FileNotFoundError(f"Source DuckDB does not exist: {source_path}")
    if not sandbox_path.is_file():
        raise FileNotFoundError(f"Sandbox Parquet does not exist: {sandbox_path}")

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=destination_path.parent, prefix=f".{destination_path.name}."
    ) as temporary_directory:
        temporary_path = Path(temporary_directory) / destination_path.name
        with duckdb.connect(str(temporary_path)) as connection:
            connection.execute(
                f"ATTACH {_sql_string(source_path)} AS source_db (READ_ONLY)"
            )
            source_schema = _schema(connection, "source_db.raw_transactions")
            if "product_id" not in {name for name, _ in source_schema}:
                raise ValueError("source raw_transactions must contain product_id")
            sandbox_columns = {
                row[0]
                for row in connection.execute(
                    f"DESCRIBE SELECT * FROM read_parquet({_sql_string(sandbox_path)})"
                ).fetchall()
            }
            if "product_id" not in sandbox_columns:
                raise ValueError("sandbox Parquet must contain product_id")

            expected_count = connection.execute(
                "SELECT count(*) FROM source_db.raw_transactions "
                "WHERE product_id IN "
                "(SELECT product_id FROM read_parquet(?))",
                [str(sandbox_path)],
            ).fetchone()[0]
            connection.execute(
                "CREATE TABLE raw_transactions AS "
                "SELECT * FROM source_db.raw_transactions "
                "WHERE product_id IN "
                f"(SELECT product_id FROM read_parquet({_sql_string(sandbox_path)}))"
            )
            object_type = connection.execute(
                "SELECT table_type FROM information_schema.tables "
                "WHERE table_catalog = current_database() "
                "AND table_schema = 'main' AND table_name = 'raw_transactions'"
            ).fetchone()
            output_schema = _schema(connection, "main.raw_transactions")
            output_count = connection.execute(
                "SELECT count(*) FROM main.raw_transactions"
            ).fetchone()[0]

            if object_type != ("BASE TABLE",):
                raise RuntimeError(
                    "Validation failed: raw_transactions is not a BASE TABLE"
                )
            if output_schema != source_schema:
                raise RuntimeError("Validation failed: raw_transactions schema changed")
            if output_count != expected_count:
                raise RuntimeError(
                    "Validation failed: raw_transactions row count differs "
                    "from source query"
                )

        os.replace(temporary_path, destination_path)

    return output_count


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a portable DuckDB with raw_transactions filtered to product IDs "
            "in the sandbox Parquet."
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_DATABASE,
        help=f"source DuckDB (default: {DEFAULT_DATABASE})",
    )
    parser.add_argument(
        "--sandbox",
        type=Path,
        default=DEFAULT_SANDBOX,
        help=f"sandbox Parquet (default: {DEFAULT_SANDBOX})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DATABASE,
        help=(
            "destination DuckDB, which may equal --source "
            f"(default: {DEFAULT_DATABASE})"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        row_count = build_portable_demo(args.source, args.sandbox, args.output)
    except Exception as error:
        print(f"ERROR: portable DuckDB was not installed: {error}", file=sys.stderr)
        return 1

    print(f"Portable DuckDB installed at {args.output} ({row_count} rows).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
