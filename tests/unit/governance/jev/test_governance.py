import math

import pytest

from ai_banking_customer_service.config import GovernancePolicy
from ai_banking_customer_service.governance.jev.decision import (
    GovernanceAction,
    GovernanceDecision,
    GovernanceStage,
    GovernanceThresholds,
    ScreeningThresholds,
    decide_routing,
    decide_screening,
)
from ai_banking_customer_service.governance.jev.evaluations import (
    EXPECTED_INTENTS,
    InputScreeningResult,
    IntentRoutingResult,
)
from ai_banking_customer_service.governance.jev.schemas import (
    ChoiceAnswer,
    NoulAnswer,
    Usage,
)


@pytest.fixture
def governance_thresholds() -> GovernanceThresholds:
    return GovernanceThresholds(
        prompt_injection=ScreeningThresholds(block=0.8, review=0.35),
        social_engineering=ScreeningThresholds(block=0.8, review=0.35),
        min_intent_confidence=0.5,
    )


_DEFAULT_USAGE = object()


def _screening_result(
    prompt_injection: float,
    social_engineering: float,
    *,
    model: object = "jev-screening",
    usage: object | None = _DEFAULT_USAGE,
) -> InputScreeningResult:
    return InputScreeningResult(
        prompt_injection=NoulAnswer.model_construct(
            type="noul", noul=prompt_injection
        ),
        social_engineering=NoulAnswer.model_construct(
            type="noul", noul=social_engineering
        ),
        model=model,
        usage=(
            Usage(input_tokens=11, output_tokens=2)
            if usage is _DEFAULT_USAGE
            else usage
        ),
    )


def test_decision_public_api_importable_from_exact_module() -> None:
    expected_module = "ai_banking_customer_service.governance.jev.decision"

    for symbol in (
        decide_screening,
        decide_routing,
        GovernanceAction,
        GovernanceStage,
        GovernanceDecision,
        GovernanceThresholds,
        ScreeningThresholds,
    ):
        assert symbol.__module__ == expected_module


@pytest.mark.parametrize(
    ("block", "review"),
    [
        (0.5, 0.5),
        (1.01, 0.35),
        (0.8, -0.01),
        (float("nan"), 0.35),
        (0.8, float("inf")),
    ],
    ids=[
        "review-not-below-block",
        "block-above-one",
        "review-below-zero",
        "non-finite-block",
        "non-finite-review",
    ],
)
def test_screening_thresholds_reject_invalid_values(
    block: float,
    review: float,
) -> None:
    with pytest.raises(ValueError):
        ScreeningThresholds(block=block, review=review)


@pytest.mark.parametrize(
    "min_intent_confidence",
    [-0.01, 1.01, float("nan"), float("inf")],
    ids=["below-zero", "above-one", "nan", "infinity"],
)
def test_governance_thresholds_reject_invalid_min_intent_confidence(
    min_intent_confidence: float,
) -> None:
    screening = ScreeningThresholds(block=0.8, review=0.35)

    with pytest.raises(ValueError):
        GovernanceThresholds(
            prompt_injection=screening,
            social_engineering=screening,
            min_intent_confidence=min_intent_confidence,
        )


def test_governance_thresholds_from_policy_maps_configured_values() -> None:
    governance_policy = GovernancePolicy(
        prompt_injection={"block": 0.8, "review": 0.35},
        social_engineering={"block": 0.8, "review": 0.35},
        min_intent_confidence=0.5,
    )
    thresholds = GovernanceThresholds.from_policy(governance_policy)

    assert thresholds == GovernanceThresholds(
        prompt_injection=ScreeningThresholds(block=0.8, review=0.35),
        social_engineering=ScreeningThresholds(block=0.8, review=0.35),
        min_intent_confidence=0.5,
    )


def test_governance_thresholds_from_policy_rejects_none_explicitly() -> None:
    with pytest.raises(ValueError, match="governance_policy no puede ser None"):
        GovernanceThresholds.from_policy(None)


