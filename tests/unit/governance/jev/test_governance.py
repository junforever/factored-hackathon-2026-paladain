import math
from dataclasses import FrozenInstanceError
from typing import get_args, get_type_hints

import pytest

from ai_banking_customer_service.config import (
    PROJECT_ROOT,
    GovernancePolicy,
    OutputScreeningPolicy,
    ToolGatingPolicy,
    load_policy,
)
from ai_banking_customer_service.governance.jev.decision import (
    GovernanceAction,
    GovernanceDecision,
    GovernanceStage,
    GovernanceThresholds,
    OutputScreeningThresholds,
    ScreeningThresholds,
    ToolGatingThresholds,
    decide_output_screening,
    decide_routing,
    decide_screening,
    decide_tool_gating,
)
from ai_banking_customer_service.governance.jev.evaluations import (
    EXPECTED_INTENTS,
    InputScreeningResult,
    IntentRoutingResult,
    OutputScreeningResult,
    ToolGatingResult,
)
from ai_banking_customer_service.governance.jev.schemas import (
    ChoiceAnswer,
    NoulAnswer,
    ScoreAnswer,
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
        prompt_injection=NoulAnswer.model_construct(type="noul", noul=prompt_injection),
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
        decide_tool_gating,
        decide_output_screening,
        GovernanceAction,
        GovernanceStage,
        GovernanceDecision,
        GovernanceThresholds,
        OutputScreeningThresholds,
        ScreeningThresholds,
        ToolGatingThresholds,
    ):
        assert symbol.__module__ == expected_module


def test_governance_decision_threshold_type_accepts_all_stage_thresholds() -> None:
    threshold_type = get_type_hints(GovernanceDecision)["governance_thresholds"]

    assert set(get_args(threshold_type)) == {
        GovernanceThresholds,
        ToolGatingThresholds,
        OutputScreeningThresholds,
    }


def test_governance_stage_includes_tool_and_output_stages() -> None:
    assert GovernanceStage.TOOL_GATING == "tool_gating"
    assert GovernanceStage.OUTPUT_SCREENING == "output_screening"
    assert GovernanceStage.INPUT_SCREENING == "input_screening"
    assert GovernanceStage.INTENT_ROUTING == "intent_routing"


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


@pytest.mark.parametrize(
    "value",
    [-0.01, 1.01, float("nan"), float("inf")],
    ids=["below-zero", "above-one", "nan", "infinity"],
)
def test_tool_gating_thresholds_reject_invalid_values(value: float) -> None:
    with pytest.raises(ValueError):
        ToolGatingThresholds(min_intent_matches_tool=value)


def test_tool_gating_thresholds_from_policy_maps_configured_value() -> None:
    policy = ToolGatingPolicy(min_intent_matches_tool=0.7)

    thresholds = ToolGatingThresholds.from_policy(policy)

    assert thresholds == ToolGatingThresholds(min_intent_matches_tool=0.7)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_output_safety_score", -0.01),
        ("min_output_safety_score", 2.01),
        ("min_output_safety_score", float("nan")),
        ("min_output_safety_score", float("inf")),
        ("min_output_safety_confidence", -0.01),
        ("min_output_safety_confidence", 1.01),
        ("min_output_safety_confidence", float("nan")),
        ("min_output_safety_confidence", float("inf")),
    ],
)
def test_output_screening_thresholds_reject_invalid_values(
    field: str,
    value: float,
) -> None:
    values = {
        "min_output_safety_score": 1.5,
        "min_output_safety_confidence": 0.5,
    }
    values[field] = value

    with pytest.raises(ValueError):
        OutputScreeningThresholds(**values)


def test_output_screening_thresholds_from_policy_maps_configured_values() -> None:
    policy = OutputScreeningPolicy(
        min_output_safety_score=1.5,
        min_output_safety_confidence=0.5,
    )

    thresholds = OutputScreeningThresholds.from_policy(policy)

    assert thresholds == OutputScreeningThresholds(
        min_output_safety_score=1.5,
        min_output_safety_confidence=0.5,
    )


@pytest.mark.parametrize("value", [0.0, 1.0], ids=["lower", "upper"])
def test_tool_gating_threshold_mapper_accepts_boundaries(value: float) -> None:
    policy = ToolGatingPolicy(min_intent_matches_tool=value)

    assert ToolGatingThresholds.from_policy(policy) == ToolGatingThresholds(value)


