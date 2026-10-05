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
from ai_banking_customer_service.observability.contract import (
    AUTHORIZATION_REASON_CODES,
    AUTHORIZATION_RESULTS,
)

_AUTHORIZATION_RESULT_BY_REASON = {
    "authorized": "allowed",
    "not_authenticated": "denied",
    "product_not_authorized": "denied",
    "authorization_unavailable": "unavailable",
    "invalid_authorization_result": "unavailable",
}


class GovernanceHooks(HookProvider):
    """Provide governance callbacks for the Strands lifecycle."""

    def __init__(
        self,
        adapter: GovernanceAdapter,
        *,
        principal: object | None = None,
    ) -> None:
        self._adapter = adapter
        self._principal = principal

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register input and tool governance callbacks."""
        registry.add_callback(BeforeInvocationEvent, self.before_invocation)
        registry.add_callback(BeforeToolCallEvent, self.before_tool_call)

    def before_invocation(self, event: BeforeInvocationEvent) -> None:
        """Screen and route the latest user message."""
        state = event.invocation_state
        for key in (
            "intent",
            "customer_message",
            "routing_event_id",
            "governance_decision",
            "governance_action",
        ):
            state.pop(key, None)
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
            orphaned=bool(state.get("audit_orphaned", False)),
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
                "authorization_result": "not_evaluated",
                "authorization_reason_code": None,
                "authorization_verified": False,
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
        principal = customer_id if self._principal is None else self._principal
        customer_context = self._adapter.build_customer_context(
            complaint_id,
            principal=principal,
        )
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
            orphaned=bool(state.get("audit_orphaned", False)),
        )
        authorization_result, reason_code, authorization_verified = (
            _authorization_observability(customer_context)
        )
        tool_governance[tool_use_id] = {
            "decision": result.decision,
            "action": result.decision.action.value,
            "event_id": result.event_id,
            "reason": None,
            "authorization_result": authorization_result,
            "authorization_reason_code": reason_code,
            "authorization_verified": authorization_verified,
        }
        if result.decision.action is GovernanceAction.BLOCK:
            event.cancel_tool = "governance:block"


def _authorization_observability(
    customer_context: object,
) -> tuple[str, str | None, bool]:
    if not isinstance(customer_context, dict):
        return "not_evaluated", None, False
    reason = customer_context.get("authorization_reason")
    if reason not in AUTHORIZATION_REASON_CODES:
        return "not_evaluated", None, False
    result = _AUTHORIZATION_RESULT_BY_REASON[reason]
    if result not in AUTHORIZATION_RESULTS:
        return "not_evaluated", None, False

    authenticated = customer_context.get("authenticated")
    authorized_ids = customer_context.get("authorized_product_ids")
    valid_authorized_ids = (
        isinstance(authorized_ids, tuple)
        and bool(authorized_ids)
        and all(_is_nonempty_string(value) for value in authorized_ids)
    )
    if reason == "authorized":
        if authenticated is True and valid_authorized_ids:
            return result, reason, True
        return "not_evaluated", None, False
    if authorized_ids != ():
        return "not_evaluated", None, False
    if reason == "product_not_authorized" and authenticated is not True:
        return "not_evaluated", None, False
    if reason != "product_not_authorized" and authenticated is not False:
        return "not_evaluated", None, False
    return result, reason, False


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
