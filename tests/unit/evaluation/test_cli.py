"""Behavior tests for the public offline-evaluation CLI boundary."""

import runpy
import sys
from pathlib import Path

import pytest

from ai_banking_customer_service.config import PROJECT_ROOT
from ai_banking_customer_service.evaluation.cases import (
    EvalCase,
    LoadedCaseSet,
    load_eval_config,
)
from ai_banking_customer_service.evaluation.cli import main
from ai_banking_customer_service.evaluation.report import ReportPaths
from ai_banking_customer_service.evaluation.runner import (
    CaseExecutionStatus,
    CaseResult,
    EvalRun,
)


def _case(case_id: str, language: str, scenario: str) -> EvalCase:
    return EvalCase.model_validate(
        {
            "case_id": case_id,
            "language": language,
            "scenario": scenario,
            "customer_message": "Evaluation message",
            "expected": {
                "intent": None,
                "action": "respond",
                "is_automatable": True,
                "requires_escalation": False,
                "expected_tools": [],
                "expected_escalation_type": None,
                "complaint_id": None,
                "customer_confirmed_block": False,
                "authorization": {
                    "authenticated": True,
                    "product_authorized": True,
                },
                "forbidden_actions": [],
                "response_required_substrings": [],
                "response_forbidden_substrings": [],
                "sensitive_output_forbidden_substrings": [],
            },
            "metadata": {"segment": "Retail", "notes": "CLI fake"},
        }
    )


def _run(case_ids: list[str], dataset_version: str = "1.0.0") -> EvalRun:
    return EvalRun(
        pipeline_version="3.0.0",
        dataset_version=dataset_version,
        timestamp="2026-10-02T12:00:00+00:00",
        timestamp_fs="20261002T120000Z",
        configured_openai_model="fake-openai",
        configured_jev_model="fake-jev",
        dependencies_lock_hash="a" * 64,
        results=tuple(
            CaseResult(case_id, CaseExecutionStatus.ERROR, None, "fake", 1)
            for case_id in case_ids
        ),
        total_duration_seconds=0.1,
    )