@pytest.mark.parametrize(
    ("score", "confidence"),
    [(0.0, 0.0), (2.0, 1.0)],
    ids=["lower", "upper"],
)
def test_output_screening_threshold_mapper_accepts_boundaries(
    score: float,
    confidence: float,
) -> None:
    policy = OutputScreeningPolicy(
        min_output_safety_score=score,
        min_output_safety_confidence=confidence,
    )

    assert OutputScreeningThresholds.from_policy(policy) == OutputScreeningThresholds(
        score, confidence
    )


@pytest.mark.parametrize(
    "threshold_type",
    [ToolGatingThresholds, OutputScreeningThresholds],
)
def test_new_threshold_mappers_reject_none_explicitly(threshold_type: type) -> None:
    with pytest.raises(ValueError, match="policy no puede ser None"):
        threshold_type.from_policy(None)


def test_new_threshold_dataclasses_are_frozen() -> None:
    tool_thresholds = ToolGatingThresholds(0.7)
    output_thresholds = OutputScreeningThresholds(1.5, 0.5)

    with pytest.raises(FrozenInstanceError):
        tool_thresholds.min_intent_matches_tool = 0.8
    with pytest.raises(FrozenInstanceError):
        output_thresholds.min_output_safety_score = 1.6


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


def _tool_gating_result(
    noul: float = 0.7,
    *,
    deterministic_block: bool = False,
    deterministic_reason: str = "",
    model: object = "jev-tool-gating",
    usage: object | None = _DEFAULT_USAGE,
) -> ToolGatingResult:
    return ToolGatingResult(
        deterministic_block=deterministic_block,
        deterministic_reason=deterministic_reason,
        intent_matches_tool=(
            None
            if deterministic_block
            else NoulAnswer.model_construct(type="noul", noul=noul)
        ),
        model=None if deterministic_block else model,
        usage=(
            None
            if deterministic_block
            else Usage(input_tokens=13, output_tokens=1)
            if usage is _DEFAULT_USAGE
            else usage
        ),
    )


def _output_screening_result(
    *,
    score: float = 1.5,
    confidence: float = 0.5,
    legend: dict[int, object] | None = None,
    probabilities: dict[int, float] | None = None,
    secrets_detected: tuple[str, ...] = (),
    model: object = "jev-output-screening",
    usage: object | None = _DEFAULT_USAGE,
) -> OutputScreeningResult:
    return OutputScreeningResult(
        secrets_detected=secrets_detected,
        secrets_sanitized_response=("[REDACTED]" if secrets_detected else None),
        output_safety_semantic=(
            None
            if secrets_detected
            else ScoreAnswer.model_construct(
                type="score",
                score=score,
                legend=(
                    {0: "unsafe", 1: "risky", 2: "safe"} if legend is None else legend
                ),
                probabilities=(
                    {0: 0.0, 1: 0.5, 2: 0.5} if probabilities is None else probabilities
                ),
                confidence=confidence,
            )
        ),
        model=None if secrets_detected else model,
        usage=(
            None
            if secrets_detected
            else Usage(input_tokens=19, output_tokens=4)
            if usage is _DEFAULT_USAGE
            else usage
        ),
    )


def test_decide_output_screening_reviews_detected_secrets() -> None:
    thresholds = OutputScreeningThresholds(1.5, 0.5)
    screening = _output_screening_result(
        secrets_detected=("PAN", "CVV"),
    )

    decision = decide_output_screening(screening, thresholds)

    assert decision.action is GovernanceAction.REVIEW
    assert decision.stage is GovernanceStage.OUTPUT_SCREENING
    assert decision.reason_codes == ("OUTPUT_SCREENING_SECRETS_DETECTED",)
    assert decision.reasons == (
        "OUTPUT_SCREENING_SECRETS_DETECTED: secrets_detected=('PAN', 'CVV')",
    )
    assert decision.model is None
    assert decision.usage is None
    assert decision.governance_thresholds is thresholds
    assert decision.output_safety_semantic is None
    assert decision.action is not GovernanceAction.BLOCK


def test_decide_output_screening_reviews_invalid_model() -> None:
    decision = decide_output_screening(
        _output_screening_result(model=""),
        OutputScreeningThresholds(1.5, 0.5),
    )

    assert decision.action is GovernanceAction.REVIEW
    assert decision.reason_codes == ("INVALID_METADATA",)
    assert decision.reasons == ("INVALID_METADATA: model is invalid",)