@pytest.mark.parametrize(
    (
        "prompt_injection",
        "social_engineering",
        "expected_action",
        "expected_codes",
    ),
    [
        (0.9, 0.1, GovernanceAction.BLOCK, ("BLOCK_PROMPT_INJECTION",)),
        (0.1, 0.9, GovernanceAction.BLOCK, ("BLOCK_SOCIAL_ENGINEERING",)),
        (
            0.8,
            0.8,
            GovernanceAction.BLOCK,
            ("BLOCK_PROMPT_INJECTION", "BLOCK_SOCIAL_ENGINEERING"),
        ),
        (0.8, 0.35, GovernanceAction.BLOCK, ("BLOCK_PROMPT_INJECTION",)),
        (0.35, 0.8, GovernanceAction.BLOCK, ("BLOCK_SOCIAL_ENGINEERING",)),
        (0.35, 0.1, GovernanceAction.REVIEW, ("REVIEW_PROMPT_INJECTION",)),
        (0.1, 0.35, GovernanceAction.REVIEW, ("REVIEW_SOCIAL_ENGINEERING",)),
        (
            0.35,
            0.35,
            GovernanceAction.REVIEW,
            ("REVIEW_PROMPT_INJECTION", "REVIEW_SOCIAL_ENGINEERING"),
        ),
        (0.1, 0.1, GovernanceAction.ALLOW, ("SCREENING_PASS",)),
    ],
    ids=[
        "prompt-injection-above-block",
        "social-engineering-above-block",
        "both-at-block",
        "block-precedes-review",
        "social-block-precedes-prompt-review",
        "prompt-injection-at-review",
        "social-engineering-at-review",
        "both-at-review",
        "both-below-review",
    ],
)
def test_decide_screening_applies_boundaries_precedence_and_fixed_reason_order(
    governance_thresholds: GovernanceThresholds,
    prompt_injection: float,
    social_engineering: float,
    expected_action: GovernanceAction,
    expected_codes: tuple[str, ...],
) -> None:
    decision = decide_screening(
        _screening_result(prompt_injection, social_engineering),
        governance_thresholds,
    )

    assert decision.action is expected_action
    assert decision.stage is GovernanceStage.INPUT_SCREENING
    assert decision.reason_codes == expected_codes
    assert decision.reason_codes == tuple(
        reason.partition(":")[0] for reason in decision.reasons
    )
    assert decision.prompt_injection_signal == prompt_injection
    assert decision.social_engineering_signal == social_engineering
    assert decision.intent is None
    assert decision.intent_confidence is None
    assert decision.intent_probabilities is None


def test_decide_screening_preserves_stage_fields_metadata_thresholds_and_reasons(
    governance_thresholds: GovernanceThresholds,
) -> None:
    screening = _screening_result(0.8, 0.1)

    decision = decide_screening(screening, governance_thresholds)

    assert decision == GovernanceDecision(
        action=GovernanceAction.BLOCK,
        stage=GovernanceStage.INPUT_SCREENING,
        reason_codes=("BLOCK_PROMPT_INJECTION",),
        reasons=("BLOCK_PROMPT_INJECTION: prompt_injection=0.8 >= block=0.8",),
        model="jev-screening",
        usage=screening.usage,
        governance_thresholds=governance_thresholds,
        prompt_injection_signal=0.8,
        social_engineering_signal=0.1,
        intent=None,
        intent_confidence=None,
        intent_probabilities=None,
    )
    assert decision.usage is screening.usage
    assert decision.governance_thresholds is governance_thresholds


