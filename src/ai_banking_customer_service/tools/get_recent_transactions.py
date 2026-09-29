"""
Tool: get_recent_transactions

Obtiene transacciones recientes de un cliente a partir de un complaint_id.
Usa el sandbox como puerta de autorización: solo permite consultar
transacciones de clientes que tienen una queja en el sandbox.
"""

from datetime import timedelta

import duckdb
from ai_banking_customer_service.config import settings

SANDBOX_PATH = settings.sandbox_full_path
DB_PATH = settings.duckdb_path


def get_recent_transactions(
    complaint_id: str,
    days_before: int = 30,
    limit: int = 10,
) -> dict:
    """
    Obtiene transacciones recientes del cliente asociado a un complaint_id.

    Args:
        complaint_id: ID de la queja (ej: CMP-LMHTOD889KGMUG3RQSAA)
        days_before: Cuántos días hacia atrás buscar (default 30)
        limit: Máximo de transacciones a devolver (default 10)

    Returns:
        dict con la lista de transacciones y metadatos del caso.
    """
    # 1. Validar input
    if not complaint_id or not isinstance(complaint_id, str):
        return {"error": "complaint_id es requerido y debe ser un string"}

    if not isinstance(days_before, int) or days_before < 1:
        return {"error": "days_before debe ser un entero positivo"}

    if not isinstance(limit, int) or limit < 1 or limit > 50:
        return {"error": "limit debe ser un entero entre 1 y 50"}

    # 2. Verificar que el sandbox existe
    if not SANDBOX_PATH.exists():
        return {"error": f"Sandbox no encontrado en {SANDBOX_PATH}"}

    if not DB_PATH.exists():
        return {"error": f"Base DuckDB no encontrada en {DB_PATH}"}

    # Conectar a la base persistente y solo en modo read_only
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        # 3. Verificar que la vista raw_transactions exista
        view_exists = con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = 'raw_transactions'
            """
        ).fetchone()[0]

        if not view_exists:
            return {
                "error": (
                    "La vista raw_transactions no existe en la base DuckDB. "
                    "Ejecuta scripts/data_preparation/07_register_transactions.py primero."
                )
            }
        # 4. Buscar el caso en el sandbox (puerta de autorización)
        sandbox_query = f"""
            SELECT customer_id, product_id, complaint_date
            FROM read_parquet('{SANDBOX_PATH.as_posix()}')
            WHERE complaint_id = ?
        """
        case = con.execute(sandbox_query, [complaint_id]).fetchone()

        if case is None:
            return {"error": f"Disputa no encontrada: {complaint_id}"}

        complaint_customer_id, product_id, complaint_date = case

        if complaint_date is None:
            return {"error": "El caso no tiene complaint_date disponible"}

        # 6. Calcular ventana de fechas en Python
        start_date = complaint_date - timedelta(days=days_before)

        # 5. Consultar transacciones recientes del cliente
        # FIX: Filtramos por product_id, no por customer_id
        # Razón: ~26% de los casos tienen inconsistencia entre
        # customer_id de la queja y customer_id de la transacción
        tx_query = """
            SELECT
                transaction_id,
                transaction_date,
                transaction_type,
                amount,
                currency,
                merchant_name,
                merchant_category,
                channel,
                transaction_status,
                is_fraud,
                fraud_score,
                customer_id AS transaction_customer_id
            FROM raw_transactions
            WHERE product_id = ?
              AND transaction_date >= CAST(? AS TIMESTAMP)
              AND transaction_date <= CAST(? AS TIMESTAMP)
            ORDER BY transaction_date DESC
            LIMIT ?
        """
        rows = con.execute(
            tx_query,
            [product_id, start_date, complaint_date, limit],
        ).fetchall()

        columns = [desc[0] for desc in con.description]
        transactions = [dict(zip(columns, row)) for row in rows]

        return {
            "complaint_id": complaint_id,
            "complaint_customer_id": complaint_customer_id,
            "product_id": product_id,
            "reference_date": str(complaint_date),
            "start_date": str(start_date),
            "days_searched": days_before,
            "transaction_count": len(transactions),
            "transactions": transactions,
            "data_quality_note": (
                "Se consultó por product_id porque ~26% de las quejas "
                "tienen customer_id distinto al de la transacción asociada. "
                "Esto puede indicar tarjetas adicionales, corporativas o errores de datos."
            ),
        }

    except Exception as e:
        return {"error": f"Error al consultar transacciones: {str(e)}"}
    finally:
        con.close()
