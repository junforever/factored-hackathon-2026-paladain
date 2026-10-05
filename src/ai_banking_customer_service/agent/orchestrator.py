"""Stateful, fail-closed Strands turn orchestration."""

import json
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from time import monotonic
from typing import Any
from uuid import uuid4

from strands import Agent
from strands.models.openai import OpenAIModel

from ai_banking_customer_service.agent.hooks import GovernanceHooks
from ai_banking_customer_service.agent.language_detector import detect_language
from ai_banking_customer_service.agent.result_capture import (
    NormalizedToolResult,
    ResultCaptureHooks,
)
from ai_banking_customer_service.agent.session_manager import (
    SessionManager,
    TurnPersistence,
)
from ai_banking_customer_service.agent.signal_parser import parse_orchestration_signal
from ai_banking_customer_service.agent.system_prompt import SYSTEM_PROMPT
from ai_banking_customer_service.agent.tools import REGISTERED_TOOLS
from ai_banking_customer_service.config import settings
from ai_banking_customer_service.governance.adapter import (
    GovernanceAdapter,
    GovernanceResult,
)
from ai_banking_customer_service.governance.jev.decision import GovernanceAction
from ai_banking_customer_service.governance.jev.evaluations import ACTION_VERIFICATIONS
from ai_banking_customer_service.governance.jev.sanitization import (
    sanitize_json_structure,
    sanitize_message,
)
from ai_banking_customer_service.observability.sink import (
    AuditPersistenceError,
    CompositeAuditSink,
)

ACTION_TOOLS = frozenset({"block_card", "escalate_case"})
_REGISTERED_TOOL_NAMES = frozenset(tool.tool_name for tool in REGISTERED_TOOLS)
_READ_TOOLS = _REGISTERED_TOOL_NAMES - ACTION_TOOLS
_NORMAL_STOP_REASONS = frozenset({"end_turn", "stop_sequence"})
_MAX_TOOL_ARGUMENT_DEPTH = 32


class TurnAction(str, Enum):  # noqa: UP042 - exact public contract
    RESPOND = "respond"
    ESCALATE = "escalate"
    BLOCK = "block"
    ABSTAIN = "abstain"


class EscalationType(str, Enum):  # noqa: UP042 - exact public contract
    GOVERNANCE_REVIEW = "governance_review"
    FAILED_ACTION = "failed_action"
    OUTPUT_SCREENING_REVIEW = "output_screening_review"
    TOOL_ESCALATION = "tool_escalation"
    UNCERTAIN_SIDE_EFFECT = "uncertain_side_effect"
    EXTERNAL_CANCELLATION = "external_cancellation"
    INCOMPLETE_INVOCATION = "incomplete_invocation"


class OutputScreeningState(str, Enum):  # noqa: UP042 - exact public contract
    ALLOW = "allow"
    REVIEW = "review"
    FAILURE = "failure"


@dataclass(frozen=True)
class OutputScreeningOutcome:
    state: OutputScreeningState
    governance_result: GovernanceResult | None
    escalation_type: EscalationType | None
    safe_response: str
    event_id: str | None


@dataclass(frozen=True)
class TurnClassification:
    action: TurnAction
    response_text: str
    escalation_type: EscalationType | None
    escalation_id: str | None
    terminal_parent_event_id: str | None


@dataclass(frozen=True)
class OrchestratorResult:
    action: TurnAction
    response_text: str
    trace_id: str
    session_id: str
    intent: str | None
    escalation_type: EscalationType | None
    escalation_id: str | None


@dataclass(frozen=True)
class _ToolRecord:
    tool_use_id: str
    tool_name: str
    tool_args: dict
    attempts: tuple[object, ...]
    results: tuple[NormalizedToolResult, ...]

    @property
    def duplicate_or_retry(self) -> bool:
        return (
            len(self.attempts) > 1
            or len(self.results) > 1
            or any(result.retry_requested for result in self.results)
        )

    @property
    def blocked_before_execution(self) -> bool:
        return any(
            bool(getattr(attempt, "blocked_before_execution", False))
            for attempt in self.attempts
        ) or any(result.blocked_before_execution for result in self.results)

    @property
    def result(self) -> NormalizedToolResult | None:
        return self.results[0] if len(self.results) == 1 else None


@dataclass
class _ToolAnalysis:
    action_payloads: list[dict]
    dispute_context: dict | None
    grounding_sources: list[str]
    uncertain_side_effect: bool = False
    failed_action: bool = False
    incomplete_invocation: bool = False
    successful_escalation: NormalizedToolResult | None = None


