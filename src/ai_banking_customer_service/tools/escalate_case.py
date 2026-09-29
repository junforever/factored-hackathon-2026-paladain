"""
Tool: escalate_case

Genera un Structured JSON Handoff para el equipo humano.
El handoff resume: request, verified_facts, actions_taken,
supporting_evidence, unresolved_questions y recommended_next_steps.

Requisito del hackathon:
"For cases requiring human intervention, produce a structured handoff
 summarizing the request, verified facts, actions already taken,
 supporting evidence, unresolved questions, and recommended next steps."
"""

import os
from datetime import datetime

from dotenv import load_dotenv

from ai_banking_customer_service.services.card_service import is_card_blocked
from ai_banking_customer_service.services.escalation_service import create_escalation
from ai_banking_customer_service.tools.get_dispute_context import get_dispute_context
from ai_banking_customer_service.tools.get_recent_transactions import (
    get_recent_transactions,
)

load_dotenv()
# Umbral de monto alto (USD) que dispara prioridad High
HIGH_AMOUNT_THRESHOLD_USD = (
    float(os.getenv("HIGH_AMOUNT_THRESHOLD_USD"))
    if os.getenv("HIGH_AMOUNT_THRESHOLD_USD") is not None
    else 500.0
)


def _determine_priority(context: dict) -> str:
    """
    Determina la prioridad del escalamiento con reglas determinísticas.
    Fuera del prompt del LLM.
    """
    amount_usd = context.get("amount_usd_estimated") or 0.0
    product_type = context.get("product_type") or ""
    merchant_name = context.get("merchant_name")
    system_flagged_fraud = context.get("system_flagged_fraud", False)

    # Monto alto siempre es High
    if amount_usd >= HIGH_AMOUNT_THRESHOLD_USD:
        return "High"

    # Fraude confirmado por el sistema es High
    if system_flagged_fraud:
        return "High"

    # Cuentas (no tarjetas) requieren revisión más cuidadosa
    if "Cuenta" in product_type:
        return "High"

    # Comercio desconocido dificulta la investigación
    if merchant_name is None:
        return "Medium"

    return "Medium"


def escalate_case(
    complaint_id: str,
    reason: str,
    unresolved_questions: list | None = None,
    agent_notes: str | None = None,
) -> dict:
    """
    Genera y persiste un Structured JSON Handoff para el equipo humano.

    Args:
        complaint_id: ID de la queja.
        reason: Razón del escalamiento (ej: 'cargo_antiguo', 'monto_alto').
        unresolved_questions: Preguntas pendientes para el equipo humano.
        agent_notes: Notas adicionales del agente virtual.

    Returns:
        dict con el resultado del escalamiento y el handoff.
    """
    # 1. Validar inputs
    if not complaint_id or not isinstance(complaint_id, str):
        return {"error": "complaint_id es requerido y debe ser un string"}

    if not reason or not isinstance(reason, str):
        return {"error": "reason es requerido y debe ser un string"}

    # 2. Obtener contexto del caso
    context = get_dispute_context(complaint_id)
    if "error" in context:
        return context

    # 3. Obtener evidencia: transacciones recientes del producto
    tx_result = get_recent_transactions(complaint_id, days_before=60, limit=10)
    recent_transactions = (
        tx_result.get("transactions", []) if "error" not in tx_result else []
    )

    # 4. Verificar acciones previas: ¿la tarjeta ya fue bloqueada?
    product_id = context.get("product_id")
    card_blocked = is_card_blocked(product_id) if product_id else False

    # 5. Determinar prioridad con política determinística
    priority = _determine_priority(context)

    # 6. Construir el Structured JSON Handoff
    handoff = {
        "request": {
            "complaint_id": complaint_id,
            "summary": f"Cliente reporta cargo no reconocido de {context.get('amount')} "
            f"{context.get('currency')} en {context.get('product_type')}.",
            "reported_at": str(context.get("complaint_date")),
        },
        "verified_facts": {
            "customer_id": context.get("customer_id"),
            "customer_country": context.get("country"),
            "customer_segment": context.get("segment"),
            "product_id": product_id,
            "product_type": context.get("product_type"),
            "product_status": context.get("product_status"),
            "transaction_id": context.get("transaction_id"),
            "transaction_date": str(context.get("transaction_date")),
            "amount": context.get("amount"),
            "currency": context.get("currency"),
            "amount_usd_estimated": context.get("amount_usd_estimated"),
            "merchant_name": context.get("merchant_name"),
            "system_flagged_fraud": context.get("system_flagged_fraud"),
            "fraud_score": context.get("fraud_score"),
        },
        "actions_taken": [
            {
                "action": "block_card",
                "executed": card_blocked,
                "product_id": product_id,
                "note": "Tarjeta bloqueada preventivamente por el agente virtual."
                if card_blocked
                else "Tarjeta no bloqueada.",
            }
        ],
        "supporting_evidence": {
            "recent_transactions_count": len(recent_transactions),
            "recent_transactions": recent_transactions,
        },
        "unresolved_questions": unresolved_questions or [],
        "risk_flags": [
            flag
            for flag, present in [
                (
                    "high_amount",
                    (context.get("amount_usd_estimated") or 0)
                    >= HIGH_AMOUNT_THRESHOLD_USD,
                ),
                ("system_flagged_fraud", bool(context.get("system_flagged_fraud"))),
                ("merchant_unknown", context.get("merchant_name") is None),
                ("card_blocked", card_blocked),
            ]
            if present
        ],
        "recommended_next_steps": [
            "Verificar identidad del cliente por canal seguro.",
            "Revisar la transacción disputada y su metadata completa.",
            "Determinar si aplica reversión o investigación de fraude.",
            "Contactar al cliente con la resolución.",
        ],
        "handoff_metadata": {
            "reason": reason,
            "priority": priority,
            "agent_notes": agent_notes,
            "generated_by": "ai_banking_customer_service_agent",
            "generated_at": datetime.now().isoformat(),
        },
    }

    # 7. PERSISTIR el escalamiento
    persistence = create_escalation(
        complaint_id=complaint_id,
        customer_id=context.get("customer_id"),
        product_id=product_id,
        reason=reason,
        priority=priority,
        handoff=handoff,
    )

    if not persistence.get("success"):
        return {
            "action": "escalate_case",
            "executed": False,
            "error": persistence.get("error"),
            "verification": persistence.get("verification"),
        }

    # 8. Retornar con verificación explícita
    return {
        "action": "escalate_case",
        "executed": True,
        "escalation_id": persistence["escalation_id"],
        "priority": priority,
        "verification": persistence["verification"],
        "handoff": handoff,
    }
