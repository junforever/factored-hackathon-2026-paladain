from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, sentinel

import pytest

from app import bootstrap, chainlit_app


def test_build_orchestrator_composes_dependencies_in_normative_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []
    policy = SimpleNamespace(
        governance=sentinel.governance_policy,
        tool_gating=sentinel.tool_gating_policy,
        output_screening=sentinel.output_screening_policy,
    )
    settings = SimpleNamespace(
        audit_log_full_path=Path("primary.jsonl"),
        audit_fallback_full_path=Path("fallback.jsonl"),
        typesafe_api_key=sentinel.api_key,
        typesafe_default_model="jev-test",
        typesafe_timeout_seconds=4.5,
        session_max_messages=12,
        session_ttl_seconds=34,
    )

    def threshold_factory(name: str, result: object):
        class Factory:
            @staticmethod
            def from_policy(value: object) -> object:
                calls.append((name, value))
                return result

        return Factory

    def jsonl_sink(path: Path) -> object:
        calls.append(("jsonl_sink", path))
        if path == settings.audit_log_full_path:
            return sentinel.primary_sink
        return sentinel.fallback_sink

    def composite_sink(primary: object, fallback: object) -> object:
        calls.append(("composite_sink", (primary, fallback)))
        return sentinel.shared_audit_sink

    def jev_client(**kwargs: object) -> object:
        calls.append(("jev_client", kwargs))
        return sentinel.jev_client

    def adapter(**kwargs: object) -> object:
        calls.append(("adapter", kwargs))
        return sentinel.adapter

    def hooks(value: object) -> object:
        calls.append(("hooks", value))
        return sentinel.hooks

    def session_manager(**kwargs: object) -> object:
        calls.append(("session_manager", kwargs))
        return sentinel.session_manager

    def orchestrator(**kwargs: object) -> object:
        calls.append(("orchestrator", kwargs))
        return sentinel.orchestrator

    monkeypatch.setattr(bootstrap, "policy", policy)
    monkeypatch.setattr(bootstrap, "settings", settings)
    monkeypatch.setattr(
        bootstrap,
        "GovernanceThresholds",
        threshold_factory("governance_thresholds", sentinel.governance_thresholds),
    )
    monkeypatch.setattr(
        bootstrap,
        "ToolGatingThresholds",
        threshold_factory("tool_gating_thresholds", sentinel.tool_gating_thresholds),
    )
    monkeypatch.setattr(
        bootstrap,
        "OutputScreeningThresholds",
        threshold_factory("output_thresholds", sentinel.output_thresholds),
    )
    monkeypatch.setattr(bootstrap, "get_dispute_context", sentinel.loader)
    monkeypatch.setattr(bootstrap, "JsonlAuditSink", jsonl_sink)
    monkeypatch.setattr(bootstrap, "CompositeAuditSink", composite_sink)
    monkeypatch.setattr(bootstrap, "JevClient", jev_client)
    monkeypatch.setattr(bootstrap, "GovernanceAdapter", adapter)
    monkeypatch.setattr(bootstrap, "GovernanceHooks", hooks)
    monkeypatch.setattr(bootstrap, "SessionManager", session_manager)
    monkeypatch.setattr(bootstrap, "BankingOrchestrator", orchestrator)

    result = bootstrap.build_orchestrator()

    assert result is sentinel.orchestrator
    assert [name for name, _ in calls] == [
        "governance_thresholds",
        "tool_gating_thresholds",
        "output_thresholds",
        "jsonl_sink",
        "jsonl_sink",
        "composite_sink",
        "jev_client",
        "adapter",
        "hooks",
        "session_manager",
        "orchestrator",
    ]
    assert calls[0][1] is policy.governance
    assert calls[1][1] is policy.tool_gating
    assert calls[2][1] is policy.output_screening
    assert calls[3][1] == settings.audit_log_full_path
    assert calls[4][1] == settings.audit_fallback_full_path
    assert calls[5][1] == (sentinel.primary_sink, sentinel.fallback_sink)
    assert calls[6][1] == {
        "api_key": settings.typesafe_api_key,
        "model": settings.typesafe_default_model,
        "timeout_seconds": settings.typesafe_timeout_seconds,
    }
    adapter_kwargs = calls[7][1]
    assert isinstance(adapter_kwargs, dict)
    assert adapter_kwargs == {
        "client": sentinel.jev_client,
        "thresholds": sentinel.governance_thresholds,
        "tool_gating_thresholds": sentinel.tool_gating_thresholds,
        "output_screening_thresholds": sentinel.output_thresholds,
        "audit_sink": sentinel.shared_audit_sink,
        "dispute_context_loader": sentinel.loader,
    }
    assert calls[8][1] is sentinel.adapter
    assert calls[9][1] == {
        "max_messages_per_session": settings.session_max_messages,
        "ttl_seconds": settings.session_ttl_seconds,
    }
    orchestrator_kwargs = calls[10][1]
    assert isinstance(orchestrator_kwargs, dict)
    assert orchestrator_kwargs == {
        "adapter": sentinel.adapter,
        "governance_hooks": sentinel.hooks,
        "audit_sink": sentinel.shared_audit_sink,
        "session_manager": sentinel.session_manager,
    }
    assert adapter_kwargs["audit_sink"] is orchestrator_kwargs["audit_sink"]


def test_get_orchestrator_is_lazy_injectable_and_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = Mock(return_value=sentinel.orchestrator)
    monkeypatch.setattr(chainlit_app, "_orchestrator_factory", factory)
    monkeypatch.setattr(chainlit_app, "_orchestrator", None)

    factory.assert_not_called()
    first = chainlit_app._get_orchestrator()
    second = chainlit_app._get_orchestrator()

    assert first is sentinel.orchestrator
    assert second is first
    factory.assert_called_once_with()


def test_get_orchestrator_does_not_cache_factory_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = Mock(side_effect=[RuntimeError("factory failed"), sentinel.orchestrator])
    monkeypatch.setattr(chainlit_app, "_orchestrator_factory", factory)
    monkeypatch.setattr(chainlit_app, "_orchestrator", None)

    with pytest.raises(RuntimeError, match="factory failed"):
        chainlit_app._get_orchestrator()

    assert chainlit_app._orchestrator is None
    assert chainlit_app._get_orchestrator() is sentinel.orchestrator
    assert factory.call_count == 2
