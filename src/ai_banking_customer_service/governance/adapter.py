"""Framework-agnostic governance pipeline adapter."""

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from ai_banking_customer_service.governance.jev.client import JevClient
from ai_banking_customer_service.governance.jev.decision import (
    GovernanceAction,
    GovernanceDecision,
    GovernanceStage,
    GovernanceThresholds,
    OutputScreeningThresholds,
    ToolGatingThresholds,
    decide_output_screening,
    decide_routing,
    decide_screening,
    decide_tool_gating,
)
from ai_banking_customer_service.governance.jev.evaluations import (
    ACTION_VERIFICATIONS,
    VERIFIED_FACTS_ALLOWLIST,
    OutputScreeningResult,
    ToolGatingResult,
    route_banking_intent,
    screen_input,
)
from ai_banking_customer_service.governance.jev.evaluations import (
    gate_tool_call as evaluate_tool_call,
)
from ai_banking_customer_service.governance.jev.evaluations import (
    screen_agent_output as evaluate_output,
)
from ai_banking_customer_service.governance.jev.exceptions import (
    JevError,
    JevValidationError,
)
from ai_banking_customer_service.governance.jev.schemas import Usage
from ai_banking_customer_service.observability.sink import AuditSink


@dataclass(frozen=True)
class ProductAuthorization:
    """Canonical authentication and product-authorization result."""

    authenticated: bool
    product_authorized: bool
    reason_code: str


class ProductAuthorizationProvider(Protocol):
    """Return only the decision for the exact principal and product arguments."""

    def authorize_product(
        self,
        *,
        principal: object,
        product_id: str,
    ) -> ProductAuthorization: ...


_PROVIDER_AUTHORIZATION_TUPLES = {
    (True, True, "authorized"),
    (False, False, "not_authenticated"),
    (True, False, "product_not_authorized"),
}


@dataclass(frozen=True)
class ScreeningRoutingResult:
    """Result of input screening followed by intent routing."""

    final_decision: GovernanceDecision
    intent: str | None
    should_continue: bool
    last_event_id: str


@dataclass(frozen=True)
class GovernanceResult:
    """Result of one governance stage and its audit event."""

    decision: GovernanceDecision
    event_id: str


