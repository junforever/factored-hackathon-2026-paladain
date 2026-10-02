# Spec 06 Review Advisories

## Objective

Resolve the two non-blocking reliability advisories from native review lineage `review-ec969246de93e771` as a separate strict-TDD candidate.

## Scope

- Reject non-finite `cost_usd` values in the audit event contract.
- Clear stale derived invocation state before processing a new invocation and preserve fail-closed cancellation state.

## Constraints

- Follow RED → GREEN → TRIANGULATE → REFACTOR.
- Keep changes limited to the two affected production modules and their existing unit tests.
- Do not alter the reviewed Spec #6 behavior beyond the advisory corrections.
- Close the work unit with a Conventional Commit on `feat/spec-06-governance-adapter`.

## Tasks

- [x] **T1 — Resolve both reliability advisories with regression tests**
  - RED: non-finite cost regression produced 2 failures/6 passes; stale-state cancellation regression produced 1 failure.
  - GREEN/TRIANGULATE: focused tests reached 112 passes; observability and agent suites reached 145 passes.
  - Checks: scoped Ruff check/format, diff check, and independent verification passed.
  - Commit: `f7547a04710fe0f8dcc009929356deefb9bd8ef6` (`fix(governance): close Spec 6 reliability advisories`).
- [x] **T2 — Record advisory resolution in project status**
  - Applied the passive-documentation TDD exception; no meaningful RED behavior test exists.
  - Added a dated `docs/STATUS.md` entry explicitly marking both advisories resolved and not pending for future specs.
  - Commit: included in `f7547a04710fe0f8dcc009929356deefb9bd8ef6`.
- [x] **T3 — Run acceptance and native review for the advisory candidate**
  - Acceptance: 112 focused and 597 unit tests passed; Ruff check, scoped format, diff check, and scope audit passed.
  - Native review: approved and acknowledged with no findings.
  - Commit: tracking evidence only; implementation candidate remains `f7547a04710fe0f8dcc009929356deefb9bd8ef6`.

## Acceptance Criteria

- `validate_event` rejects positive/negative infinity and NaN for `cost_usd`.
- Every new invocation removes stale derived governance keys before validation or adapter execution.
- Fail-closed cancellation leaves only the current invocation's conservative governance state.
- Focused and full unit tests, Ruff check, scoped format, and diff checks pass.

## Progress

- Completed: T1, T2, T3.
- Active task: none.
- Branch: `feat/spec-06-governance-adapter`.
- Native review advisories: `R3-nonfinite-cost`, `R3-stale-invocation-state`.
- Engram mirror: synchronized as observation 143.

## Verification Evidence

- T1 focused regression suite: 112 passed.
- T1 observability and agent suites: 145 passed.
- T1 quality: scoped Ruff check/format and diff check passed.
- T1 independent verification: PASS; all non-finite costs rejected and stale derived state cleared without removing orchestrator-owned context.
- T1 runtime harness: N/A beyond the project `uv` test runtime; live Jev/network execution is outside these boundaries.
- T1 rollback boundary: revert the four affected source/test files.
- T2 documentation exception: passive status text has no meaningful RED behavior test; targeted readback will be included in final verification.
- T2 rollback boundary: revert the advisory register entry in `docs/STATUS.md`.
- T3 full unit suite: 597 passed.
- T3 quality: Ruff check and scoped formatting passed; global formatting retains the same 11 pre-existing failures outside candidate paths.
- T3 native review: approved and acknowledged under lineage `review-45d3423718014bdf`, receipt revision `sha256:12b2f19b8d82a0b2218e9f674505a7a98b5f7601339385af61aa544f419335b5`; no findings.

## Next Step

Both advisories are resolved, documented as non-pending, verified, and natively approved. Delivery remains the user's decision.
