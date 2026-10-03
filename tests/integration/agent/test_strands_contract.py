import inspect
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from importlib.metadata import version
from types import SimpleNamespace
from typing import get_type_hints

from strands import Agent
from strands.agent import AgentResult
from strands.hooks import (
    AfterInvocationEvent,
    AfterToolCallEvent,
    BeforeToolCallEvent,
    HookRegistry,
)
from strands.models import Model
from strands.types.content import Message

from ai_banking_customer_service.agent import orchestrator as orchestrator_module
from ai_banking_customer_service.agent.hooks import GovernanceHooks
from ai_banking_customer_service.agent.orchestrator import (
    BankingOrchestrator,
    TurnAction,
)
from ai_banking_customer_service.agent.result_capture import ResultCaptureHooks
from ai_banking_customer_service.governance.adapter import GovernanceResult
from ai_banking_customer_service.governance.jev.decision import GovernanceAction
from ai_banking_customer_service.observability.sink import CompositeAuditSink


class FakeModel(Model):
    def __init__(
        self,
        response: str = "Safe response",
        barrier: threading.Barrier | None = None,
    ) -> None:
        self.response = response
        self.barrier = barrier
        self.received_messages: list[list[Message]] = []

    def update_config(self, **model_config) -> None:
        pass

    def get_config(self) -> dict:
        return {}

    async def structured_output(
        self, output_model, prompt, system_prompt=None, **kwargs
    ):
        if False:
            yield {}

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.received_messages.append(messages)
        if self.barrier is not None:
            self.barrier.wait(timeout=5)
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"contentBlockIndex": 0, "start": {}}}
        yield {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"text": self.response},
            }
        }
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                "metrics": {"latencyMs": 1},
            }
        }


class AllowAdapter:
    def screen_and_route(
        self,
        message,
        trace_id,
        session_id,
        customer_id,
        parent_event_id=None,
        *,
        orphaned=False,
    ):
        decision = SimpleNamespace(action=GovernanceAction.ALLOW)
        return SimpleNamespace(
            final_decision=decision,
            intent="dispute_charge",
            should_continue=True,
            last_event_id=f"routing-{session_id}",
        )

    def build_customer_context(self, complaint_id):
        return {"authenticated": True}

    def gate_tool_call(
        self,
        tool_name,
        tool_args,
        intent,
        customer_message,
        customer_context,
        trace_id,
        session_id,
        customer_id,
        parent_event_id=None,
        *,
        orphaned=False,
    ):
        return GovernanceResult(
            SimpleNamespace(action=GovernanceAction.BLOCK), "gating-1"
        )

    def build_actions_taken(self, tool_results):
        return [], False

    def screen_output(
        self,
        proposed_response,
        customer_message,
        verified_facts,
        actions_taken,
        trace_id,
        session_id,
        customer_id,
        parent_event_id=None,
        *,
        orphaned=False,
    ):
        return GovernanceResult(
            SimpleNamespace(action=GovernanceAction.ALLOW), f"output-{session_id}"
        )


class MemorySink:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self._lock = threading.Lock()

    def emit(self, event: dict) -> None:
        with self._lock:
            self.events.append(event)