SAFE_TEMPLATES = {
    "es": {
        "block": "No puedo procesar esta solicitud de forma segura.",
        "abstain": (
            "No puedo resolver esta solicitud de forma segura con la "
            "información disponible."
        ),
        "review_failure": (
            "No puedo completar esta solicitud de forma segura. "
            "La derivaré a un especialista."
        ),
        "tool_escalation": "El caso fue escalado correctamente a un especialista.",
        "uncertain_side_effect": (
            "No puedo confirmar el resultado de la operación. Un especialista "
            "revisará el caso antes de realizar otra acción."
        ),
        "external_cancellation": (
            "La operación se interrumpió antes de completarse. "
            "Un especialista revisará el caso."
        ),
        "incomplete_invocation": (
            "No pude completar la respuesta de forma segura. "
            "Un especialista revisará el caso."
        ),
    },
    "pt": {
        "block": "Não posso processar esta solicitação com segurança.",
        "abstain": (
            "Não posso resolver esta solicitação com segurança com as "
            "informações disponíveis."
        ),
        "review_failure": (
            "Não posso concluir esta solicitação com segurança. "
            "Vou encaminhá-la a um especialista."
        ),
        "tool_escalation": "O caso foi encaminhado com sucesso a um especialista.",
        "uncertain_side_effect": (
            "Não posso confirmar o resultado da operação. Um especialista "
            "revisará o caso antes de realizar outra ação."
        ),
        "external_cancellation": (
            "A operação foi interrompida antes de ser concluída. "
            "Um especialista revisará o caso."
        ),
        "incomplete_invocation": (
            "Não consegui concluir a resposta com segurança. "
            "Um especialista revisará o caso."
        ),
    },
}


