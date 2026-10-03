"""Pure governance decision types and runtime threshold validation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from .evaluations import EXPECTED_INTENTS
from .schemas import NoulAnswer, ScoreAnswer, Usage

if TYPE_CHECKING:
    from ai_banking_customer_service.config import (
        GovernancePolicy,
        OutputScreeningPolicy,
        ToolGatingPolicy,
    )

    from .evaluations import (
        InputScreeningResult,
        IntentRoutingResult,
        OutputScreeningResult,
        ToolGatingResult,
    )


class GovernanceAction(StrEnum):
    BLOCK = "block"
    REVIEW = "review"
    ALLOW = "allow"


class GovernanceStage(StrEnum):
    INPUT_SCREENING = "input_screening"
    INTENT_ROUTING = "intent_routing"
    TOOL_GATING = "tool_gating"
    OUTPUT_SCREENING = "output_screening"


@dataclass(frozen=True)
class ScreeningThresholds:
    block: float
    review: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.block) and math.isfinite(self.review)):
            raise ValueError("ScreeningThresholds: block y review deben ser finitos")
        if not (0.0 <= self.review < self.block <= 1.0):
            raise ValueError(
                "ScreeningThresholds: se requiere 0 <= review < block <= 1"
            )


@dataclass(frozen=True)
class ToolGatingThresholds:
    min_intent_matches_tool: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.min_intent_matches_tool):
            raise ValueError(
                "ToolGatingThresholds: min_intent_matches_tool debe ser finito"
            )
        if not (0.0 <= self.min_intent_matches_tool <= 1.0):
            raise ValueError(
                "ToolGatingThresholds: se requiere 0 <= min_intent_matches_tool <= 1"
            )

    @classmethod
    def from_policy(
        cls,
        policy: ToolGatingPolicy,
    ) -> ToolGatingThresholds:
        if policy is None:
            raise ValueError("from_policy: policy no puede ser None")
        return cls(min_intent_matches_tool=policy.min_intent_matches_tool)


@dataclass(frozen=True)
class OutputScreeningThresholds:
    min_output_safety_score: float
    min_output_safety_confidence: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.min_output_safety_score):
            raise ValueError(
                "OutputScreeningThresholds: min_output_safety_score debe ser finito"
            )
        if not (0.0 <= self.min_output_safety_score <= 2.0):
            raise ValueError(
                "OutputScreeningThresholds: se requiere "
                "0 <= min_output_safety_score <= 2"
            )
        if not math.isfinite(self.min_output_safety_confidence):
            raise ValueError(
                "OutputScreeningThresholds: "
                "min_output_safety_confidence debe ser finito"
            )
        if not (0.0 <= self.min_output_safety_confidence <= 1.0):
            raise ValueError(
                "OutputScreeningThresholds: se requiere "
                "0 <= min_output_safety_confidence <= 1"
            )

    @classmethod
    def from_policy(
        cls,
        policy: OutputScreeningPolicy,
    ) -> OutputScreeningThresholds:
        if policy is None:
            raise ValueError("from_policy: policy no puede ser None")
        return cls(
            min_output_safety_score=policy.min_output_safety_score,
            min_output_safety_confidence=policy.min_output_safety_confidence,
        )


@dataclass(frozen=True)
class GovernanceThresholds:
    prompt_injection: ScreeningThresholds
    social_engineering: ScreeningThresholds
    min_intent_confidence: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.min_intent_confidence):
            raise ValueError(
                "GovernanceThresholds: min_intent_confidence debe ser finito"
            )
        if not (0.0 <= self.min_intent_confidence <= 1.0):
            raise ValueError(
                "GovernanceThresholds: se requiere 0 <= min_intent_confidence <= 1"
            )

    @classmethod
    def from_policy(
        cls,
        governance_policy: GovernancePolicy,
    ) -> GovernanceThresholds:
        if governance_policy is None:
            raise ValueError("from_policy: governance_policy no puede ser None")
        return cls(
            prompt_injection=ScreeningThresholds(
                block=governance_policy.prompt_injection.block,
                review=governance_policy.prompt_injection.review,
            ),
            social_engineering=ScreeningThresholds(
                block=governance_policy.social_engineering.block,
                review=governance_policy.social_engineering.review,
            ),
            min_intent_confidence=governance_policy.min_intent_confidence,
        )


@dataclass(frozen=True)
class GovernanceDecision:
    action: GovernanceAction
    stage: GovernanceStage
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]
    model: str | None
    usage: Usage | None
    governance_thresholds: (
        GovernanceThresholds | ToolGatingThresholds | OutputScreeningThresholds
    )
    prompt_injection_signal: float | None = None
    social_engineering_signal: float | None = None
    intent: str | None = None
    intent_confidence: float | None = None
    intent_probabilities: dict[str, float] | None = None
    intent_matches_tool: NoulAnswer | None = None
    output_safety_semantic: ScoreAnswer | None = None


def decide_screening(
    screening: InputScreeningResult,
    thresholds: GovernanceThresholds,
) -> GovernanceDecision:
    """Apply screening thresholds with BLOCK taking precedence over REVIEW."""
    prompt_injection = screening.prompt_injection.noul
    social_engineering = screening.social_engineering.noul
    signals = (
        ("prompt_injection", prompt_injection, thresholds.prompt_injection),
        ("social_engineering", social_engineering, thresholds.social_engineering),
    )

    def decision(
        action: GovernanceAction,
        reasons: tuple[str, ...],
    ) -> GovernanceDecision:
        return GovernanceDecision(
            action=action,
            stage=GovernanceStage.INPUT_SCREENING,
            reason_codes=tuple(reason.partition(":")[0] for reason in reasons),
            reasons=reasons,
            model=screening.model if isinstance(screening.model, str) else None,
            usage=screening.usage if isinstance(screening.usage, Usage) else None,
            governance_thresholds=thresholds,
            prompt_injection_signal=prompt_injection,
            social_engineering_signal=social_engineering,
        )

    invalid_signals = tuple(
        f"INVALID_SIGNAL: {field} is not finite or is outside [0, 1]"
        for field, value, _ in signals
        if not (math.isfinite(value) and 0.0 <= value <= 1.0)
    )
    if invalid_signals:
        return decision(GovernanceAction.BLOCK, invalid_signals)

    if not isinstance(screening.model, str) or not screening.model.strip():
        return decision(
            GovernanceAction.BLOCK,
            ("INVALID_METADATA: model is not a non-blank string",),
        )
    if not isinstance(screening.usage, Usage):
        return decision(
            GovernanceAction.BLOCK,
            ("INVALID_METADATA: usage is missing",),
        )

    blocked = tuple(signal for signal in signals if signal[1] >= signal[2].block)
    if blocked:
        reasons = tuple(
            (
                f"BLOCK_{field.upper()}: {field}={repr(float(value))} "
                f">= block={repr(float(limit.block))}"
            )
            for field, value, limit in blocked
        )
        return decision(GovernanceAction.BLOCK, reasons)

    review = tuple(signal for signal in signals if signal[1] >= signal[2].review)
    if review:
        reasons = tuple(
            (
                f"REVIEW_{field.upper()}: {field}={repr(float(value))} "
                f">= review={repr(float(limit.review))}"
            )
            for field, value, limit in review
        )
        return decision(GovernanceAction.REVIEW, reasons)

    return decision(
        GovernanceAction.ALLOW,
        ("SCREENING_PASS: all signals below review thresholds",),
    )


def decide_tool_gating(
    gating: ToolGatingResult,
    thresholds: ToolGatingThresholds,
) -> GovernanceDecision:
    """Decide whether one concrete tool call may execute."""

    def decision(
        action: GovernanceAction,
        reason: str,
    ) -> GovernanceDecision:
        return GovernanceDecision(
            action=action,
            stage=GovernanceStage.TOOL_GATING,
            reason_codes=(reason.partition(":")[0],),
            reasons=(reason,),
            model=gating.model if isinstance(gating.model, str) else None,
            usage=gating.usage if isinstance(gating.usage, Usage) else None,
            governance_thresholds=thresholds,
            intent_matches_tool=gating.intent_matches_tool,
        )

    if gating.deterministic_block:
        return decision(
            GovernanceAction.BLOCK,
            f"TOOL_GATING_DETERMINISTIC_BLOCK: {gating.deterministic_reason}",
        )
    if not isinstance(gating.model, str) or not gating.model.strip():
        return decision(
            GovernanceAction.BLOCK,
            "INVALID_METADATA: model is invalid",
        )
    if not isinstance(gating.usage, Usage):
        return decision(
            GovernanceAction.BLOCK,
            "INVALID_METADATA: usage is invalid",
        )

    probability = gating.intent_matches_tool.noul
    if not (math.isfinite(probability) and 0.0 <= probability <= 1.0):
        return decision(
            GovernanceAction.BLOCK,
            "INVALID_SIGNAL: intent_matches_tool.noul failed validation",
        )

    threshold = thresholds.min_intent_matches_tool
    if probability >= threshold:
        return decision(
            GovernanceAction.ALLOW,
            "TOOL_GATING_ALLOW: "
            f"intent_matches_tool={repr(float(probability))} "
            f">= min_intent_matches_tool={repr(float(threshold))}",
        )

    return decision(
        GovernanceAction.BLOCK,
        "TOOL_GATING_BLOCK_LOW_INTENT_MATCH: "
        f"intent_matches_tool={repr(float(probability))} "
        f"< min_intent_matches_tool={repr(float(threshold))}",
    )


def decide_output_screening(
    screening: OutputScreeningResult,
    thresholds: OutputScreeningThresholds,
) -> GovernanceDecision:
    """Decide whether a proposed response may be delivered."""

    def decision(
        action: GovernanceAction,
        reason: str,
    ) -> GovernanceDecision:
        return GovernanceDecision(
            action=action,
            stage=GovernanceStage.OUTPUT_SCREENING,
            reason_codes=(reason.partition(":")[0],),
            reasons=(reason,),
            model=screening.model if isinstance(screening.model, str) else None,
            usage=screening.usage if isinstance(screening.usage, Usage) else None,
            governance_thresholds=thresholds,
            output_safety_semantic=screening.output_safety_semantic,
        )

    if screening.secrets_detected:
        return decision(
            GovernanceAction.REVIEW,
            "OUTPUT_SCREENING_SECRETS_DETECTED: "
            f"secrets_detected={screening.secrets_detected!r}",
        )
    if not isinstance(screening.model, str) or not screening.model.strip():
        return decision(
            GovernanceAction.REVIEW,
            "INVALID_METADATA: model is invalid",
        )
    if not isinstance(screening.usage, Usage):
        return decision(
            GovernanceAction.REVIEW,
            "INVALID_METADATA: usage is invalid",
        )

    answer = screening.output_safety_semantic
    score = answer.score
    if not (math.isfinite(score) and 0.0 <= score <= 2.0):
        return decision(
            GovernanceAction.REVIEW,
            "INVALID_SIGNAL: score failed validation",
        )
    if set(answer.legend) != {0, 1, 2}:
        return decision(
            GovernanceAction.REVIEW,
            "INVALID_SIGNAL: legend_domain failed validation",
        )
    if set(answer.probabilities) != {0, 1, 2}:
        return decision(
            GovernanceAction.REVIEW,
            "INVALID_SIGNAL: probabilities_domain failed validation",
        )
    if not all(
        math.isfinite(probability) and 0.0 <= probability <= 1.0
        for probability in answer.probabilities.values()
    ):
        return decision(
            GovernanceAction.REVIEW,
            "INVALID_SIGNAL: probability_values failed validation",
        )
    if not math.isclose(
        sum(answer.probabilities.values()),
        1.0,
        abs_tol=1e-6,
    ):
        return decision(
            GovernanceAction.REVIEW,
            "INVALID_SIGNAL: probability_sum failed validation",
        )
    weighted_score = sum(
        level * probability for level, probability in answer.probabilities.items()
    )
    if not math.isclose(score, weighted_score, abs_tol=0.1):
        return decision(
            GovernanceAction.REVIEW,
            "INVALID_SIGNAL: weighted_score failed validation",
        )

    confidence = answer.confidence
    if not (math.isfinite(confidence) and 0.0 <= confidence <= 1.0):
        return decision(
            GovernanceAction.REVIEW,
            "INVALID_SIGNAL: confidence failed validation",
        )

    confidence_threshold = thresholds.min_output_safety_confidence
    if confidence < confidence_threshold:
        return decision(
            GovernanceAction.REVIEW,
            "OUTPUT_SCREENING_REVIEW_LOW_CONFIDENCE: "
            f"confidence={repr(float(confidence))} "
            "< min_output_safety_confidence="
            f"{repr(float(confidence_threshold))}",
        )

    score_threshold = thresholds.min_output_safety_score
    if score < score_threshold:
        return decision(
            GovernanceAction.REVIEW,
            "OUTPUT_SCREENING_REVIEW_LOW_SCORE: "
            f"output_safety_score={repr(float(score))} "
            f"< min_output_safety_score={repr(float(score_threshold))}",
        )

    return decision(
        GovernanceAction.ALLOW,
        "OUTPUT_SCREENING_ALLOW: "
        f"output_safety_score={repr(float(score))} "
        f">= min_output_safety_score={repr(float(score_threshold))} "
        f"and confidence={repr(float(confidence))} "
        ">= min_output_safety_confidence="
        f"{repr(float(confidence_threshold))}",
    )


def decide_routing(
    routing: IntentRoutingResult,
    thresholds: GovernanceThresholds,
) -> GovernanceDecision:
    """Apply the minimum-confidence policy to a routed banking intent."""
    intent = routing.intent.choice
    confidence = routing.intent.confidence
    normalized_intent = (
        intent if isinstance(intent, str) and intent in EXPECTED_INTENTS else None
    )

    def decision(
        action: GovernanceAction,
        reason: str,
    ) -> GovernanceDecision:
        return GovernanceDecision(
            action=action,
            stage=GovernanceStage.INTENT_ROUTING,
            reason_codes=(reason.partition(":")[0],),
            reasons=(reason,),
            model=routing.model if isinstance(routing.model, str) else None,
            usage=routing.usage if isinstance(routing.usage, Usage) else None,
            governance_thresholds=thresholds,
            intent=normalized_intent,
            intent_confidence=confidence,
            intent_probabilities=routing.intent.probabilities,
        )

    if not isinstance(intent, str) or not intent.strip():
        return decision(
            GovernanceAction.BLOCK,
            "INVALID_INTENT: intent choice is not a non-blank string",
        )
    if intent not in EXPECTED_INTENTS:
        return decision(
            GovernanceAction.BLOCK,
            "INVALID_INTENT_DOMAIN: "
            f"intent choice '{intent}' is not in the supported intent domain",
        )
    if not (math.isfinite(confidence) and 0.0 <= confidence <= 1.0):
        return decision(
            GovernanceAction.BLOCK,
            "INVALID_CONFIDENCE: intent_confidence is not finite or is outside [0, 1]",
        )
    if not isinstance(routing.model, str) or not routing.model.strip():
        return decision(
            GovernanceAction.BLOCK,
            "INVALID_METADATA: model is not a non-blank string",
        )
    if not isinstance(routing.usage, Usage):
        return decision(
            GovernanceAction.BLOCK,
            "INVALID_METADATA: usage is missing",
        )

    threshold = thresholds.min_intent_confidence
    if confidence < threshold:
        return decision(
            GovernanceAction.REVIEW,
            "REVIEW_LOW_INTENT_CONFIDENCE: "
            f"intent_confidence={repr(float(confidence))} "
            f"< min_intent_confidence={repr(float(threshold))}",
        )

    return decision(
        GovernanceAction.ALLOW,
        f"ROUTING_ALLOW: intent='{intent}' "
        f"intent_confidence={repr(float(confidence))} "
        f">= min_intent_confidence={repr(float(threshold))}",
    )
