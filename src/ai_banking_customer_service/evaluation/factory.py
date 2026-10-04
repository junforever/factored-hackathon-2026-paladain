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
from ai_banking_customer_service.evaluation.sink import RecordingAuditSink
from ai_banking_customer_service.governance.adapter import GovernanceAdapter
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


def build_evaluation_dependencies(
    *,
    state_dir: Path,
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
    adapter = GovernanceAdapter(
        client=client,
        thresholds=GovernanceThresholds.from_policy(policy.governance),
        tool_gating_thresholds=ToolGatingThresholds.from_policy(policy.tool_gating),
        output_screening_thresholds=OutputScreeningThresholds.from_policy(
            policy.output_screening
        ),
        audit_sink=audit_sink,
        dispute_context_loader=get_dispute_context,
    )
    orchestrator = BankingOrchestrator(
        adapter=adapter,
        governance_hooks=GovernanceHooks(adapter),
        audit_sink=audit_sink,
        session_manager=SessionManager(),
        model_factory=model_factory,
        tools=build_evaluation_tools(state_dir=state_dir),
    )
    return EvaluationDependencies(orchestrator, recording_sink)


def build_evaluation_tools(*, state_dir: Path) -> list:
    """Bind the two case-local SQLite files into canonical model-facing tools."""
    return build_registered_tools(
        card_db_path=state_dir / "card_service.sqlite3",
        escalation_db_path=state_dir / "escalation_service.sqlite3",
    )