def test_installed_strands_cancel_signal_signature_is_pinned() -> None:
    assert version("strands-agents") == "1.57.1"

    parameter = inspect.signature(Agent.__call__).parameters["cancel_signal"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is None
    assert get_type_hints(Agent.__call__)["cancel_signal"] == threading.Event | None


def test_real_agent_cancellation_and_message_contract() -> None:
    history = [
        {"role": "user", "content": [{"text": "Previous question"}]},
        {"role": "assistant", "content": [{"text": "Previous answer"}]},
    ]
    model = FakeModel("Current answer")
    result = Agent(model=model, messages=history, callback_handler=None)(
        "Current question"
    )

    assert isinstance(result, AgentResult)
    assert result.stop_reason == "end_turn"
    assert result.message["role"] == "assistant"
    assert result.message["content"] == [{"text": "Current answer"}]
    assert model.received_messages == [
        [
            {"role": "user", "content": [{"text": "Previous question"}]},
            {"role": "assistant", "content": [{"text": "Previous answer"}]},
            {"role": "user", "content": [{"text": "Current question"}]},
        ]
    ]

    cancel_signal = threading.Event()
    cancel_signal.set()
    cancelled = Agent(model=FakeModel(), callback_handler=None)(
        "Cancel this turn", cancel_signal=cancel_signal
    )

    assert cancelled.stop_reason == "cancelled"
    assert cancel_signal.is_set()


def test_provider_order_exposes_governance_block_to_result_capture() -> None:
    adapter = AllowAdapter()
    capture = ResultCaptureHooks()
    agent = Agent(
        model=FakeModel(),
        hooks=[GovernanceHooks(adapter), capture],
        callback_handler=None,
    )
    state = {
        "trace_id": "trace-1",
        "session_id": "session-1",
        "customer_id": "customer-1",
        "intent": "dispute_charge",
        "customer_message": "Block my card",
        "routing_event_id": "routing-1",
        "tool_governance": {},
    }
    event = BeforeToolCallEvent(
        agent=agent,
        selected_tool=None,
        tool_use={
            "toolUseId": "tool-use-1",
            "name": "block_card",
            "input": {"complaint_id": "CMP-1", "confirmed_by_customer": True},
        },
        invocation_state=state,
    )

    agent.hooks.invoke_callbacks(event)

    assert event.cancel_tool == "governance:block"
    assert state["tool_governance"]["tool-use-1"] == {
        "decision": SimpleNamespace(action=GovernanceAction.BLOCK),
        "action": "block",
        "event_id": "gating-1",
        "reason": None,
    }
    assert capture.snapshot_attempts()[0].blocked_before_execution is True


def test_installed_after_tool_event_and_capture_registration_contract() -> None:
    required_fields = {
        "tool_use",
        "result",
        "exception",
        "cancel_message",
        "duration",
        "retry",
    }
    assert required_fields <= {field.name for field in fields(AfterToolCallEvent)}

    capture = ResultCaptureHooks()
    registry = HookRegistry()
    capture.register_hooks(registry)
    after_invocation = AfterInvocationEvent(agent=SimpleNamespace())
    assert list(registry.get_callbacks_for(after_invocation)) == []

    event = AfterToolCallEvent(
        agent=SimpleNamespace(),
        selected_tool=None,
        tool_use={"toolUseId": "tool-1", "name": "read", "input": {}},
        invocation_state={},
        result={"toolUseId": "tool-1", "status": "error", "content": []},
        exception=RuntimeError("failed"),
        cancel_message="cancelled",
        duration=0.012,
        retry=True,
    )
    capture.after_tool_call(event)
    normalized = capture.snapshot_results()[0]

    assert isinstance(event.retry, bool)
    assert (
        normalized.exception,
        normalized.cancel_message,
        normalized.duration_ms,
        normalized.retry_requested,
    ) == ("RuntimeError: failed", "cancelled", 12, True)


def test_concurrent_sessions_use_distinct_agents_models_and_captures(
    monkeypatch,
) -> None:
    barrier = threading.Barrier(2)
    models: list[FakeModel] = []
    agents: list[Agent] = []
    captures: list[ResultCaptureHooks] = []
    real_agent = Agent
    real_capture = ResultCaptureHooks

    def model_factory() -> FakeModel:
        model = FakeModel(barrier=barrier)
        models.append(model)
        return model

    def agent_factory(**kwargs) -> Agent:
        agent = real_agent(callback_handler=None, retry_strategy=None, **kwargs)
        agents.append(agent)
        return agent

    class TrackingCapture(real_capture):
        def __init__(self) -> None:
            super().__init__()
            captures.append(self)

    monkeypatch.setattr(orchestrator_module, "Agent", agent_factory)
    monkeypatch.setattr(orchestrator_module, "ResultCaptureHooks", TrackingCapture)
    adapter = AllowAdapter()
    primary = MemorySink()
    orchestrator = BankingOrchestrator(
        adapter=adapter,
        governance_hooks=GovernanceHooks(adapter),
        audit_sink=CompositeAuditSink(primary, MemorySink()),
        model_factory=model_factory,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(orchestrator.handle_turn, "First", "session-1", "c-1"),
            executor.submit(orchestrator.handle_turn, "Second", "session-2", "c-2"),
        ]
        results = [future.result(timeout=10) for future in futures]

    assert [result.action for result in results] == [TurnAction.RESPOND] * 2
    assert len({id(agent) for agent in agents}) == 2
    assert len({id(model) for model in models}) == 2
    assert len({id(capture) for capture in captures}) == 2
    assert sorted(
        model.received_messages[0][0]["content"][0]["text"] for model in models
    ) == ["First", "Second"]
