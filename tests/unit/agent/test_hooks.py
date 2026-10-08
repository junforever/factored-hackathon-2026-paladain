from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from strands.hooks import (
    AfterToolCallEvent,
    BeforeInvocationEvent,
    BeforeToolCallEvent,
    HookOrder,
    HookProvider,
    HookRegistry,
)

from ai_banking_customer_service.agent.hooks import GovernanceHooks, create_hooks
from ai_banking_customer_service.agent.result_capture import ResultCaptureHooks
from ai_banking_customer_service.governance.adapter import (
    GovernanceAdapter,
    GovernanceResult,
    ScreeningRoutingResult,
)
from ai_banking_customer_service.governance.jev.decision import GovernanceAction

_DEFAULT = object()


def _decision(action: GovernanceAction) -> SimpleNamespace:
    return SimpleNamespace(action=action)


def _adapter() -> Mock:
    return Mock(spec=GovernanceAdapter)


def _invocation_event(
    *,
    messages: object = _DEFAULT,
    state: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        messages=(
            [{"role": "user", "content": [{"text": "Cargo no reconocido"}]}]
            if messages is _DEFAULT
            else messages
        ),
        invocation_state=(
            {
                "trace_id": "trace-1",
                "session_id": "session-1",
                "customer_id": "customer-1",
                "input_event_id": "input-event-1",
            }
            if state is None
            else state
        ),
        cancel=False,
    )


def _tool_state() -> dict:
    return {
        "trace_id": "trace-1",
        "session_id": "session-1",
        "customer_id": "customer-1",
        "intent": "transaction_dispute",
        "customer_message": "Cargo no reconocido",
        "routing_event_id": "routing-event-1",
        "last_event_id": "stable-last-event",
        "governance_decision": object(),
        "governance_action": "allow",
        "tool_governance": {},
    }


def _tool_event(
    *,
    tool_use: object = _DEFAULT,
    state: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        tool_use=(
            {
                "toolUseId": "tool-use-1",
                "name": "block_card",
                "input": {
                    "complaint_id": "CMP-1",
                    "confirmed_by_customer": True,
                },
            }
            if tool_use is _DEFAULT
            else tool_use
        ),
        invocation_state=_tool_state() if state is None else state,
        cancel_tool=False,
    )


def _global_state(state: dict) -> tuple[object, object, object]:
    return (
        state.get("last_event_id"),
        state.get("governance_decision"),
        state.get("governance_action"),
    )


def test_create_hooks_returns_one_governance_hook_provider() -> None:
    adapter = _adapter()

    hooks = create_hooks(adapter)

    assert isinstance(hooks, list)
    assert len(hooks) == 1
    assert isinstance(hooks[0], GovernanceHooks)
    assert isinstance(hooks[0], HookProvider)


def test_register_hooks_registers_exactly_the_two_typed_callbacks() -> None:
    hooks = GovernanceHooks(_adapter())
    registry = Mock(spec=HookRegistry)

    hooks.register_hooks(registry)

    assert registry.add_callback.call_args_list == [
        call(BeforeInvocationEvent, hooks.before_invocation),
        call(
            BeforeToolCallEvent,
            hooks.before_tool_call,
            order=HookOrder.SDK_FIRST,
        ),
    ]


def test_before_invocation_uses_last_user_message_and_concatenates_text_blocks() -> (
    None
):
    adapter = _adapter()
    decision = _decision(GovernanceAction.ALLOW)
    adapter.screen_and_route.return_value = ScreeningRoutingResult(
        decision, "transaction_dispute", True, "routing-event-1"
    )
    event = _invocation_event(
        messages=[
            {"role": "user", "content": [{"text": "Older message"}]},
            {"role": "assistant", "content": [{"text": "How can I help?"}]},
            {
                "role": "user",
                "content": [
                    {"text": "Cargo no "},
                    {"image": {"format": "png"}},
                    {"text": "reconocido"},
                ],
            },
        ],
        state={
            "trace_id": "trace-1",
            "session_id": "session-1",
            "customer_id": "customer-1",
            "input_event_id": "input-event-1",
            "intent": "stale-intent",
            "customer_message": "stale-message",
            "routing_event_id": "stale-routing-event",
            "governance_decision": object(),
            "governance_action": "block",
            "tool_governance": {"stale": object()},
        },
    )

    GovernanceHooks(adapter).before_invocation(event)

    adapter.screen_and_route.assert_called_once_with(
        "Cargo no reconocido",
        "trace-1",
        "session-1",
        "customer-1",
        parent_event_id="input-event-1",
        orphaned=False,
    )
    assert event.cancel is False
    assert event.invocation_state == {
        "trace_id": "trace-1",
        "session_id": "session-1",
        "customer_id": "customer-1",
        "input_event_id": "input-event-1",
        "intent": "transaction_dispute",
        "customer_message": "Cargo no reconocido",
        "routing_event_id": "routing-event-1",
        "governance_decision": decision,
        "governance_action": "allow",
        "tool_governance": {},
    }
    assert "customer_context" not in event.invocation_state