def test_decide_screening_uses_custom_thresholds() -> None:
    screening = _screening_result(0.6, 0.1)
    lower_thresholds = GovernanceThresholds(
        prompt_injection=ScreeningThresholds(block=0.8, review=0.35),
        social_engineering=ScreeningThresholds(block=0.8, review=0.35),
        min_intent_confidence=0.5,
    )
    higher_thresholds = GovernanceThresholds(
        prompt_injection=ScreeningThresholds(block=0.9, review=0.7),
        social_engineering=ScreeningThresholds(block=0.9, review=0.7),
        min_intent_confidence=0.5,
    )

    assert (
        decide_screening(screening, lower_thresholds).action is GovernanceAction.REVIEW
    )
    assert (
        decide_screening(screening, higher_thresholds).action is GovernanceAction.ALLOW
    )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        (field, value)
        for field in ("prompt_injection", "social_engineering")
        for value in (
            float("nan"),
            float("inf"),
            float("-inf"),
            -0.01,
            1.01,
        )
    ],
)
def test_decide_screening_blocks_each_invalid_signal_without_raising(
    governance_thresholds: GovernanceThresholds,
    field: str,
    invalid_value: float,
) -> None:
    values = {"prompt_injection": 0.1, "social_engineering": 0.1}
    values[field] = invalid_value

    decision = decide_screening(
        _screening_result(**values),
        governance_thresholds,
    )

    assert decision.action is GovernanceAction.BLOCK
    assert decision.reason_codes == ("INVALID_SIGNAL",)
    assert decision.reasons == (
        f"INVALID_SIGNAL: {field} is not finite or is outside [0, 1]",
    )


def test_decide_screening_reports_both_invalid_signals_before_invalid_metadata(
    governance_thresholds: GovernanceThresholds,
) -> None:
    decision = decide_screening(
        _screening_result(float("nan"), 1.01, model=" ", usage=None),
        governance_thresholds,
    )

    assert decision.action is GovernanceAction.BLOCK
    assert decision.reason_codes == ("INVALID_SIGNAL", "INVALID_SIGNAL")
    assert decision.reasons == (
        "INVALID_SIGNAL: prompt_injection is not finite or is outside [0, 1]",
        "INVALID_SIGNAL: social_engineering is not finite or is outside [0, 1]",
    )
    assert len(decision.reason_codes) == len(decision.reasons)


@pytest.mark.parametrize(
    ("model", "usage", "expected_model", "expected_usage", "expected_detail"),
    [
        ("", _DEFAULT_USAGE, "", "valid", "model is not a non-blank string"),
        ("   ", _DEFAULT_USAGE, "   ", "valid", "model is not a non-blank string"),
        (123, _DEFAULT_USAGE, None, "valid", "model is not a non-blank string"),
        ("jev-screening", None, "jev-screening", None, "usage is missing"),
        ("jev-screening", object(), "jev-screening", None, "usage is missing"),
        ("", None, "", None, "model is not a non-blank string"),
    ],
    ids=[
        "empty-model",
        "blank-model",
        "non-string-model",
        "missing-usage",
        "wrong-usage-type",
        "model-precedes-usage",
    ],
)
def test_decide_screening_blocks_invalid_metadata_with_field_precedence(
    governance_thresholds: GovernanceThresholds,
    model: object,
    usage: object | None,
    expected_model: str | None,
    expected_usage: str | None,
    expected_detail: str,
) -> None:
    screening = _screening_result(0.1, 0.1, model=model, usage=usage)

    decision = decide_screening(screening, governance_thresholds)

    assert decision.action is GovernanceAction.BLOCK
    assert decision.reason_codes == ("INVALID_METADATA",)
    assert decision.reasons == (f"INVALID_METADATA: {expected_detail}",)
    assert decision.model == expected_model
    if expected_usage == "valid":
        assert decision.usage is screening.usage
    else:
        assert decision.usage is None
    assert decision.prompt_injection_signal == 0.1
    assert decision.social_engineering_signal == 0.1
    assert decision.intent is None
    assert decision.intent_confidence is None
    assert decision.intent_probabilities is None


def test_decide_screening_reasons_use_exact_float_repr(
    governance_thresholds: GovernanceThresholds,
) -> None:
    signal = 0.35000000000000003

    decision = decide_screening(
        _screening_result(signal, 0.1),
        governance_thresholds,
    )

    assert decision.reasons == (
        "REVIEW_PROMPT_INJECTION: "
        f"prompt_injection={repr(float(signal))} >= review=0.35",
    )