class BankingOrchestrator:
    def __init__(
        self,
        adapter: GovernanceAdapter,
        governance_hooks: GovernanceHooks,
        audit_sink: CompositeAuditSink,
        session_manager: SessionManager | None = None,
        model_factory: Callable[[], Any] | None = None,
        model_id: str | None = None,
        model: Any | None = None,
        tools: Sequence[Any] | None = None,
    ) -> None:
        if model_factory is not None and model is not None:
            raise ValueError("model_factory and model are mutually exclusive")
        self._adapter = adapter
        self._governance_hooks = governance_hooks
        self._audit_sink = audit_sink
        self._tools = _validated_tools(tools)
        self._session_manager = (
            SessionManager() if session_manager is None else session_manager
        )
        if model_factory is not None:
            self._model_factory = model_factory
        elif model is not None:
            self._model_factory = lambda: model
        else:
            resolved_model_id = model_id or settings.openai_model
            api_key = settings.openai_api_key.get_secret_value()
            self._model_factory = lambda: OpenAIModel(
                model_id=resolved_model_id,
                client_args={"api_key": api_key},
            )

    def handle_turn(
        self,
        message: str,
        session_id: str,
        customer_id: str,
        cancel_signal: threading.Event | None = None,
    ) -> OrchestratorResult:
        _validate_turn_inputs(message, session_id, customer_id)
        turn_started = monotonic()
        with self._session_manager.turn(session_id) as session_turn:
            agent = model_instance = result_capture = None
            attempts_snapshot = results_snapshot = ()
            invocation_state: dict = {}
            try:
                history_snapshot = session_turn.history
                language = detect_language(message)
                trace_id = str(uuid4())
                sanitized_input = sanitize_message(message)
                input_payload = {
                    "text": sanitized_input[:2000],
                    "language": language,
                    "channel": "api",
                }
                if len(sanitized_input) > 2000:
                    input_payload["text_truncated"] = True
                input_event_id = self._emit_event(
                    self._event(
                        trace_id,
                        session_id,
                        customer_id,
                        None,
                        "input",
                        "success",
                        _elapsed_ms(turn_started),
                        input_payload,
                    )
                )
                invocation_state = {
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "customer_id": customer_id,
                    "input_event_id": input_event_id,
                }
                if input_event_id is None:
                    invocation_state["audit_orphaned"] = True

                model_instance = self._model_factory()
                result_capture = ResultCaptureHooks()
                agent = Agent(
                    model=model_instance,
                    tools=list(self._tools),
                    hooks=[self._governance_hooks, result_capture],
                    system_prompt=SYSTEM_PROMPT,
                    messages=history_snapshot,
                )
                agent_result = None
                agent_exception = None
                try:
                    agent_result = agent(
                        message,
                        invocation_state=invocation_state,
                        cancel_signal=cancel_signal,
                    )
                except Exception as error:
                    agent_exception = _safe_exception(error)
                attempts_snapshot = result_capture.snapshot_attempts()
                results_snapshot = result_capture.snapshot_results()

                records = _tool_records(attempts_snapshot, results_snapshot)
                analysis = _analyze_tools(records)
                durable_parent = _last_durable_parent(
                    invocation_state.get("routing_event_id"), input_event_id
                )
                for record in records:
                    parent_event_id, used_fallback = _tool_parent(
                        record.tool_use_id,
                        invocation_state,
                    )
                    payload = _tool_event_payload(record, used_fallback)
                    _add_orphaned(payload, invocation_state)
                    event_id = self._emit_event(
                        self._event(
                            trace_id,
                            session_id,
                            customer_id,
                            parent_event_id,
                            "tool_call",
                            _tool_outcome(record),
                            _tool_latency(record),
                            payload,
                        )
                    )
                    if event_id is None:
                        invocation_state["audit_orphaned"] = True
                        if _sensitive_effect_may_have_happened(record):
                            analysis.uncertain_side_effect = True
                    else:
                        durable_parent = event_id

                classification = self._classify_result(
                    language=language,
                    message=message,
                    agent_result=agent_result,
                    agent_exception=agent_exception,
                    invocation_state=invocation_state,
                    analysis=analysis,
                    durable_parent=durable_parent,
                    trace_id=trace_id,
                    session_id=session_id,
                    customer_id=customer_id,
                )
                terminal_parent = classification.terminal_parent_event_id
                if classification.action is TurnAction.ESCALATE:
                    escalation_started = monotonic()
                    escalation_payload = _escalation_payload(
                        classification,
                        analysis.successful_escalation,
                    )
                    _add_orphaned(escalation_payload, invocation_state)
                    escalation_event_id = self._emit_event(
                        self._event(
                            trace_id,
                            session_id,
                            customer_id,
                            terminal_parent,
                            "escalation",
                            "escalated",
                            _elapsed_ms(escalation_started),
                            escalation_payload,
                        )
                    )
                    if escalation_event_id is None:
                        invocation_state["audit_orphaned"] = True
                    else:
                        terminal_parent = escalation_event_id

                response_started = monotonic()
                response_payload = _response_payload(
                    classification,
                    language,
                    analysis,
                )
                _add_orphaned(response_payload, invocation_state)
                response_event_id = self._emit_event(
                    self._event(
                        trace_id,
                        session_id,
                        customer_id,
                        terminal_parent,
                        "response",
                        {
                            TurnAction.RESPOND: "success",
                            TurnAction.BLOCK: "blocked",
                            TurnAction.ESCALATE: "escalated",
                            TurnAction.ABSTAIN: "abstained",
                        }[classification.action],
                        _elapsed_ms(response_started),
                        response_payload,
                    )
                )
                if response_event_id is None:
                    invocation_state["audit_orphaned"] = True

                session_turn.persist(
                    TurnPersistence(
                        action=classification.action.value,
                        user_text=message,
                        assistant_text=(
                            classification.response_text
                            if classification.action
                            in {TurnAction.RESPOND, TurnAction.ABSTAIN}
                            else None
                        ),
                    )
                )
                return OrchestratorResult(
                    action=classification.action,
                    response_text=classification.response_text,
                    trace_id=trace_id,
                    session_id=session_id,
                    intent=_nonempty_string(invocation_state.get("intent")),
                    escalation_type=classification.escalation_type,
                    escalation_id=classification.escalation_id,
                )
            finally:
                agent = model_instance = result_capture = None
                attempts_snapshot = results_snapshot = ()
                invocation_state.clear()
                message = ""

    def _classify_result(
        self,
        *,
        language: str,
        message: str,
        agent_result: object,
        agent_exception: str | None,
        invocation_state: dict,
        analysis: _ToolAnalysis,
        durable_parent: str | None,
        trace_id: str,
        session_id: str,
        customer_id: str,
    ) -> TurnClassification:
        governance_action = invocation_state.get("governance_action")
        governance_parent = _last_durable_parent(
            invocation_state.get("routing_event_id"), durable_parent
        )
        if governance_action in {"block", "review"}:
            return _fixed_classification(
                TurnAction.ESCALATE,
                language,
                "review_failure",
                EscalationType.GOVERNANCE_REVIEW,
                governance_parent,
            )
        if analysis.uncertain_side_effect:
            return _fixed_classification(
                TurnAction.ESCALATE,
                language,
                "uncertain_side_effect",
                EscalationType.UNCERTAIN_SIDE_EFFECT,
                durable_parent,
            )
        if analysis.failed_action:
            return _fixed_classification(
                TurnAction.ESCALATE,
                language,
                "review_failure",
                EscalationType.FAILED_ACTION,
                durable_parent,
            )
        if analysis.successful_escalation is not None:
            escalation_id = analysis.successful_escalation.content["escalation_id"]
            return TurnClassification(
                TurnAction.ESCALATE,
                SAFE_TEMPLATES[language]["tool_escalation"],
                EscalationType.TOOL_ESCALATION,
                escalation_id,
                durable_parent,
            )
        if agent_result is None or agent_exception is not None:
            return _fixed_classification(
                TurnAction.ESCALATE,
                language,
                "external_cancellation",
                EscalationType.EXTERNAL_CANCELLATION,
                durable_parent,
            )
        stop_reason = getattr(agent_result, "stop_reason", None)
        if stop_reason == "cancelled":
            return _fixed_classification(
                TurnAction.ESCALATE,
                language,
                "external_cancellation",
                EscalationType.EXTERNAL_CANCELLATION,
                durable_parent,
            )
        if analysis.incomplete_invocation or stop_reason not in _NORMAL_STOP_REASONS:
            return _fixed_classification(
                TurnAction.ESCALATE,
                language,
                "incomplete_invocation",
                EscalationType.INCOMPLETE_INVOCATION,
                durable_parent,
            )
        proposed_response = _message_text(getattr(agent_result, "message", None))
        if not proposed_response:
            return _fixed_classification(
                TurnAction.ESCALATE,
                language,
                "incomplete_invocation",
                EscalationType.INCOMPLETE_INVOCATION,
                durable_parent,
            )
        if governance_action != "allow":
            return _fixed_classification(
                TurnAction.ESCALATE,
                language,
                "incomplete_invocation",
                EscalationType.INCOMPLETE_INVOCATION,
                durable_parent,
            )

        signal = parse_orchestration_signal(proposed_response)
        if signal is not None and signal["orchestration_signal"] == "abstention":
            return _fixed_classification(
                TurnAction.ABSTAIN, language, "abstain", None, durable_parent
            )
        if signal is not None:
            proposed_response = signal["question"]
        outcome = self._run_output_screening(
            proposed_response=proposed_response,
            action_payloads=analysis.action_payloads,
            dispute_context=analysis.dispute_context,
            customer_message=message,
            trace_id=trace_id,
            session_id=session_id,
            customer_id=customer_id,
            parent_event_id=durable_parent,
            invocation_state=invocation_state,
            language=language,
        )
        terminal_parent = outcome.event_id or durable_parent
        if outcome.state is OutputScreeningState.ALLOW:
            return TurnClassification(
                TurnAction.RESPOND,
                outcome.safe_response,
                None,
                None,
                terminal_parent,
            )
        return TurnClassification(
            TurnAction.ESCALATE,
            outcome.safe_response,
            outcome.escalation_type,
            None,
            terminal_parent,
        )

    def _run_output_screening(
        self,
        *,
        proposed_response: str,
        action_payloads: list[dict],
        dispute_context: dict | None,
        customer_message: str,
        trace_id: str,
        session_id: str,
        customer_id: str,
        parent_event_id: str | None,
        invocation_state: dict,
        language: str,
    ) -> OutputScreeningOutcome:
        generic_response = SAFE_TEMPLATES[language]["review_failure"]
        try:
            verified_facts = (
                self._adapter.build_verified_facts(dispute_context)
                if dispute_context is not None
                else {}
            )
        except Exception:
            return OutputScreeningOutcome(
                OutputScreeningState.FAILURE,
                None,
                EscalationType.FAILED_ACTION,
                generic_response,
                None,
            )
        try:
            actions_taken, has_failed_actions = self._adapter.build_actions_taken(
                action_payloads
            )
        except Exception:
            return OutputScreeningOutcome(
                OutputScreeningState.FAILURE,
                None,
                EscalationType.FAILED_ACTION,
                generic_response,
                None,
            )
        if has_failed_actions:
            return OutputScreeningOutcome(
                OutputScreeningState.FAILURE,
                None,
                EscalationType.FAILED_ACTION,
                generic_response,
                None,
            )
        try:
            governance_result = self._adapter.screen_output(
                proposed_response,
                customer_message,
                verified_facts,
                actions_taken,
                trace_id,
                session_id,
                customer_id,
                parent_event_id=parent_event_id,
                orphaned=bool(invocation_state.get("audit_orphaned", False)),
            )
        except AuditPersistenceError:
            invocation_state["audit_orphaned"] = True
            return OutputScreeningOutcome(
                OutputScreeningState.FAILURE,
                None,
                EscalationType.OUTPUT_SCREENING_REVIEW,
                generic_response,
                None,
            )
        except Exception:
            return OutputScreeningOutcome(
                OutputScreeningState.FAILURE,
                None,
                EscalationType.OUTPUT_SCREENING_REVIEW,
                generic_response,
                None,
            )
        if governance_result.decision.action is GovernanceAction.ALLOW:
            return OutputScreeningOutcome(
                OutputScreeningState.ALLOW,
                governance_result,
                None,
                proposed_response,
                governance_result.event_id,
            )
        return OutputScreeningOutcome(
            OutputScreeningState.REVIEW,
            governance_result,
            EscalationType.OUTPUT_SCREENING_REVIEW,
            generic_response,
            governance_result.event_id,
        )

    def _event(
        self,
        trace_id: str,
        session_id: str,
        customer_id: str,
        parent_event_id: str | None,
        event_type: str,
        outcome: str,
        latency_ms: int,
        payload: dict,
    ) -> dict:
        return {
            "trace_id": trace_id,
            "event_id": str(uuid4()),
            "parent_event_id": parent_event_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "component": "orchestrator",
            "event_type": event_type,
            "customer_id": _mask_customer_id(customer_id),
            "session_id": session_id,
            "outcome": outcome,
            "latency_ms": max(0, int(latency_ms)),
            "tokens": None,
            "cost_usd": None,
            "payload": sanitize_json_structure(payload),
        }

    def _emit_event(self, event: dict) -> str | None:
        try:
            self._audit_sink.emit(event)
        except AuditPersistenceError:
            return None
        return event["event_id"]


