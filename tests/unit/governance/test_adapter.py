from unittest.mock import Mock, patch

import pytest

from ai_banking_customer_service.governance.adapter import GovernanceAdapter
from ai_banking_customer_service.governance.jev.decision import (
    GovernanceAction,
    GovernanceStage,
    GovernanceThresholds,
    OutputScreeningThresholds,
    ScreeningThresholds,
    ToolGatingThresholds,
)
from ai_banking_customer_service.governance.jev.evaluations import (
    ACTION_REQUIRED_FIELDS,
    EXPECTED_INTENTS,
    VERIFIED_FACTS_ALLOWLIST,
    InputScreeningResult,
    IntentRoutingResult,
    OutputScreeningResult,
    ToolGatingResult,
)
from ai_banking_customer_service.governance.jev.exceptions import (
    JevUnavailableError,
    JevValidationError,
)
from ai_banking_customer_service.governance.jev.schemas import (
    ChoiceAnswer,
    NoulAnswer,
    ScoreAnswer,
    Usage,
)
from ai_banking_customer_service.observability.contract import validate_event
from ai_banking_customer_service.observability.sink import AuditPersistenceError


def _thresholds() -> GovernanceThresholds:
    return GovernanceThresholds(
        prompt_injection=ScreeningThresholds(block=0.8, review=0.35),
        social_engineering=ScreeningThresholds(block=0.8, review=0.35),
        min_intent_confidence=0.5,
    )


def _adapter(
    *,
    sink: Mock | None = None,
    loader: Mock | None = None,
) -> GovernanceAdapter:
    return GovernanceAdapter(
        client=Mock(),
        thresholds=_thresholds(),
        tool_gating_thresholds=ToolGatingThresholds(0.7),
        output_screening_thresholds=OutputScreeningThresholds(1.5, 0.5),
        audit_sink=sink or Mock(),
        dispute_context_loader=loader or Mock(),
    )


def test_screening_block_emits_one_event_and_skips_routing() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)
    screening = InputScreeningResult(
        prompt_injection=NoulAnswer(noul=0.9),
        social_engineering=NoulAnswer(noul=0.1),
        model="jev-test",
        usage=Usage(input_tokens=10, output_tokens=2),
    )

    with (
        patch(
            "ai_banking_customer_service.governance.adapter.screen_input",
            return_value=screening,
        ) as screen,
        patch(
            "ai_banking_customer_service.governance.adapter.route_banking_intent"
        ) as route,
    ):
        result = adapter.screen_and_route(
            "No reconozco el cargo",
            "trace-1",
            "session-1",
            "CLI-9W3CREKG73Q7",
            parent_event_id="input-event",
        )

    assert result.final_decision.action is GovernanceAction.BLOCK
    assert result.intent is None
    assert result.should_continue is False
    assert result.last_event_id
    screen.assert_called_once()
    route.assert_not_called()
    sink.emit.assert_called_once()
    event = sink.emit.call_args.args[0]
    validate_event(event)
    assert event["event_id"] == result.last_event_id
    assert event["parent_event_id"] == "input-event"
    assert event["customer_id"] == "************73Q7"
    assert event["outcome"] == "blocked"
    assert event["tokens"] == 12
    assert event["payload"]["stage"] == "input_screening"
    assert event["payload"]["decision"] == "block"
    assert isinstance(event["payload"]["reasons"], list)
    assert "orphaned" not in event["payload"]


def test_screening_allow_routes_and_marks_both_events_orphaned() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)
    screening = InputScreeningResult(
        prompt_injection=NoulAnswer(noul=0.1),
        social_engineering=NoulAnswer(noul=0.1),
        model="jev-test",
        usage=Usage(input_tokens=10, output_tokens=2),
    )
    routing = IntentRoutingResult(
        intent=ChoiceAnswer(
            choice="dispute_charge",
            probabilities={
                intent: 1.0 if intent == "dispute_charge" else 0.0
                for intent in EXPECTED_INTENTS
            },
            confidence=0.9,
        ),
        model="jev-test",
        usage=Usage(input_tokens=8, output_tokens=1),
    )

    with (
        patch(
            "ai_banking_customer_service.governance.adapter.screen_input",
            return_value=screening,
        ),
        patch(
            "ai_banking_customer_service.governance.adapter.route_banking_intent",
            return_value=routing,
        ),
    ):
        adapter.screen_and_route(
            "No reconozco el cargo",
            "trace-1",
            "session-1",
            "customer-1234",
            parent_event_id="input-event",
            orphaned=True,
        )

    screening_event, routing_event = [call.args[0] for call in sink.emit.call_args_list]
    assert screening_event["payload"]["orphaned"] is True
    assert routing_event["payload"]["orphaned"] is True
    assert screening_event["parent_event_id"] == "input-event"
    assert routing_event["parent_event_id"] == screening_event["event_id"]