def test_decide_output_screening_reviews_invalid_usage() -> None:
    decision = decide_output_screening(
        _output_screening_result(usage=object()),
        OutputScreeningThresholds(1.5, 0.5),
    )

    assert decision.action is GovernanceAction.REVIEW
    assert decision.reason_codes == ("INVALID_METADATA",)
    assert decision.reasons == ("INVALID_METADATA: usage is invalid",)


@pytest.mark.parametrize(
    "score",
    [float("nan"), float("inf"), float("-inf"), -0.01, 2.01],
    ids=["nan", "positive-infinity", "negative-infinity", "below-zero", "above-two"],
)
def test_decide_output_screening_reviews_invalid_score_without_raising(
    score: float,
) -> None:
    decision = decide_output_screening(
        _output_screening_result(score=score),
        OutputScreeningThresholds(1.5, 0.5),
    )

    assert decision.action is GovernanceAction.REVIEW
    assert decision.reason_codes == ("INVALID_SIGNAL",)
    assert decision.reasons == ("INVALID_SIGNAL: score failed validation",)


@pytest.mark.parametrize(
    "legend",
    [{0: "unsafe", 1: "risky"}, {0: "unsafe", 1: "risky", 2: "safe", 3: "extra"}],
    ids=["missing-level", "extra-level"],
)
def test_decide_output_screening_reviews_invalid_legend_domain(
    legend: dict[int, object],
) -> None:
    decision = decide_output_screening(
        _output_screening_result(legend=legend),
        OutputScreeningThresholds(1.5, 0.5),
    )

    assert decision.action is GovernanceAction.REVIEW
    assert decision.reasons == ("INVALID_SIGNAL: legend_domain failed validation",)


@pytest.mark.parametrize(
    "probabilities",
    [{0: 0.5, 1: 0.5}, {0: 0.0, 1: 0.5, 2: 0.5, 3: 0.0}],
    ids=["missing-level", "extra-level"],
)
def test_decide_output_screening_reviews_invalid_probabilities_domain(
    probabilities: dict[int, float],
) -> None:
    decision = decide_output_screening(
        _output_screening_result(probabilities=probabilities),
        OutputScreeningThresholds(1.5, 0.5),
    )

    assert decision.action is GovernanceAction.REVIEW
    assert decision.reasons == (
        "INVALID_SIGNAL: probabilities_domain failed validation",
    )


@pytest.mark.parametrize(
    "invalid_probability",
    [float("nan"), float("inf"), float("-inf"), -0.01, 1.01],
    ids=["nan", "positive-infinity", "negative-infinity", "negative", "above-one"],
)
def test_decide_output_screening_reviews_invalid_probability_values(
    invalid_probability: float,
) -> None:
    decision = decide_output_screening(
        _output_screening_result(
            probabilities={0: invalid_probability, 1: 0.5, 2: 0.5},
        ),
        OutputScreeningThresholds(1.5, 0.5),
    )

    assert decision.action is GovernanceAction.REVIEW
    assert decision.reasons == ("INVALID_SIGNAL: probability_values failed validation",)


def test_decide_output_screening_reviews_invalid_probability_sum() -> None:
    decision = decide_output_screening(
        _output_screening_result(probabilities={0: 0.0, 1: 0.5, 2: 0.499998}),
        OutputScreeningThresholds(1.5, 0.5),
    )

    assert decision.action is GovernanceAction.REVIEW
    assert decision.reasons == ("INVALID_SIGNAL: probability_sum failed validation",)


def test_decide_output_screening_reviews_incoherent_weighted_score() -> None:
    decision = decide_output_screening(
        _output_screening_result(score=1.39),
        OutputScreeningThresholds(1.0, 0.5),
    )

    assert decision.action is GovernanceAction.REVIEW
    assert decision.reasons == ("INVALID_SIGNAL: weighted_score failed validation",)


@pytest.mark.parametrize(
    "confidence",
    [float("nan"), float("inf"), float("-inf"), -0.01, 1.01],
    ids=["nan", "positive-infinity", "negative-infinity", "below-zero", "above-one"],
)
def test_decide_output_screening_reviews_invalid_confidence_without_raising(
    confidence: float,
) -> None:
    decision = decide_output_screening(
        _output_screening_result(confidence=confidence),
        OutputScreeningThresholds(1.5, 0.5),
    )

    assert decision.action is GovernanceAction.REVIEW
    assert decision.reasons == ("INVALID_SIGNAL: confidence failed validation",)