class GovernanceAdapter:
    """Coordinate governance evaluations, decisions, and audit events."""

    def __init__(
        self,
        client: JevClient,
        thresholds: GovernanceThresholds,
        tool_gating_thresholds: ToolGatingThresholds,
        output_screening_thresholds: OutputScreeningThresholds,
        audit_sink: AuditSink,
        dispute_context_loader: Callable[[str], dict],
        product_authorization_provider: ProductAuthorizationProvider | None = None,
    ) -> None:
        self._client = client
        self._thresholds = thresholds
        self._tool_gating_thresholds = tool_gating_thresholds
        self._output_screening_thresholds = output_screening_thresholds
        self._audit_sink = audit_sink
        self._dispute_context_loader = dispute_context_loader
        self._product_authorization_provider = product_authorization_provider

    def screen_and_route(
        self,
        message: str,
        trace_id: str,
        session_id: str,
        customer_id: str,
        parent_event_id: str | None = None,
        *,
        orphaned: bool = False,
    ) -> ScreeningRoutingResult:
        """Run input screening and, when allowed, intent routing."""
        _validate_orphaned(orphaned)
        started = time.monotonic()
        try:
            screening = screen_input(self._client, message)
        except JevValidationError:
            latency_ms = _latency_ms(started)
            decision = _fail_closed_decision(
                GovernanceStage.INPUT_SCREENING,
                GovernanceAction.BLOCK,
                "INPUT_SCREENING_VALIDATION_ERROR",
                self._thresholds,
            )
            event_id = self._emit_event(
                decision=decision,
                raw_result=None,
                latency_ms=latency_ms,
                trace_id=trace_id,
                session_id=session_id,
                customer_id=customer_id,
                parent_event_id=parent_event_id,
                orphaned=orphaned,
            )
            return ScreeningRoutingResult(decision, None, False, event_id)
        except JevError:
            latency_ms = _latency_ms(started)
            decision = _fail_closed_decision(
                GovernanceStage.INPUT_SCREENING,
                GovernanceAction.BLOCK,
                "JEV_ERROR",
                self._thresholds,
            )
            event_id = self._emit_event(
                decision=decision,
                raw_result=None,
                latency_ms=latency_ms,
                trace_id=trace_id,
                session_id=session_id,
                customer_id=customer_id,
                parent_event_id=parent_event_id,
                orphaned=orphaned,
            )
            return ScreeningRoutingResult(decision, None, False, event_id)
        except Exception:
            _latency_ms(started)
            raise
        latency_ms = _latency_ms(started)
        decision = decide_screening(screening, self._thresholds)
        event_id = self._emit_event(
            decision=decision,
            raw_result=screening,
            latency_ms=latency_ms,
            trace_id=trace_id,
            session_id=session_id,
            customer_id=customer_id,
            parent_event_id=parent_event_id,
            orphaned=orphaned,
        )
        if decision.action is not GovernanceAction.ALLOW:
            return ScreeningRoutingResult(decision, None, False, event_id)

        started = time.monotonic()
        try:
            routing = route_banking_intent(self._client, message)
        except JevValidationError:
            latency_ms = _latency_ms(started)
            decision = _fail_closed_decision(
                GovernanceStage.INTENT_ROUTING,
                GovernanceAction.BLOCK,
                "INTENT_ROUTING_VALIDATION_ERROR",
                self._thresholds,
            )
            event_id = self._emit_event(
                decision=decision,
                raw_result=None,
                latency_ms=latency_ms,
                trace_id=trace_id,
                session_id=session_id,
                customer_id=customer_id,
                parent_event_id=event_id,
                orphaned=orphaned,
            )
            return ScreeningRoutingResult(decision, None, False, event_id)
        except JevError:
            latency_ms = _latency_ms(started)
            decision = _fail_closed_decision(
                GovernanceStage.INTENT_ROUTING,
                GovernanceAction.BLOCK,
                "JEV_ERROR",
                self._thresholds,
            )
            event_id = self._emit_event(
                decision=decision,
                raw_result=None,
                latency_ms=latency_ms,
                trace_id=trace_id,
                session_id=session_id,
                customer_id=customer_id,
                parent_event_id=event_id,
                orphaned=orphaned,
            )
            return ScreeningRoutingResult(decision, None, False, event_id)
        except Exception:
            _latency_ms(started)
            raise
        latency_ms = _latency_ms(started)
        decision = decide_routing(routing, self._thresholds)
        event_id = self._emit_event(
            decision=decision,
            raw_result=routing,
            latency_ms=latency_ms,
            trace_id=trace_id,
            session_id=session_id,
            customer_id=customer_id,
            parent_event_id=event_id,
            orphaned=orphaned,
        )
        should_continue = decision.action is GovernanceAction.ALLOW
        return ScreeningRoutingResult(
            decision,
            decision.intent if should_continue else None,
            should_continue,
            event_id,
        )

    def build_customer_context(
        self,
        complaint_id: str,
        *,
        principal: object | None = None,
    ) -> dict:
        """Resolve the exact complaint before authorizing its product."""
        if not isinstance(complaint_id, str) or not complaint_id.strip():
            return _customer_context()
        try:
            context = self._dispute_context_loader(complaint_id)
        except Exception:
            return _customer_context()
        if not isinstance(context, dict) or "error" in context:
            return _customer_context()
        loaded_complaint_id = context.get("complaint_id")
        if (
            not isinstance(loaded_complaint_id, str)
            or not loaded_complaint_id.strip()
            or loaded_complaint_id != complaint_id
        ):
            return _customer_context()

        verified_complaint_ids = (complaint_id,)
        product_id = context.get("product_id")
        if not isinstance(product_id, str) or not product_id.strip():
            return _customer_context(verified_complaint_ids=verified_complaint_ids)
        if principal is None or (isinstance(principal, str) and not principal.strip()):
            return _customer_context(
                verified_complaint_ids=verified_complaint_ids,
                authorization=ProductAuthorization(False, False, "not_authenticated"),
            )
        if self._product_authorization_provider is None:
            return _customer_context(
                verified_complaint_ids=verified_complaint_ids,
                authorization=ProductAuthorization(
                    False, False, "authorization_unavailable"
                ),
            )

        try:
            authorization = self._product_authorization_provider.authorize_product(
                principal=principal,
                product_id=product_id,
            )
        except Exception:
            authorization = None
        if authorization is None:
            authorization = ProductAuthorization(
                False, False, "authorization_unavailable"
            )
        elif not _is_valid_provider_authorization(authorization):
            authorization = ProductAuthorization(
                False, False, "invalid_authorization_result"
            )
        return _customer_context(
            verified_complaint_ids=verified_complaint_ids,
            product_id=product_id,
            authorization=authorization,
        )

    def build_verified_facts(self, dispute_context: dict) -> dict:
        """Keep only facts approved for output screening."""
        return {
            key: value
            for key, value in dispute_context.items()
            if key in VERIFIED_FACTS_ALLOWLIST
        }

    def build_actions_taken(
        self,
        tool_results: list[dict],
    ) -> tuple[list[dict], bool]:
        """Normalize verified action results for output screening."""
        valid_actions = []
        has_failed_actions = False

        for result in tool_results:
            if not isinstance(result, dict):
                raise ValueError(f"Resultado de tool no es dict: {type(result)}")
            if "action" not in result:
                continue

            action_name = result["action"]
            if (
                not isinstance(action_name, str)
                or action_name not in ACTION_VERIFICATIONS
            ):
                raise ValueError(f"Acción desconocida: {action_name!r}")
            expected = ACTION_VERIFICATIONS[action_name]

            if result.get("reason") == "already_blocked":
                if action_name != "block_card" or result.get("executed") is not False:
                    raise ValueError(
                        "already_blocked requiere action=block_card y executed=False"
                    )
                if "verification" in result:
                    if result["verification"] != "already_blocked_no_action_taken":
                        raise ValueError(
                            "already_blocked tiene verification contradictoria"
                        )
                else:
                    valid_actions.append(
                        {
                            "action_name": action_name,
                            "executed": False,
                            "verification": "already_blocked_no_action_taken",
                        }
                    )
                    continue

            if "verification" in result:
                verification = result["verification"]
                if verification not in expected:
                    has_failed_actions = True
                    continue
                executed = result.get("executed")
                if not isinstance(executed, bool):
                    raise ValueError("executed debe ser bool")
                if executed is not expected[verification]:
                    raise ValueError("verification contradice executed")
                valid_actions.append(
                    {
                        "action_name": action_name,
                        "executed": executed,
                        "verification": verification,
                    }
                )
                continue

            if result.get("executed") is False and "reason" in result:
                continue
            raise ValueError(
                f"Resultado de tool malformado para action '{action_name}'"
            )

        return valid_actions, has_failed_actions

    def gate_tool_call(
        self,
        tool_name: str,
        tool_args: dict,
        intent: str,
        customer_message: str,
        customer_context: dict,
        trace_id: str,
        session_id: str,
        customer_id: str,
        parent_event_id: str | None = None,
        *,
        orphaned: bool = False,
    ) -> GovernanceResult:
        """Evaluate whether one concrete tool call may execute."""
        _validate_orphaned(orphaned)
        started = time.monotonic()
        try:
            gating = evaluate_tool_call(
                self._client,
                tool_name,
                tool_args,
                intent,
                customer_message,
                customer_context,
            )
        except JevValidationError:
            latency_ms = _latency_ms(started)
            decision = _fail_closed_decision(
                GovernanceStage.TOOL_GATING,
                GovernanceAction.BLOCK,
                "TOOL_GATING_VALIDATION_ERROR",
                self._tool_gating_thresholds,
            )
            return self._governance_result(
                decision,
                None,
                latency_ms,
                trace_id,
                session_id,
                customer_id,
                parent_event_id,
                orphaned=orphaned,
            )
        except JevError:
            latency_ms = _latency_ms(started)
            decision = _fail_closed_decision(
                GovernanceStage.TOOL_GATING,
                GovernanceAction.BLOCK,
                "JEV_ERROR",
                self._tool_gating_thresholds,
            )
            return self._governance_result(
                decision,
                None,
                latency_ms,
                trace_id,
                session_id,
                customer_id,
                parent_event_id,
                orphaned=orphaned,
            )
        except Exception:
            _latency_ms(started)
            raise
        latency_ms = _latency_ms(started)
        decision = decide_tool_gating(gating, self._tool_gating_thresholds)
        return self._governance_result(
            decision,
            gating,
            latency_ms,
            trace_id,
            session_id,
            customer_id,
            parent_event_id,
            orphaned=orphaned,
        )

    def screen_output(
        self,
        proposed_response: str,
        customer_message: str,
        verified_facts: dict,
        actions_taken: list,
        trace_id: str,
        session_id: str,
        customer_id: str,
        parent_event_id: str | None = None,
        *,
        orphaned: bool = False,
    ) -> GovernanceResult:
        """Evaluate whether a proposed response may be delivered."""
        _validate_orphaned(orphaned)
        started = time.monotonic()
        try:
            screening = evaluate_output(
                self._client,
                proposed_response,
                customer_message,
                verified_facts,
                actions_taken,
            )
        except JevValidationError:
            latency_ms = _latency_ms(started)
            decision = _fail_closed_decision(
                GovernanceStage.OUTPUT_SCREENING,
                GovernanceAction.REVIEW,
                "OUTPUT_SCREENING_VALIDATION_ERROR",
                self._output_screening_thresholds,
            )
            return self._governance_result(
                decision,
                None,
                latency_ms,
                trace_id,
                session_id,
                customer_id,
                parent_event_id,
                orphaned=orphaned,
            )
        except JevError:
            latency_ms = _latency_ms(started)
            decision = _fail_closed_decision(
                GovernanceStage.OUTPUT_SCREENING,
                GovernanceAction.REVIEW,
                "JEV_ERROR",
                self._output_screening_thresholds,
            )
            return self._governance_result(
                decision,
                None,
                latency_ms,
                trace_id,
                session_id,
                customer_id,
                parent_event_id,
                orphaned=orphaned,
            )
        except Exception:
            _latency_ms(started)
            raise
        latency_ms = _latency_ms(started)
        decision = decide_output_screening(
            screening,
            self._output_screening_thresholds,
        )
        return self._governance_result(
            decision,
            screening,
            latency_ms,
            trace_id,
            session_id,
            customer_id,
            parent_event_id,
            orphaned=orphaned,
        )

    def _governance_result(
        self,
        decision: GovernanceDecision,
        raw_result: object | None,
        latency_ms: int,
        trace_id: str,
        session_id: str,
        customer_id: str,
        parent_event_id: str | None,
        *,
        orphaned: bool,
    ) -> GovernanceResult:
        event_id = self._emit_event(
            decision=decision,
            raw_result=raw_result,
            latency_ms=latency_ms,
            trace_id=trace_id,
            session_id=session_id,
            customer_id=customer_id,
            parent_event_id=parent_event_id,
            orphaned=orphaned,
        )
        return GovernanceResult(decision, event_id)

    def _emit_event(
        self,
        *,
        decision: GovernanceDecision,
        raw_result: object | None,
        latency_ms: int,
        trace_id: str,
        session_id: str,
        customer_id: str,
        parent_event_id: str | None,
        orphaned: bool,
    ) -> str:
        event_id = str(uuid4())
        payload = {
            "stage": decision.stage.value,
            "signals": _signals(decision, raw_result),
            "decision": decision.action.value,
            "reasons": list(decision.reasons),
            "thresholds": asdict(decision.governance_thresholds),
        }
        if orphaned:
            payload["orphaned"] = True
        event = {
            "trace_id": trace_id,
            "event_id": event_id,
            "parent_event_id": parent_event_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "component": "governance",
            "event_type": "governance",
            "customer_id": _mask_customer_id(customer_id),
            "session_id": session_id,
            "outcome": {
                GovernanceAction.BLOCK: "blocked",
                GovernanceAction.REVIEW: "escalated",
                GovernanceAction.ALLOW: "success",
            }[decision.action],
            "latency_ms": latency_ms,
            "tokens": _tokens_from_usage(decision.usage),
            "cost_usd": None,
            "payload": payload,
        }
        self._audit_sink.emit(event)
        return event_id