def test_screening_allow_routes_and_chains_two_events() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)
    screening = InputScreeningResult(
        prompt_injection=NoulAnswer(noul=0.1),
        social_engineering=NoulAnswer(noul=0.1),
        model="jev-test",
        usage=Usage(input_tokens=10, output_tokens=2),
    )
    routing = IntentRoutingResult(
        intent=ChoiceAnswer(
            choice="dispute_charge",
            probabilities={
                intent: 1.0 if intent == "dispute_charge" else 0.0
                for intent in EXPECTED_INTENTS
            },
            confidence=0.9,
        ),
        model="jev-test",
        usage=Usage(input_tokens=8, output_tokens=1),
    )

    with (
        patch(
            "ai_banking_customer_service.governance.adapter.screen_input",
            return_value=screening,
        ),
        patch(
            "ai_banking_customer_service.governance.adapter.route_banking_intent",
            return_value=routing,
        ) as route,
    ):
        result = adapter.screen_and_route(
            "No reconozco el cargo",
            "trace-1",
            "session-1",
            "customer-1234",
            parent_event_id="input-event",
        )

    assert result.final_decision.action is GovernanceAction.ALLOW
    assert result.intent == "dispute_charge"
    assert result.should_continue is True
    route.assert_called_once()
    assert sink.emit.call_count == 2
    screening_event, routing_event = [call.args[0] for call in sink.emit.call_args_list]
    assert screening_event["parent_event_id"] == "input-event"
    assert routing_event["parent_event_id"] == screening_event["event_id"]
    assert result.last_event_id == routing_event["event_id"]
    assert routing_event["payload"]["signals"] == {
        "intent": "dispute_charge",
        "intent_confidence": 0.9,
        "intent_probabilities": routing.intent.probabilities,
    }


def test_screening_audit_failure_propagates_before_routing() -> None:
    primary_error = OSError("primary unavailable")
    sink = Mock()
    sink.emit.side_effect = AuditPersistenceError(primary_error)
    adapter = _adapter(sink=sink)
    screening = InputScreeningResult(
        prompt_injection=NoulAnswer(noul=0.1),
        social_engineering=NoulAnswer(noul=0.1),
        model="jev-test",
        usage=Usage(input_tokens=10, output_tokens=2),
    )

    with (
        patch(
            "ai_banking_customer_service.governance.adapter.screen_input",
            return_value=screening,
        ),
        patch(
            "ai_banking_customer_service.governance.adapter.route_banking_intent"
        ) as route,
        pytest.raises(AuditPersistenceError) as captured,
    ):
        adapter.screen_and_route(
            "No reconozco el cargo",
            "trace-1",
            "session-1",
            "customer-1234",
        )

    assert captured.value.primary_error is primary_error
    route.assert_not_called()
    sink.emit.assert_called_once()


def test_screening_review_short_circuits_routing() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)
    screening = InputScreeningResult(
        prompt_injection=NoulAnswer(noul=0.35),
        social_engineering=NoulAnswer(noul=0.1),
        model="jev-test",
        usage=Usage(input_tokens=10, output_tokens=2),
    )

    with (
        patch(
            "ai_banking_customer_service.governance.adapter.screen_input",
            return_value=screening,
        ),
        patch(
            "ai_banking_customer_service.governance.adapter.route_banking_intent"
        ) as route,
    ):
        result = adapter.screen_and_route(
            "Urgente",
            "trace-1",
            "session-1",
            "customer-1234",
        )

    assert result.final_decision.action is GovernanceAction.REVIEW
    assert result.should_continue is False
    assert result.intent is None
    route.assert_not_called()
    assert sink.emit.call_count == 1
    assert sink.emit.call_args.args[0]["outcome"] == "escalated"