def test_decide_output_screening_reviews_low_confidence_before_low_score() -> None:
    confidence = 0.49900000000000005
    threshold = 0.5

    decision = decide_output_screening(
        _output_screening_result(
            score=1.0,
            confidence=confidence,
            probabilities={0: 0.0, 1: 1.0, 2: 0.0},
        ),
        OutputScreeningThresholds(1.5, threshold),
    )

    assert decision.action is GovernanceAction.REVIEW
    assert decision.reason_codes == ("OUTPUT_SCREENING_REVIEW_LOW_CONFIDENCE",)
    assert decision.reasons == (
        "OUTPUT_SCREENING_REVIEW_LOW_CONFIDENCE: "
        f"confidence={repr(float(confidence))} "
        f"< min_output_safety_confidence={repr(float(threshold))}",
    )


def test_decide_output_screening_reviews_low_score() -> None:
    score = 0.9990000000000001
    threshold = 1.0

    decision = decide_output_screening(
        _output_screening_result(
            score=score,
            confidence=0.8,
            probabilities={0: 0.0, 1: 1.0, 2: 0.0},
        ),
        OutputScreeningThresholds(threshold, 0.5),
    )

    assert decision.action is GovernanceAction.REVIEW
    assert decision.reason_codes == ("OUTPUT_SCREENING_REVIEW_LOW_SCORE",)
    assert decision.reasons == (
        "OUTPUT_SCREENING_REVIEW_LOW_SCORE: "
        f"output_safety_score={repr(float(score))} "
        f"< min_output_safety_score={repr(float(threshold))}",
    )


def test_decide_output_screening_allows_boundary_and_preserves_raw_answer() -> None:
    thresholds = OutputScreeningThresholds(1.5, 0.5)
    screening = _output_screening_result(score=1.5, confidence=0.5)

    decision = decide_output_screening(screening, thresholds)

    assert decision.action is GovernanceAction.ALLOW
    assert decision.stage is GovernanceStage.OUTPUT_SCREENING
    assert decision.reason_codes == ("OUTPUT_SCREENING_ALLOW",)
    assert decision.reasons == (
        "OUTPUT_SCREENING_ALLOW: output_safety_score=1.5 "
        ">= min_output_safety_score=1.5 and confidence=0.5 "
        ">= min_output_safety_confidence=0.5",
    )
    assert decision.model == screening.model
    assert decision.usage is screening.usage
    assert decision.governance_thresholds is thresholds
    assert decision.output_safety_semantic is screening.output_safety_semantic
    assert decision.action is not GovernanceAction.BLOCK
    assert len(decision.reason_codes) == len(decision.reasons) == 1


@pytest.mark.parametrize(
    ("score", "confidence", "probabilities"),
    [
        (0.0, 0.0, {0: 1.0, 1: 0.0, 2: 0.0}),
        (2.0, 1.0, {0: 0.0, 1: 0.0, 2: 1.0}),
    ],
    ids=["lower", "upper"],
)
def test_decide_output_screening_accepts_score_confidence_and_threshold_boundaries(
    score: float,
    confidence: float,
    probabilities: dict[int, float],
) -> None:
    decision = decide_output_screening(
        _output_screening_result(
            score=score,
            confidence=confidence,
            probabilities=probabilities,
        ),
        OutputScreeningThresholds(score, confidence),
    )

    assert decision.action is GovernanceAction.ALLOW
    assert decision.action is not GovernanceAction.BLOCK


def test_decide_output_screening_accepts_probability_tolerances() -> None:
    probability_sum_tolerance = decide_output_screening(
        _output_screening_result(
            probabilities={0: 0.0, 1: 0.5, 2: 0.4999995},
        ),
        OutputScreeningThresholds(1.5, 0.5),
    )
    weighted_score_tolerance = decide_output_screening(
        _output_screening_result(score=1.400001),
        OutputScreeningThresholds(1.4, 0.5),
    )

    assert probability_sum_tolerance.action is GovernanceAction.ALLOW
    assert weighted_score_tolerance.action is GovernanceAction.ALLOW