@pytest.mark.parametrize("action", [GovernanceAction.BLOCK, GovernanceAction.REVIEW])
def test_before_invocation_cancels_with_the_adapter_decision(action) -> None:
    adapter = _adapter()
    decision = _decision(action)
    adapter.screen_and_route.return_value = ScreeningRoutingResult(
        decision, None, False, "governance-event-1"
    )
    event = _invocation_event()

    GovernanceHooks(adapter).before_invocation(event)

    assert event.cancel == f"governance:{action.value}"
    assert event.invocation_state["governance_decision"] is decision
    assert event.invocation_state["governance_action"] == action.value
    assert event.invocation_state["tool_governance"] == {}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("trace_id", None),
        ("trace_id", ""),
        ("session_id", "   "),
        ("customer_id", 123),
    ],
)
def test_before_invocation_missing_required_state_fails_closed_and_resets_tools(
    field: str,
    value: object,
) -> None:
    adapter = _adapter()
    state = {
        "trace_id": "trace-1",
        "session_id": "session-1",
        "customer_id": "customer-1",
        "tool_governance": {"stale": object()},
    }
    state[field] = value
    event = _invocation_event(state=state)

    GovernanceHooks(adapter).before_invocation(event)

    assert event.cancel == "governance:block"
    assert state["governance_action"] == "block"
    assert state["tool_governance"] == {}
    assert "customer_context" not in state
    adapter.screen_and_route.assert_not_called()


@pytest.mark.parametrize(
    "messages",
    [
        [],
        None,
        [{"role": "assistant", "content": [{"text": "No user"}]}],
        [{"role": "user", "content": [{"image": {}}]}],
        [{"role": "user", "content": [{"text": "   "}]}],
    ],
)
def test_before_invocation_without_user_text_fails_closed(messages: object) -> None:
    adapter = _adapter()
    event = _invocation_event(messages=messages)

    GovernanceHooks(adapter).before_invocation(event)

    assert event.cancel == "governance:block"
    assert event.invocation_state["governance_action"] == "block"
    assert event.invocation_state["tool_governance"] == {}
    adapter.screen_and_route.assert_not_called()


def test_before_invocation_passes_boolean_orphaned_without_changing_parent() -> None:
    adapter = _adapter()
    decision = _decision(GovernanceAction.ALLOW)
    adapter.screen_and_route.return_value = ScreeningRoutingResult(
        decision, "transaction_dispute", True, "routing-event-1"
    )
    state = {
        "trace_id": "trace-1",
        "session_id": "session-1",
        "customer_id": "customer-1",
        "input_event_id": None,
        "audit_orphaned": "truthy",
    }
    event = _invocation_event(state=state)

    GovernanceHooks(adapter).before_invocation(event)

    adapter.screen_and_route.assert_called_once_with(
        "Cargo no reconocido",
        "trace-1",
        "session-1",
        "customer-1",
        parent_event_id=None,
        orphaned=True,
    )


def test_before_invocation_clears_stale_derived_state_before_failing_closed() -> None:
    adapter = _adapter()
    state = {
        "trace_id": "trace-1",
        "session_id": "session-1",
        "customer_id": "customer-1",
        "input_event_id": "input-event-1",
        "intent": "stale-intent",
        "customer_message": "stale-message",
        "routing_event_id": "stale-routing-event",
        "governance_decision": object(),
        "governance_action": "allow",
        "missing_merchant_verified": True,
        "tool_governance": {"stale": object()},
    }
    event = _invocation_event(messages=[], state=state)

    GovernanceHooks(adapter).before_invocation(event)

    assert event.cancel == "governance:block"
    assert state == {
        "trace_id": "trace-1",
        "session_id": "session-1",
        "customer_id": "customer-1",
        "input_event_id": "input-event-1",
        "governance_action": "block",
        "tool_governance": {},
    }
    adapter.screen_and_route.assert_not_called()