def test_screening_validation_error_blocks_emits_and_measures_latency() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)

    with (
        patch(
            "ai_banking_customer_service.governance.adapter.screen_input",
            side_effect=JevValidationError("bad response"),
        ),
        patch(
            "ai_banking_customer_service.governance.adapter.time.monotonic",
            side_effect=[10.0, 10.012],
        ) as monotonic,
    ):
        result = adapter.screen_and_route(
            "No reconozco el cargo",
            "trace-1",
            "session-1",
            "customer-1234",
        )

    assert result.final_decision.action is GovernanceAction.BLOCK
    assert result.final_decision.stage is GovernanceStage.INPUT_SCREENING
    assert result.final_decision.reason_codes == ("INPUT_SCREENING_VALIDATION_ERROR",)
    assert result.should_continue is False
    assert monotonic.call_count == 2
    sink.emit.assert_called_once()
    event = sink.emit.call_args.args[0]
    assert event["latency_ms"] == 12
    assert event["payload"]["decision"] == "block"


def test_screening_generic_jev_error_uses_exact_fail_closed_reason() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)

    with patch(
        "ai_banking_customer_service.governance.adapter.screen_input",
        side_effect=JevUnavailableError("down"),
    ):
        result = adapter.screen_and_route(
            "Mensaje",
            "trace-1",
            "session-1",
            "customer-1234",
        )

    assert result.final_decision.action is GovernanceAction.BLOCK
    assert result.final_decision.reason_codes == ("JEV_ERROR",)
    sink.emit.assert_called_once()


def test_screening_propagates_non_jev_errors_after_measuring_latency() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)

    with (
        patch(
            "ai_banking_customer_service.governance.adapter.screen_input",
            side_effect=RuntimeError("programming defect"),
        ),
        patch(
            "ai_banking_customer_service.governance.adapter.time.monotonic",
            side_effect=[1.0, 1.1],
        ) as monotonic,
        pytest.raises(RuntimeError, match="programming defect"),
    ):
        adapter.screen_and_route(
            "Mensaje",
            "trace-1",
            "session-1",
            "customer-1234",
        )

    assert monotonic.call_count == 2
    sink.emit.assert_not_called()


def test_routing_validation_error_blocks_and_chains_error_event() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)
    screening = InputScreeningResult(
        prompt_injection=NoulAnswer(noul=0.1),
        social_engineering=NoulAnswer(noul=0.1),
        model="jev-test",
        usage=Usage(input_tokens=10, output_tokens=2),
    )

    with (
        patch(
            "ai_banking_customer_service.governance.adapter.screen_input",
            return_value=screening,
        ),
        patch(
            "ai_banking_customer_service.governance.adapter.route_banking_intent",
            side_effect=JevValidationError("bad routing"),
        ),
    ):
        result = adapter.screen_and_route(
            "No reconozco el cargo",
            "trace-1",
            "session-1",
            "customer-1234",
        )

    assert result.final_decision.action is GovernanceAction.BLOCK
    assert result.final_decision.stage is GovernanceStage.INTENT_ROUTING
    assert result.final_decision.reason_codes == ("INTENT_ROUTING_VALIDATION_ERROR",)
    assert result.intent is None
    assert result.should_continue is False
    assert sink.emit.call_count == 2
    first, second = [call.args[0] for call in sink.emit.call_args_list]
    assert second["parent_event_id"] == first["event_id"]
    assert result.last_event_id == second["event_id"]


def test_routing_generic_jev_error_uses_exact_fail_closed_reason() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)
    screening = InputScreeningResult(
        prompt_injection=NoulAnswer(noul=0.1),
        social_engineering=NoulAnswer(noul=0.1),
        model="jev-test",
        usage=Usage(input_tokens=10, output_tokens=2),
    )

    with (
        patch(
            "ai_banking_customer_service.governance.adapter.screen_input",
            return_value=screening,
        ),
        patch(
            "ai_banking_customer_service.governance.adapter.route_banking_intent",
            side_effect=JevUnavailableError("down"),
        ),
    ):
        result = adapter.screen_and_route(
            "Mensaje",
            "trace-1",
            "session-1",
            "customer-1234",
        )

    assert result.final_decision.action is GovernanceAction.BLOCK
    assert result.final_decision.stage is GovernanceStage.INTENT_ROUTING
    assert result.final_decision.reason_codes == ("JEV_ERROR",)
    assert sink.emit.call_count == 2


