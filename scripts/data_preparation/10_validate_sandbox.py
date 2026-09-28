"""
Data Quality Gate: Valida el contrato del sandbox antes de que el agente lo consuma.
Si falla, el pipeline debería detenerse y alertar.
"""

import os
import sys
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
from dotenv import load_dotenv

load_dotenv()

SANDBOX_PATH = Path(os.getenv("SANDBOX_PATH"))

# 1. Definir el Contrato de Datos (Data Contract)
# validamos las columnas críticas para el agente
sandbox_schema = pa.DataFrameSchema(
    {
        # Identificadores (Obligatorios y Únicos)
        "complaint_id": pa.Column(
            str, nullable=False, unique=True, description="ID único de la queja"
        ),
        "customer_id": pa.Column(str, nullable=False, description="ID del cliente"),
        # Datos financieros (No pueden ser negativos)
        "amount": pa.Column(
            float, nullable=True, checks=pa.Check.ge(0), description="Monto original"
        ),
        "amount_usd_estimated": pa.Column(
            float, nullable=True, checks=pa.Check.ge(0), description="Monto en USD"
        ),
        # Categorías (Deben estar dentro de los valores permitidos)
        "complaint_status": pa.Column(
            str,
            nullable=False,
            checks=pa.Check.isin(
                ["Open", "In Process", "Escalated", "Resolved", "Closed", "Rejected"]
            ),
        ),
        "recommended_action": pa.Column(
            str,
            nullable=False,
            checks=pa.Check.isin(
                [
                    "AUTO_BLOCK_AND_DISPUTE",
                    "ASK_FOR_DETAILS_THEN_DECIDE",
                    "ESCALATE_TO_HUMAN",
                ]
            ),
            description="Acción determinística que el agente debe seguir",
        ),
        # Campos que pueden ser nulos (ej. merchant_name a veces es NULL en la data)
        "merchant_name": pa.Column(str, nullable=True),
        "fraud_score": pa.Column(
            float, nullable=True, checks=pa.Check.in_range(0, 100)
        ),
    },
    strict=False,
)  # strict=False permite que existan otras columnas no listadas aquí


def validate_sandbox():
    if not SANDBOX_PATH.exists():
        print(f"ERROR: No se encuentra el sandbox en {SANDBOX_PATH}")
        sys.exit(1)

    print(f"Leyendo sandbox desde {SANDBOX_PATH}...")
    df = pd.read_parquet(SANDBOX_PATH)

    print(f"Validando {len(df)} registros contra el contrato de datos...")

    try:
        # lazy=True recopila TODOS los errores antes de fallar, no solo el primero
        sandbox_schema.validate(df, lazy=True)
        print(
            "ÉXITO: El sandbox cumple con el contrato de datos. Listo para el agente."
        )
        return True

    except pa.errors.SchemaErrors as err:
        print("ERROR: El sandbox VIOLA el contrato de datos.")
        print("\n--- Detalles de los fallos ---")
        # Mostramos un resumen de los fallos
        print(err.failure_cases.head(10))

        sys.exit(1)


if __name__ == "__main__":
    validate_sandbox()