@pytest.mark.parametrize(
    "tool_use",
    [
        None,
        [],
        {"id": "legacy-id", "name": "block_card", "input": {}},
        {"toolUseId": "", "name": "block_card", "input": {}},
        {"toolUseId": "   ", "name": "block_card", "input": {}},
        {"toolUseId": 123, "name": "block_card", "input": {}},
    ],
)
def test_before_tool_call_requires_dict_and_nonempty_exact_tool_use_id(
    tool_use: object,
) -> None:
    adapter = _adapter()
    state = _tool_state()
    state["tool_governance"] = {"existing": {"action": "allow"}}
    before = dict(state)
    event = _tool_event(tool_use=tool_use, state=state)

    GovernanceHooks(adapter).before_tool_call(event)

    assert event.cancel_tool == "governance:block"
    assert state == before
    adapter.build_customer_context.assert_not_called()
    adapter.gate_tool_call.assert_not_called()


def test_before_tool_call_rejects_non_dict_tool_governance_without_global_changes() -> (
    None
):
    adapter = _adapter()
    state = _tool_state()
    state["tool_governance"] = []
    globals_before = _global_state(state)
    event = _tool_event(state=state)

    GovernanceHooks(adapter).before_tool_call(event)

    assert event.cancel_tool == "governance:block"
    assert state["tool_governance"] == []
    assert _global_state(state) == globals_before
    adapter.build_customer_context.assert_not_called()
    adapter.gate_tool_call.assert_not_called()


@pytest.mark.parametrize(
    ("tool_use", "expected_reason"),
    [
        (
            {"toolUseId": "tool-use-1", "name": None, "input": {}},
            "invalid_tool_name",
        ),
        (
            {"toolUseId": "tool-use-1", "name": " ", "input": {}},
            "invalid_tool_name",
        ),
        (
            {"toolUseId": "tool-use-1", "name": "block_card", "input": None},
            "invalid_tool_input",
        ),
        (
            {"toolUseId": "tool-use-1", "name": "block_card", "input": []},
            "invalid_tool_input",
        ),
        (
            {"toolUseId": "tool-use-1", "name": "block_card", "input": {}},
            "invalid_complaint_id",
        ),
        (
            {
                "toolUseId": "tool-use-1",
                "name": "block_card",
                "input": {"complaint_id": "   "},
            },
            "invalid_complaint_id",
        ),
        (
            {
                "toolUseId": "tool-use-1",
                "name": "block_card",
                "input": {"complaint_id": 123},
            },
            "invalid_complaint_id",
        ),
    ],
)
def test_before_tool_call_records_exact_per_tool_validation_reason(
    tool_use: object,
    expected_reason: str,
) -> None:
    adapter = _adapter()
    state = _tool_state()
    globals_before = _global_state(state)
    event = _tool_event(tool_use=tool_use, state=state)

    GovernanceHooks(adapter).before_tool_call(event)

    assert event.cancel_tool == "governance:block"
    assert state["tool_governance"]["tool-use-1"] == {
        "decision": None,
        "action": "block",
        "event_id": None,
        "reason": expected_reason,
        "authorization_result": "not_evaluated",
        "authorization_reason_code": None,
        "authorization_verified": False,
    }
    assert _global_state(state) == globals_before
    adapter.build_customer_context.assert_not_called()
    adapter.gate_tool_call.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("trace_id", None),
        ("session_id", ""),
        ("customer_id", "   "),
        ("intent", 123),
        ("customer_message", None),
        ("routing_event_id", ""),
    ],
)
def test_before_tool_call_invalid_required_state_records_per_tool_block(
    field: str,
    value: object,
) -> None:
    adapter = _adapter()
    state = _tool_state()
    state[field] = value
    globals_before = _global_state(state)
    event = _tool_event(state=state)

    GovernanceHooks(adapter).before_tool_call(event)

    assert event.cancel_tool == "governance:block"
    assert state["tool_governance"]["tool-use-1"] == {
        "decision": None,
        "action": "block",
        "event_id": None,
        "reason": "invalid_invocation_state",
        "authorization_result": "not_evaluated",
        "authorization_reason_code": None,
        "authorization_verified": False,
    }
    assert _global_state(state) == globals_before
    adapter.build_customer_context.assert_not_called()
    adapter.gate_tool_call.assert_not_called()