def _routing_result(
    intent: object = "dispute_charge",
    confidence: float = 0.5,
    *,
    probabilities: dict[str, float] | None = None,
    model: object = "jev-routing",
    usage: object | None = _DEFAULT_USAGE,
) -> IntentRoutingResult:
    raw_probabilities = probabilities or {
        expected_intent: (confidence if expected_intent == intent else 0.01)
        for expected_intent in EXPECTED_INTENTS
    }
    return IntentRoutingResult(
        intent=ChoiceAnswer.model_construct(
            type="choice",
            choice=intent,
            confidence=confidence,
            probabilities=raw_probabilities,
        ),
        model=model,
        usage=(
            Usage(input_tokens=17, output_tokens=3)
            if usage is _DEFAULT_USAGE
            else usage
        ),
    )


@pytest.mark.parametrize("confidence", [0.5, 0.9], ids=["at-threshold", "above"])
def test_decide_routing_allows_valid_intent_at_or_above_threshold(
    governance_thresholds: GovernanceThresholds,
    confidence: float,
) -> None:
    routing = _routing_result(confidence=confidence)

    decision = decide_routing(routing, governance_thresholds)

    assert decision.action is GovernanceAction.ALLOW
    assert decision.stage is GovernanceStage.INTENT_ROUTING
    assert decision.reason_codes == ("ROUTING_ALLOW",)
    assert decision.reasons == (
        "ROUTING_ALLOW: intent='dispute_charge' "
        f"intent_confidence={repr(float(confidence))} "
        ">= min_intent_confidence=0.5",
    )


def test_decide_routing_reviews_low_confidence_and_preserves_routing_fields(
    governance_thresholds: GovernanceThresholds,
) -> None:
    confidence = 0.49900000000000005
    probabilities = {
        intent: index / 10 for index, intent in enumerate(EXPECTED_INTENTS)
    }
    routing = _routing_result(confidence=confidence, probabilities=probabilities)

    decision = decide_routing(routing, governance_thresholds)

    assert decision == GovernanceDecision(
        action=GovernanceAction.REVIEW,
        stage=GovernanceStage.INTENT_ROUTING,
        reason_codes=("REVIEW_LOW_INTENT_CONFIDENCE",),
        reasons=(
            "REVIEW_LOW_INTENT_CONFIDENCE: "
            f"intent_confidence={repr(float(confidence))} "
            "< min_intent_confidence=0.5",
        ),
        model="jev-routing",
        usage=routing.usage,
        governance_thresholds=governance_thresholds,
        prompt_injection_signal=None,
        social_engineering_signal=None,
        intent="dispute_charge",
        intent_confidence=confidence,
        intent_probabilities=probabilities,
    )
    assert decision.intent_probabilities is probabilities
    assert decision.usage is routing.usage
    assert decision.governance_thresholds is governance_thresholds
    assert len(decision.reason_codes) == len(decision.reasons) == 1


@pytest.mark.parametrize("intent", sorted(EXPECTED_INTENTS))
def test_decide_routing_allows_every_expected_intent(
    governance_thresholds: GovernanceThresholds,
    intent: str,
) -> None:
    decision = decide_routing(
        _routing_result(intent=intent, confidence=0.8),
        governance_thresholds,
    )

    assert decision.action is GovernanceAction.ALLOW
    assert decision.intent == intent


def test_decide_routing_uses_custom_confidence_thresholds() -> None:
    routing = _routing_result(confidence=0.7)
    screening = ScreeningThresholds(block=0.8, review=0.35)
    lower_threshold = GovernanceThresholds(screening, screening, 0.6)
    higher_threshold = GovernanceThresholds(screening, screening, 0.75)

    assert decide_routing(routing, lower_threshold).action is GovernanceAction.ALLOW
    assert decide_routing(routing, higher_threshold).action is GovernanceAction.REVIEW


