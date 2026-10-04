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
- Running authored count: 410 lines from T1.
- Planned slices: PR 1 contains T1 commit `5fac720`; PR 2 will contain the reset work unit; PR 3 will contain documentation and final integration evidence.
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

- [ ] Add failing tests for scoped cleanup, idempotency, preservation of unrelated rows/files, transactional verification, and lock failure behavior.
- [ ] Add minimal service reset operations and a CLI that defaults to catalog scope.
- [ ] Observe focused GREEN, triangulate relevant alternate cases, and record evidence.
- [ ] Commit as one Conventional Commit work unit.

Route: delegated to `gentle-ai-worker` because multiple service/CLI/test files trigger mandatory delegation.

Acceptance:

- Default reset removes only mutable card and escalation rows associated with cataloged cases/products.
- Unrelated SQLite rows, audit files, DuckDB, and Parquet remain untouched.
- Repeated reset is safe and reports verified counts.
- SQLite errors fail closed without deleting database files.

### T3 — Document and verify the local demo workflow

- [ ] Replace placeholder examples with the six cataloged cases and copy-ready prompts.
- [ ] Add concise generate/run/reset instructions to the README and Chainlit guide.
- [ ] Update `docs/STATUS.md` with the delivered workflow and remaining limitations.
- [ ] Run focused tests, the applicable full suite, Ruff, and portable artifact verification.
- [ ] Commit documentation and integration evidence as one Conventional Commit work unit.

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
- Native assessment: unavailable because the untracked ODD feature document required explicit declaration; native plan treats the candidate as high risk and requires an independent verifier.

## Next step

Independently verify and review the T1 slice, then continue with T2.
