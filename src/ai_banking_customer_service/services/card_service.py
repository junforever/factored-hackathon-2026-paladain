"""
Servicio mock de tarjetas (almacenamiento SQLite).

Simula la API del banco para acciones de tarjetas.
Usa SQLite para garantizar atomicidad y concurrencia segura.

IMPORTANTE: Esto es un servicio sintético para el prototipo.
En producción sería la API real del banco.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from ai_banking_customer_service.config import settings

STATE_PATH: Path = settings.state_dir / "card_service.sqlite3"


def _get_conn(db_path: Path | None = None) -> sqlite3.Connection:
    """
    Abre una conexión SQLite configurada para concurrencia.

    - timeout=30: espera hasta 30s si la BD está bloqueada por otra escritura.
    - isolation_level=None: autocommit, para controlar transacciones manualmente.
    - WAL mode: permite múltiples lectores concurrentes sin bloquearse.
    """
    resolved_path = STATE_PATH if db_path is None else db_path
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved_path), timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Crea las tablas si no existen (idempotente)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blocked_cards (
            product_id   TEXT PRIMARY KEY,
            blocked_at   TEXT NOT NULL,
            complaint_id TEXT NOT NULL,
            reason       TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS actions_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            action       TEXT NOT NULL,
            product_id   TEXT NOT NULL,
            complaint_id TEXT,
            timestamp    TEXT NOT NULL
        )
    """)


def block_card(
    product_id: str,
    complaint_id: str,
    reason: str,
    *,
    db_path: Path | None = None,
) -> dict:
    """
    Bloquea una tarjeta de forma atómica y verifica el resultado.

    Returns:
        dict con success, verification y metadatos.
    """
    conn = _get_conn(db_path)
    try:
        _init_schema(conn)
        now = datetime.now().isoformat()

        # BEGIN IMMEDIATE adquiere el lock de escritura desde el inicio.
        # Esto evita la race condition entre "verificar" y "bloquear".
        conn.execute("BEGIN IMMEDIATE")

        # 1. Verificar si ya está bloqueada (dentro de la transacción)
        row = conn.execute(
            "SELECT blocked_at FROM blocked_cards WHERE product_id = ?",
            (product_id,),
        ).fetchone()

        if row is not None:
            conn.execute("ROLLBACK")
            return {
                "success": False,
                "already_blocked": True,
                "product_id": product_id,
                "blocked_at": row[0],
                "verification": "already_blocked_no_action_taken",
            }

        # 2. Ejecutar el bloqueo
        conn.execute(
            "INSERT INTO blocked_cards (product_id, blocked_at, complaint_id, reason) "
            "VALUES (?, ?, ?, ?)",
            (product_id, now, complaint_id, reason),
        )

        # 3. Registrar en el log de auditoría
        conn.execute(
            "INSERT INTO actions_log (action, product_id, complaint_id, timestamp) "
            "VALUES (?, ?, ?, ?)",
            ("block_card", product_id, complaint_id, now),
        )

        conn.execute("COMMIT")

        # 4. VERIFICACIÓN: releer y confirmar que quedó bloqueada
        verified = (
            conn.execute(
                "SELECT 1 FROM blocked_cards WHERE product_id = ?",
                (product_id,),
            ).fetchone()
            is not None
        )

        if verified:
            return {
                "success": True,
                "product_id": product_id,
                "blocked_at": now,
                "verification": "confirmed_blocked",
            }
        else:
            return {
                "success": False,
                "error": "Block failed verification",
                "verification": "block_not_confirmed",
            }

    except sqlite3.Error as e:
        # Ante cualquier error de BD, revertir cambios.
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        return {
            "success": False,
            "error": f"Database error: {str(e)}",
            "verification": "block_failed_db_error",
        }
    finally:
        conn.close()


def is_card_blocked(
    product_id: str,
    *,
    db_path: Path | None = None,
) -> bool:
    """Consulta si una tarjeta está bloqueada (operación de solo lectura)."""
    conn = _get_conn(db_path)
    try:
        _init_schema(conn)
        row = conn.execute(
            "SELECT 1 FROM blocked_cards WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def reset_demo_state(
    product_ids: list[str],
    *,
    db_path: Path | None = None,
    dry_run: bool = False,
) -> dict:
    """Remove card state for exact sandbox-derived products without deleting files."""
    resolved_path = STATE_PATH if db_path is None else db_path
    affected = {"blocked_cards": 0, "actions_log": 0}
    if not product_ids or not resolved_path.is_file():
        return {
            "success": True,
            "affected": affected,
            "verification": "dry_run_no_changes" if dry_run else "confirmed_reset",
        }

    product_ids = sorted(set(product_ids))
    placeholders = ", ".join("?" for _ in product_ids)
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(
            resolved_path.resolve().as_uri() + "?mode=rw",
            timeout=0,
            isolation_level=None,
            uri=True,
        )
        if not dry_run:
            conn.execute("BEGIN IMMEDIATE")
        for table in affected:
            affected[table] = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE product_id IN ({placeholders})",
                product_ids,
            ).fetchone()[0]
        if dry_run:
            return {
                "success": True,
                "affected": affected,
                "verification": "dry_run_no_changes",
            }

        for table in affected:
            conn.execute(
                f"DELETE FROM {table} WHERE product_id IN ({placeholders})",
                product_ids,
            )
        remaining = sum(
            conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE product_id IN ({placeholders})",
                product_ids,
            ).fetchone()[0]
            for table in affected
        )
        if remaining:
            conn.execute("ROLLBACK")
            return {
                "success": False,
                "affected": {key: 0 for key in affected},
                "error": "Card reset failed verification",
                "verification": "reset_not_confirmed",
            }
        conn.execute("COMMIT")
        return {
            "success": True,
            "affected": affected,
            "verification": "confirmed_reset",
        }
    except sqlite3.Error as error:
        if conn is not None:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
        return {
            "success": False,
            "affected": {key: 0 for key in affected},
            "error": f"Database error: {error}",
            "verification": "reset_failed_db_error",
        }
    finally:
        if conn is not None:
            conn.close()
