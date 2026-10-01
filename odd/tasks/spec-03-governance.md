# Spec 03 Governance Decision

## Objective

Implement the audited `docs/specs/spec_03.md` contract with strict behavior-level TDD.

## Problem

Spec #2 produces raw Jev screening and routing results, but the project lacks deterministic, typed, fail-closed governance decisions and validated configuration thresholds.

## Why

The later Strands governance adapter needs pure decisions that preserve audit metadata, reject anomalous values, and never confuse stage progression with authorization of banking actions.

## Scope

- Add typed, fail-fast governance policy configuration.
- Add runtime threshold types and the two-stage decision API.
- Cover the complete Spec #3 behavior backlog without network calls.
- Update ownership documentation and project status after behavior is verified.

## Constraints

- Follow RED → GREEN → TRIANGULATE → REFACTOR using `uv run pytest`.
- Do not call Jev or the network.
- Do not modify Spec #1/#2 production code or `governance/jev/__init__.py`.
- Keep decision logic pure; no I/O, audit emission, or latency measurement.
- Use `EXPECTED_INTENTS` from Spec #2 as the only intent-domain source.
- Do not commit unless the user explicitly authorizes commits.

## Tasks

- [x] **T1 — Add typed governance policy configuration**
  - RED: 13 focused tests failed before production changes.
  - GREEN: typed policy models, fail-fast `load_policy`, and configured governance values pass all focused tests.
  - Check: `uv run pytest tests/unit/test_config.py -q` → 13 passed.
- [x] **T2 — Add validated runtime threshold types**
  - RED: focused tests failed at collection because `decision.py` did not exist.
  - GREEN: validated frozen thresholds, mapper, enums, decision dataclass, and public module surface pass 12 tests.
  - Check: `uv run pytest tests/unit/governance/jev/test_governance.py -q` → 12 passed.
- [x] **T3 — Implement screening decisions**
  - RED/GREEN: BLOCK, REVIEW, ALLOW, boundaries, precedence, invalid values, metadata preservation, and deterministic reasons implemented.
  - TRIANGULATE: both signals covered across NaN, ±inf, range violations, boundaries, and dual-signal cases.
  - Check: focused governance module → 41 passed.
- [x] **T4 — Implement routing decisions**
  - RED/GREEN: intent validation/domain, confidence gating, precedence, all intents, metadata/probability preservation, and custom thresholds implemented.
  - TRIANGULATE: every `EXPECTED_INTENTS` value plus invalid confidence, metadata, boundaries, and precedence cases covered.
  - Check: governance module → 66 passed; complete Jev suite → 194 passed.
- [x] **T5 — Update documentation and status**
  - Updated Spec #1, Spec #2, observability ownership language, and marked Spec #3 complete in `docs/STATUS.md`.
  - Validation: 79 combined behavior tests passed; documentation diff check and targeted readback passed.
- [x] **T6 — Run final verification and native review**
  - Focused Spec #3 tests, complete Jev unit suite, config tests, Ruff, and diff checks passed.
  - Native review approved and acknowledged lineage `review-5a0f4901be1c7b71`.
  - Corrected `R3-test-collection-policy` by replacing the module-level `policy` singleton dependency with a local typed policy fixture in 9 diff lines (within the approved 16-line plan).

## Acceptance Criteria

- Every criterion in `docs/specs/spec_03.md` sections 14 and 17 is covered and green.
- `uv run pytest tests/unit/governance/jev/test_governance.py -q` passes.
- `uv run pytest tests/unit/governance/jev -q` passes.
- `uv run pytest tests/unit/test_config.py -q` passes.
- No test calls Jev or the network.
- Configuration is typed and fail-fast; decision behavior is pure, deterministic, and fail-closed for the specified value anomalies.
- Required documentation and `docs/STATUS.md` are current.

## Progress

- Completed: T1, T2, T3, T4, T5, T6.
- Active task: none.
- Branch: `feat/spec-03-governance`.
- Exploration: completed by `gentle-ai-explore`; no unresolved spec mismatch found.
- Commit evidence: pending; commits are not authorized by the user.

## Verification Evidence

- Test runner resolved from `pyproject.toml`: pytest via `uv run pytest`.
- Pre-work suite: `uv run pytest tests/unit/governance/jev -q` → 128 passed.
- T1 RED: `uv run pytest tests/unit/test_config.py -q` → 13 failed before production changes.
- T1 GREEN (worker): `uv run pytest tests/unit/test_config.py -q` → 13 passed; regression suite → 128 passed; Ruff passed.
- T1 parent spot check: `uv run pytest tests/unit/test_config.py -q` → 13 passed.
- T2 RED: focused tests failed at collection with `ModuleNotFoundError` for the absent decision module.
- T2 GREEN (worker): 12 focused tests passed; config regression and Ruff passed.
- T2 parent spot check: `uv run pytest tests/unit/governance/jev/test_governance.py -q` → 12 passed.
- T3 RED/GREEN: screening behavior progressed from 11 `NotImplementedError` failures and 17 validation failures to 29 focused passes.
- T3 worker verification: full governance module → 41 passed; config → 13 passed; Ruff passed after formatting two long test lines.
- T3 parent spot check: `uv run pytest tests/unit/governance/jev/test_governance.py -q` → 41 passed.
- T4 RED/GREEN: 10 routing tests initially failed with `NotImplementedError`; 25 focused routing tests then passed.
- T4 worker verification: governance module → 66 passed; complete Jev suite → 194 passed; config → 13 passed; Ruff passed after formatting two long test lines.
- T4 parent spot check: `uv run pytest tests/unit/governance/jev/test_governance.py -q` → 66 passed.
- T5 documentation-only TDD exception: no artificial RED test; existing behavior remained green.
- T5 worker verification: governance + config tests → 79 passed; documentation `git diff --check` passed.
- T5 parent spot check: governance + config tests → 79 passed; targeted ownership/status readback passed.
- T6 independent verifier: PASS; governance module → 66 passed, Jev suite → 194 passed, config → 13 passed, Ruff and diff checks passed.
- Native review: reliability lens requested one bounded correction (`R3-test-collection-policy`); 16 diff lines authorized by the provider correction plan.
- Correction: 9 diff lines; focused governance tests → 66 passed; complete Jev suite → 194 passed; Ruff passed; parent spot check → 66 passed.
- Targeted native validator approved the correction; acknowledgement burned lineage `review-5a0f4901be1c7b71`.
- Non-blocking advisory: `R3-nonnumeric-fail-closed` at `decision.py:115`; out of the audited bounded-value contract because structurally invalid types may raise.
- Final assessment could not independently enumerate untracked files, but explicit `nativeReviewOutcome=closed` produced the on-path plan; independent verification had already passed.

## Next Step

User may inspect the diff and explicitly authorize a commit when ready.