@pytest.mark.parametrize(
    ("action", "expected_cancel"),
    [
        (GovernanceAction.ALLOW, False),
        (GovernanceAction.BLOCK, "governance:block"),
    ],
)
def test_before_tool_call_builds_complaint_context_and_records_adapter_result(
    action: GovernanceAction,
    expected_cancel: bool | str,
) -> None:
    adapter = _adapter()
    customer_context = {
        "authenticated": True,
        "verified_complaint_ids": ("CMP-1",),
        "authorized_product_ids": ("PRD-1",),
        "authorization_reason": "authorized",
    }
    decision = _decision(action)
    adapter.build_customer_context.return_value = customer_context
    adapter.gate_tool_call.return_value = GovernanceResult(
        decision, "tool-governance-event-1"
    )
    state = _tool_state()
    globals_before = _global_state(state)
    event = _tool_event(state=state)

    GovernanceHooks(adapter).before_tool_call(event)

    adapter.build_customer_context.assert_called_once_with(
        "CMP-1", principal="customer-1"
    )
    adapter.gate_tool_call.assert_called_once_with(
        "block_card",
        {"complaint_id": "CMP-1", "confirmed_by_customer": True},
        "transaction_dispute",
        "Cargo no reconocido",
        customer_context,
        "trace-1",
        "session-1",
        "customer-1",
        parent_event_id="routing-event-1",
        orphaned=False,
    )
    assert event.cancel_tool == expected_cancel
    assert state["tool_governance"]["tool-use-1"] == {
        "decision": decision,
        "action": action.value,
        "event_id": "tool-governance-event-1",
        "reason": None,
        "authorization_result": "allowed",
        "authorization_reason_code": "authorized",
        "authorization_verified": True,
    }
    assert _global_state(state) == globals_before
    assert "customer_context" not in state


@pytest.mark.parametrize(
    ("tool_name", "tool_args", "customer_message"),
    [
        ("get_dispute_context", {"complaint_id": "CMP-Exact"}, "Cargo no reconocido"),
        (
            "get_recent_transactions",
            {"complaint_id": "CMP-Exact"},
            "Quais foram minhas transações recentes?",
        ),
        (
            "block_card",
            {"complaint_id": "CMP-Exact", "confirmed_by_customer": True},
            "Confirmo el bloqueo de la tarjeta",
        ),
        (
            "escalate_case",
            {"complaint_id": "CMP-Exact", "reason": "cliente_pede_humano"},
            "Quero falar com uma pessoa",
        ),
    ],
)
def test_before_tool_call_uses_one_explicit_principal_gate_for_all_sensitive_tools(
    tool_name: str,
    tool_args: dict,
    customer_message: str,
) -> None:
    adapter = _adapter()
    principal = object()
    customer_context = {
        "authenticated": True,
        "verified_complaint_ids": ("CMP-Exact",),
        "authorized_product_ids": ("PRD-Exact",),
        "authorization_reason": "authorized",
    }
    adapter.build_customer_context.return_value = customer_context
    adapter.gate_tool_call.return_value = GovernanceResult(
        _decision(GovernanceAction.ALLOW), "tool-governance-event-1"
    )
    state = _tool_state()
    state["customer_message"] = customer_message
    event = _tool_event(
        tool_use={
            "toolUseId": "tool-use-1",
            "name": tool_name,
            "input": tool_args,
        },
        state=state,
    )

    GovernanceHooks(adapter, principal=principal).before_tool_call(event)

    adapter.build_customer_context.assert_called_once_with(
        "CMP-Exact", principal=principal
    )
    assert adapter.gate_tool_call.call_args.args[:5] == (
        tool_name,
        tool_args,
        "transaction_dispute",
        customer_message,
        customer_context,
    )
    assert event.cancel_tool is False