def test_cli_orchestrates_canonical_pipeline_with_output_override_and_fakes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[object] = []
    cases = [
        _case("ES-1", "es", "normal_resolution"),
        _case("PT-1", "pt", "attack"),
    ]
    config = load_eval_config(PROJECT_ROOT / "configs" / "eval.yaml")
    classifications = {case.case_id: object() for case in cases}

    def fake_load_config(path: Path):
        calls.append(("load_config", path))
        return config

    def fake_load_cases(held: Path, development: Path, received_config, case_set: str):
        calls.append(
            (
                "load_cases",
                held,
                development,
                received_config.output_dir,
                case_set,
            )
        )
        return LoadedCaseSet(cases, "development-1.0.5")

    def fake_run(received_cases, received_config):
        calls.append(("run", [case.case_id for case in received_cases]))
        assert received_config.output_dir == PROJECT_ROOT / "evals/reports/override"
        assert received_config.dataset_version == "development-1.0.5"
        return _run(
            [case.case_id for case in received_cases],
            received_config.dataset_version,
        )

    def fake_classify(case, result):
        calls.append(("classify", case.case_id, result.case_id))
        return classifications[case.case_id]

    def fake_metrics(received_cases, received_classifications, received_results):
        calls.append(("metrics", [case.case_id for case in received_cases]))
        assert received_classifications == [
            classifications["ES-1"],
            classifications["PT-1"],
        ]
        assert [result.case_id for result in received_results] == ["ES-1", "PT-1"]
        return "global-metrics"

    def fake_segment(
        segment, received_cases, received_classifications, received_results
    ):
        case_ids = [case.case_id for case in received_cases]
        assert [item.case_id for item in received_results] == case_ids
        assert len(received_classifications) == len(case_ids)
        calls.append(("segment", segment, case_ids))
        return f"segment:{segment}:{','.join(case_ids)}"

    def fake_generate(
        received_run, metrics, by_language, by_scenario, received_classifications
    ):
        calls.append("generate")
        assert received_run.dataset_version == "development-1.0.5"
        assert metrics == "global-metrics"
        assert by_language == {
            "es": "segment:es:ES-1",
            "pt": "segment:pt:PT-1",
        }
        assert by_scenario["normal_resolution"] == "segment:normal_resolution:ES-1"
        assert by_scenario["attack"] == "segment:attack:PT-1"
        assert by_scenario["missing_data"] == "segment:missing_data:"
        assert received_classifications == [
            classifications["ES-1"],
            classifications["PT-1"],
        ]
        return {"same": "report"}

    def fake_save(report, output_dir: Path):
        calls.append(("save", report, output_dir))
        return ReportPaths(output_dir / "report.json", output_dir / "report.md")

    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.cli.load_eval_config", fake_load_config
    )
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.cli.load_eval_case_set",
        fake_load_cases,
    )
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.cli.run_evaluation", fake_run
    )
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.cli.classify_case", fake_classify
    )
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.cli.calculate_metrics", fake_metrics
    )
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.cli.calculate_segment_metrics",
        fake_segment,
    )
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.cli.generate_report", fake_generate
    )
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.cli.save_report", fake_save
    )

    exit_code = main(
        [
            "--config",
            "configs/eval.yaml",
            "--output-dir",
            "evals/reports/override",
            "--case-set",
            "development",
        ]
    )

    captured = capsys.readouterr()
    output_dir = PROJECT_ROOT / "evals/reports/override"
    assert exit_code == 0
    assert captured.out.splitlines() == [
        str(output_dir / "report.json"),
        str(output_dir / "report.md"),
    ]
    assert captured.err == ""
    assert calls[0] == ("load_config", PROJECT_ROOT / "configs/eval.yaml")
    assert calls[1][-1] == "development"
    assert calls[-1] == ("save", {"same": "report"}, output_dir)


def test_cli_error_exit_is_nonzero_and_does_not_expose_paths_or_secrets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_config(_path: Path):
        raise ValueError("D:/private/.env password=hunter2")

    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.cli.load_eval_config", fail_config
    )

    exit_code = main(["--config", "configs/eval.yaml", "--case-set", "development"])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert captured.out == ""
    assert "private" not in captured.err
    assert "hunter2" not in captured.err
    assert ".env" not in captured.err


def test_cli_rejects_unsafe_output_override_before_run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = load_eval_config(PROJECT_ROOT / "configs" / "eval.yaml")
    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.cli.load_eval_config",
        lambda _path: config,
    )
    run_called = False

    def fail_if_run(*_args):
        nonlocal run_called
        run_called = True
        raise AssertionError("must not run")

    monkeypatch.setattr(
        "ai_banking_customer_service.evaluation.cli.run_evaluation", fail_if_run
    )

    exit_code = main(
        [
            "--config",
            "configs/eval.yaml",
            "--output-dir",
            "../escape",
            "--case-set",
            "development",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert run_called is False
    assert "escape" not in captured.err


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--config", "configs/eval.yaml"],
        [
            "--config",
            "configs/eval.yaml",
            "--case-set",
            "not-a-case-set",
        ],
    ],
)
def test_cli_usage_errors_return_nonzero_without_raising(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv) != 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err


def test_module_entrypoint_delegates_canonical_argv_to_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ai_banking_customer_service.evaluation.cli as cli

    observed: list[object] = []
    monkeypatch.setattr(cli, "main", lambda argv=None: observed.append(argv) or 0)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ai_banking_customer_service.evaluation",
            "--config",
            "configs/eval.yaml",
            "--case-set",
            "development",
        ],
    )

    with pytest.raises(SystemExit) as raised:
        runpy.run_module(
            "ai_banking_customer_service.evaluation.__main__", run_name="__main__"
        )

    assert raised.value.code == 0
    assert observed == [None]