def test_routing_review_stops_with_no_exposed_intent() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)
    screening = InputScreeningResult(
        prompt_injection=NoulAnswer(noul=0.1),
        social_engineering=NoulAnswer(noul=0.1),
        model="jev-test",
        usage=Usage(input_tokens=10, output_tokens=2),
    )
    routing = IntentRoutingResult(
        intent=ChoiceAnswer(
            choice="dispute_charge",
            probabilities={
                intent: 0.4 if intent == "dispute_charge" else 0.12
                for intent in EXPECTED_INTENTS
            },
            confidence=0.4,
        ),
        model="jev-test",
        usage=Usage(input_tokens=8, output_tokens=1),
    )

    with (
        patch(
            "ai_banking_customer_service.governance.adapter.screen_input",
            return_value=screening,
        ),
        patch(
            "ai_banking_customer_service.governance.adapter.route_banking_intent",
            return_value=routing,
        ),
    ):
        result = adapter.screen_and_route(
            "No reconozco el cargo",
            "trace-1",
            "session-1",
            "customer-1234",
        )

    assert result.final_decision.action is GovernanceAction.REVIEW
    assert result.intent is None
    assert result.should_continue is False
    assert sink.emit.call_count == 2


def test_gate_tool_call_ignores_inconsistent_signal_for_deterministic_block() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)
    gating = ToolGatingResult(
        deterministic_block=True,
        deterministic_reason="confirmation_required",
        intent_matches_tool=NoulAnswer(noul=0.99),
        model=None,
        usage=None,
    )

    with patch(
        "ai_banking_customer_service.governance.adapter.evaluate_tool_call",
        return_value=gating,
    ) as evaluate:
        result = adapter.gate_tool_call(
            "block_card",
            {"complaint_id": "CMP-1"},
            "block_card",
            "Bloqueá mi tarjeta",
            {
                "authenticated": True,
                "verified_complaint_ids": ("CMP-1",),
            },
            "trace-1",
            "session-1",
            "customer-1234",
            parent_event_id="routing-event",
            orphaned=True,
        )

    assert result.decision.action is GovernanceAction.BLOCK
    assert result.decision.stage is GovernanceStage.TOOL_GATING
    assert result.event_id
    evaluate.assert_called_once()
    sink.emit.assert_called_once()
    event = sink.emit.call_args.args[0]
    assert event["parent_event_id"] == "routing-event"
    assert event["payload"]["orphaned"] is True
    assert event["payload"]["signals"] == {
        "intent_matches_tool": None,
        "deterministic_reason": "confirmation_required",
    }


def test_gate_tool_call_allow_emits_semantic_signal_tokens_and_thresholds() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)
    gating = ToolGatingResult(
        deterministic_block=False,
        deterministic_reason="",
        intent_matches_tool=NoulAnswer(noul=0.9),
        model="jev-test",
        usage=Usage(input_tokens=13, output_tokens=1),
    )

    with patch(
        "ai_banking_customer_service.governance.adapter.evaluate_tool_call",
        return_value=gating,
    ):
        result = adapter.gate_tool_call(
            "get_dispute_context",
            {"complaint_id": "CMP-1"},
            "dispute_charge",
            "No reconozco el cargo",
            {"authenticated": True, "verified_complaint_ids": ("CMP-1",)},
            "trace-1",
            "session-1",
            "customer-1234",
        )

    assert result.decision.action is GovernanceAction.ALLOW
    event = sink.emit.call_args.args[0]
    assert event["outcome"] == "success"
    assert event["tokens"] == 14
    assert event["payload"]["signals"] == {"intent_matches_tool": 0.9}
    assert event["payload"]["thresholds"] == {"min_intent_matches_tool": 0.7}
    assert "orphaned" not in event["payload"]


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        (JevValidationError("invalid"), "TOOL_GATING_VALIDATION_ERROR"),
        (JevUnavailableError("down"), "JEV_ERROR"),
    ],
)
def test_gate_tool_call_fails_closed_for_jev_errors(
    error: Exception,
    expected_reason: str,
) -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)

    with patch(
        "ai_banking_customer_service.governance.adapter.evaluate_tool_call",
        side_effect=error,
    ):
        result = adapter.gate_tool_call(
            "get_dispute_context",
            {"complaint_id": "CMP-1"},
            "dispute_charge",
            "No reconozco el cargo",
            {"authenticated": True, "verified_complaint_ids": ("CMP-1",)},
            "trace-1",
            "session-1",
            "customer-1234",
        )

    assert result.decision.action is GovernanceAction.BLOCK
    assert result.decision.reason_codes == (expected_reason,)
    sink.emit.assert_called_once()


