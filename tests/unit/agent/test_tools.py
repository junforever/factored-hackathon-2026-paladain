import inspect
from pathlib import Path
from unittest.mock import Mock, call

import pytest

from ai_banking_customer_service.agent import tools as agent_tools
from ai_banking_customer_service.agent.tools import (
    REGISTERED_TOOLS,
    block_card,
    build_registered_tools,
    escalate_case,
    get_dispute_context,
    get_recent_transactions,
)
from ai_banking_customer_service.governance.jev.evaluations import (
    ALLOWED_TOOLS,
    TOOL_ARG_CONTRACTS,
)
from ai_banking_customer_service.governance.jev.sanitization import detect_secrets
from ai_banking_customer_service.tools.block_card import (
    block_card as original_block_card,
)
from ai_banking_customer_service.tools.escalate_case import (
    escalate_case as original_escalate_case,
)
from ai_banking_customer_service.tools.get_dispute_context import (
    get_dispute_context as original_get_dispute_context,
)
from ai_banking_customer_service.tools.get_recent_transactions import (
    get_recent_transactions as original_get_recent_transactions,
)

WRAPPERS = {registered.tool_name: registered for registered in REGISTERED_TOOLS}
ORIGINAL_TOOLS = {
    "get_dispute_context": original_get_dispute_context,
    "get_recent_transactions": original_get_recent_transactions,
    "block_card": original_block_card,
    "escalate_case": original_escalate_case,
}


def _schema_types(property_schema: dict) -> set[str]:
    declared_type = property_schema.get("type")
    if isinstance(declared_type, str):
        return {declared_type}
    if isinstance(declared_type, list):
        return set(declared_type)
    return {
        option["type"]
        for option in property_schema.get("anyOf", [])
        if "type" in option
    }


def test_public_registration_contains_exactly_the_allowed_unique_tools() -> None:
    public_tools = (
        get_dispute_context,
        get_recent_transactions,
        block_card,
        escalate_case,
    )

    assert {registered.tool_name for registered in public_tools} == ALLOWED_TOOLS
    assert len(REGISTERED_TOOLS) == 4
    assert set(WRAPPERS) == ALLOWED_TOOLS
    assert len(WRAPPERS) == len(REGISTERED_TOOLS)


@pytest.mark.parametrize(
    "registered", REGISTERED_TOOLS, ids=lambda item: item.tool_name
)
def test_registered_tools_expose_strands_metadata(registered: object) -> None:
    assert isinstance(registered.tool_name, str)
    assert registered.tool_name
    assert isinstance(registered.tool_spec["description"], str)
    assert registered.tool_spec["description"]
    assert isinstance(registered.tool_spec["inputSchema"]["json"], dict)


@pytest.mark.parametrize("tool_name", sorted(ALLOWED_TOOLS))
def test_schema_and_signature_match_authoritative_contracts(tool_name: str) -> None:
    registered = WRAPPERS[tool_name]
    contract = TOOL_ARG_CONTRACTS[tool_name]
    schema = registered.tool_spec["inputSchema"]["json"]

    assert set(schema["properties"]) == set(contract["required"] + contract["optional"])
    assert set(schema.get("required", [])) == set(contract["required"])
    assert inspect.signature(registered) == inspect.signature(ORIGINAL_TOOLS[tool_name])


def test_generated_json_types_and_nullability_match_python_signatures() -> None:
    schemas = {
        name: registered.tool_spec["inputSchema"]["json"]["properties"]
        for name, registered in WRAPPERS.items()
    }

    for properties in schemas.values():
        assert _schema_types(properties["complaint_id"]) == {"string"}
    assert _schema_types(schemas["escalate_case"]["reason"]) == {"string"}
    assert _schema_types(schemas["get_recent_transactions"]["days_before"]) == {
        "integer"
    }
    assert _schema_types(schemas["get_recent_transactions"]["limit"]) == {"integer"}
    assert _schema_types(schemas["block_card"]["confirmed_by_customer"]) == {"boolean"}
    unresolved_schema = schemas["escalate_case"]["unresolved_questions"]
    notes_schema = schemas["escalate_case"]["agent_notes"]
    assert _schema_types(unresolved_schema) == {"array", "null"}, unresolved_schema
    assert _schema_types(notes_schema) == {"string", "null"}, notes_schema


@pytest.mark.parametrize(
    ("tool_name", "parameter", "expected_default"),
    [
        ("get_recent_transactions", "days_before", 30),
        ("get_recent_transactions", "limit", 10),
        ("block_card", "confirmed_by_customer", False),
        ("escalate_case", "unresolved_questions", None),
        ("escalate_case", "agent_notes", None),
    ],
)
def test_optional_schema_defaults_match_function_defaults(
    tool_name: str,
    parameter: str,
    expected_default: object,
) -> None:
    schema = WRAPPERS[tool_name].tool_spec["inputSchema"]["json"]

    assert schema["properties"][parameter]["default"] == expected_default
    assert inspect.signature(WRAPPERS[tool_name]).parameters[parameter].default == (
        expected_default
    )