def _customer_context(
    *,
    verified_complaint_ids: tuple[str, ...] = (),
    product_id: str | None = None,
    authorization: ProductAuthorization | None = None,
) -> dict:
    authorized_product_ids = (
        (product_id,)
        if authorization is not None
        and authorization.product_authorized is True
        and product_id is not None
        else ()
    )
    return {
        "authenticated": (
            authorization.authenticated if authorization is not None else False
        ),
        "verified_complaint_ids": verified_complaint_ids,
        "authorized_product_ids": authorized_product_ids,
        "authorization_reason": (
            authorization.reason_code if authorization is not None else None
        ),
    }


def _is_valid_provider_authorization(authorization: object) -> bool:
    if not isinstance(authorization, ProductAuthorization):
        return False
    if type(authorization.authenticated) is not bool:
        return False
    if type(authorization.product_authorized) is not bool:
        return False
    if not isinstance(authorization.reason_code, str):
        return False
    return (
        authorization.authenticated,
        authorization.product_authorized,
        authorization.reason_code,
    ) in _PROVIDER_AUTHORIZATION_TUPLES


def _validate_orphaned(orphaned: bool) -> None:
    if not isinstance(orphaned, bool):
        raise TypeError("orphaned must be bool")


def _fail_closed_decision(
    stage: GovernanceStage,
    action: GovernanceAction,
    reason_code: str,
    thresholds: GovernanceThresholds | ToolGatingThresholds | OutputScreeningThresholds,
) -> GovernanceDecision:
    return GovernanceDecision(
        action=action,
        stage=stage,
        reason_codes=(reason_code,),
        reasons=(reason_code,),
        model=None,
        usage=None,
        governance_thresholds=thresholds,
    )