def test_gate_tool_call_propagates_non_jev_error_after_measuring_latency() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)

    with (
        patch(
            "ai_banking_customer_service.governance.adapter.evaluate_tool_call",
            side_effect=RuntimeError("programming defect"),
        ),
        patch(
            "ai_banking_customer_service.governance.adapter.time.monotonic",
            side_effect=[1.0, 1.1],
        ) as monotonic,
        pytest.raises(RuntimeError, match="programming defect"),
    ):
        adapter.gate_tool_call(
            "get_dispute_context",
            {"complaint_id": "CMP-1"},
            "dispute_charge",
            "No reconozco el cargo",
            {"authenticated": True, "verified_complaint_ids": ("CMP-1",)},
            "trace-1",
            "session-1",
            "customer-1234",
        )

    assert monotonic.call_count == 2
    sink.emit.assert_not_called()


def test_screen_output_emits_review_for_detected_secrets() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)
    screening = OutputScreeningResult(
        secrets_detected=("PAN",),
        secrets_sanitized_response="[REDACTED_PAN]",
        output_safety_semantic=None,
        model=None,
        usage=None,
    )

    with patch(
        "ai_banking_customer_service.governance.adapter.evaluate_output",
        return_value=screening,
    ):
        result = adapter.screen_output(
            "Tarjeta 4111 1111 1111 1111",
            "Bloqueá mi tarjeta",
            {"product_status": "active"},
            [],
            "trace-1",
            "session-1",
            "customer-1234",
            parent_event_id="tool-event",
            orphaned=True,
        )

    assert result.decision.action is GovernanceAction.REVIEW
    assert result.decision.stage is GovernanceStage.OUTPUT_SCREENING
    assert result.event_id
    sink.emit.assert_called_once()
    event = sink.emit.call_args.args[0]
    assert event["parent_event_id"] == "tool-event"
    assert event["outcome"] == "escalated"
    assert event["payload"]["orphaned"] is True
    assert event["payload"]["signals"] == {
        "score": None,
        "confidence": None,
        "secrets_detected": ["PAN"],
    }


def test_screen_output_allow_emits_semantic_signals_and_tokens() -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)
    screening = OutputScreeningResult(
        secrets_detected=(),
        secrets_sanitized_response=None,
        output_safety_semantic=ScoreAnswer(
            score=1.8,
            legend={0: "unsafe", 1: "risky", 2: "safe"},
            probabilities={0: 0.0, 1: 0.2, 2: 0.8},
            confidence=0.9,
        ),
        model="jev-test",
        usage=Usage(input_tokens=20, output_tokens=3),
    )

    with patch(
        "ai_banking_customer_service.governance.adapter.evaluate_output",
        return_value=screening,
    ):
        result = adapter.screen_output(
            "La tarjeta fue bloqueada.",
            "Bloqueá mi tarjeta",
            {"product_status": "blocked"},
            [
                {
                    "action_name": "block_card",
                    "executed": True,
                    "verification": "confirmed_blocked",
                }
            ],
            "trace-1",
            "session-1",
            "customer-1234",
        )

    assert result.decision.action is GovernanceAction.ALLOW
    event = sink.emit.call_args.args[0]
    assert event["tokens"] == 23
    assert event["payload"]["signals"] == {
        "score": 1.8,
        "confidence": 0.9,
        "secrets_detected": [],
    }
    assert event["payload"]["thresholds"] == {
        "min_output_safety_score": 1.5,
        "min_output_safety_confidence": 0.5,
    }
    assert "orphaned" not in event["payload"]


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        (JevValidationError("invalid"), "OUTPUT_SCREENING_VALIDATION_ERROR"),
        (JevUnavailableError("down"), "JEV_ERROR"),
    ],
)
def test_screen_output_fails_closed_to_review_for_jev_errors(
    error: Exception,
    expected_reason: str,
) -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)

    with patch(
        "ai_banking_customer_service.governance.adapter.evaluate_output",
        side_effect=error,
    ):
        result = adapter.screen_output(
            "Respuesta",
            "Mensaje",
            {},
            [],
            "trace-1",
            "session-1",
            "customer-1234",
        )

    assert result.decision.action is GovernanceAction.REVIEW
    assert result.decision.reason_codes == (expected_reason,)
    assert sink.emit.call_count == 1


