"""Safely reset mutable SQLite state for cataloged local demo cases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

import duckdb
from ai_banking_customer_service.config import PROJECT_ROOT, settings
from ai_banking_customer_service.services import card_service, escalation_service

CATALOG_PATH = PROJECT_ROOT / "configs" / "demo_cases.yaml"
CARD_DB_PATH = settings.state_dir / "card_service.sqlite3"
ESCALATION_DB_PATH = settings.state_dir / "escalation_service.sqlite3"


def _load_scope(
    catalog_path: Path,
    sandbox_path: Path,
    selected_complaint_id: str | None,
) -> tuple[list[str], list[str]]:
    if not catalog_path.is_file():
        raise FileNotFoundError(f"Demo catalog not found: {catalog_path}")
    if not sandbox_path.is_file():
        raise FileNotFoundError(f"Sandbox not found: {sandbox_path}")

    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    cases = catalog.get("cases") if isinstance(catalog, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError("Demo catalog must contain a non-empty cases list")
    complaint_ids = [
        case.get("complaint_id") if isinstance(case, dict) else None for case in cases
    ]
    if any(not isinstance(value, str) or not value.strip() for value in complaint_ids):
        raise ValueError("Every demo case must contain a complaint_id")
    if len(complaint_ids) != len(set(complaint_ids)):
        raise ValueError("Demo catalog complaint IDs must be unique")
    if selected_complaint_id is not None:
        if selected_complaint_id not in complaint_ids:
            raise ValueError(
                f"Case is not in the demo catalog: {selected_complaint_id}"
            )
        complaint_ids = [selected_complaint_id]

    product_ids = []
    with duckdb.connect() as connection:
        for complaint_id in complaint_ids:
            rows = connection.execute(
                "SELECT DISTINCT product_id FROM read_parquet(?) "
                "WHERE complaint_id = ?",
                [str(sandbox_path), complaint_id],
            ).fetchall()
            if len(rows) != 1 or not rows[0][0]:
                raise ValueError(
                    "Catalog complaint must map to exactly one product_id in the "
                    f"sandbox: {complaint_id}"
                )
            product_ids.append(str(rows[0][0]))
    return complaint_ids, product_ids


def reset_demo_state(
    *,
    catalog_path: Path = CATALOG_PATH,
    sandbox_path: Path = settings.sandbox_full_path,
    card_db_path: Path = CARD_DB_PATH,
    escalation_db_path: Path = ESCALATION_DB_PATH,
    complaint_id: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Reset exact catalog state and return verified per-service counts."""
    complaint_ids, product_ids = _load_scope(
        Path(catalog_path), Path(sandbox_path), complaint_id
    )
    card_result = card_service.reset_demo_state(
        product_ids, db_path=Path(card_db_path), dry_run=dry_run
    )
    if not card_result["success"]:
        raise RuntimeError(f"Card service reset failed: {card_result['error']}")
    escalation_result = escalation_service.reset_demo_state(
        complaint_ids, db_path=Path(escalation_db_path), dry_run=dry_run
    )
    if not escalation_result["success"]:
        raise RuntimeError(
            f"Escalation service reset failed: {escalation_result['error']}"
        )
    return {
        "dry_run": dry_run,
        "complaint_ids": complaint_ids,
        "product_ids": product_ids,
        "card_service": card_result,
        "escalation_service": escalation_result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reset mutable state for cataloged local demo cases."
    )
    parser.add_argument(
        "--case", metavar="COMPLAINT_ID", help="reset one cataloged complaint"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report matching rows without deleting"
    )
    args = parser.parse_args(argv)
    try:
        report = reset_demo_state(complaint_id=args.case, dry_run=args.dry_run)
    except Exception as error:  # CLI boundary: all failures must return nonzero.
        print(f"Reset failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
