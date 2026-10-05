from ai_banking_customer_service.agent.system_prompt import SYSTEM_PROMPT
from ai_banking_customer_service.agent.tools import (
    escalate_case,
    get_dispute_context,
)
from ai_banking_customer_service.governance.jev.sanitization import detect_secrets


def test_system_prompt_defines_banking_dispute_role() -> None:
    assert isinstance(SYSTEM_PROMPT, str)
    assert "banking customer-service agent" in SYSTEM_PROMPT
    assert "unrecognized-charge disputes" in SYSTEM_PROMPT


def test_system_prompt_covers_language_tools_and_dispute_flow() -> None:
    for phrase in (
        "Spanish or Portuguese",
        "get_dispute_context",
        "get_recent_transactions",
        "block_card",
        "escalate_case",
        "clarify missing details",
        "product-linked transactions",
        "resolve safely or escalate",
    ):
        assert phrase in SYSTEM_PROMPT


def test_system_prompt_requires_exact_signal_only_outputs() -> None:
    assert '{"orchestration_signal":"abstention","reason":"reason"}' in SYSTEM_PROMPT
    assert (
        '{"orchestration_signal":"clarification","question":"question"}'
        in SYSTEM_PROMPT
    )
    assert SYSTEM_PROMPT.count("no Markdown or additional text") == 2


def test_system_prompt_preserves_opaque_complaint_identity_and_tool_order() -> None:
    for phrase in (
        "Complaint IDs are opaque identifiers",
        "copy the exact complaint ID from the current user message",
        "never alter, translate, abbreviate, infer, or invent it",
        "Call get_dispute_context first and wait for its result",
        "before calling any other tool",
    ):
        assert phrase in SYSTEM_PROMPT


def test_system_prompt_defines_verified_terminal_action_plans() -> None:
    for phrase in (
        "recommended_action requires blocking",
        "confirmed_by_customer=true",
        "verified context requires escalation",
        "explicitly requests a human",
        "unresolved_questions must be a JSON list or null",
        "agent_notes must be a string or null",
        "omit optional escalation fields when they are unnecessary",
        "return the abstention JSON signal",
        "do not invent facts or execute an action",
        "After a verified successful action, respond with that result",
        "do not perform a fallback escalation",
    ):
        assert phrase in SYSTEM_PROMPT


def test_public_tool_contracts_reinforce_identity_and_escalation_types() -> None:
    context_id = get_dispute_context.tool_spec["inputSchema"]["json"]["properties"][
        "complaint_id"
    ]["description"]
    escalation_spec = escalate_case.tool_spec
    escalation_properties = escalation_spec["inputSchema"]["json"]["properties"]

    assert "exact complaint ID from the current user message" in context_id
    assert (
        "JSON list or null"
        in escalation_properties["unresolved_questions"]["description"]
    )
    assert "string or null" in escalation_properties["agent_notes"]["description"]
    assert "Omit optional fields when unnecessary" in escalation_spec["description"]


def test_system_prompt_keeps_hard_policy_and_secrets_out() -> None:
    lowered = SYSTEM_PROMPT.casefold()

    assert detect_secrets(SYSTEM_PROMPT) == ()
    for forbidden in (
        "high_amount_threshold",
        "min_output_safety",
        "typesafe",
        "api_key",
        "governed tool access",
    ):
        assert forbidden not in lowered
