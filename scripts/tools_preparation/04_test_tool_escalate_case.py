"""
Prueba de la tool escalate_case.
Ejecutar desde la raíz del proyecto:
    uv run python scripts/13_test_tool_escalate_case.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_banking_customer_service.services.escalation_service import get_escalation
from ai_banking_customer_service.tools.escalate_case import escalate_case

TEST_ID = "CMP-LMHTOD889KGMUG3RQSAA"

print("=" * 60)
print("Prueba 1: Escalamiento por cargo antiguo con preguntas pendientes")
print("=" * 60)
result = escalate_case(
    complaint_id=TEST_ID,
    reason="cargo_antiguo_fuera_de_ventana",
    unresolved_questions=[
        "¿El cliente reconoce alguna transacción parcial en el período?",
        "¿Hubo cambio de dispositivo o IP en la fecha de la transacción?",
    ],
    agent_notes=(
        "Cliente reporta cargo de hace varias semanas. "
        "Fuera de ventana de bloqueo automático."
    ),
)

if "error" in result:
    print(f"  ERROR: {result['error']}")
else:
    print(f"  Ejecutado: {result.get('executed')}")
    print(f"  Escalation ID: {result.get('escalation_id')}")
    print(f"  Prioridad: {result.get('priority')}")
    print(f"  Verificación: {result.get('verification')}")
    print(f"  Risk flags: {result['handoff']['risk_flags']}")
    print(f"  Preguntas pendientes: {len(result['handoff']['unresolved_questions'])}")

print("\n" + "=" * 60)
print("Prueba 2: Verificar que el handoff se persistió")
print("=" * 60)

if "escalation_id" in result:
    stored = get_escalation(result["escalation_id"])
    if stored:
        print(f"  Estado: {stored['status']}")
        print(f"  Creado en: {stored['created_at']}")
        print("  Handoff persistido: OK")
    else:
        print("  ERROR: No se encontró el escalamiento persistido")

print("\n" + "=" * 60)
print("Prueba 3: Handoff completo (JSON)")
print("=" * 60)
if "handoff" in result:
    print(json.dumps(result["handoff"], indent=2, ensure_ascii=False, default=str))

print("\n" + "=" * 60)
print("Prueba 4: Complaint inexistente")
print("=" * 60)
result = escalate_case(complaint_id="CMP-NO-EXISTE", reason="prueba")
print(f"  Resultado: {result}")
