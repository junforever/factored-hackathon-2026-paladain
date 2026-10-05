import inspect
import json
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from ai_banking_customer_service.agent import orchestrator as orchestrator_module
from ai_banking_customer_service.agent.tools import REGISTERED_TOOLS
from ai_banking_customer_service.config import settings
from ai_banking_customer_service.evaluation import (
    EvaluationDependencies as PublicEvaluationDependencies,
)
from ai_banking_customer_service.evaluation import (
    build_evaluation_dependencies as public_build_evaluation_dependencies,
)
from ai_banking_customer_service.evaluation import factory as factory_module
from ai_banking_customer_service.evaluation.cases import EvalCase
from ai_banking_customer_service.evaluation.factory import (
    EvaluationDependencies,
    build_evaluation_dependencies,
)
from ai_banking_customer_service.evaluation.sink import RecordingAuditSink
from ai_banking_customer_service.governance.adapter import ProductAuthorization
from ai_banking_customer_service.services import card_service, escalation_service
from ai_banking_customer_service.tools import block_card as block_card_module
from ai_banking_customer_service.tools import escalate_case as escalate_case_module

_INTERNAL_PATH_NAMES = {
    "state_dir",
    "state_path",
    "db_path",
    "card_db_path",
    "escalation_db_path",
}


def _context() -> dict:
    return {
        "complaint_id": "CMP-EVAL",
        "customer_id": "CUS-EVAL",
        "country": "CO",
        "segment": "Premium",
        "product_id": "PROD-EVAL",
        "product_type": "Tarjeta Crédito",
        "product_status": "Active",
        "transaction_id": "TX-EVAL",
        "transaction_date": "2026-09-30",
        "complaint_date": "2026-10-01",
        "amount": 25.0,
        "currency": "USD",
        "amount_usd_estimated": 25.0,
        "merchant_name": "Evaluation Store",
        "system_flagged_fraud": False,
        "fraud_score": 0.1,
    }


def _case() -> EvalCase:
    return EvalCase.model_validate(
        {
            "case_id": "EVAL-FACTORY-001",
            "language": "es",
            "scenario": "normal_resolution",
            "customer_message": "Complaint CMP-EVAL; block card.",
            "expected": {
                "intent": "dispute_charge",
                "action": "respond",
                "is_automatable": True,
                "requires_escalation": False,
                "expected_tools": ["block_card"],
                "expected_escalation_type": None,
                "complaint_id": "CMP-EVAL",
                "customer_confirmed_block": True,
                "forbidden_actions": [],
                "response_required_substrings": [],
                "response_forbidden_substrings": [],
                "sensitive_output_forbidden_substrings": [],
            },
            "metadata": {"segment": "Retail", "notes": "Factory contract case"},
        }
    )


@pytest.fixture(autouse=True)
def _resolve_factory_complaint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(factory_module, "get_dispute_context", lambda _: _context())


def test_factory_grants_only_the_case_principal_and_exact_resolved_product(
    tmp_path: Path,
) -> None:
    principal = object()

    dependencies = build_evaluation_dependencies(
        state_dir=tmp_path,
        case=_case(),
        principal=principal,
        model_factory=lambda: object(),
    )
    provider = dependencies.orchestrator._adapter._product_authorization_provider

    assert provider.authorize_product(
        principal=principal, product_id="PROD-EVAL"
    ) == ProductAuthorization(True, True, "authorized")
    assert provider.authorize_product(
        principal=object(), product_id="PROD-EVAL"
    ) == ProductAuthorization(False, False, "not_authenticated")
    assert provider.authorize_product(
        principal=principal, product_id="PROD-OTHER"
    ) == ProductAuthorization(True, False, "product_not_authorized")
    assert "PROD-EVAL" not in repr(provider)
    assert repr(principal) not in repr(provider)


def test_factory_bounds_complaint_resolution_exceptions_without_identity_leakage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = object()
    monkeypatch.setattr(
        factory_module,
        "get_dispute_context",
        lambda _: (_ for _ in ()).throw(RuntimeError(f"backend {principal!r}")),
    )

    with pytest.raises(
        ValueError,
        match="^evaluation authorization context unavailable$",
    ) as captured:
        build_evaluation_dependencies(
            state_dir=tmp_path,
            case=_case(),
            principal=principal,
            model_factory=lambda: object(),
        )

    assert repr(principal) not in str(captured.value)