def _signals(decision: GovernanceDecision, raw_result: object | None) -> dict:
    if decision.stage is GovernanceStage.INPUT_SCREENING:
        return {
            "prompt_injection": decision.prompt_injection_signal,
            "social_engineering": decision.social_engineering_signal,
        }
    if decision.stage is GovernanceStage.INTENT_ROUTING:
        return {
            "intent": decision.intent,
            "intent_confidence": decision.intent_confidence,
            "intent_probabilities": decision.intent_probabilities,
        }
    if decision.stage is GovernanceStage.TOOL_GATING:
        if isinstance(raw_result, ToolGatingResult):
            if raw_result.deterministic_block:
                return {
                    "intent_matches_tool": None,
                    "deterministic_reason": raw_result.deterministic_reason,
                }
            return {
                "intent_matches_tool": (
                    raw_result.intent_matches_tool.noul
                    if raw_result.intent_matches_tool is not None
                    else None
                )
            }
        return {"intent_matches_tool": None}
    if isinstance(raw_result, OutputScreeningResult):
        answer = raw_result.output_safety_semantic
        return {
            "score": answer.score if answer is not None else None,
            "confidence": answer.confidence if answer is not None else None,
            "secrets_detected": list(raw_result.secrets_detected),
        }
    return {"score": None, "confidence": None, "secrets_detected": []}


def _latency_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def _mask_customer_id(customer_id: str) -> str:
    if len(customer_id) <= 4:
        return "****"
    return "*" * (len(customer_id) - 4) + customer_id[-4:]


def _tokens_from_usage(usage: Usage | None) -> int | None:
    if usage is None or usage.input_tokens is None or usage.output_tokens is None:
        return None
    return usage.input_tokens + usage.output_tokens