def _validated_tools(tools: Sequence[Any] | None) -> tuple[Any, ...]:
    try:
        candidates = tuple(REGISTERED_TOOLS if tools is None else tools)
    except TypeError as error:
        raise ValueError("tools must match the canonical tool contract") from error
    expected = tuple(REGISTERED_TOOLS)
    if len(candidates) != len(expected):
        raise ValueError("tools must match the canonical tool contract")
    for candidate, registered in zip(candidates, expected, strict=True):
        if (
            not isinstance(getattr(candidate, "tool_name", None), str)
            or not isinstance(getattr(candidate, "tool_spec", None), dict)
            or candidate.tool_name != registered.tool_name
            or candidate.tool_spec != registered.tool_spec
        ):
            raise ValueError("tools must match the canonical tool contract")
    return candidates


def _validate_turn_inputs(
    message: object,
    session_id: object,
    customer_id: object,
) -> None:
    for name, value in (
        ("message", message),
        ("session_id", session_id),
        ("customer_id", customer_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")


def _tool_records(attempts: tuple, results: tuple) -> list[_ToolRecord]:
    valid_order: list[str] = []
    attempts_by_id: dict[str, list] = {}
    results_by_id: dict[str, list[NormalizedToolResult]] = {}
    invalid_attempts = []
    invalid_results = []
    for attempt in attempts:
        tool_use_id = getattr(attempt, "tool_use_id", "")
        if _nonempty_string(tool_use_id):
            if tool_use_id not in attempts_by_id and tool_use_id not in results_by_id:
                valid_order.append(tool_use_id)
            attempts_by_id.setdefault(tool_use_id, []).append(attempt)
        else:
            invalid_attempts.append(attempt)
    for result in results:
        if _nonempty_string(result.tool_use_id):
            if (
                result.tool_use_id not in attempts_by_id
                and result.tool_use_id not in results_by_id
            ):
                valid_order.append(result.tool_use_id)
            results_by_id.setdefault(result.tool_use_id, []).append(result)
        else:
            invalid_results.append(result)

    records = []
    for tool_use_id in valid_order:
        grouped_attempts = tuple(attempts_by_id.get(tool_use_id, ()))
        grouped_results = tuple(results_by_id.get(tool_use_id, ()))
        identity = grouped_attempts[0] if grouped_attempts else grouped_results[0]
        records.append(
            _ToolRecord(
                tool_use_id,
                _valid_tool_name(getattr(identity, "tool_name", None)),
                _valid_args(getattr(identity, "tool_args", None)),
                grouped_attempts,
                grouped_results,
            )
        )
    for index, attempt in enumerate(invalid_attempts):
        matching = (invalid_results[index],) if index < len(invalid_results) else ()
        records.append(
            _ToolRecord(
                "",
                _valid_tool_name(getattr(attempt, "tool_name", None)),
                _valid_args(getattr(attempt, "tool_args", None)),
                (attempt,),
                matching,
            )
        )
    for result in invalid_results[len(invalid_attempts) :]:
        records.append(
            _ToolRecord(
                "",
                _valid_tool_name(result.tool_name),
                _valid_args(result.tool_args),
                (),
                (result,),
            )
        )
    return records


def _analyze_tools(records: list[_ToolRecord]) -> _ToolAnalysis:
    analysis = _ToolAnalysis([], None, [])
    for record in records:
        result = record.result
        if _record_is_sensitive(record):
            if (
                record.duplicate_or_retry
                or not record.tool_use_id
                or not record.attempts
                or not _identity_matches(record)
            ):
                analysis.uncertain_side_effect = True
                continue
            if record.blocked_before_execution:
                analysis.failed_action = True
                continue
            if result is None:
                analysis.uncertain_side_effect = True
                continue
            if result.exception is not None or result.cancel_message is not None:
                analysis.uncertain_side_effect = True
                continue
            if result.status != "success" or not isinstance(result.content, dict):
                analysis.uncertain_side_effect = True
                continue
            content = result.content
            if content.get("action") != record.tool_name:
                analysis.uncertain_side_effect = True
                continue
            if (
                content.get("executed") is False
                and isinstance(content.get("reason"), str)
                and "verification" not in content
            ):
                analysis.failed_action = True
                continue
            if record.tool_name == "escalate_case":
                if not _is_successful_escalation(result):
                    analysis.uncertain_side_effect = True
                    continue
                analysis.successful_escalation = result
            elif not _is_canonical_block(content):
                analysis.uncertain_side_effect = True
                continue
            analysis.action_payloads.append(content)
            analysis.grounding_sources.append(f"action:{record.tool_name}")
            if record.tool_name == "escalate_case":
                escalation_id = sanitize_message(content["escalation_id"])[:128]
                analysis.grounding_sources.append(f"handoff:{escalation_id}")
            continue

        if (
            record.tool_name not in _READ_TOOLS
            or record.duplicate_or_retry
            or not record.tool_use_id
            or not _identity_matches(record)
        ):
            analysis.incomplete_invocation = True
            continue
        if not record.attempts or result is None:
            analysis.incomplete_invocation = True
            continue
        if (
            result.status == "success"
            and result.exception is None
            and result.cancel_message is None
            and isinstance(result.content, dict)
            and "error" not in result.content
        ):
            analysis.grounding_sources.append(f"tool:{record.tool_name}")
            if record.tool_name == "get_dispute_context":
                analysis.dispute_context = result.content
    return analysis


def _record_is_sensitive(record: _ToolRecord) -> bool:
    if record.tool_name in ACTION_TOOLS:
        return True
    return any(
        result.tool_name in ACTION_TOOLS
        or (
            isinstance(result.content, dict)
            and result.content.get("action") in ACTION_TOOLS
        )
        for result in record.results
    )


def _same_tool_arguments(
    left: object,
    right: object,
    *,
    _depth: int = 0,
    _active_left: set[int] | None = None,
    _active_right: set[int] | None = None,
) -> bool:
    if _depth > _MAX_TOOL_ARGUMENT_DEPTH or type(left) is not type(right):
        return False
    if left is None:
        return True
    if type(left) in (bool, int, float, str):
        return left == right
    if type(left) not in (list, dict):
        return False

    active_left = set() if _active_left is None else _active_left
    active_right = set() if _active_right is None else _active_right
    left_id = id(left)
    right_id = id(right)
    if left_id in active_left or right_id in active_right:
        return False
    active_left.add(left_id)
    active_right.add(right_id)
    try:
        if type(left) is list:
            return len(left) == len(right) and all(
                _same_tool_arguments(
                    left_item,
                    right_item,
                    _depth=_depth + 1,
                    _active_left=active_left,
                    _active_right=active_right,
                )
                for left_item, right_item in zip(left, right, strict=True)
            )
        if not all(type(key) is str for key in left) or not all(
            type(key) is str for key in right
        ):
            return False
        return left.keys() == right.keys() and all(
            _same_tool_arguments(
                left[key],
                right[key],
                _depth=_depth + 1,
                _active_left=active_left,
                _active_right=active_right,
            )
            for key in left
        )
    finally:
        active_left.remove(left_id)
        active_right.remove(right_id)


def _identity_matches(record: _ToolRecord) -> bool:
    result = record.result
    return result is None or (
        result.tool_use_id == record.tool_use_id
        and result.tool_name == record.tool_name
        and _same_tool_arguments(result.tool_args, record.tool_args)
    )


def _is_successful_escalation(result: NormalizedToolResult) -> bool:
    return (
        result.status == "success"
        and isinstance(result.content, dict)
        and result.content.get("action") == "escalate_case"
        and result.content.get("executed") is True
        and result.content.get("verification") in ("confirmed_persisted",)
        and isinstance(result.content.get("escalation_id"), str)
        and result.content.get("escalation_id") != ""
    )


def _is_canonical_block(content: dict) -> bool:
    if content.get("action") != "block_card":
        return False
    verification = content.get("verification")
    expected = ACTION_VERIFICATIONS["block_card"].get(verification)
    return expected is not None and content.get("executed") is expected


def _tool_parent(tool_use_id: str, state: dict) -> tuple[str | None, bool]:
    governance = state.get("tool_governance")
    info = (
        governance.get(tool_use_id)
        if tool_use_id and isinstance(governance, dict)
        else None
    )
    parent = info.get("event_id") if isinstance(info, dict) else None
    if _nonempty_string(parent):
        return parent, False
    return _nonempty_string(state.get("routing_event_id")), True


def _tool_event_payload(record: _ToolRecord, used_fallback: bool) -> dict:
    blocked = record.blocked_before_execution and not record.duplicate_or_retry
    status = (
        "blocked"
        if blocked
        else "success"
        if _tool_outcome(record) == "success"
        else "error"
    )
    payload = {
        "tool_name": record.tool_name,
        "tool_use_id": record.tool_use_id,
        "args": _audit_args(record.tool_name, record.tool_args),
        "result_status": status,
        "result_summary": _result_summary(record)[:500],
        "verified": _verified(record),
    }
    if record.tool_name in _REGISTERED_TOOL_NAMES:
        payload["authorization_verified"] = _authorization_verified(record)
    if used_fallback:
        payload["correlation"] = "routing_fallback"
    return payload


def _authorization_verified(record: _ToolRecord) -> bool:
    if record.duplicate_or_retry or len(record.attempts) != 1:
        return False
    if getattr(record.attempts[0], "authorization_verified", None) is not True:
        return False
    result = record.result
    return (
        result is not None
        and _identity_matches(record)
        and result.authorization_verified is True
    )


def _audit_args(tool_name: str, args: dict) -> dict:
    complaint_id = args.get("complaint_id")
    projected = {}
    if isinstance(complaint_id, str) and complaint_id.strip():
        projected["complaint_id"] = sanitize_message(complaint_id)[:128]
    if tool_name == "get_recent_transactions":
        days_before = args.get("days_before")
        if (
            isinstance(days_before, int)
            and not isinstance(days_before, bool)
            and days_before > 0
        ):
            projected["days_before"] = days_before
        limit = args.get("limit")
        if isinstance(limit, int) and not isinstance(limit, bool) and 1 <= limit <= 50:
            projected["limit"] = limit
    elif tool_name == "block_card":
        value = args.get("confirmed_by_customer")
        if isinstance(value, bool):
            projected["confirmed_by_customer"] = value
    elif tool_name == "escalate_case":
        reason = args.get("reason")
        if isinstance(reason, str) and reason.strip():
            projected["reason"] = sanitize_message(reason)[:500]
        unresolved = args.get("unresolved_questions")
        if isinstance(unresolved, list):
            projected["unresolved_questions_count"] = len(unresolved)
        if "agent_notes" in args and (
            args["agent_notes"] is None or isinstance(args["agent_notes"], str)
        ):
            projected["agent_notes_present"] = bool(args["agent_notes"])
    return projected if tool_name in _REGISTERED_TOOL_NAMES else {}


def _result_summary(record: _ToolRecord) -> str:
    if record.duplicate_or_retry:
        return "retry_or_duplicate_uncertain"
    if record.blocked_before_execution:
        return "blocked_before_execution"
    result = record.result
    if result is None:
        return "missing_terminal_result"
    if result.exception is not None:
        return f"exception:{result.exception.partition(':')[0]}"
    if result.cancel_message is not None:
        return "cancelled"
    if _record_is_sensitive(record):
        projection = {}
        if isinstance(result.content, dict):
            for key in ("action", "executed", "verification", "reason", "error"):
                if key in result.content:
                    value = result.content[key]
                    projection[key] = value if _is_scalar(value) else "<invalid>"
        return json.dumps(projection, ensure_ascii=False, sort_keys=True)
    if result.status != "success":
        if isinstance(result.content, dict) and isinstance(
            result.content.get("error"), str
        ):
            return sanitize_message(result.content["error"])
        return "error"
    return "success"


def _verified(record: _ToolRecord) -> bool:
    if (
        record.duplicate_or_retry
        or record.blocked_before_execution
        or record.result is None
        or record.result.exception is not None
        or record.result.cancel_message is not None
    ):
        return False
    result = record.result
    if record.tool_name == "escalate_case":
        return _is_successful_escalation(result)
    if record.tool_name == "block_card":
        return (
            result.status == "success"
            and isinstance(result.content, dict)
            and _is_canonical_block(result.content)
        )
    return (
        record.tool_name in _READ_TOOLS
        and result.status == "success"
        and isinstance(result.content, dict)
        and "error" not in result.content
    )


def _tool_outcome(record: _ToolRecord) -> str:
    if record.blocked_before_execution and not record.duplicate_or_retry:
        return "blocked"
    result = record.result
    if (
        not record.duplicate_or_retry
        and result is not None
        and result.status == "success"
        and result.exception is None
        and result.cancel_message is None
    ):
        return "success"
    return "failure"


def _tool_latency(record: _ToolRecord) -> int:
    result = record.result
    if result is None or result.duration_ms is None:
        return 0
    return result.duration_ms


def _sensitive_effect_may_have_happened(record: _ToolRecord) -> bool:
    if not _record_is_sensitive(record) or record.blocked_before_execution:
        return _record_is_sensitive(record) and record.duplicate_or_retry
    result = record.result
    if result is None or not isinstance(result.content, dict):
        return True
    return result.content.get("executed") is not False


def _fixed_classification(
    action: TurnAction,
    language: str,
    template: str,
    escalation_type: EscalationType | None,
    parent_event_id: str | None,
) -> TurnClassification:
    return TurnClassification(
        action,
        SAFE_TEMPLATES[language][template],
        escalation_type,
        None,
        parent_event_id,
    )


def _escalation_payload(
    classification: TurnClassification,
    successful_escalation: NormalizedToolResult | None,
) -> dict:
    if (
        classification.escalation_type is EscalationType.TOOL_ESCALATION
        and successful_escalation is not None
        and _is_successful_escalation(successful_escalation)
    ):
        content = successful_escalation.content
        handoff = (
            content.get("handoff") if isinstance(content.get("handoff"), dict) else {}
        )
        questions = handoff.get("unresolved_questions")
        metadata = handoff.get("handoff_metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        reason = metadata.get("reason")
        reason = (
            sanitize_message(reason)[:500]
            if isinstance(reason, str) and reason.strip()
            else "tool_escalation"
        )
        priority = content.get("priority")
        priority = (
            sanitize_message(priority)[:50]
            if isinstance(priority, str) and priority.strip()
            else "unknown"
        )
        return {
            "reason": reason,
            "priority": priority,
            "unresolved_questions_count": len(questions)
            if isinstance(questions, list)
            else 0,
            "handoff_id": sanitize_message(content["escalation_id"])[:128],
        }
    return {
        "reason": classification.escalation_type.value,
        "priority": "unknown",
        "unresolved_questions_count": 0,
    }


def _response_payload(
    classification: TurnClassification,
    language: str,
    analysis: _ToolAnalysis,
) -> dict:
    sources = list(analysis.grounding_sources)
    if classification.action is TurnAction.RESPOND:
        sources.append("model:screened")
    else:
        sources.append("orchestrator:template")
    grounded_in = []
    for source in sources:
        source = sanitize_message(source)[:200]
        if source not in grounded_in:
            grounded_in.append(source)
        if len(grounded_in) == 8:
            break

    summaries = []
    for payload in analysis.action_payloads:
        action = payload.get("action")
        verification = payload.get("verification")
        if isinstance(action, str) and isinstance(verification, str):
            summaries.append(f"{action}:{verification}")
    if summaries:
        action_summary = ", ".join(summaries)
    elif classification.action is TurnAction.BLOCK:
        action_summary = "blocked"
    elif classification.action is TurnAction.ABSTAIN:
        action_summary = "abstained"
    elif classification.action is TurnAction.ESCALATE:
        action_summary = classification.escalation_type.value
    else:
        action_summary = "none"
    return {
        "grounded_in": grounded_in,
        "action_summary": sanitize_message(action_summary)[:500],
        "language": language,
    }


def _message_text(message: object) -> str:
    if not isinstance(message, dict) or not isinstance(message.get("content"), list):
        return ""
    return "".join(
        block["text"]
        for block in message["content"]
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    )


def _safe_exception(error: Exception) -> str:
    message = sanitize_message(str(error))
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


def _mask_customer_id(customer_id: str) -> str:
    if len(customer_id) <= 4:
        return "****"
    return "*" * (len(customer_id) - 4) + customer_id[-4:]


def _elapsed_ms(started: float) -> int:
    return max(0, int((monotonic() - started) * 1000))


def _add_orphaned(payload: dict, state: dict) -> None:
    if state.get("audit_orphaned") is True:
        payload["orphaned"] = True


def _last_durable_parent(candidate: object, fallback: str | None) -> str | None:
    return _nonempty_string(candidate) or fallback


def _nonempty_string(value: object) -> str | None:
    return value if isinstance(value, str) and bool(value.strip()) else None


def _valid_tool_name(value: object) -> str:
    return _nonempty_string(value) or "unknown"


def _valid_args(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _is_scalar(value: object) -> bool:
    return value is None or isinstance(value, str | int | float | bool)
