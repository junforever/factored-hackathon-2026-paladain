# Spec 04 Tool Gating and Output Screening

## Objective

Implement the reviewed `docs/specs/spec_04.md` v5 contract with strict behavior-level TDD.

## Problem

The governance layer can screen input and route intent, but it cannot yet deterministically gate concrete tool calls or screen proposed agent output against secrets and verified evidence.

## Why

The later Strands adapter needs fail-closed, auditable governance primitives that keep hard banking rules in code and use Jev only for one bounded semantic judgment per stage.

## Scope

- Add typed, fail-fast tool-gating and output-screening policy configuration.
- Extract reusable secret sanitization and recursive JSON sanitization.
- Add deterministic tool eligibility, minimized Jev projections, and semantic tool gating.
- Add deterministic secret detection, verified-evidence trust boundaries, and semantic output screening.
- Extend pure governance decisions and stages without changing existing Spec #3 behavior.
- Update observability ownership language and project status after verification.

## Constraints

- Follow RED → GREEN → TRIANGULATE → REFACTOR with `uv run pytest`; add one smallest meaningful failing behavior test before each production increment.
- Unit tests must not call Jev or the network.
- Keep deterministic rules before Jev and preserve one semantic judgment per evaluation.
- Do not modify current tool signatures or `governance/jev/__init__.py`.
- Do not change `decide_screening` or `decide_routing` behavior.
- Never send raw banking identifiers or `agent_notes` to Jev.
- Preserve `_sanitize_message` as a temporary compatibility alias.
- Use repository-local contracts plus current official TypeSafe State, Noul, Score, and Python SDK documentation consulted on 2026-10-01.
- Do not commit unless the user explicitly authorizes commits.

## Tasks

- [x] **T1 — Add typed policy configuration and runtime thresholds**
  - RED: missing required policy sections and absent runtime mapper behavior failed as expected.
  - GREEN: required typed policy models, provisional YAML values, frozen runtime thresholds, explicit `from_policy(None)` rejection, and widened threshold union implemented.
  - Checks: 119 focused tests and 247 combined regression tests passed; Ruff and diff checks passed; independent verification PASS.
- [x] **T2 — Extract and extend sanitization**
  - RED: the first import failed with `ModuleNotFoundError`; subsequent focused tests failed for each missing detection and recursive behavior.
  - GREEN: public sanitization APIs, centralized regex ownership, deterministic detection, recursive exact-key redaction, and the Spec #2 alias implemented.
  - Checks: 21 sanitization, 59 evaluation, and 237 complete Jev tests passed; Ruff and diff checks passed; independent verification PASS.
- [x] **T3 — Implement deterministic and semantic tool gating**
  - RED: missing validators/API and unknown-tool acceptance failed before their minimum implementations.
  - GREEN: exact deterministic precedence, trust-boundary validation, per-tool contracts, minimized projection, deterministic short-circuit, frozen result, and one-Noul Jev evaluation implemented.
  - Checks: 122 evaluation, 300 Jev, and 331 full-repository tests passed; Ruff and diff checks passed; independent verification PASS.
- [x] **T4 — Implement deterministic and semantic output screening**
  - RED: missing output constants/result/API, invalid-action handling, secret short-circuit, Score flow, and sanitization conversion failed before minimum implementations.
  - GREEN: exact trust boundaries, canonical action coherence, original-response secret short-circuit, minimized state, frozen result, and one-Score Jev evaluation implemented.
  - Checks: 172 focused, 329 Jev, and 360 full-repository tests passed; Ruff and diff checks passed; independent verification PASS.
- [x] **T5 — Implement fail-closed governance decisions**
  - RED: absent stages/APIs and each incremental decision branch failed before minimum implementations.
  - GREEN: new stages, preserved raw answers/thresholds, exact action domains, anomaly validation, deterministic precedence, and one-reason decisions implemented without changing Spec #3 behavior.
  - Checks: 133 governance and 405 full-repository tests passed; Ruff and diff checks passed; independent verification PASS.
- [x] **T6 — Update documentation and run final verification**
  - Updated observability ownership language and marked Spec #4 complete with provisional-threshold calibration debt.
  - Final behavior checks passed; repository-wide Ruff exposed 16 pre-existing violations outside the candidate while candidate-scoped Ruff remained green.
  - Native reliability review found and validated one bounded tuple-sanitization correction, then approved and acknowledged the candidate.

## Acceptance Criteria

- Every criterion in `docs/specs/spec_04.md` sections 18 and 21 is covered and green.
- `uv run pytest tests/unit/governance/jev -q` passes.
- `uv run pytest tests/unit/test_config.py -q` passes.
- No test calls Jev or the network.
- Deterministic checks always run before Jev and covered secrets never reach Jev for authorization.
- `decide_tool_gating` never returns REVIEW; `decide_output_screening` never returns BLOCK.
- Boundary, non-finite, out-of-range, probability-domain, probability-sum, weighted-score, and precedence cases are covered.
- Effective threshold objects are preserved in every decision.
- Recursive sanitization handles nested dicts/lists with exact sensitive-key comparison.
- Public API inputs, customer context, verified facts, and canonical actions are validated at their trust boundaries.
- Jev state includes only the specified allowlisted, minimized fields.
- Existing Spec #1–#3 contracts remain green.
- `docs/observability.md` and `docs/STATUS.md` are current.

## Progress

- Completed: T1, T2, T3, T4, T5, T6.
- Active task: none.
- Branch: `feat/spec-04-tool-output-governance`.
- Exploration: completed by `gentle-ai-explore`; no implementation blocker found. The plan adopts whitespace-only response rejection and allows unused extra customer-context keys without projecting them to Jev.
- Baseline: `uv run pytest tests/unit/governance/jev tests/unit/test_config.py -q` → 207 passed.
- Commit evidence: pending; commits are not authorized by the user.

