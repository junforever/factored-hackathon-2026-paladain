# Demo case catalog and reset

## Objective

Provide judges and local users with six reproducible Chainlit demo cases and a safe command that restores mutable demo state between runs.

## Problem

The repository documents six demo capabilities but uses placeholder complaint IDs and has no repeatable way to discover representative local cases or reset card/escalation SQLite state after testing.

## Why

A generated catalog plus a bounded reset workflow makes the portable demo easy to evaluate repeatedly without rebuilding or mutating source data.

## Scope

- Select and validate one stable `complaint_id` for each of the six existing scenario categories.
- Publish copy-ready prompts and expected behavior for Chainlit.
- Reset only mutable state associated with cataloged demo cases by default.
- Preserve DuckDB, Parquet, configuration, secrets, and audit files.
- Document the generate, run, reset, and repeat workflow.

## Constraints

- `product_id` is the trusted complaint-to-product link.
- Use `settings` paths and existing dependencies only.
- Keep hard policy in Python, not prompts.
- SQLite mutations must be transactional, verified, fail closed, and idempotent.
- Strict TDD: observe RED, GREEN, TRIANGULATE, and REFACTOR for behavioral changes.
- Technical artifacts are written in English unless extending existing Spanish-only source conventions.
- No push, pull request, or merge is authorized.

## Delivery

- Branch: `feat/demo-case-catalog`
- Branch point: `c1e66a399f873a3823506cefa33d79de1047c6f2`
- Strategy: `auto-chain` with `chain_strategy=feature-branch-chain`, selected by the user after T1 reached 410 authored lines.
- Forecast: revised from approximately 350 to more than 400 authored changed lines; generated catalog data excluded.
- Running authored count: 1,174 lines across T1, T2, and T3.
- Planned slices: PR 1 contains T1 commit `5fac720`; PR 2 contains T2 commit `ad02e04`; PR 3 contains T3 commit `8bbadf4`.
- Native review boundary: each work-unit commit, subject to the repository RDD switch and native assessment.

## Tasks

### T1 — Generate a validated six-scenario demo catalog

- [x] Add failing behavior-level tests for catalog schema, scenario coverage, valid unique complaint IDs, and deterministic generation.
- [x] Query the local sandbox read-only and select representative IDs using explicit deterministic criteria.
- [x] Add the smallest generator and versioned catalog artifact using existing dependencies.
- [x] Observe focused GREEN and record evidence.
- [x] Commit as one Conventional Commit work unit.

Route: delegated to `gentle-ai-worker` because preparation plus multiple non-trivial files triggers mandatory delegation.

Acceptance:

- Exactly these scenarios exist: `normal_resolution`, `ambiguous`, `human_required`, `attack`, `missing_data`, `edge_case`.
- Every catalog entry uses a real sandbox `complaint_id` and includes language, a copy-ready prompt, purpose, and expected behavior.
- Generation is deterministic and does not mutate source data.

### T2 — Reset catalog demo state safely

- [x] Add failing tests for scoped cleanup, idempotency, preservation of unrelated rows/files, transactional verification, and lock failure behavior.
- [x] Add minimal service reset operations and a CLI that defaults to catalog scope.
- [x] Observe focused GREEN, triangulate relevant alternate cases, and record evidence.
- [x] Commit as one Conventional Commit work unit.

Route: delegated to `gentle-ai-worker` because multiple service/CLI/test files trigger mandatory delegation.

Acceptance:

- Default reset removes only mutable card and escalation rows associated with cataloged cases/products.
- Unrelated SQLite rows, audit files, DuckDB, and Parquet remain untouched.
- Repeated reset is safe and reports verified counts.
- SQLite errors fail closed without deleting database files.

### T3 — Document and verify the local demo workflow

- [x] Replace placeholder examples with the six cataloged cases and copy-ready prompts.
- [x] Add concise generate/run/reset instructions to the README and Chainlit guide.
- [x] Update `docs/STATUS.md` with the delivered workflow and remaining limitations.
- [x] Run focused tests, the applicable full suite, Ruff, and portable artifact verification.
- [x] Commit documentation and integration evidence as one Conventional Commit work unit.

Route: documentation write delegated to `gentle-ai-worker`; final command verification delegated to `gentle-ai-verify` when required by native assessment or verification policy.

Acceptance:

- A new user can identify a case, paste a prompt into Chainlit, understand the expected outcome, reset state, and repeat.
- Documentation clearly distinguishes immutable source data from mutable demo state.
- Every failed, skipped, unavailable, or pending check is recorded.

## Progress

- 2026-10-04: Authorized by the user.
- 2026-10-04: Read-only exploration confirmed the six scenario taxonomy, `complaint_id` chat contract, portable data build path, and mutable SQLite tables.
- 2026-10-04: Feature branch created at the recorded branch point.
- 2026-10-04: T1 generated six deterministic, sandbox-validated demo cases without modifying Parquet, DuckDB, or SQLite state.
- 2026-10-04: T1 committed as `5fac720ed361cd37150dfbe25fd17cfd2748362d`; its 410 authored lines triggered the configured `ask-on-risk` delivery decision.
- 2026-10-04: User selected `feature-branch-chain`; delivery will use three focused slices for catalog, reset, and documentation.
- 2026-10-04: T2 added a catalog-scoped reset with dry-run and single-case selection; unrestricted `--all` was intentionally omitted to preserve the safe default.
- 2026-10-04: T2 committed as `ad02e04d412c7b16ed4f87847809b96c15dd0768`.
- 2026-10-04: T3 published the six-case judge workflow and reset/repeat instructions in README, Chainlit, and status documentation.
- 2026-10-04: T3 committed as `8bbadf44e859b119881b3ab53ca8dec3ad560fb4`.
- 2026-10-04: Feature implementation closed with all automated checks passing; live Chainlit execution remains an explicit manual check.