@pytest.mark.parametrize(
    "context",
    [
        None,
        {"error": "unavailable"},
        {"complaint_id": "CMP-OTHER", "product_id": "PROD-EVAL"},
        {"complaint_id": "CMP-EVAL", "product_id": None},
        {"complaint_id": "CMP-EVAL", "product_id": "   "},
    ],
)
def test_factory_fails_closed_when_exact_case_product_cannot_be_resolved(
    context: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(factory_module, "get_dispute_context", lambda _: context)

    with pytest.raises(
        ValueError,
        match="^evaluation authorization context unavailable$",
    ):
        build_evaluation_dependencies(
            state_dir=tmp_path,
            case=_case(),
            principal=object(),
            model_factory=lambda: object(),
        )


def test_card_service_explicit_file_is_isolated_from_default_and_other_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_path = tmp_path / "default" / "card_service.sqlite3"
    explicit_path = tmp_path / "case" / "card_service.sqlite3"
    escalation_path = tmp_path / "case" / "escalation_service.sqlite3"
    monkeypatch.setattr(card_service, "STATE_PATH", default_path)

    result = card_service.block_card(
        "PROD-EVAL",
        "CMP-EVAL",
        "fraud_dispute",
        db_path=explicit_path,
    )

    assert result["verification"] == "confirmed_blocked"
    assert card_service.is_card_blocked("PROD-EVAL", db_path=explicit_path) is True
    assert card_service.is_card_blocked("PROD-EVAL") is False
    assert explicit_path.is_file()
    assert default_path.is_file()
    assert not escalation_path.exists()


def test_escalation_service_explicit_file_is_isolated_from_default_and_card_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_path = tmp_path / "default" / "escalation_service.sqlite3"
    explicit_path = tmp_path / "case" / "escalation_service.sqlite3"
    card_path = tmp_path / "case" / "card_service.sqlite3"
    monkeypatch.setattr(escalation_service, "STATE_PATH", default_path)

    result = escalation_service.create_escalation(
        "CMP-EVAL",
        "CUS-EVAL",
        "PROD-EVAL",
        "needs_review",
        "Medium",
        {"request": {"complaint_id": "CMP-EVAL"}},
        db_path=explicit_path,
    )

    assert result["verification"] == "confirmed_persisted"
    assert (
        escalation_service.get_escalation(
            result["escalation_id"], db_path=explicit_path
        )
        is not None
    )
    assert escalation_service.get_escalation(result["escalation_id"]) is None
    assert explicit_path.is_file()
    assert default_path.is_file()
    assert not card_path.exists()


def test_public_business_tools_keep_default_service_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card_path = tmp_path / "production-default" / "card_service.sqlite3"
    escalation_path = tmp_path / "production-default" / "escalation_service.sqlite3"
    monkeypatch.setattr(card_service, "STATE_PATH", card_path)
    monkeypatch.setattr(escalation_service, "STATE_PATH", escalation_path)
    monkeypatch.setattr(block_card_module, "get_dispute_context", lambda _: _context())
    monkeypatch.setattr(
        escalate_case_module, "get_dispute_context", lambda _: _context()
    )
    monkeypatch.setattr(
        escalate_case_module,
        "get_recent_transactions",
        lambda *_args, **_kwargs: {"transactions": []},
    )

    blocked = block_card_module.block_card("CMP-EVAL", True)
    escalated = escalate_case_module.escalate_case("CMP-EVAL", "needs_review")

    assert blocked["verification"] == "confirmed_blocked"
    assert escalated["verification"] == "confirmed_persisted"
    assert card_path.is_file()
    assert escalation_path.is_file()


def test_public_factory_api_and_dependency_identity_guarantees(tmp_path: Path) -> None:
    signature = inspect.signature(build_evaluation_dependencies)
    parameters = signature.parameters

    def model_factory():
        return object()

    principal = object()
    dependencies = build_evaluation_dependencies(
        state_dir=tmp_path,
        case=_case(),
        principal=principal,
        model_factory=model_factory,
    )
    audit_sink = dependencies.orchestrator._audit_sink

    assert PublicEvaluationDependencies is EvaluationDependencies
    assert public_build_evaluation_dependencies is build_evaluation_dependencies
    assert [field.name for field in fields(EvaluationDependencies)] == [
        "orchestrator",
        "recording_sink",
    ]
    assert list(parameters) == ["state_dir", "case", "principal", "model_factory"]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in parameters.values()
    )
    assert parameters["case"].default is inspect.Parameter.empty
    assert parameters["principal"].default is inspect.Parameter.empty
    assert parameters["model_factory"].default is None
    assert isinstance(dependencies, EvaluationDependencies)
    assert isinstance(dependencies.recording_sink, RecordingAuditSink)
    assert audit_sink is dependencies.orchestrator._adapter._audit_sink
    assert dependencies.orchestrator._governance_hooks._adapter is (
        dependencies.orchestrator._adapter
    )
    assert dependencies.orchestrator._governance_hooks._principal is principal
    assert audit_sink._primary_sink is dependencies.recording_sink
    assert isinstance(audit_sink._fallback_sink, RecordingAuditSink)
    assert audit_sink._fallback_sink is not dependencies.recording_sink
    assert dependencies.orchestrator._model_factory is model_factory
    assert [tool.tool_name for tool in dependencies.orchestrator._tools] == [
        tool.tool_name for tool in REGISTERED_TOOLS
    ]
    with pytest.raises(FrozenInstanceError):
        dependencies.recording_sink = RecordingAuditSink()