@pytest.mark.parametrize(
    "intent",
    ["", "   ", 123],
    ids=["empty", "blank", "non-string"],
)
def test_decide_routing_blocks_invalid_intent_before_other_invalid_values(
    governance_thresholds: GovernanceThresholds,
    intent: object,
) -> None:
    decision = decide_routing(
        _routing_result(intent=intent, confidence=float("nan"), model="", usage=None),
        governance_thresholds,
    )

    assert decision.action is GovernanceAction.BLOCK
    assert decision.reason_codes == ("INVALID_INTENT",)
    assert decision.reasons == (
        "INVALID_INTENT: intent choice is not a non-blank string",
    )
    assert len(decision.reason_codes) == len(decision.reasons) == 1


def test_decide_routing_blocks_out_of_domain_intent_before_confidence_and_metadata(
    governance_thresholds: GovernanceThresholds,
) -> None:
    intent = "execute_wire_transfer"

    decision = decide_routing(
        _routing_result(intent=intent, confidence=float("inf"), model="", usage=None),
        governance_thresholds,
    )

    assert decision.action is GovernanceAction.BLOCK
    assert decision.reason_codes == ("INVALID_INTENT_DOMAIN",)
    assert decision.reasons == (
        "INVALID_INTENT_DOMAIN: intent choice "
        f"'{intent}' is not in the supported intent domain",
    )
    assert decision.intent is None


@pytest.mark.parametrize(
    "confidence",
    [float("nan"), float("inf"), float("-inf"), -0.01, 1.01],
    ids=["nan", "positive-infinity", "negative-infinity", "below-zero", "above-one"],
)
def test_decide_routing_blocks_invalid_confidence_before_invalid_metadata(
    governance_thresholds: GovernanceThresholds,
    confidence: float,
) -> None:
    routing = _routing_result(confidence=confidence, model="", usage=None)

    decision = decide_routing(routing, governance_thresholds)

    assert decision.action is GovernanceAction.BLOCK
    assert decision.reason_codes == ("INVALID_CONFIDENCE",)
    assert decision.reasons == (
        "INVALID_CONFIDENCE: intent_confidence is not finite or is outside [0, 1]",
    )
    assert decision.intent == "dispute_charge"
    assert decision.intent_confidence == confidence or (
        math.isnan(decision.intent_confidence) and math.isnan(confidence)
    )
    assert decision.intent_probabilities is routing.intent.probabilities
    assert len(decision.reason_codes) == len(decision.reasons) == 1


@pytest.mark.parametrize(
    ("model", "usage", "expected_model", "expected_usage", "expected_detail"),
    [
        ("", _DEFAULT_USAGE, "", "valid", "model is not a non-blank string"),
        ("   ", _DEFAULT_USAGE, "   ", "valid", "model is not a non-blank string"),
        (123, _DEFAULT_USAGE, None, "valid", "model is not a non-blank string"),
        ("jev-routing", None, "jev-routing", None, "usage is missing"),
        ("jev-routing", object(), "jev-routing", None, "usage is missing"),
        ("", None, "", None, "model is not a non-blank string"),
    ],
    ids=[
        "empty-model",
        "blank-model",
        "non-string-model",
        "missing-usage",
        "wrong-usage-type",
        "model-precedes-usage",
    ],
)
def test_decide_routing_blocks_invalid_metadata_with_normalized_preservation(
    governance_thresholds: GovernanceThresholds,
    model: object,
    usage: object | None,
    expected_model: str | None,
    expected_usage: str | None,
    expected_detail: str,
) -> None:
    routing = _routing_result(confidence=0.9, model=model, usage=usage)

    decision = decide_routing(routing, governance_thresholds)

    assert decision.action is GovernanceAction.BLOCK
    assert decision.reason_codes == ("INVALID_METADATA",)
    assert decision.reasons == (f"INVALID_METADATA: {expected_detail}",)
    assert decision.model == expected_model
    if expected_usage == "valid":
        assert decision.usage is routing.usage
    else:
        assert decision.usage is None
    assert decision.intent == "dispute_charge"
    assert decision.intent_confidence == 0.9
    assert decision.intent_probabilities is routing.intent.probabilities
    assert len(decision.reason_codes) == len(decision.reasons) == 1
