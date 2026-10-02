# Spec 05 Strands Tool Registration

## Objective

Implement the reviewed `docs/specs/spec_05.md` v3 contract with strict behavior-level TDD.

## Problem

The four banking tools exist, but the Strands agent has no thin, schema-verified registration layer that exposes them to the future orchestrator.

## Why

Spec #6 needs a stable public tool set whose signatures, JSON schemas, governance names, delegation behavior, and documentation remain synchronized with the existing tools and Spec #4 contracts.

## Scope

- Add four minimal Strands `@tool` wrappers and one `REGISTERED_TOOLS` list.
- Add behavior tests for imports, metadata, schemas, signature parity, direct delegation, and docstring secret safety.
- Assign `tool_call` audit ownership to the orchestrator in observability documentation.
- Mark Spec #5 complete and record its three exact known-debt items in project status.

## Constraints

- Follow RED → GREEN → TRIANGULATE → REFACTOR with `uv run pytest`.
- Tests must not call the network, Jev, DuckDB, or SQLite.
- Wrappers contain only direct delegation and preserve original signatures/defaults/nullability.
- Do not modify `tools/*.py`, `governance/`, services, configuration, or policy.
- Keep production and repository-facing artifacts in English, following current project conventions.
- Use Strands 1.57.1 behavior already locked by the repository; add no dependency.
- Keep each completed task as a reviewable Conventional Commit on `feat/spec-05-strands-tools`.

## Tasks

- [x] **T1 — Register and verify the four Strands tools**
  - RED observed: focused collection failed because `agent.tools` did not exist.
  - GREEN/TRIANGULATE: added four direct wrappers, registration, public imports, and 25 behavior tests covering the reviewed contract.
  - Checks: 25 focused and 431 unit tests passed; scoped Ruff check/format and `git diff --check` passed; independent verification PASS.
  - Commit: `0a70ddbe2cdf5577d175cf484c7660fd8861603a` (`feat(agent): register Strands banking tools`).
- [x] **T2 — Update ownership and project status documentation**
  - Applied the narrow non-behavioral TDD exception; no artificial RED test was created.
  - Updated exact-once `tool_call` ownership, Spec #5 completion state, and all three required debt entries.
  - Checks: targeted readback/grep and `git diff --check` passed; independent verification PASS.
  - Commit: `bbf31df140bc8ff63121e2c0f92aa6e67321b2af` (`docs: record Strands tool registration`).
- [x] **T3 — Run final acceptance and close Spec #5**
  - Ran every acceptance command from the spec and confirmed prohibited files remain unchanged from `6e34a15`.
  - Checks: 25 focused and 431 unit tests passed; scoped Ruff check/format and commit-range diff check passed; independent final verification PASS.
  - Commit: `a132245866cfb98eac6d75562c7669a9df37e5ca` (`test(agent): verify Strands tool registration`).

## Acceptance Criteria

- Every criterion in `docs/specs/spec_05.md` section 15 is satisfied.
- `REGISTERED_TOOLS` contains exactly four unique wrappers synchronized with `ALLOWED_TOOLS` and `TOOL_ARG_CONTRACTS`.
- Wrapper signatures, defaults, nullability, generated JSON types, metadata, docstrings, and delegation match the reviewed contract.
- Tests perform no network, Jev, DuckDB, or SQLite work.
- Original tools and governance code remain unchanged.
- Observability assigns exactly one `tool_call` event to the orchestrator.
- STATUS marks Spec #5 complete and includes all three section 17 debt entries.

## Progress

- Completed: T1, T2, T3.
- Active task: none.
- Branch: `feat/spec-05-strands-tools`.
- Exploration: completed by `gentle-ai-explore`; no implementation blocker found.
- Review workload: T1 is one cohesive 403-line work unit (including 338 test lines), slightly above the 400-line guide; keep it unsplit because separating its contract tests would break work-unit cohesion. Record a `size:exception` if delivered as one PR.
- Engram mirror: synchronized as observation 107.

## Verification Evidence

- Test runner resolved from `pyproject.toml`: pytest via `uv run pytest`.
- Strands dependency is already locked at 1.57.1.
- Existing tests use plain pytest, parametrization, and mocks.
- T1 RED: `uv run pytest tests/unit/agent/test_tools.py -q` exited 2 because `agent.tools` was absent.
- T1 GREEN: focused suite reached 20 passed; triangulation finished at 25 passed.
- T1 regression: `uv run pytest tests/unit -q` → 431 passed.
- T1 quality: scoped Ruff check passed; format check reported 4 files formatted; `git diff --check` passed.
- T1 independent verification: PASS; wrappers are one-return delegates, external I/O is mocked, prohibited files unchanged, and the Strands 1.57.1 nullable-schema restoration is correctly covered.
- T1 runtime harness: N/A because the governed Agent runtime belongs to a later spec.
- T1 rollback boundary: revert commit `0a70ddbe2cdf5577d175cf484c7660fd8861603a`.
- T2 documentation-only TDD exception: no meaningful executable RED exists for ownership/status prose.
- T2 structural validation: targeted readback and grep confirmed exact-once orchestrator ownership, completion state, and all three exact debt entries.
- T2 quality: `git diff --check -- docs/observability.md docs/STATUS.md` passed.
- T2 independent verification: PASS with `docs/observability.md:108,113` and `docs/STATUS.md:58,77,101,103,105,111` evidence.
- T2 runtime harness: N/A because this task changes documentation only.
- T2 rollback boundary: revert commit `bbf31df140bc8ff63121e2c0f92aa6e67321b2af`.
- T3 final acceptance: 25 focused and 431 unit tests passed; scoped Ruff check and format check passed; `git diff --check 6e34a15..HEAD` passed.
- T3 scope audit: only the expected agent, test, and documentation paths changed; original tools, governance, services, config, and policy remain unchanged.
- T3 independent verification: PASS; no checks skipped or pending.
- T3 runtime harness: N/A because governed Agent orchestration belongs to a later spec; mocks prove delegation without external I/O.
- T3 rollback boundary: revert T1 and T2 commits; T3 is an empty verification-evidence commit.
- Delivery workload: 153 code lines, 250 test lines, and 36 documentation diff lines (439 total). The feature is cohesive; use a `size:exception` rather than splitting contract tests from behavior if opened as one PR.

## Next Step

Run native review for the completed committed feature slice when offered, then report the verified outcome and delivery options.
