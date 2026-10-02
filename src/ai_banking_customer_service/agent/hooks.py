"""Strands lifecycle hooks that integrate the governance adapter."""

from typing import Any

from strands.hooks import (
    BeforeInvocationEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

from ai_banking_customer_service.governance.adapter import GovernanceAdapter
from ai_banking_customer_service.governance.jev.decision import GovernanceAction


class GovernanceHooks(HookProvider):
    """Provide governance callbacks for the Strands lifecycle."""

    def __init__(self, adapter: GovernanceAdapter) -> None:
        self._adapter = adapter

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register input and tool governance callbacks."""
        registry.add_callback(BeforeInvocationEvent, self.before_invocation)
        registry.add_callback(BeforeToolCallEvent, self.before_tool_call)

    def before_invocation(self, event: BeforeInvocationEvent) -> None:
        """Screen and route the latest user message."""
        state = event.invocation_state
        state["tool_governance"] = {}
        message = _last_user_text(event.messages)
        if message is None:
            _cancel_invocation(event)
            return

        required = (
            state.get("trace_id"),
            state.get("session_id"),
            state.get("customer_id"),
        )
        if not all(_is_nonempty_string(value) for value in required):
            _cancel_invocation(event)
            return

        trace_id, session_id, customer_id = required
        result = self._adapter.screen_and_route(
            message,
            trace_id,
            session_id,
            customer_id,
            parent_event_id=state.get("input_event_id"),
        )
        state.update(
            intent=result.intent,
            customer_message=message,
            routing_event_id=result.last_event_id,
            governance_decision=result.final_decision,
            governance_action=result.final_decision.action.value,
        )
        if not result.should_continue:
            event.cancel = f"governance:{result.final_decision.action.value}"

    def before_tool_call(self, event: BeforeToolCallEvent) -> None:
        """Gate one tool call and keep its state isolated by toolUseId."""
        tool_use = event.tool_use
        if not isinstance(tool_use, dict):
            event.cancel_tool = "governance:block"
            return

        tool_use_id = tool_use.get("toolUseId")
        if not _is_nonempty_string(tool_use_id):
            event.cancel_tool = "governance:block"
            return

        state = event.invocation_state
        tool_governance = state.setdefault("tool_governance", {})
        if not isinstance(tool_governance, dict):
            event.cancel_tool = "governance:block"
            return

        def cancel_tool(reason: str) -> None:
            tool_governance[tool_use_id] = {
                "decision": None,
                "action": "block",
                "event_id": None,
                "reason": reason,
            }
            event.cancel_tool = "governance:block"

        tool_name = tool_use.get("name")
        if not _is_nonempty_string(tool_name):
            cancel_tool("invalid_tool_name")
            return

        tool_args = tool_use.get("input")
        if not isinstance(tool_args, dict):
            cancel_tool("invalid_tool_input")
            return

        complaint_id = tool_args.get("complaint_id")
        if not _is_nonempty_string(complaint_id):
            cancel_tool("invalid_complaint_id")
            return

        required = (
            state.get("trace_id"),
            state.get("session_id"),
            state.get("customer_id"),
            state.get("intent"),
            state.get("customer_message"),
            state.get("routing_event_id"),
        )
        if not all(_is_nonempty_string(value) for value in required):
            cancel_tool("invalid_invocation_state")
            return

        (
            trace_id,
            session_id,
            customer_id,
            intent,
            customer_message,
            routing_event_id,
        ) = required
        customer_context = self._adapter.build_customer_context(complaint_id)
        result = self._adapter.gate_tool_call(
            tool_name,
            tool_args,
            intent,
            customer_message,
            customer_context,
            trace_id,
            session_id,
            customer_id,
            parent_event_id=routing_event_id,
        )
        tool_governance[tool_use_id] = {
            "decision": result.decision,
            "action": result.decision.action.value,
            "event_id": result.event_id,
            "reason": None,
        }
        if result.decision.action is GovernanceAction.BLOCK:
            event.cancel_tool = "governance:block"


def create_hooks(adapter: GovernanceAdapter) -> list[HookProvider]:
    """Create the governance hook providers expected by Strands."""
    return [GovernanceHooks(adapter)]


def _last_user_text(messages: object) -> str | None:
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            return None
        text = "".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
        return text if text.strip() else None
    return None


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _cancel_invocation(event: BeforeInvocationEvent) -> None:
    event.invocation_state["governance_action"] = "block"
    event.cancel = "governance:block"