def _capture_canonical_missing_merchant(
    adapter: Mock,
) -> tuple[HookRegistry, dict]:
    adapter.build_customer_context.return_value = {
        "authenticated": True,
        "authorized_product_ids": ("PRD-1",),
        "authorization_reason": "authorized",
    }
    adapter.gate_tool_call.return_value = GovernanceResult(
        _decision(GovernanceAction.ALLOW), "tool-governance-event-1"
    )
    registry = HookRegistry()
    registry.add_hook(GovernanceHooks(adapter))
    registry.add_hook(ResultCaptureHooks())
    state = _tool_state()
    read = {
        "toolUseId": "read-1",
        "name": "get_recent_transactions",
        "input": {"complaint_id": "CMP-1"},
    }
    registry.invoke_callbacks(
        BeforeToolCallEvent(
            agent=SimpleNamespace(),
            selected_tool=None,
            tool_use=read,
            invocation_state=state,
        )
    )
    registry.invoke_callbacks(
        AfterToolCallEvent(
            agent=SimpleNamespace(),
            selected_tool=None,
            tool_use=read,
            invocation_state=state,
            result={
                "status": "success",
                "content": [{"json": {"transactions": [{"merchant_name": None}]}}],
            },
        )
    )
    return registry, state


@pytest.mark.parametrize("tool_name", ["block_card", "escalate_case"])
def test_canonical_missing_merchant_cancels_later_write_before_service(
    tool_name: str,
) -> None:
    adapter = _adapter()
    registry, state = _capture_canonical_missing_merchant(adapter)
    event = BeforeToolCallEvent(
        agent=SimpleNamespace(),
        selected_tool=None,
        tool_use={
            "toolUseId": "write-1",
            "name": tool_name,
            "input": {"complaint_id": "CMP-1"},
        },
        invocation_state=state,
    )
    service = Mock()

    registry.invoke_callbacks(event)
    if not event.cancel_tool:
        service()

    assert state["tool_governance"]["write-1"]["action"] == "allow"
    assert event.cancel_tool == "missing_merchant:clarification"
    service.assert_not_called()


def test_missing_merchant_preserves_governance_denial_reason() -> None:
    adapter = _adapter()
    registry, state = _capture_canonical_missing_merchant(adapter)
    adapter.build_customer_context.return_value = {
        "authenticated": True,
        "authorized_product_ids": (),
        "authorization_reason": "product_not_authorized",
    }
    adapter.gate_tool_call.return_value = GovernanceResult(
        _decision(GovernanceAction.BLOCK), "tool-governance-event-2"
    )
    event = BeforeToolCallEvent(
        agent=SimpleNamespace(),
        selected_tool=None,
        tool_use={
            "toolUseId": "tool-use-1",
            "name": "block_card",
            "input": {"complaint_id": "CMP-1", "confirmed_by_customer": True},
        },
        invocation_state=state,
    )

    registry.invoke_callbacks(event)

    assert event.cancel_tool == "governance:block"
    assert state["tool_governance"]["tool-use-1"]["action"] == "block"
    assert state["tool_governance"]["tool-use-1"]["authorization_reason_code"] == (
        "product_not_authorized"
    )


def test_missing_merchant_does_not_block_reads() -> None:
    adapter = _adapter()
    registry, state = _capture_canonical_missing_merchant(adapter)
    event = BeforeToolCallEvent(
        agent=SimpleNamespace(),
        selected_tool=None,
        tool_use={
            "toolUseId": "read-2",
            "name": "get_recent_transactions",
            "input": {"complaint_id": "CMP-1"},
        },
        invocation_state=state,
    )

    registry.invoke_callbacks(event)

    assert event.cancel_tool is False


def test_before_tool_call_passes_boolean_orphaned_without_changing_parent() -> None:
    adapter = _adapter()
    adapter.build_customer_context.return_value = {"authenticated": True}
    adapter.gate_tool_call.return_value = GovernanceResult(
        _decision(GovernanceAction.ALLOW), "tool-governance-event-1"
    )
    state = _tool_state()
    state["audit_orphaned"] = 1
    event = _tool_event(state=state)

    GovernanceHooks(adapter).before_tool_call(event)

    assert adapter.gate_tool_call.call_args.kwargs == {
        "parent_event_id": "routing-event-1",
        "orphaned": True,
    }


