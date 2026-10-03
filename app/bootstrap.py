"""Composition root for the banking customer-service application."""

from ai_banking_customer_service.agent.hooks import GovernanceHooks
from ai_banking_customer_service.agent.orchestrator import BankingOrchestrator
from ai_banking_customer_service.agent.session_manager import SessionManager
from ai_banking_customer_service.config import policy, settings
from ai_banking_customer_service.governance.adapter import GovernanceAdapter
from ai_banking_customer_service.governance.jev import JevClient
from ai_banking_customer_service.governance.jev.decision import (
    GovernanceThresholds,
    OutputScreeningThresholds,
    ToolGatingThresholds,
)
from ai_banking_customer_service.observability.sink import (
    CompositeAuditSink,
    JsonlAuditSink,
)
from ai_banking_customer_service.tools.get_dispute_context import get_dispute_context


def build_orchestrator() -> BankingOrchestrator:
    """Build the real orchestrator dependency graph in its normative order."""
    thresholds = GovernanceThresholds.from_policy(policy.governance)
    tool_gating_thresholds = ToolGatingThresholds.from_policy(policy.tool_gating)
    output_screening_thresholds = OutputScreeningThresholds.from_policy(
        policy.output_screening
    )
    dispute_context_loader = get_dispute_context

    primary_sink = JsonlAuditSink(settings.audit_log_full_path)
    fallback_sink = JsonlAuditSink(settings.audit_fallback_full_path)
    audit_sink = CompositeAuditSink(primary_sink, fallback_sink)

    jev_client = JevClient(
        api_key=settings.typesafe_api_key,
        model=settings.typesafe_default_model,
        timeout_seconds=settings.typesafe_timeout_seconds,
    )
    adapter = GovernanceAdapter(
        client=jev_client,
        thresholds=thresholds,
        tool_gating_thresholds=tool_gating_thresholds,
        output_screening_thresholds=output_screening_thresholds,
        audit_sink=audit_sink,
        dispute_context_loader=dispute_context_loader,
    )
    governance_hooks = GovernanceHooks(adapter)
    session_manager = SessionManager(
        max_messages_per_session=settings.session_max_messages,
        ttl_seconds=settings.session_ttl_seconds,
    )
    return BankingOrchestrator(
        adapter=adapter,
        governance_hooks=governance_hooks,
        audit_sink=audit_sink,
        session_manager=session_manager,
    )
