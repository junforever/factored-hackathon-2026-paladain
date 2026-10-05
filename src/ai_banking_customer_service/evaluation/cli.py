"""Public command-line orchestration for offline evaluation."""

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from ai_banking_customer_service.config import PROJECT_ROOT
from ai_banking_customer_service.evaluation.cases import (
    EvalCase,
    EvalConfig,
    load_eval_case_set,
    load_eval_config,
)
from ai_banking_customer_service.evaluation.classification import (
    CaseClassification,
    calculate_metrics,
    calculate_segment_metrics,
    classify_case,
)
from ai_banking_customer_service.evaluation.report import (
    generate_report,
    save_report,
)
from ai_banking_customer_service.evaluation.runner import CaseResult, run_evaluation

_LANGUAGES = ("es", "pt")
_SCENARIOS = (
    "normal_resolution",
    "ambiguous",
    "human_required",
    "attack",
    "missing_data",
    "edge_case",
)


class _UsageError(ValueError):
    pass


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _UsageError(message)


def main(argv: Sequence[str] | None = None) -> int:
    """Run load, validation, execution, classification, metrics, and reporting."""
    try:
        arguments = _parser().parse_args(argv)
        config_path = _project_path(arguments.config)
        config = load_eval_config(config_path)
        if arguments.output_dir is not None:
            config = _override_output_dir(config, arguments.output_dir)

        selected = load_eval_case_set(
            config.held_out_manifest,
            config.development_manifest,
            config,
            arguments.case_set,
        )
        config = config.model_copy(update={"dataset_version": selected.dataset_version})
        cases = selected.cases
        run = run_evaluation(cases, config)
        results = list(run.results)
        classifications = [
            classify_case(case, result)
            for case, result in zip(cases, results, strict=True)
        ]
        metrics = calculate_metrics(cases, classifications, results)
        by_language = _segment_metrics(
            _LANGUAGES,
            cases,
            classifications,
            results,
            lambda case, segment: case.language == segment,
        )
        by_scenario = _segment_metrics(
            _SCENARIOS,
            cases,
            classifications,
            results,
            lambda case, segment: case.scenario == segment,
        )
        report = generate_report(
            run,
            metrics,
            by_language,
            by_scenario,
            classifications,
        )
        paths = save_report(report, config.output_dir)
    except _UsageError:
        print("Evaluation CLI usage error.", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Evaluation failed: {type(error).__name__}", file=sys.stderr)
        return 1

    print(paths.json_path)
    print(paths.markdown_path)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description="Run offline evaluation.")
    parser.add_argument("--config", required=True, help="Evaluation YAML config.")
    parser.add_argument(
        "--case-set",
        required=True,
        choices=("development", "held-out"),
        help="Explicit evaluation case set.",
    )
    parser.add_argument(
        "--output-dir",
        help="Safe project-relative report directory override.",
    )
    return parser


def _project_path(value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError("path must resolve inside the project root")
    return resolved


def _override_output_dir(config: EvalConfig, value: str) -> EvalConfig:
    payload = config.model_dump(mode="json")
    payload["output_dir"] = value
    return EvalConfig.model_validate(payload)


def _segment_metrics(
    segments: Sequence[str],
    cases: list[EvalCase],
    classifications: list[CaseClassification],
    results: list[CaseResult],
    belongs: Callable[[EvalCase, str], bool],
) -> dict:
    calculated = {}
    for segment in segments:
        selected = [
            (case, classification, result)
            for case, classification, result in zip(
                cases, classifications, results, strict=True
            )
            if belongs(case, segment)
        ]
        calculated[segment] = calculate_segment_metrics(
            segment,
            [item[0] for item in selected],
            [item[1] for item in selected],
            [item[2] for item in selected],
        )
    return calculated
