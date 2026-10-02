from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from strands.hooks import (
    BeforeInvocationEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

from ai_banking_customer_service.agent.hooks import GovernanceHooks, create_hooks
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
        call(BeforeToolCallEvent, hooks.before_tool_call),
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

    adapter.build_customer_context.assert_called_once_with("CMP-1")
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
    )
    assert event.cancel_tool == expected_cancel
    assert state["tool_governance"]["tool-use-1"] == {
        "decision": decision,
        "action": action.value,
        "event_id": "tool-governance-event-1",
        "reason": None,
    }
    assert _global_state(state) == globals_before
    assert "customer_context" not in state


def test_concurrent_duplicate_tool_calls_remain_independent_siblings() -> None:
    class ConcurrentAdapter:
        def __init__(self) -> None:
            self.barrier = __import__("threading").Barrier(2)
            self.lock = __import__("threading").Lock()
            self.gate_calls: list[dict] = []
            self.context_calls: list[str] = []

        def build_customer_context(self, complaint_id: str) -> dict:
            with self.lock:
                self.context_calls.append(complaint_id)
            return {"verified_complaint_ids": (complaint_id,)}

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
    assert adapter.context_calls == ["CMP-SAME", "CMP-SAME"]
    assert len(adapter.gate_calls) == 2
    assert all(
        recorded["kwargs"] == {"parent_event_id": "routing-event-1"}
        for recorded in adapter.gate_calls
    )
    assert _global_state(state) == globals_before
    assert all(event.cancel_tool is False for event in events)