@pytest.mark.parametrize(
    (
        "wrapper",
        "delegate_name",
        "default_args",
        "default_delegate_args",
        "explicit_args",
    ),
    [
        (
            get_dispute_context,
            "_get_dispute_context",
            ("CMP-TEST",),
            ("CMP-TEST",),
            ("CMP-OTHER",),
        ),
        (
            get_recent_transactions,
            "_get_recent_transactions",
            ("CMP-TEST",),
            ("CMP-TEST", 30, 10),
            ("CMP-OTHER", 14, 5),
        ),
        (
            block_card,
            "_block_card",
            ("CMP-TEST",),
            ("CMP-TEST", False),
            ("CMP-OTHER", True),
        ),
        (
            escalate_case,
            "_escalate_case",
            ("CMP-TEST", "needs_review"),
            ("CMP-TEST", "needs_review", None, None),
            (
                "CMP-OTHER",
                "customer_request",
                ["Which charge?"],
                "Follow up with the customer.",
            ),
        ),
    ],
    ids=lambda value: getattr(value, "tool_name", None),
)
def test_wrappers_delegate_defaults_and_explicit_arguments_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    wrapper: object,
    delegate_name: str,
    default_args: tuple,
    default_delegate_args: tuple,
    explicit_args: tuple,
) -> None:
    default_result = {"result": "default"}
    explicit_result = {"result": "explicit"}
    delegate = Mock(side_effect=[default_result, explicit_result])
    monkeypatch.setattr(agent_tools, delegate_name, delegate)

    assert wrapper(*default_args) is default_result
    assert wrapper(*explicit_args) is explicit_result
    assert delegate.call_args_list == [
        call(*default_delegate_args),
        call(*explicit_args),
    ]


@pytest.mark.parametrize(
    "registered", REGISTERED_TOOLS, ids=lambda item: item.tool_name
)
def test_wrapper_docstrings_are_structured_and_secret_safe(registered: object) -> None:
    docstring = registered.__doc__ or ""

    assert "Args:" in docstring
    assert "Returns:" in docstring
    assert detect_secrets(docstring) == ()


def test_action_docstrings_cover_real_outcome_categories() -> None:
    context_doc = get_dispute_context.__doc__ or ""
    block_doc = block_card.__doc__ or ""
    escalation_doc = escalate_case.__doc__ or ""

    assert "FIRST" in context_doc
    assert "SENSITIVE ACTION" in block_doc
    assert '{"error":' in block_doc
    for value in (
        "customer_confirmation_required",
        "product_not_blockable",
        "product_not_active",
        "already_blocked",
        "confirmed_blocked",
        "already_blocked_no_action_taken",
        "block_not_confirmed",
        "block_failed_db_error",
    ):
        assert value in block_doc
    for value in (
        "escalation_not_confirmed",
        "escalation_failed_db_error",
        "confirmed_persisted",
    ):
        assert value in escalation_doc
    assert "not a closed vocabulary" in escalation_doc


def test_bound_registration_passes_internal_paths_only_to_business_factories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card_path = tmp_path / "card_service.sqlite3"
    escalation_path = tmp_path / "escalation_service.sqlite3"
    bound_block = Mock(return_value={"action": "block_card"})
    bound_escalation = Mock(return_value={"action": "escalate_case"})
    block_factory = Mock(return_value=bound_block)
    escalation_factory = Mock(return_value=bound_escalation)
    monkeypatch.setattr(agent_tools, "_build_block_card", block_factory)
    monkeypatch.setattr(agent_tools, "_build_escalate_case", escalation_factory)

    registered = {
        item.tool_name: item
        for item in build_registered_tools(
            card_db_path=card_path,
            escalation_db_path=escalation_path,
        )
    }

    assert registered["block_card"]("CMP-BOUND", True) == {"action": "block_card"}
    assert registered["escalate_case"]("CMP-BOUND", "review") == {
        "action": "escalate_case"
    }
    block_factory.assert_called_once_with(db_path=card_path)
    escalation_factory.assert_called_once_with(
        card_db_path=card_path,
        escalation_db_path=escalation_path,
    )
    bound_block.assert_called_once_with("CMP-BOUND", True)
    bound_escalation.assert_called_once_with("CMP-BOUND", "review", None, None)


def test_delegation_fixtures_are_secret_safe() -> None:
    fixture_text = " ".join(
        (
            "CMP-TEST",
            "CMP-OTHER",
            "needs_review",
            "customer_request",
            "Which charge?",
            "Follow up with the customer.",
        )
    )

    assert detect_secrets(fixture_text) == ()
