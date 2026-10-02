# Repository Ruff Cleanup

## Objective

Restore a green repository-wide `uv run ruff check .` without changing runtime behavior.

## Problem

The repository has 16 pre-existing Ruff violations across nine files: 15 line-length (`E501`) violations and one import-order (`E402`) violation.

## Why

A permanently failing global lint gate hides newly introduced quality regressions and weakens verification for subsequent specs.

## Scope

- Reformat long SQL, comments, error messages, and response strings without changing their values or semantics.
- Resolve the late import in the escalation tool smoke-test script while preserving its `sys.path` bootstrap behavior.
- Verify repository-wide Ruff, full tests, and whitespace integrity.

## Constraints

- No dedicated product spec is required; this is bounded maintenance.
- Preserve exact user-facing strings, persisted text, SQL semantics, and tool behavior.
- Do not change dependencies, configuration, policy, or business rules.
- Use the observed failing `uv run ruff check .` result as the RED quality-gate baseline; no artificial behavior test is needed for mechanical formatting.
- Do not commit unless the user explicitly authorizes commits.

## Tasks

- [x] **T1 — Fix the 16 Ruff violations mechanically**
  - Resolved 15 `E501` violations and one `E402` violation across the nine classified files.
  - Preserved runtime strings, SQL semantics/whitespace, comments, and post-bootstrap project imports.
  - Check: repository-wide Ruff passes; independent verification PASS.
- [x] **T2 — Verify behavior and candidate integrity**
  - Full tests, repository-wide Ruff, and `git diff --check` passed.
  - Independent verification confirmed runtime strings, SQL semantics, comments, and import bootstrap behavior are preserved.
  - Native reliability review approved and acknowledged the candidate without findings.

## Acceptance Criteria

- `uv run ruff check .` passes with zero violations.
- `uv run pytest -q` passes.
- `git diff --check` passes.
- User-facing and persisted strings remain byte-for-byte equivalent at runtime.
- SQL queries/comments retain their intended semantics.
- The smoke-test script imports correctly after its path bootstrap.
- Only the nine classified source/script files plus this task record are changed.

## Progress

- Completed: T1, T2.
- Active task: none.
- Branch: `chore/ruff-cleanup`.
- RED baseline: `uv run ruff check .` exited 1 with 16 violations (15 E501, 1 E402).
- Commit evidence: pending; commits are not authorized by the user.

## Verification Evidence

- Read-only classification confirmed all findings are mechanical and outside the completed Spec #4 candidate.
- T1 RED: `uv run ruff check .` exited 1 with 15 E501 and one E402.
- T1 GREEN: `uv run ruff check .` → All checks passed.
- T1 regression: `uv run pytest -q` → 406 passed.
- T1 integrity: `git diff --check` passed; AST/literal comparison confirmed runtime string, f-string, and SQL equivalence.
- T1 E402 correction: moved both project imports together after the required `sys.path.insert` bootstrap; no suppression added.
- T1 independent verification: PASS; exactly the nine authorized files plus this task record are changed.
- T1 runtime harness: N/A because this is lexical formatting/import ordering and the smoke script would mutate SQLite state.
- T1 rollback boundary: revert the nine classified files together without affecting task tracking or behavior.
- T2 independent verification: repository-wide Ruff green, 406 tests passed, diff integrity clean, and exactly nine source/script files plus this task record changed.
- Native review approved and acknowledgement burned lineage `review-2ddbd3ef47b3135b` with no findings.
- T2 runtime harness: N/A because the cleanup is lexical and the standalone smoke script would mutate SQLite state.
- T2 rollback boundary: revert the nine mechanical cleanup files and remove this task record.

## Next Step

User may inspect the uncommitted diff and explicitly authorize a commit when ready.