def test_screen_output_propagates_non_jev_errors() -> None:
    adapter = _adapter()

    with (
        patch(
            "ai_banking_customer_service.governance.adapter.evaluate_output",
            side_effect=TypeError("programming defect"),
        ),
        pytest.raises(TypeError, match="programming defect"),
    ):
        adapter.screen_output(
            "Respuesta",
            "Mensaje",
            {},
            [],
            "trace-1",
            "session-1",
            "customer-1234",
        )


@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        (
            "screen_and_route",
            ("Mensaje", "trace-1", "session-1", "customer-1234"),
        ),
        (
            "gate_tool_call",
            (
                "get_dispute_context",
                {"complaint_id": "CMP-1"},
                "dispute_charge",
                "Mensaje",
                {"authenticated": True},
                "trace-1",
                "session-1",
                "customer-1234",
            ),
        ),
        (
            "screen_output",
            (
                "Respuesta",
                "Mensaje",
                {},
                [],
                "trace-1",
                "session-1",
                "customer-1234",
            ),
        ),
    ],
)
def test_adapter_entry_points_require_boolean_orphaned(
    method_name: str,
    args: tuple,
) -> None:
    sink = Mock()
    adapter = _adapter(sink=sink)

    with pytest.raises(TypeError, match="orphaned must be bool"):
        getattr(adapter, method_name)(*args, orphaned="yes")

    sink.emit.assert_not_called()


def test_build_customer_context_uses_matching_complaint_and_product() -> None:
    loader = Mock(return_value={"complaint_id": "CMP-1", "product_id": "PRD-1"})
    adapter = _adapter(loader=loader)

    context = adapter.build_customer_context("CMP-1")

    assert context == {
        "authenticated": True,
        "verified_complaint_ids": ("CMP-1",),
        "authorized_product_ids": ("PRD-1",),
    }
    loader.assert_called_once_with("CMP-1")


@pytest.mark.parametrize(
    "loaded",
    [
        None,
        [],
        {"error": "not found"},
        {},
        {"complaint_id": 1, "product_id": "PRD-1"},
        {"complaint_id": "CMP-2", "product_id": "PRD-1"},
    ],
)
def test_build_customer_context_fails_closed_for_unverified_loader_data(
    loaded: object,
) -> None:
    adapter = _adapter(loader=Mock(return_value=loaded))

    assert adapter.build_customer_context("CMP-1") == {
        "authenticated": True,
        "verified_complaint_ids": (),
        "authorized_product_ids": (),
    }


@pytest.mark.parametrize("product_id", [None, "", "   ", 1])
def test_build_customer_context_keeps_verified_complaint_without_valid_product(
    product_id: object,
) -> None:
    adapter = _adapter(
        loader=Mock(return_value={"complaint_id": "CMP-1", "product_id": product_id})
    )

    assert adapter.build_customer_context("CMP-1") == {
        "authenticated": True,
        "verified_complaint_ids": ("CMP-1",),
        "authorized_product_ids": (),
    }


def test_build_customer_context_handles_loader_exception() -> None:
    adapter = _adapter(loader=Mock(side_effect=RuntimeError("sandbox failed")))

    assert adapter.build_customer_context("CMP-1")["verified_complaint_ids"] == ()


