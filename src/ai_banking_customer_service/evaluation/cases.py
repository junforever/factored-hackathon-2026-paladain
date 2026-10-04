"""Typed configuration, case identity, coverage, and leakage validation."""

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    field_validator,
    model_validator,
)

from ai_banking_customer_service.agent.orchestrator import EscalationType, TurnAction
from ai_banking_customer_service.agent.tools import REGISTERED_TOOLS
from ai_banking_customer_service.config import PROJECT_ROOT, settings

_MAX_RESULT_BYTES = 16 * 1024 * 1024
MAX_CASE_ID_LENGTH = 128
_CANONICAL_OVERSIZE_ERROR = "result_envelope_too_large"
# A JSON control character has the largest possible encoding (``\u0000``): six
# bytes per code point. This computes the largest canonical bounded error envelope.
MIN_RESULT_BYTES = len(
    json.dumps(
        {
            "schema_version": 1,
            "case_id": "\x00" * MAX_CASE_ID_LENGTH,
            "status": "error",
            "error": _CANONICAL_OVERSIZE_ERROR,
            "observation": None,
        },
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
)
_SCENARIOS = (
    "normal_resolution",
    "ambiguous",
    "human_required",
    "attack",
    "missing_data",
    "edge_case",
)
Scenario = Literal[
    "normal_resolution",
    "ambiguous",
    "human_required",
    "attack",
    "missing_data",
    "edge_case",
]
Language = Literal["es", "pt"]
_REGISTERED_TOOL_NAMES = frozenset(tool.tool_name for tool in REGISTERED_TOOLS)
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_RUNTIME_SANDBOX_PATH = settings.sandbox_full_path


def _nonempty_string(value: object) -> object:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must be a non-empty string")
    return value


def _project_path(value: object) -> Path:
    _nonempty_string(value)
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError("path must resolve inside the project root")
    return resolved


def _strict_nonnegative_integer(value: object) -> object:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("must be a non-negative integer")
    return value


def _strict_positive_integer(value: object) -> object:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("must be a positive integer")
    return value


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MinimumCoverage(_StrictModel):
    total_cases: int
    min_portuguese_cases: int
    min_cases_per_scenario: int

    @field_validator(
        "total_cases",
        "min_portuguese_cases",
        "min_cases_per_scenario",
        mode="before",
    )
    @classmethod
    def _positive_integer(cls, value: object) -> object:
        return _strict_positive_integer(value)


class EvalConfig(_StrictModel):
    pipeline_version: str
    dataset_version: str
    held_out_manifest: Path
    development_manifest: Path
    sandbox_file: Path
    sandbox_sha256: str
    output_dir: Path
    baseline: Literal["all_human"]
    case_timeout_seconds: float
    grace_period_seconds: float
    max_result_bytes: int
    min_coverage: MinimumCoverage

    @field_validator("pipeline_version", "dataset_version", mode="before")
    @classmethod
    def _versions_are_nonempty(cls, value: object) -> object:
        return _nonempty_string(value)

    @field_validator(
        "held_out_manifest",
        "development_manifest",
        "sandbox_file",
        "output_dir",
        mode="before",
    )
    @classmethod
    def _paths_stay_in_project(cls, value: object) -> Path:
        return _project_path(value)

    @field_validator("sandbox_sha256", mode="before")
    @classmethod
    def _sandbox_sha256_is_hex(cls, value: object) -> object:
        return _validate_sha256(value)

    @field_validator("case_timeout_seconds", "grace_period_seconds", mode="before")
    @classmethod
    def _duration_is_numeric(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("must be a finite number")
        return value

    @field_validator("case_timeout_seconds")
    @classmethod
    def _timeout_is_positive(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("must be a finite number greater than zero")
        return value

    @field_validator("grace_period_seconds")
    @classmethod
    def _grace_is_nonnegative(cls, value: float) -> float:
        if not math.isfinite(value) or value < 0:
            raise ValueError("must be a finite non-negative number")
        return value

    @field_validator("max_result_bytes", mode="before")
    @classmethod
    def _result_limit_is_bounded(cls, value: object) -> object:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < MIN_RESULT_BYTES
            or value > _MAX_RESULT_BYTES
        ):
            raise ValueError(
                "must fit the canonical error envelope: "
                f"an integer from {MIN_RESULT_BYTES} through 16777216"
            )
        return value


class EvalManifest(_StrictModel):
    """Identity fields shared by held-out and development manifests."""

    dataset_version: str
    cases_file: Path
    sha256: str
    sandbox_sha256: str
    frozen_at: str
    owner: str
    total_cases: int

    @field_validator("dataset_version", "frozen_at", "owner", mode="before")
    @classmethod
    def _identity_strings_are_nonempty(cls, value: object) -> object:
        return _nonempty_string(value)

    @field_validator("cases_file", mode="before")
    @classmethod
    def _cases_file_stays_in_project(cls, value: object) -> Path:
        return _project_path(value)

    @field_validator("sha256", "sandbox_sha256", mode="before")
    @classmethod
    def _sha256_is_hex(cls, value: object) -> object:
        return _validate_sha256(value)

    @field_validator("total_cases", mode="before")
    @classmethod
    def _total_is_positive(cls, value: object) -> object:
        return _strict_positive_integer(value)


class _ManifestCoverage(_StrictModel):
    total_cases: int
    portuguese_cases: int
    cases_per_scenario: dict[str, int]

    @field_validator("total_cases", "portuguese_cases", mode="before")
    @classmethod
    def _counts_are_nonnegative(cls, value: object) -> object:
        return _strict_nonnegative_integer(value)

    @field_validator("cases_per_scenario", mode="before")
    @classmethod
    def _scenario_counts_are_exact(cls, value: object) -> object:
        if not isinstance(value, dict) or set(value) != set(_SCENARIOS):
            raise ValueError("cases_per_scenario must contain exactly six scenarios")
        for count in value.values():
            _strict_nonnegative_integer(count)
        return value


class _HeldOutManifest(EvalManifest):
    pipeline_version: str
    coverage: _ManifestCoverage

    @field_validator("pipeline_version", mode="before")
    @classmethod
    def _pipeline_version_is_nonempty(cls, value: object) -> object:
        return _nonempty_string(value)


class _ExpectedOutcome(_StrictModel):
    intent: str | None
    action: TurnAction
    is_automatable: StrictBool
    requires_escalation: StrictBool
    expected_tools: list[str]
    expected_escalation_type: EscalationType | None
    complaint_id: str | None
    customer_confirmed_block: StrictBool
    forbidden_actions: list[TurnAction]
    response_required_substrings: list[str]
    response_forbidden_substrings: list[str]
    sensitive_output_forbidden_substrings: list[str]

    @field_validator("intent", "complaint_id", mode="before")
    @classmethod
    def _nullable_strings_are_nonempty(cls, value: object) -> object:
        if value is None:
            return value
        return _nonempty_string(value)

    @field_validator("expected_tools")
    @classmethod
    def _tools_are_registered(cls, value: list[str]) -> list[str]:
        unknown = set(value) - _REGISTERED_TOOL_NAMES
        if unknown:
            names = sorted(unknown)
            raise ValueError(f"expected_tools contains unknown names: {names}")
        return value

    @field_validator("forbidden_actions")
    @classmethod
    def _forbidden_actions_are_unique(cls, value: list[TurnAction]) -> list[TurnAction]:
        if len(value) != len(set(value)):
            raise ValueError("forbidden_actions must not contain duplicates")
        return value

    @field_validator(
        "response_required_substrings",
        "response_forbidden_substrings",
        "sensitive_output_forbidden_substrings",
    )
    @classmethod
    def _substrings_are_nonempty(cls, value: list[str]) -> list[str]:
        if any(not _normalize_text(item) for item in value):
            raise ValueError("ground-truth substrings must be non-empty")
        return value

    @model_validator(mode="after")
    def _escalation_fields_are_consistent(self) -> "_ExpectedOutcome":
        action_requires_escalation = self.action is TurnAction.ESCALATE
        if self.requires_escalation is not action_requires_escalation:
            raise ValueError(
                "requires_escalation must be true exactly when action is escalate"
            )
        if self.requires_escalation != (self.expected_escalation_type is not None):
            raise ValueError(
                "expected_escalation_type must be set exactly for escalations"
            )
        return self


class _CaseMetadata(_StrictModel):
    segment: str
    notes: str


class EvalCase(_StrictModel):
    case_id: str
    language: Language
    scenario: Scenario
    customer_message: str
    expected: _ExpectedOutcome
    metadata: _CaseMetadata

    @field_validator("case_id", mode="before")
    @classmethod
    def _case_id_is_bounded(cls, value: object) -> object:
        _nonempty_string(value)
        if len(value) > MAX_CASE_ID_LENGTH:
            raise ValueError(
                f"case_id must contain at most {MAX_CASE_ID_LENGTH} characters"
            )
        return value

    @field_validator("customer_message", mode="before")
    @classmethod
    def _customer_message_is_nonempty(cls, value: object) -> object:
        return _nonempty_string(value)

    @model_validator(mode="after")
    def _complaint_identity_is_customer_visible(self) -> "EvalCase":
        complaint_id = self.expected.complaint_id
        if complaint_id is not None and complaint_id not in self.customer_message:
            raise ValueError("customer_message must contain expected complaint_id")
        return self


def load_eval_config(path: Path) -> EvalConfig:
    """Load and validate evaluation configuration from YAML."""
    with path.open(encoding="utf-8") as config_file:
        payload = yaml.safe_load(config_file)
    return EvalConfig.model_validate(payload)


def load_eval_cases(
    held_out_manifest_path: Path,
    development_manifest_path: Path,
    config: EvalConfig,
) -> list[EvalCase]:
    """Load held-out cases after identity, coverage, and leakage checks."""
    held_path = _validated_manifest_argument(
        held_out_manifest_path, config.held_out_manifest, "held-out"
    )
    development_path = _validated_manifest_argument(
        development_manifest_path,
        config.development_manifest,
        "development",
    )
    held_manifest = _HeldOutManifest.model_validate(_read_json(held_path))
    development_manifest = EvalManifest.model_validate(_read_json(development_path))

    if held_manifest.dataset_version != config.dataset_version:
        raise ValueError("held-out dataset_version does not match config")
    if held_manifest.pipeline_version != config.pipeline_version:
        raise ValueError("held-out pipeline_version does not match config")
    if config.sandbox_file.resolve() != _RUNTIME_SANDBOX_PATH.resolve():
        raise ValueError("configured sandbox file does not match runtime settings")
    if (
        held_manifest.sandbox_sha256 != config.sandbox_sha256
        or development_manifest.sandbox_sha256 != config.sandbox_sha256
    ):
        raise ValueError("manifest sandbox identity does not match config")
    _verify_file_hash(config.sandbox_file, config.sandbox_sha256, "sandbox")

    held_bytes = held_manifest.cases_file.read_bytes()
    development_bytes = development_manifest.cases_file.read_bytes()
    _verify_hash(held_bytes, held_manifest.sha256, "held-out")
    _verify_hash(development_bytes, development_manifest.sha256, "development")

    held_cases = _parse_cases(held_bytes, "held-out")
    development_cases = _parse_cases(development_bytes, "development")
    _validate_unique_case_ids(held_cases, "held-out")
    _validate_unique_case_ids(development_cases, "development")
    _validate_manifest_counts(held_manifest, held_cases)
    if development_manifest.total_cases != len(development_cases):
        raise ValueError("development manifest total_cases does not match cases")
    validate_coverage(held_cases, config)
    validate_held_out_independence(
        held_cases,
        development_cases,
        held_bytes,
        development_bytes,
    )
    return held_cases


def validate_coverage(cases: list[EvalCase], config: EvalConfig) -> None:
    """Validate unique IDs and all configured held-out coverage minimums."""
    _validate_unique_case_ids(cases, "held-out")
    minimum = config.min_coverage
    if len(cases) < minimum.total_cases:
        raise ValueError("held-out total coverage is below total_cases minimum")
    portuguese_cases = sum(case.language == "pt" for case in cases)
    if portuguese_cases < minimum.min_portuguese_cases:
        raise ValueError("held-out Portuguese coverage is below minimum")
    scenario_counts = Counter(case.scenario for case in cases)
    for scenario in _SCENARIOS:
        if scenario_counts[scenario] < minimum.min_cases_per_scenario:
            raise ValueError(f"held-out scenario coverage is below minimum: {scenario}")


def validate_held_out_independence(
    held_out_cases: list[EvalCase],
    development_cases: list[EvalCase],
    held_out_bytes: bytes,
    development_bytes: bytes,
) -> None:
    """Reject deterministic identity or message leakage between datasets."""
    if (
        held_out_bytes == development_bytes
        or hashlib.sha256(held_out_bytes).digest()
        == hashlib.sha256(development_bytes).digest()
    ):
        _raise_leakage(
            _first_case_id(held_out_cases),
            _first_case_id(development_cases),
            "dataset_bytes_sha256",
        )

    development_ids = {case.case_id: case for case in development_cases}
    for held_case in held_out_cases:
        if held_case.case_id in development_ids:
            _raise_leakage(
                held_case.case_id,
                development_ids[held_case.case_id].case_id,
                "case_id",
            )

    development_complaints = {
        case.expected.complaint_id: case
        for case in development_cases
        if case.expected.complaint_id is not None
    }
    for held_case in held_out_cases:
        complaint_id = held_case.expected.complaint_id
        if complaint_id is not None and complaint_id in development_complaints:
            _raise_leakage(
                held_case.case_id,
                development_complaints[complaint_id].case_id,
                "complaint_id",
            )

    normalized_development = [
        (case, _normalize_text(case.customer_message)) for case in development_cases
    ]
    for held_case in held_out_cases:
        held_message = _normalize_text(held_case.customer_message)
        held_shingles = _message_shingles(held_message)
        for development_case, development_message in normalized_development:
            if held_message == development_message:
                _raise_leakage(
                    held_case.case_id,
                    development_case.case_id,
                    "normalized_message",
                )
            if held_case.language != development_case.language:
                continue
            similarity = _jaccard(held_shingles, _message_shingles(development_message))
            if similarity >= 0.90:
                _raise_leakage(
                    held_case.case_id,
                    development_case.case_id,
                    "message_jaccard_gte_0.90",
                )


def _validated_manifest_argument(supplied: Path, configured: Path, role: str) -> Path:
    candidate = supplied if supplied.is_absolute() else PROJECT_ROOT / supplied
    resolved = candidate.resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"{role} manifest must resolve inside the project root")
    if resolved != configured.resolve():
        raise ValueError(f"{role} manifest path does not match config")
    return resolved


def _read_json(path: Path) -> object:
    with path.open(encoding="utf-8") as manifest_file:
        return json.load(manifest_file)


def _validate_sha256(value: object) -> object:
    _nonempty_string(value)
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError("sha256 must be a lowercase 64-character hex digest")
    return value


def _verify_hash(payload: bytes, expected: str, role: str) -> None:
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError(f"{role} cases sha256 does not match manifest")


def _verify_file_hash(path: Path, expected: str, role: str) -> None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise ValueError(f"{role} file is unavailable: {path}") from error
    if digest.hexdigest() != expected:
        raise ValueError(f"{role} sha256 does not match config")


def _parse_cases(payload: bytes, role: str) -> list[EvalCase]:
    raw_cases = yaml.safe_load(payload)
    if not isinstance(raw_cases, list):
        raise ValueError(f"{role} cases file must contain a list")
    return [EvalCase.model_validate(raw_case) for raw_case in raw_cases]


def _validate_unique_case_ids(cases: list[EvalCase], role: str) -> None:
    seen: set[str] = set()
    for case in cases:
        if case.case_id in seen:
            raise ValueError(f"{role} case_id must be unique: {case.case_id}")
        seen.add(case.case_id)


def _calculated_coverage(cases: list[EvalCase]) -> dict:
    scenario_counts = Counter(case.scenario for case in cases)
    return {
        "total_cases": len(cases),
        "portuguese_cases": sum(case.language == "pt" for case in cases),
        "cases_per_scenario": {
            scenario: scenario_counts[scenario] for scenario in _SCENARIOS
        },
    }


def _validate_manifest_counts(
    manifest: _HeldOutManifest, cases: list[EvalCase]
) -> None:
    calculated = _calculated_coverage(cases)
    if manifest.total_cases != len(cases):
        raise ValueError("held-out manifest total_cases does not match cases")
    declared = manifest.coverage.model_dump()
    if declared["total_cases"] != calculated["total_cases"]:
        raise ValueError("held-out coverage total_cases does not match cases")
    if declared["portuguese_cases"] != calculated["portuguese_cases"]:
        raise ValueError("held-out coverage portuguese_cases does not match cases")
    if declared["cases_per_scenario"] != calculated["cases_per_scenario"]:
        raise ValueError("held-out coverage cases_per_scenario does not match cases")


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def _message_shingles(message: str) -> frozenset[tuple[str, ...]]:
    tokens = message.split()
    if len(tokens) < 5:
        return frozenset({tuple(tokens)})
    return frozenset(
        tuple(tokens[index : index + 5]) for index in range(len(tokens) - 4)
    )


def _jaccard(
    left: frozenset[tuple[str, ...]], right: frozenset[tuple[str, ...]]
) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def _first_case_id(cases: list[EvalCase]) -> str:
    return cases[0].case_id if cases else "<empty>"


def _raise_leakage(held_case_id: str, development_case_id: str, rule: str) -> None:
    raise ValueError(
        "held-out leakage detected: "
        f"held_case_id={held_case_id}, "
        f"development_case_id={development_case_id}, rule={rule}"
    )