## Verification Evidence

- Test runner resolved from `pyproject.toml`: pytest via `uv run pytest`.
- Pre-work combined suite: 207 passed in 3.18s, exit code 0.
- Official TypeSafe docs checked: State permits structured JSON; Noul returns one yes-probability with no separate confidence; Score returns ordered-level probabilities, weighted score, and confidence; application code owns thresholds.
- T1 RED: missing `tool_gating` did not initially raise `ValidationError`; missing `OutputScreeningThresholds.from_policy` failed as expected.
- T1 GREEN: `uv run pytest tests/unit/test_config.py tests/unit/governance/jev/test_governance.py -q` → 119 passed.
- T1 regression: `uv run pytest tests/unit/governance/jev tests/unit/test_config.py -q` → 247 passed.
- T1 quality: Ruff and `git diff --check` passed. Two pre-existing format-check deviations reproduce against `HEAD` and were not changed.
- T1 independent verification: PASS with structural readback; no out-of-scope stages or decisions were added.
- T1 runtime harness: N/A because configuration and frozen value types have no separate runtime adapter; focused tests exercise loading and construction.
- T1 rollback boundary: the five T1 files listed in the task evidence can be reverted without affecting later behavior.
- T2 RED/GREEN: initial missing module and subsequent missing behaviors failed before minimum implementations; focused suite finished at 21 passed.
- T2 regression: evaluation tests → 59 passed; complete Jev suite → 237 passed.
- T2 quality: Ruff, format check for changed implementation/test files, and `git diff --check` passed.
- T2 independent verification: PASS with structural readback and no out-of-scope gating/screening behavior.
- T2 runtime harness: N/A because the module is pure deterministic transformation with no I/O boundary.
- T2 rollback boundary: revert `evaluations.py` and remove the new sanitization module/test together, without touching T1.
- T3 RED/GREEN: missing validator imports, unknown-tool acceptance, and absent semantic API failed before minimum implementations; focused suite finished at 122 passed.
- T3 regression: complete Jev suite → 300 passed; full repository suite → 331 passed.
- T3 quality: Ruff and `git diff --check` passed.
- T3 independent verification: PASS with exact precedence, minimization, short-circuit, one-Noul, error propagation, and scope readback.
- T3 runtime harness: N/A because real adapter and tool execution belong to later specs; mocked behavior tests exercise this boundary without network calls.
- T3 rollback boundary: remove only T3 additions from `evaluations.py` and `test_evaluations.py`, preserving T2 code in the same files.
- T4 RED/GREEN: missing public surface and each output-screening branch failed before minimum implementations; focused evaluation/sanitization suites finished at 172 passed.
- T4 regression: complete Jev suite → 329 passed; full repository suite → 360 passed.
- T4 quality: Ruff and `git diff --check` passed; pre-existing format-check deviations in the cumulative test file remain untouched.
- T4 independent verification: PASS with trust-boundary, secret short-circuit, minimized one-Score state, error propagation, and scope readback.
- T4 runtime harness: N/A because response delivery and the real adapter belong to Spec #6; mocked tests exercise the current boundary without network calls.
- T4 rollback boundary: remove only T4 additions from `evaluations.py` and `test_evaluations.py`, preserving T2/T3 content.
- T5 RED/GREEN: absent stages/APIs and each decision branch failed before minimum implementations; focused governance suite finished at 133 passed.
- T5 regression: complete Jev/config and full repository suites → 405 passed.
- T5 quality: Ruff and `git diff --check` passed; pre-existing format-check deviations remain untouched.
- T5 independent verification: PASS with stages, exact action domains/precedence, signal invariants/tolerances, one-reason formatting, preservation, and Spec #3 regression readback.
- T5 runtime harness: N/A because these are pure decision functions; the runtime adapter belongs to Spec #6.
- T5 rollback boundary: remove only T5 hunks from `decision.py` and `test_governance.py`, preserving T1 and Spec #3 code.
- T6 documentation-only TDD exception: no artificial RED test; targeted readback and `git diff --check` passed.
- Final acceptance: Jev suite → 374 passed before correction and 375 passed after correction; config suite → 31 passed; full suite before correction → 405 passed; `git diff --check` passed.
- Final candidate-scoped Ruff checks passed. Repository-wide `uv run ruff check .` failed on 16 pre-existing violations (15 E501, 1 E402), all outside Spec #4 changed paths.
- Native review lineage `review-e2063e2adff25af3` required correction `R3-secret-tuple-leak` because tuple-nested secrets were not recursively sanitized.
- Correction TDD: regression test RED with 1 failed/21 passed; GREEN with 22 passed; evaluation suite → 151 passed; Jev suite → 375 passed; Ruff passed. Correction used 8 provider-counted diff lines within the authorized 16-line plan.
- The generic independent verifier could not prove the correction delta from Git because both files were untracked, but behavior passed and the native frozen-tree targeted validator approved the exact correction.
- Native review approved and acknowledgement burned lineage `review-e2063e2adff25af3`.
- Native non-blocking advisories for later work: `R3-intent-domain-validation` and `R3-null-semantic-answer`; neither reopens this review.
- T6 runtime harness: N/A because Spec #4 exposes pure governance/evaluation primitives; adapter/tool execution belongs to Spec #6.
- T6 rollback boundary: revert the 12 Spec #4 candidate paths together; no tool signatures or `jev/__init__.py` changed.

## Next Step

User may inspect the uncommitted diff and explicitly authorize a commit when ready.
