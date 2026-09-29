"""
Tool: get_dispute_context

Obtiene el contexto completo de una disputa por cargo no reconocido.
Lee del sandbox generado en el paso 9.
"""

import duckdb
from ai_banking_customer_service.config import settings

# Path al sandbox
SANDBOX_PATH = settings.sandbox_full_path


def get_dispute_context(complaint_id: str) -> dict:
    """
    Obtiene el contexto completo de una disputa.

    Args:
        complaint_id: ID único de la queja (ej: CMP-LMHTOD889KGMUG3RQSAA)

    Returns:
        dict con el contexto del caso, o {"error": "..."} si falla.
    """
    # 1. Validar input
    if not complaint_id or not isinstance(complaint_id, str):
        return {"error": "complaint_id es requerido y debe ser un string"}

    # 2. Verificar que el sandbox existe
    if not SANDBOX_PATH.exists():
        return {"error": f"Sandbox no encontrado en {SANDBOX_PATH}"}

    # 3. Consultar el parquet
    con = duckdb.connect()
    try:
        # El path es una constante nuestra (seguro usar f-string).
        # El complaint_id es input del usuario (se parametriza con ?).
        query = f"""
            SELECT *
            FROM read_parquet('{SANDBOX_PATH.as_posix()}')
            WHERE complaint_id = ?
        """
        result = con.execute(query, [complaint_id]).fetchone()

        if result is None:
            return {"error": f"Disputa no encontrada: {complaint_id}"}

        # 4. Convertir a diccionario
        columns = [desc[0] for desc in con.description]
        return dict(zip(columns, result))

    except Exception as e:
        return {"error": f"Error al consultar: {str(e)}"}
    finally:
        con.close()
