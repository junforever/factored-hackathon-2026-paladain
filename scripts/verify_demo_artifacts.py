"""Verify the checksums and structure of portable demo artifacts."""

import argparse
import hashlib
import re
import sys
from pathlib import Path

import duckdb

EXPECTED_ARTIFACTS = (
    "duckdb/ai_banking.duckdb",
    "data/sandbox/agent_sandbox_final.parquet",
)
_MANIFEST_LINE = re.compile(r"([0-9a-fA-F]{64})  (.+)")


def _read_manifest(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"Manifest does not exist: {path}")

    entries: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        match = _MANIFEST_LINE.fullmatch(line)
        if not match:
            raise ValueError(
                f"Malformed manifest entry on line {line_number}: {line!r}"
            )
        checksum, relative_path = match.groups()
        if relative_path in entries:
            raise ValueError(f"Duplicate manifest path: {relative_path}")
        entries[relative_path] = checksum.lower()

    if set(entries) != set(EXPECTED_ARTIFACTS):
        raise ValueError(
            "Manifest must contain exactly: " + ", ".join(EXPECTED_ARTIFACTS)
        )
    return entries


def _sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def verify_demo_artifacts(
    root: str | Path = ".", manifest: str | Path = "demo-artifacts.sha256"
) -> int:
    """Verify artifact hashes and return the portable transaction row count."""
    root_path = Path(root).resolve()
    manifest_path = Path(manifest)
    if not manifest_path.is_absolute():
        manifest_path = root_path / manifest_path
    entries = _read_manifest(manifest_path)

    for relative_path, expected_checksum in entries.items():
        artifact_path = root_path / relative_path
        if not artifact_path.is_file():
            raise FileNotFoundError(f"Artifact does not exist: {relative_path}")
        actual_checksum = _sha256(artifact_path)
        if actual_checksum != expected_checksum:
            raise ValueError(
                f"Checksum mismatch for {relative_path}: "
                f"expected {expected_checksum}, got {actual_checksum}"
            )

    database_path = root_path / EXPECTED_ARTIFACTS[0]
    sandbox_path = root_path / EXPECTED_ARTIFACTS[1]
    with duckdb.connect(str(database_path), read_only=True) as connection:
        object_type = connection.execute(
            "SELECT table_type FROM information_schema.tables "
            "WHERE table_catalog = current_database() "
            "AND table_schema = 'main' AND table_name = 'raw_transactions'"
        ).fetchone()
        if object_type != ("BASE TABLE",):
            actual_type = object_type[0] if object_type else "missing"
            raise ValueError(
                f"DuckDB raw_transactions must be a BASE TABLE (found {actual_type})"
            )
        columns = {
            row[0]
            for row in connection.execute(
                "DESCRIBE SELECT * FROM main.raw_transactions"
            ).fetchall()
        }
        if "product_id" not in columns:
            raise ValueError("DuckDB raw_transactions must contain product_id")
        row_count = connection.execute(
            "SELECT count(*) FROM main.raw_transactions"
        ).fetchone()[0]
        if row_count == 0:
            raise ValueError("DuckDB raw_transactions must not be empty")
        absent_count = connection.execute(
            "SELECT count(*) FROM main.raw_transactions AS transactions "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM read_parquet(?) AS sandbox "
            "WHERE sandbox.product_id = transactions.product_id)",
            [str(sandbox_path)],
        ).fetchone()[0]
        if absent_count:
            raise ValueError(
                f"DuckDB contains {absent_count} transaction(s) whose product_id "
                "is absent from the sandbox"
            )

    return row_count


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--manifest", type=Path, default=Path("demo-artifacts.sha256"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        row_count = verify_demo_artifacts(args.root, args.manifest)
    except Exception as error:
        print(f"ERROR: artifact verification failed: {error}", file=sys.stderr)
        return 1

    print(f"Verified {len(EXPECTED_ARTIFACTS)} demo artifacts ({row_count} rows).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