def test_build_verified_facts_keeps_only_allowlisted_fields() -> None:
    adapter = _adapter()
    dispute_context = {key: f"value-{key}" for key in VERIFIED_FACTS_ALLOWLIST}
    dispute_context.update(
        {
            "complaint_id": "CMP-1",
            "product_id": "PRD-1",
            "customer_id": "CUST-1",
        }
    )

    facts = adapter.build_verified_facts(dispute_context)

    assert facts == {key: dispute_context[key] for key in VERIFIED_FACTS_ALLOWLIST}
    assert "complaint_id" not in facts
    assert "product_id" not in facts
    assert "customer_id" not in facts


def test_build_actions_taken_returns_exact_canonical_success_fields() -> None:
    adapter = _adapter()

    actions, has_failed_actions = adapter.build_actions_taken(
        [
            {
                "action": "block_card",
                "executed": True,
                "verification": "confirmed_blocked",
                "product_id": "PRD-1",
                "target_id": "PRD-1",
            }
        ]
    )

    assert actions == [
        {
            "action_name": "block_card",
            "executed": True,
            "verification": "confirmed_blocked",
        }
    ]
    assert set(actions[0]) == ACTION_REQUIRED_FIELDS
    assert "target_id" not in actions[0]
    assert has_failed_actions is False


@pytest.mark.parametrize(
    "result",
    [
        {
            "action": "block_card",
            "executed": False,
            "reason": "already_blocked",
        },
        {
            "action": "block_card",
            "executed": False,
            "reason": "already_blocked",
            "verification": "already_blocked_no_action_taken",
        },
    ],
)
def test_build_actions_taken_normalizes_idempotent_block(result: dict) -> None:
    actions, failed = _adapter().build_actions_taken([result])

    assert actions == [
        {
            "action_name": "block_card",
            "executed": False,
            "verification": "already_blocked_no_action_taken",
        }
    ]
    assert failed is False


@pytest.mark.parametrize(
    "result",
    [
        {
            "action": "block_card",
            "reason": "already_blocked",
        },
        {
            "action": "block_card",
            "executed": True,
            "reason": "already_blocked",
        },
        {
            "action": "block_card",
            "executed": False,
            "reason": "already_blocked",
            "verification": "confirmed_blocked",
        },
        {
            "action": "escalate_case",
            "executed": False,
            "reason": "already_blocked",
        },
    ],
)
def test_build_actions_taken_rejects_invalid_idempotency(result: dict) -> None:
    with pytest.raises(ValueError):
        _adapter().build_actions_taken([result])


def test_build_actions_taken_preserves_order_and_flags_failed_actions() -> None:
    actions, failed = _adapter().build_actions_taken(
        [
            {"complaint_id": "CMP-1"},
            {
                "action": "escalate_case",
                "executed": True,
                "verification": "confirmed_persisted",
            },
            {
                "action": "block_card",
                "executed": False,
                "verification": "block_not_confirmed",
                "error": "write failed",
            },
            {
                "action": "block_card",
                "executed": True,
                "verification": "confirmed_blocked",
            },
        ]
    )

    assert [action["action_name"] for action in actions] == [
        "escalate_case",
        "block_card",
    ]
    assert failed is True


@pytest.mark.parametrize(
    "result",
    [
        {
            "action": "block_card",
            "executed": False,
            "verification": "confirmed_blocked",
        },
        {
            "action": "block_card",
            "executed": 1,
            "verification": "confirmed_blocked",
        },
        {"action": "unknown", "executed": True, "verification": "confirmed"},
        {"action": "block_card", "executed": True},
        "not-a-dict",
    ],
)
def test_build_actions_taken_rejects_malformed_results(result: object) -> None:
    with pytest.raises(ValueError):
        _adapter().build_actions_taken([result])  # type: ignore[list-item]


def test_build_actions_taken_omits_policy_denial_and_read_result() -> None:
    actions, failed = _adapter().build_actions_taken(
        [
            {"transactions": []},
            {
                "action": "block_card",
                "executed": False,
                "reason": "customer_confirmation_required",
            },
        ]
    )

    assert actions == []
    assert failed is False
