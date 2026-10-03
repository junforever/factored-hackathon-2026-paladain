"""
Tool: block_card

Bloquea la tarjeta asociada a un complaint_id.
Aplica política fuera del prompt, ejecuta la acción en el servicio mock,
y verifica el resultado.
"""

from ai_banking_customer_service.services.card_service import (
    block_card as service_block_card,
)
from ai_banking_customer_service.services.card_service import is_card_blocked
from ai_banking_customer_service.tools.get_dispute_context import get_dispute_context

# Productos que pueden bloquearse (tarjetas). Las cuentas NO se bloquean aquí.
BLOCKABLE_PRODUCT_TYPES = {"Tarjeta Crédito", "Tarjeta Débito"}


def block_card(complaint_id: str, confirmed_by_customer: bool = False) -> dict:
    """
    Bloquea la tarjeta asociada a un complaint_id.

    Args:
        complaint_id: ID de la queja.
        confirmed_by_customer: True si el cliente confirmó explícitamente el bloqueo.

    Returns:
        dict con el resultado de la acción y su verificación.
    """
    # 1. Validar input
    if not complaint_id or not isinstance(complaint_id, str):
        return {"error": "complaint_id es requerido y debe ser un string"}

    # 2. Obtener contexto del caso
    context = get_dispute_context(complaint_id)
    if "error" in context:
        return context

    product_id = context.get("product_id")
    product_type = context.get("product_type")
    product_status = context.get("product_status")

    # 3. POLÍTICA: ¿el cliente confirmó?
    # Requisito del hackathon: acciones sensibles requieren confirmación explícita.
    if not confirmed_by_customer:
        return {
            "action": "block_card",
            "executed": False,
            "reason": "customer_confirmation_required",
            "message": (
                "El cliente debe confirmar explícitamente antes de bloquear la tarjeta."
            ),
        }

    # 4. POLÍTICA: ¿es un producto bloqueable?
    if product_type not in BLOCKABLE_PRODUCT_TYPES:
        return {
            "action": "block_card",
            "executed": False,
            "reason": "product_not_blockable",
            "product_type": product_type,
            "message": (
                f"El producto '{product_type}' no puede bloquearse con esta acción."
            ),
        }

    # 5. POLÍTICA: ¿el producto está activo?
    if product_status != "Active":
        return {
            "action": "block_card",
            "executed": False,
            "reason": "product_not_active",
            "product_status": product_status,
            "message": (
                f"El producto está en estado '{product_status}' y no puede bloquearse."
            ),
        }

    # 6. POLÍTICA: ¿ya está bloqueada?
    if is_card_blocked(product_id):
        return {
            "action": "block_card",
            "executed": False,
            "reason": "already_blocked",
            "product_id": product_id,
            "message": "La tarjeta ya estaba bloqueada.",
        }

    # 7. EJECUTAR la acción en el servicio mock
    result = service_block_card(
        product_id=product_id,
        complaint_id=complaint_id,
        reason="fraud_dispute",
    )

    # 8. RETORNAR con verificación explícita
    return {
        "action": "block_card",
        "executed": result.get("success", False),
        "complaint_id": complaint_id,
        "product_id": product_id,
        "product_type": product_type,
        "verification": result.get("verification"),
        "blocked_at": result.get("blocked_at"),
        "detail": result,
    }
