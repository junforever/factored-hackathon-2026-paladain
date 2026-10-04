"""Strands tool wrappers for the four banking agent tools.

This is a thin delegation layer. Direct calls are for unit tests only; production
must invoke tools through the governed agent from Specs #4, #6, and #7.
"""

from collections.abc import Callable
from pathlib import Path

from strands import tool

from ai_banking_customer_service.tools.block_card import (
    _build_block_card,
)
from ai_banking_customer_service.tools.block_card import (
    block_card as _block_card,
)
from ai_banking_customer_service.tools.escalate_case import (
    _build_escalate_case,
)
from ai_banking_customer_service.tools.escalate_case import (
    escalate_case as _escalate_case,
)
from ai_banking_customer_service.tools.get_dispute_context import (
    get_dispute_context as _get_dispute_context,
)
from ai_banking_customer_service.tools.get_recent_transactions import (
    get_recent_transactions as _get_recent_transactions,
)


@tool
def get_dispute_context(complaint_id: str) -> dict:
    """Retrieve the full context of a transaction dispute case.

    Use this tool FIRST when a customer reports an unrecognized charge. It returns
    customer information, product details, transaction data, and the system's
    recommended action. Do not skip this step.

    Args:
        complaint_id: Unique complaint ID (for example, CMP-EXAMPLE).

    Returns:
        A dict with the full dispute context, including customer_id, product_id,
        product_type, transaction_id, amount, currency, merchant_name,
        complaint_date, and recommended_action. Returns {"error": "..."} on input
        validation, missing data or storage, or query failure.
    """
    return _get_dispute_context(complaint_id)


@tool
def get_recent_transactions(
    complaint_id: str,
    days_before: int = 30,
    limit: int = 10,
) -> dict:
    """Retrieve recent transactions for the product linked to a complaint.

    Use this tool to show the customer recent transactions so they can identify
    which one they do not recognize. Transactions are filtered by product_id due
    to data quality constraints.

    Args:
        complaint_id: Unique complaint ID.
        days_before: How many days back to search (default 30, positive integer).
        limit: Maximum transactions to return (default 10, between 1 and 50).

    Returns:
        A dict with transaction_count, transactions, and case metadata. Each
        transaction includes transaction_id, transaction_date, transaction_type,
        amount, currency, and merchant_name. Returns {"error": "..."} on input
        validation, missing data or storage, or query failure.
    """
    return _get_recent_transactions(complaint_id, days_before, limit)


@tool
def block_card(
    complaint_id: str,
    confirmed_by_customer: bool = False,
) -> dict:
    """Block the card associated with a dispute.

    SENSITIVE ACTION. Only call this tool AFTER the customer has EXPLICITLY
    confirmed they want to block their card. Never call with
    confirmed_by_customer=False. The tool rejects unconfirmed requests.

    Args:
        complaint_id: Unique complaint ID.
        confirmed_by_customer: Must be True, only after explicit confirmation.

    Returns:
        A dict in one of these categories:
        - Context error: {"error": "..."} on validation, data, storage, or query
          failure.
        - Policy denial (executed=False, reason set):
          customer_confirmation_required, product_not_blockable,
          product_not_active, or already_blocked.
        - Service outcome (executed=True or False, verification set):
          confirmed_blocked, already_blocked_no_action_taken,
          block_not_confirmed, or block_failed_db_error.
    """
    return _block_card(complaint_id, confirmed_by_customer)


@tool
def escalate_case(
    complaint_id: str,
    reason: str,
    unresolved_questions: list | None = None,
    agent_notes: str | None = None,
) -> dict:
    """Escalate a case to a human agent with a structured handoff.

    Use this tool when the case cannot be resolved automatically, including old
    charges, high-value disputes, investigations, or a customer request for a
    human.

    Args:
        complaint_id: Unique complaint ID.
        reason: Escalation reason. Examples are cargo_antiguo, monto_alto, and
            cliente_solicita_humano; this is not a closed vocabulary.
        unresolved_questions: Optional pending questions for the human team;
            elements may be of any type.
        agent_notes: Optional notes from the virtual agent.

    Returns:
        A dict in one of these categories:
        - Input or context error: {"error": "..."} on validation, data, storage,
          or query failure.
        - Persistence failure (executed=False, verification set):
          escalation_not_confirmed or escalation_failed_db_error.
        - Success (executed=True): escalation_id, priority,
          verification=confirmed_persisted, and the structured handoff.
    """
    return _escalate_case(
        complaint_id,
        reason,
        unresolved_questions,
        agent_notes,
    )


def _restore_optional_nullability(registered: object) -> None:
    """Restore null variants dropped by Strands 1.57.1 schema cleaning."""
    properties = registered.tool_spec["inputSchema"]["json"]["properties"]
    unresolved_schema = properties["unresolved_questions"]
    unresolved_schema["anyOf"] = [
        {
            "type": unresolved_schema.pop("type"),
            "items": unresolved_schema.pop("items"),
        },
        {"type": "null"},
    ]
    notes_schema = properties["agent_notes"]
    notes_schema["anyOf"] = [
        {"type": notes_schema.pop("type")},
        {"type": "null"},
    ]


_restore_optional_nullability(escalate_case)

REGISTERED_TOOLS: list = [
    get_dispute_context,
    get_recent_transactions,
    block_card,
    escalate_case,
]


def _register_bound(
    function: Callable,
    default_tool: object,
) -> object:
    function.__name__ = default_tool.tool_name
    function.__doc__ = default_tool.__doc__
    registered = tool(function)
    if registered.tool_name == "escalate_case":
        _restore_optional_nullability(registered)
    return registered


def build_registered_tools(
    *,
    card_db_path: Path,
    escalation_db_path: Path,
) -> list:
    """Build canonical model tools with internal SQLite paths bound in closures."""
    bound_block = _build_block_card(db_path=card_db_path)
    bound_escalation = _build_escalate_case(
        card_db_path=card_db_path,
        escalation_db_path=escalation_db_path,
    )

    def bound_get_dispute_context(complaint_id: str) -> dict:
        return _get_dispute_context(complaint_id)

    def bound_get_recent_transactions(
        complaint_id: str,
        days_before: int = 30,
        limit: int = 10,
    ) -> dict:
        return _get_recent_transactions(complaint_id, days_before, limit)

    def bound_block_card(
        complaint_id: str,
        confirmed_by_customer: bool = False,
    ) -> dict:
        return bound_block(complaint_id, confirmed_by_customer)

    def bound_escalate_case(
        complaint_id: str,
        reason: str,
        unresolved_questions: list | None = None,
        agent_notes: str | None = None,
    ) -> dict:
        return bound_escalation(
            complaint_id,
            reason,
            unresolved_questions,
            agent_notes,
        )

    return [
        _register_bound(bound_get_dispute_context, get_dispute_context),
        _register_bound(bound_get_recent_transactions, get_recent_transactions),
        _register_bound(bound_block_card, block_card),
        _register_bound(bound_escalate_case, escalate_case),
    ]
