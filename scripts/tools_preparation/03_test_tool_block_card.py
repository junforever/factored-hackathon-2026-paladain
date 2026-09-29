"""
Prueba de la tool block_card.
Ejecutar desde la raíz del proyecto:
    uv run python scripts/12_test_tool_block_card.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_banking_customer_service.tools.block_card import block_card

TEST_ID = "CMP-LMHTOD889KGMUG3RQSAA"

print("=" * 60)
print("Prueba 1: Bloqueo SIN confirmación del cliente")
print("=" * 60)
result = block_card(TEST_ID, confirmed_by_customer=False)
print(f"  Ejecutado: {result.get('executed')}")
print(f"  Razón: {result.get('reason')}")
print(f"  Mensaje: {result.get('message')}")

print("\n" + "=" * 60)
print("Prueba 2: Bloqueo CON confirmación del cliente")
print("=" * 60)
result = block_card(TEST_ID, confirmed_by_customer=True)
print(f"  Ejecutado: {result.get('executed')}")
print(f"  Verificación: {result.get('verification')}")
print(f"  Bloqueada en: {result.get('blocked_at')}")

print("\n" + "=" * 60)
print("Prueba 3: Intentar bloquear de nuevo (idempotencia)")
print("=" * 60)
result = block_card(TEST_ID, confirmed_by_customer=True)
print(f"  Ejecutado: {result.get('executed')}")
print(f"  Razón: {result.get('reason')}")
print(f"  Mensaje: {result.get('message')}")

print("\n" + "=" * 60)
print("Prueba 4: Complaint inexistente")
print("=" * 60)
result = block_card("CMP-NO-EXISTE", confirmed_by_customer=True)
print(f"  Resultado: {result}")
