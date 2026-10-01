"""Pure governance decision types and runtime threshold validation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from .evaluations import EXPECTED_INTENTS
from .schemas import Usage

if TYPE_CHECKING:
    from ai_banking_customer_service.config import GovernancePolicy

    from .evaluations import InputScreeningResult, IntentRoutingResult


class GovernanceAction(StrEnum):
    BLOCK = "block"
    REVIEW = "review"
    ALLOW = "allow"


class GovernanceStage(StrEnum):
    INPUT_SCREENING = "input_screening"
    INTENT_ROUTING = "intent_routing"


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
    governance_thresholds: GovernanceThresholds
    prompt_injection_signal: float | None = None
    social_engineering_signal: float | None = None
    intent: str | None = None
    intent_confidence: float | None = None
    intent_probabilities: dict[str, float] | None = None


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
            "INVALID_CONFIDENCE: "
            "intent_confidence is not finite or is outside [0, 1]",
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
