"""
Servicio mock de escalamiento.

Persiste los Structured JSON Handoffs para el equipo humano.
Usa SQLite para atomicidad y concurrencia segura.

IMPORTANTE: Servicio sintético para el prototipo.
En producción se integraría con el sistema de tickets del banco.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
STATE_PATH = Path(os.getenv("STATE_PATH")) if os.getenv("STATE_PATH") else None


def _get_conn() -> sqlite3.Connection:
    """Abre una conexión SQLite configurada para concurrencia."""

    if not STATE_PATH:
        raise ValueError("La variable de entorno STATE_PATH no está configurada")

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(STATE_PATH), timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Crea la tabla de escalamientos si no existe."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS escalations (
            escalation_id TEXT PRIMARY KEY,
            complaint_id  TEXT NOT NULL,
            customer_id   TEXT NOT NULL,
            product_id    TEXT,
            reason        TEXT NOT NULL,
            priority      TEXT NOT NULL,
            status        TEXT NOT NULL,
            handoff_json  TEXT NOT NULL,
            created_at    TEXT NOT NULL
        )
    """)


def create_escalation(
    complaint_id: str,
    customer_id: str,
    product_id: str,
    reason: str,
    priority: str,
    handoff: dict,
) -> dict:
    """
    Persiste un escalamiento con su handoff estructurado.

    Returns:
        dict con success, escalation_id y verificación.
    """
    conn = _get_conn()
    try:
        _init_schema(conn)

        escalation_id = f"ESC-{uuid.uuid4().hex[:12].upper()}"
        created_at = datetime.now().isoformat()

        conn.execute("BEGIN IMMEDIATE")

        conn.execute(
            """
            INSERT INTO escalations
                (escalation_id, complaint_id, customer_id, product_id,
                 reason, priority, status, handoff_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                escalation_id,
                complaint_id,
                customer_id,
                product_id,
                reason,
                priority,
                "Open",
                json.dumps(handoff, ensure_ascii=False, default=str),
                created_at,
            ),
        )

        conn.execute("COMMIT")

        # VERIFICACIÓN: releer y confirmar que quedó persistido
        verified = (
            conn.execute(
                "SELECT escalation_id FROM escalations WHERE escalation_id = ?",
                (escalation_id,),
            ).fetchone()
            is not None
        )

        if verified:
            return {
                "success": True,
                "escalation_id": escalation_id,
                "created_at": created_at,
                "verification": "confirmed_persisted",
            }
        else:
            return {
                "success": False,
                "error": "Escalation failed verification",
                "verification": "escalation_not_confirmed",
            }

    except sqlite3.Error as e:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        return {
            "success": False,
            "error": f"Database error: {str(e)}",
            "verification": "escalation_failed_db_error",
        }
    finally:
        conn.close()


def get_escalation(escalation_id: str) -> dict | None:
    """Consulta un escalamiento por su ID."""
    conn = _get_conn()
    try:
        _init_schema(conn)
        row = conn.execute(
            "SELECT handoff_json, status, created_at FROM escalations WHERE escalation_id = ?",
            (escalation_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "handoff": json.loads(row[0]),
            "status": row[1],
            "created_at": row[2],
        }
    finally:
        conn.close()
