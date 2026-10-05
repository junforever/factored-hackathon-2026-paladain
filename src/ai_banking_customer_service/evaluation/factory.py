"""Child-local evaluation dependency composition helpers."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_banking_customer_service.agent.hooks import GovernanceHooks
from ai_banking_customer_service.agent.orchestrator import BankingOrchestrator
from ai_banking_customer_service.agent.session_manager import SessionManager
from ai_banking_customer_service.agent.tools import build_registered_tools
from ai_banking_customer_service.config import policy, settings
from ai_banking_customer_service.evaluation.cases import EvalCase
from ai_banking_customer_service.evaluation.sink import RecordingAuditSink
from ai_banking_customer_service.governance.adapter import (
    GovernanceAdapter,
    ProductAuthorization,
)
from ai_banking_customer_service.governance.jev import JevClient
from ai_banking_customer_service.governance.jev.decision import (
    GovernanceThresholds,
    OutputScreeningThresholds,
    ToolGatingThresholds,
)
from ai_banking_customer_service.observability.sink import CompositeAuditSink
from ai_banking_customer_service.tools.get_dispute_context import get_dispute_context


@dataclass(frozen=True)
class EvaluationDependencies:
    orchestrator: BankingOrchestrator
    recording_sink: RecordingAuditSink


class _CaseProductAuthorizationProvider:
    __slots__ = (
        "_authenticated",
        "_principal",
        "_product_authorized",
        "_product_id",
    )

    def __init__(
        self,
        *,
        principal: object,
        product_id: str,
        authenticated: bool,
        product_authorized: bool,
    ) -> None:
        self._principal = principal
        self._product_id = product_id
        self._authenticated = authenticated
        self._product_authorized = product_authorized

    def authorize_product(
        self,
        *,
        principal: object,
        product_id: str,
    ) -> ProductAuthorization:
        if principal is not self._principal or not self._authenticated:
            return ProductAuthorization(False, False, "not_authenticated")
        if product_id != self._product_id or not self._product_authorized:
            return ProductAuthorization(True, False, "product_not_authorized")
        return ProductAuthorization(True, True, "authorized")


def build_evaluation_dependencies(
    *,
    state_dir: Path,
    case: EvalCase,
    principal: object,
    model_factory: Callable[[], Any] | None = None,
) -> EvaluationDependencies:
    """Build the complete case-local dependency graph inside a child process."""
    recording_sink = RecordingAuditSink()
    fallback_sink = RecordingAuditSink()
    audit_sink = CompositeAuditSink(recording_sink, fallback_sink)
    client = JevClient(
        api_key=settings.typesafe_api_key,
        model=settings.typesafe_default_model,
        timeout_seconds=settings.typesafe_timeout_seconds,
    )
    authorization_provider = _build_case_authorization_provider(case, principal)
    adapter = GovernanceAdapter(
        client=client,
        thresholds=GovernanceThresholds.from_policy(policy.governance),
        tool_gating_thresholds=ToolGatingThresholds.from_policy(policy.tool_gating),
        output_screening_thresholds=OutputScreeningThresholds.from_policy(
            policy.output_screening
        ),
        audit_sink=audit_sink,
        dispute_context_loader=get_dispute_context,
        product_authorization_provider=authorization_provider,
    )
    orchestrator = BankingOrchestrator(
        adapter=adapter,
        governance_hooks=GovernanceHooks(adapter, principal=principal),
        audit_sink=audit_sink,
        session_manager=SessionManager(),
        model_factory=model_factory,
        tools=build_evaluation_tools(state_dir=state_dir),
    )
    return EvaluationDependencies(orchestrator, recording_sink)


def _build_case_authorization_provider(
    case: EvalCase,
    principal: object,
) -> _CaseProductAuthorizationProvider:
    authorization = case.expected.authorization
    if authorization is None:
        raise ValueError("evaluation authorization expectation unavailable")
    complaint_id = case.expected.complaint_id
    if not isinstance(complaint_id, str) or not complaint_id.strip():
        raise ValueError("evaluation authorization context unavailable")
    try:
        context = get_dispute_context(complaint_id)
    except Exception:
        raise ValueError("evaluation authorization context unavailable") from None
    if not isinstance(context, dict) or "error" in context:
        raise ValueError("evaluation authorization context unavailable")
    if context.get("complaint_id") != complaint_id:
        raise ValueError("evaluation authorization context unavailable")
    product_id = context.get("product_id")
    if not isinstance(product_id, str) or not product_id.strip():
        raise ValueError("evaluation authorization context unavailable")
    return _CaseProductAuthorizationProvider(
        principal=principal,
        product_id=product_id,
        authenticated=authorization.authenticated,
        product_authorized=authorization.product_authorized,
    )


def build_evaluation_tools(*, state_dir: Path) -> list:
    """Bind the two case-local SQLite files into canonical model-facing tools."""
    return build_registered_tools(
        card_db_path=state_dir / "card_service.sqlite3",
        escalation_db_path=state_dir / "escalation_service.sqlite3",
    )