def test_factory_preserves_configured_default_model(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[dict] = []

    class FakeOpenAIModel:
        def __init__(self, **kwargs) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(orchestrator_module, "OpenAIModel", FakeOpenAIModel)

    dependencies = build_evaluation_dependencies(
        state_dir=tmp_path,
        case=_case(),
        principal=object(),
    )
    dependencies.orchestrator._model_factory()

    assert calls == [
        {
            "model_id": settings.openai_model,
            "client_args": {"api_key": settings.openai_api_key.get_secret_value()},
        }
    ]


def test_evaluation_factory_binds_exact_files_and_actions_share_case_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(block_card_module, "get_dispute_context", lambda _: _context())
    monkeypatch.setattr(
        escalate_case_module, "get_dispute_context", lambda _: _context()
    )
    monkeypatch.setattr(
        escalate_case_module,
        "get_recent_transactions",
        lambda *_args, **_kwargs: {"transactions": []},
    )
    dependencies = build_evaluation_dependencies(
        state_dir=tmp_path,
        case=_case(),
        principal=object(),
        model_factory=lambda: object(),
    )
    tools = {
        registered.tool_name: registered
        for registered in dependencies.orchestrator._tools
    }

    blocked = tools["block_card"]("CMP-EVAL", True)
    escalated = tools["escalate_case"]("CMP-EVAL", "needs_review")

    card_path = tmp_path / "card_service.sqlite3"
    escalation_path = tmp_path / "escalation_service.sqlite3"
    assert blocked["verification"] == "confirmed_blocked"
    assert escalated["verification"] == "confirmed_persisted"
    assert escalated["handoff"]["actions_taken"][0]["executed"] is True
    assert card_service.is_card_blocked("PROD-EVAL", db_path=card_path) is True
    assert (
        escalation_service.get_escalation(
            escalated["escalation_id"], db_path=escalation_path
        )
        is not None
    )
    assert card_path.is_file()
    assert escalation_path.is_file()


def test_bound_tools_preserve_exact_order_signatures_and_schemas_without_paths(
    tmp_path: Path,
) -> None:
    dependencies = build_evaluation_dependencies(
        state_dir=tmp_path,
        case=_case(),
        principal=object(),
        model_factory=lambda: object(),
    )
    bound_tools = dependencies.orchestrator._tools

    assert [tool.tool_name for tool in bound_tools] == [
        tool.tool_name for tool in REGISTERED_TOOLS
    ]
    for bound, default in zip(bound_tools, REGISTERED_TOOLS, strict=True):
        assert inspect.signature(bound) == inspect.signature(default)
        assert bound.tool_spec == default.tool_spec
        exposed = set(inspect.signature(bound).parameters) | set(
            bound.tool_spec["inputSchema"]["json"]["properties"]
        )
        assert exposed.isdisjoint(_INTERNAL_PATH_NAMES)
        serialized_schema = json.dumps(bound.tool_spec, sort_keys=True).casefold()
        assert not any(name in serialized_schema for name in _INTERNAL_PATH_NAMES)
