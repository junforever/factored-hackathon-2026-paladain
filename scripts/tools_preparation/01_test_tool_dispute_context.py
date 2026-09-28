"""
Prueba de la tool get_dispute_context.
Ejecutar desde la raíz del proyecto:
    uv run python scripts/tools_preparation/01_test_tool_dispute_context.py
"""

import sys
from pathlib import Path

# Agregar src al path para importar el paquete
# (necesario si el paquete no está instalado en el entorno)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_banking_customer_service.tools.get_dispute_context import get_dispute_context

# ID real del resultado del paso 8
TEST_ID = "CMP-LMHTOD889KGMUG3RQSAA"

print("=" * 60)
print("Prueba 1: Caso existente")
print("=" * 60)
result = get_dispute_context(TEST_ID)
if "error" in result:
    print(f"  ERROR: {result['error']}")
else:
    for key, value in result.items():
        print(f"  {key}: {value}")

print("\n" + "=" * 60)
print("Prueba 2: Caso inexistente")
print("=" * 60)
result = get_dispute_context("CMP-NO-EXISTE")
print(f"  Resultado: {result}")

print("\n" + "=" * 60)
print("Prueba 3: Input inválido")
print("=" * 60)
result = get_dispute_context("")
print(f"  Resultado: {result}")
