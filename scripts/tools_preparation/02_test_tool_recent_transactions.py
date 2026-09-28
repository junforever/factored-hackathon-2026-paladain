"""
Prueba de la tool get_recent_transactions.
Ejecutar desde la raíz del proyecto:
    uv run python scripts/11_test_tool_recent_transactions.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_banking_customer_service.tools.get_recent_transactions import (
    get_recent_transactions,
)

TEST_ID = "CMP-LMHTOD889KGMUG3RQSAA"

print("=" * 60)
print("Prueba 1: Transacciones recientes del caso de prueba")
print("=" * 60)
result = get_recent_transactions(TEST_ID, days_before=30, limit=5)

if "error" in result:
    print(f"  ERROR: {result['error']}")
else:
    print(f"  Cliente: {result['complaint_customer_id']}")
    print(f"  Producto: {result['product_id']}")
    print(f"  Fecha de referencia: {result['reference_date']}")
    print(f"  Transacciones encontradas: {result['transaction_count']}")
    print()
    for tx in result["transactions"]:
        print(
            f"  {tx['transaction_date']} | "
            f"{tx['transaction_type']:>10} | "
            f"${tx['amount']:>10.2f} {tx['currency']} | "
            f"{tx['merchant_name'] or '(sin comercio)':>20} | "
            f"{'FRAUDE' if tx['is_fraud'] else 'ok'}"
        )

print("\n" + "=" * 60)
print("Prueba 2: Complaint inexistente")
print("=" * 60)
result = get_recent_transactions("CMP-NO-EXISTE")
print(f"  Resultado: {result}")

print("\n" + "=" * 60)
print("Prueba 3: Input inválido")
print("=" * 60)
result = get_recent_transactions("")
print(f"  Resultado: {result}")
