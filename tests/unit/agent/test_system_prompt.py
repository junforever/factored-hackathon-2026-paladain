from ai_banking_customer_service.agent.system_prompt import SYSTEM_PROMPT
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
        "verified case context",
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


def test_system_prompt_keeps_hard_policy_and_secrets_out() -> None:
    lowered = SYSTEM_PROMPT.casefold()

    assert detect_secrets(SYSTEM_PROMPT) == ()
    for forbidden in (
        "confirmed_by_customer",
        "high_amount_threshold",
        "min_output_safety",
        "typesafe",
        "api_key",
    ):
        assert forbidden not in lowered