def test_decide_output_screening_uses_required_invalid_field_precedence() -> None:
    thresholds = OutputScreeningThresholds(1.5, 0.5)
    cases = (
        (
            _output_screening_result(
                score=float("nan"),
                secrets_detected=("PAN",),
            ),
            "secrets_detected=('PAN',)",
        ),
        (
            _output_screening_result(
                score=float("nan"),
                model="",
                usage=object(),
            ),
            "model is invalid",
        ),
        (
            _output_screening_result(score=float("nan"), usage=object()),
            "usage is invalid",
        ),
        (
            _output_screening_result(
                score=float("nan"),
                legend={0: "unsafe"},
                probabilities={0: float("nan")},
                confidence=float("nan"),
            ),
            "score failed validation",
        ),
        (
            _output_screening_result(
                legend={0: "unsafe"},
                probabilities={0: float("nan")},
                confidence=float("nan"),
            ),
            "legend_domain failed validation",
        ),
        (
            _output_screening_result(
                probabilities={0: float("nan"), 1: 0.5},
                confidence=float("nan"),
            ),
            "probabilities_domain failed validation",
        ),
        (
            _output_screening_result(
                probabilities={0: float("nan"), 1: 0.5, 2: 0.5},
                confidence=float("nan"),
            ),
            "probability_values failed validation",
        ),
        (
            _output_screening_result(
                probabilities={0: 0.0, 1: 0.5, 2: 0.499},
                confidence=float("nan"),
            ),
            "probability_sum failed validation",
        ),
        (
            _output_screening_result(score=1.3, confidence=float("nan")),
            "weighted_score failed validation",
        ),
        (
            _output_screening_result(confidence=float("nan")),
            "confidence failed validation",
        ),
    )

    decisions = [
        decide_output_screening(screening, thresholds) for screening, _ in cases
    ]

    assert [decision.reasons[0].partition(": ")[2] for decision in decisions] == [
        detail for _, detail in cases
    ]


def test_decide_tool_gating_blocks_deterministic_failure() -> None:
    thresholds = ToolGatingThresholds(min_intent_matches_tool=0.7)
    gating = _tool_gating_result(
        deterministic_block=True,
        deterministic_reason="confirmation_required",
    )

    decision = decide_tool_gating(gating, thresholds)

    assert decision.action is GovernanceAction.BLOCK
    assert decision.stage is GovernanceStage.TOOL_GATING
    assert decision.reason_codes == ("TOOL_GATING_DETERMINISTIC_BLOCK",)
    assert decision.reasons == (
        "TOOL_GATING_DETERMINISTIC_BLOCK: confirmation_required",
    )
    assert decision.model is None
    assert decision.usage is None
    assert decision.governance_thresholds is thresholds


@pytest.mark.parametrize("model", [None, "", "   ", 123])
def test_decide_tool_gating_blocks_invalid_or_missing_model(model: object) -> None:
    decision = decide_tool_gating(
        _tool_gating_result(model=model),
        ToolGatingThresholds(min_intent_matches_tool=0.7),
    )

    assert decision.action is GovernanceAction.BLOCK
    assert decision.reason_codes == ("INVALID_METADATA",)
    assert decision.reasons == ("INVALID_METADATA: model is invalid",)


@pytest.mark.parametrize("usage", [None, object()])
def test_decide_tool_gating_blocks_invalid_or_missing_usage(usage: object) -> None:
    decision = decide_tool_gating(
        _tool_gating_result(usage=usage),
        ToolGatingThresholds(min_intent_matches_tool=0.7),
    )

    assert decision.action is GovernanceAction.BLOCK
    assert decision.reason_codes == ("INVALID_METADATA",)
    assert decision.reasons == ("INVALID_METADATA: usage is invalid",)


@pytest.mark.parametrize(
    "noul",
    [float("nan"), float("inf"), float("-inf"), -0.01, 1.01],
    ids=["nan", "positive-infinity", "negative-infinity", "below-zero", "above-one"],
)
def test_decide_tool_gating_blocks_invalid_noul_without_raising(noul: float) -> None:
    decision = decide_tool_gating(
        _tool_gating_result(noul),
        ToolGatingThresholds(min_intent_matches_tool=0.7),
    )

    assert decision.action is GovernanceAction.BLOCK
    assert decision.reason_codes == ("INVALID_SIGNAL",)
    assert decision.reasons == (
        "INVALID_SIGNAL: intent_matches_tool.noul failed validation",
    )