## Verification evidence

### T1

- RED: `uv run pytest -q tests/unit/test_demo_cases.py` — 2 failed because the generator did not exist.
- GREEN: `uv run pytest -q tests/unit/test_demo_cases.py` — 2 passed after minimum implementation.
- TRIANGULATE/REFACTOR: missing-candidate fail-closed coverage added; 3 passed.
- Worker lint: `uv run ruff check scripts/data_preparation/12_build_demo_cases.py tests/unit/test_demo_cases.py` — all checks passed after correcting eight initial findings.
- Generator: `uv run python scripts/data_preparation/12_build_demo_cases.py` — wrote 6 demo cases.
- Parent spot check: `uv run pytest -q tests/unit/test_demo_cases.py` — 3 passed in 1.47s.
- Rollback boundary: remove `configs/demo_cases.yaml`, `scripts/data_preparation/12_build_demo_cases.py`, and `tests/unit/test_demo_cases.py`.
- Commit: `5fac720ed361cd37150dfbe25fd17cfd2748362d` (`feat(demo): add reproducible case catalog`).
- Initial native assessment: unavailable because the untracked ODD feature document required explicit declaration.
- Final native assessment after committing tracking metadata: medium risk (`configuration_change`); writer verification stood without a separate verifier.
- Native review: approved and acknowledged; lineage `review-6599edc08586ca8f`, consumed revision `sha256:9444eb7faf9dfe6801626f7d4e3887221f2616c52f6e1bb10b457220b0773cdb`.
- Advisory follow-up: `R3-edge-card-selector` at `scripts/data_preparation/12_build_demo_cases.py:130-135` was informational and opened no correction.

### T2

- RED: `uv run pytest -q tests/unit/services/test_demo_state_reset.py` — 1 failed because the reset CLI did not exist.
- GREEN: focused reset behavior passed with 1 test after minimum implementation.
- TRIANGULATE/REFACTOR: 5 tests passed in 1.60s covering scope, preservation, idempotency, dry-run, selection, locking, database errors, and CLI failure.
- Worker lint: Ruff passed for both services, the reset CLI, and reset tests.
- Worker dry-run: validated six catalog complaints/products and reported zero matching rows without mutation.
- Invalid requested check: two nonexistent service test paths caused exit 4; repository inspection confirmed the authorization error.
- Independent verifier: 5 reset tests and 33 existing factory/tool tests passed; Ruff, dry-run, and `git diff --check` passed.
- Parent spot check: `uv run pytest -q tests/unit/services/test_demo_state_reset.py` — 5 passed in 1.60s.
- Risk: card and escalation databases use separate transactions; a safe targeted partial reset may require an idempotent retry if the second database fails.
- Rollback boundary: remove `scripts/reset_demo_state.py` and `tests/unit/services/test_demo_state_reset.py`, then revert only the reset functions in both service modules.
- Commit: `ad02e04d412c7b16ed4f87847809b96c15dd0768` (`feat(demo): add scoped state reset`).
- Native assessment: medium risk (`executable_change`); existing writer and independent verification evidence stood.
- Native review: approved and acknowledged; lineage `review-cfe36180a35f72ee`, consumed revision `sha256:278d7c615c6c3b71ac38e9704cf0b4e6f559a28ce5dee336a5979e2596804e55`.
- Advisory follow-ups: `R3-cross-db-partial-reset` and `R3-shared-product-scope` were informational and opened no correction.

### T3

- TDD exception: passive documentation has no meaningful RED behavior test; structural verification was used instead.
- Worker structural checks: all six catalog IDs appeared in the docs, `CMP-DEMO` was absent from `chainlit.md`, and documentation diff checks passed.
- Full suite: `uv run pytest -q` — 1,015 passed, 0 failed, with 1 deprecation warning.
- Ruff: `uv run ruff check .` — all checks passed.
- Portable artifacts: `uv run python scripts/verify_demo_artifacts.py` — 2 artifacts verified with 89,472 rows.
- Reset dry-run: completed without mutation and reported zero matching mutable rows.
- Documentation consistency: all six IDs documented and no Chainlit placeholder remained.
- Parent spot check: documentation consistency command passed with no output.
- `git diff --check` passed with only an informational line-ending warning for `chainlit.md`.
- Manual check pending: live Chainlit interaction was not exercised because it requires the configured runtime/model credentials.
- Rollback boundary: revert only `README.md`, `chainlit.md`, and `docs/STATUS.md`.
- Commit: `8bbadf44e859b119881b3ab53ca8dec3ad560fb4` (`docs(demo): publish repeatable judge workflow`).
- Native assessment: passive (`non_executable_only`); structural readback was the complete required review path, with no reviewer run due.

## Next step

User may exercise the six documented prompts in live Chainlit, then choose whether to push or open the planned PR chain.