def test_concurrent_duplicate_tool_calls_remain_independent_siblings() -> None:
    class ConcurrentAdapter:
        def __init__(self) -> None:
            self.barrier = __import__("threading").Barrier(2)
            self.lock = __import__("threading").Lock()
            self.gate_calls: list[dict] = []
            self.context_calls: list[str] = []

        def build_customer_context(
            self,
            complaint_id: str,
            *,
            principal: object,
        ) -> dict:
            assert principal == "customer-1"
            with self.lock:
                self.context_calls.append(complaint_id)
            return {
                "authenticated": True,
                "verified_complaint_ids": (complaint_id,),
                "authorized_product_ids": ("PRD-SAME",),
                "authorization_reason": "authorized",
            }

        def gate_tool_call(self, *args, **kwargs) -> GovernanceResult:
            with self.lock:
                event_id = f"tool-event-{len(self.gate_calls) + 1}"
                self.gate_calls.append({"args": args, "kwargs": kwargs})
            self.barrier.wait(timeout=2)
            return GovernanceResult(_decision(GovernanceAction.ALLOW), event_id)

    adapter = ConcurrentAdapter()
    hooks = GovernanceHooks(adapter)  # type: ignore[arg-type]
    state = _tool_state()
    state["tool_governance"] = {}
    globals_before = _global_state(state)
    events = [
        _tool_event(
            tool_use={
                "toolUseId": tool_use_id,
                "name": "block_card",
                "input": {"complaint_id": "CMP-SAME"},
            },
            state=state,
        )
        for tool_use_id in ("tool-use-a", "tool-use-b")
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(hooks.before_tool_call, events))

    assert set(state["tool_governance"]) == {"tool-use-a", "tool-use-b"}
    assert {entry["event_id"] for entry in state["tool_governance"].values()} == {
        "tool-event-1",
        "tool-event-2",
    }
    assert all(
        entry["action"] == "allow" for entry in state["tool_governance"].values()
    )
    assert all(
        entry["authorization_verified"] is True
        and entry["authorization_result"] == "allowed"
        and entry["authorization_reason_code"] == "authorized"
        for entry in state["tool_governance"].values()
    )
    assert adapter.context_calls == ["CMP-SAME", "CMP-SAME"]
    assert len(adapter.gate_calls) == 2
    assert all(
        recorded["kwargs"] == {"parent_event_id": "routing-event-1", "orphaned": False}
        for recorded in adapter.gate_calls
    )
    assert _global_state(state) == globals_before
    assert all(event.cancel_tool is False for event in events)


@pytest.mark.parametrize(
    ("context", "result", "reason_code", "verified"),
    [
        (
            {
                "authenticated": True,
                "authorized_product_ids": ("PRD-1",),
                "authorization_reason": "authorized",
            },
            "allowed",
            "authorized",
            True,
        ),
        (
            {
                "authenticated": False,
                "authorized_product_ids": (),
                "authorization_reason": "not_authenticated",
            },
            "denied",
            "not_authenticated",
            False,
        ),
        (
            {
                "authenticated": True,
                "authorized_product_ids": (),
                "authorization_reason": "product_not_authorized",
            },
            "denied",
            "product_not_authorized",
            False,
        ),
        (
            {
                "authenticated": False,
                "authorized_product_ids": (),
                "authorization_reason": "authorization_unavailable",
            },
            "unavailable",
            "authorization_unavailable",
            False,
        ),
        (
            {
                "authenticated": False,
                "authorized_product_ids": (),
                "authorization_reason": "invalid_authorization_result",
            },
            "unavailable",
            "invalid_authorization_result",
            False,
        ),
        ({"authorization_reason": None}, "not_evaluated", None, False),
    ],
)
def test_before_tool_call_records_only_bounded_authorization_observability(
    context: dict,
    result: str,
    reason_code: str | None,
    verified: bool,
) -> None:
    adapter = _adapter()
    sentinel = object()
    private_markers = {
        "principal": sentinel,
        "product_id": "PRD-PRIVATE",
        "provider_error": "D:/private/provider token=secret",
        "raw_jev_state": {"private": True},
    }
    adapter.build_customer_context.return_value = {**context, **private_markers}
    adapter.gate_tool_call.return_value = GovernanceResult(
        _decision(GovernanceAction.BLOCK), "tool-governance-event-1"
    )
    state = _tool_state()

    GovernanceHooks(adapter).before_tool_call(_tool_event(state=state))

    authorization = state["tool_governance"]["tool-use-1"]
    assert authorization["authorization_result"] == result
    assert authorization["authorization_reason_code"] == reason_code
    assert authorization["authorization_verified"] is verified
    serialized = repr(authorization)
    for marker in private_markers.values():
        assert repr(marker) not in serialized
    assert str(hash(sentinel)) not in serialized