def test_decide_tool_gating_allows_boundary_and_preserves_raw_answer() -> None:
    thresholds = ToolGatingThresholds(min_intent_matches_tool=0.7)
    gating = _tool_gating_result(0.7)

    decision = decide_tool_gating(gating, thresholds)

    assert decision.action is GovernanceAction.ALLOW
    assert decision.stage is GovernanceStage.TOOL_GATING
    assert decision.reason_codes == ("TOOL_GATING_ALLOW",)
    assert decision.reasons == (
        "TOOL_GATING_ALLOW: intent_matches_tool=0.7 >= min_intent_matches_tool=0.7",
    )
    assert decision.model == gating.model
    assert decision.usage is gating.usage
    assert decision.governance_thresholds is thresholds
    assert decision.intent_matches_tool is gating.intent_matches_tool
    assert len(decision.reason_codes) == len(decision.reasons) == 1


def test_decide_tool_gating_blocks_low_intent_match_with_float_repr() -> None:
    probability = 0.6990000000000001
    threshold = 0.7

    decision = decide_tool_gating(
        _tool_gating_result(probability),
        ToolGatingThresholds(min_intent_matches_tool=threshold),
    )

    assert decision.action is GovernanceAction.BLOCK
    assert decision.reason_codes == ("TOOL_GATING_BLOCK_LOW_INTENT_MATCH",)
    assert decision.reasons == (
        "TOOL_GATING_BLOCK_LOW_INTENT_MATCH: "
        f"intent_matches_tool={repr(float(probability))} "
        f"< min_intent_matches_tool={repr(float(threshold))}",
    )
    assert decision.action is not GovernanceAction.REVIEW


@pytest.mark.parametrize(
    ("probability", "expected_action"),
    [
        (0.65, GovernanceAction.ALLOW),
        (math.nextafter(0.65, 0.0), GovernanceAction.BLOCK),
    ],
    ids=["at-calibrated-boundary", "below-calibrated-boundary"],
)
def test_project_policy_applies_calibrated_tool_gating_boundary(
    probability: float,
    expected_action: GovernanceAction,
) -> None:
    configured = load_policy(PROJECT_ROOT / "configs" / "policy.yaml")
    thresholds = ToolGatingThresholds.from_policy(configured.tool_gating)

    decision = decide_tool_gating(_tool_gating_result(probability), thresholds)

    assert thresholds.min_intent_matches_tool == 0.65
    assert decision.action is expected_action


@pytest.mark.parametrize("boundary", [0.0, 1.0], ids=["lower", "upper"])
def test_decide_tool_gating_accepts_noul_and_threshold_boundaries(
    boundary: float,
) -> None:
    decision = decide_tool_gating(
        _tool_gating_result(boundary),
        ToolGatingThresholds(min_intent_matches_tool=boundary),
    )

    assert decision.action is GovernanceAction.ALLOW
    assert decision.action is not GovernanceAction.REVIEW


def test_decide_tool_gating_uses_required_precedence() -> None:
    thresholds = ToolGatingThresholds(min_intent_matches_tool=0.7)

    deterministic = decide_tool_gating(
        ToolGatingResult(
            deterministic_block=True,
            deterministic_reason="confirmation_required",
            intent_matches_tool=NoulAnswer.model_construct(noul=float("nan")),
            model="",
            usage=object(),
        ),
        thresholds,
    )
    invalid_model = decide_tool_gating(
        _tool_gating_result(float("nan"), model="", usage=object()),
        thresholds,
    )
    invalid_usage = decide_tool_gating(
        _tool_gating_result(float("nan"), usage=object()),
        thresholds,
    )

    assert deterministic.reason_codes == ("TOOL_GATING_DETERMINISTIC_BLOCK",)
    assert invalid_model.reasons == ("INVALID_METADATA: model is invalid",)
    assert invalid_usage.reasons == ("INVALID_METADATA: usage is invalid",)


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


@pytest.mark.parametrize(
    ("confidence", "expected_action"),
    [(0.35, GovernanceAction.ALLOW), (0.349, GovernanceAction.REVIEW)],
    ids=["at-calibrated-boundary", "below-calibrated-boundary"],
)
def test_project_policy_applies_calibrated_routing_boundary(
    confidence: float,
    expected_action: GovernanceAction,
) -> None:
    configured = load_policy(PROJECT_ROOT / "configs" / "policy.yaml")
    thresholds = GovernanceThresholds.from_policy(configured.governance)

    decision = decide_routing(_routing_result(confidence=confidence), thresholds)

    assert thresholds.min_intent_confidence == 0.35
    assert decision.action is expected_action


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
