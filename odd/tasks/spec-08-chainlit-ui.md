# Spec 08 — Chainlit UI

Repository locator: `odd/tasks/spec-08-chainlit-ui.md`

## Objective

Implement `docs/specs/spec_08.md` as a thin, fail-closed Chainlit 2.12 UI over the existing banking orchestrator, using strict RED → GREEN → TRIANGULATE → REFACTOR development.

## Problem and why

The project has a complete orchestrator but no demo UI. The hackathon needs a safe Spanish/Portuguese interaction layer that preserves orchestrator governance, handles cancellation and late completion correctly, and never leaks sensitive inputs or exceptions.

## Scope

- Add typed UI/composition settings and documented environment defaults.
- Add fail-closed Chainlit startup configuration validation.
- Add the real composition root and lazy orchestrator factory seam.
- Add localized UI helpers and exhaustive result rendering.
- Add per-session active/pending turn state, deadlines, cancellation, monitoring, and reconciliation.
- Add unit, contract, and loopback smoke coverage.
- Update `docs/STATUS.md` only after the required checks pass.

## Constraints

- Follow `docs/specs/spec_08.md` exactly; no new product decisions are open.
- Strict TDD: observe a meaningful RED before each production behavior, then GREEN, alternate cases, and refactor while green.
- UI remains thin: no policy, governance, audit emission, direct service calls, or Jev calls.
- Reuse the exact dispute-context loader and one shared `CompositeAuditSink` identity.
- Use Chainlit's reserved `cl.user_session["id"]`; never synthesize session IDs.
- Fail closed on unsafe/missing TOML configuration and on unknown actions.
- Keep logs allowlisted; never log user text, responses, raw exceptions, credentials, PAN, CVV, or tracebacks.
- Generated technical artifacts remain in English except normative localized Spanish/Portuguese UI copy.
- No dependency or lockfile changes; retain `chainlit==2.12.0` and `requests==2.32.5`.
- No commit, push, PR, or merge without explicit user authorization.

## Delivery forecast

Estimated authored change: 1,200–1,800 lines including tests. Delivery strategy: `ask-on-risk`. This exceeds the ~400-line review heuristic; if commits/PR delivery are authorized, ask once for the required chain strategy before the first work-unit commit.

## Tasks

- [x] **S08-T1 — Configuration, startup safety, and composition root**
  - Route: delegated writer; trigger: multiple non-trivial production and test files.
  - Added the six typed Settings fields, validators, resolved audit paths, and `.env.example` defaults.
  - Added `.chainlit/config.toml` and fail-closed stdlib TOML validation at UI import/startup.
  - Added lazy/injectable orchestrator construction in `app/bootstrap.py` with the exact Spec 08 dependency order and shared audit sink identity.
  - TDD evidence: RED observed 20 configuration failures plus missing `app` module collection failures; GREEN observed 63 focused tests. Independent verification repeated 63 passes, Ruff check passed, Ruff format check passed; parent spot check observed 3 bootstrap tests pass.
  - Native assessment: unavailable because untracked files require explicit declaration; per returned plan, independent verification was completed.
  - Commit evidence: none; commit operation not explicitly authorized.

- [x] **S08-T2 — Localized UI helpers and safe rendering**
  - Route: delegated writer; trigger: multiple non-trivial production and test files.
  - Added language-aware validation/templates, reserved session/customer accessors, safe sender, exhaustive `TurnAction` mapping, pending rendering helpers, and fail-closed unknown action behavior.
  - Verified all UI-owned output uses the safe sender and logs use only allowlisted codes/metadata.
  - TDD evidence: RED observed missing `app.ui_helpers`; GREEN observed 32 focused tests after alternate invalid-pending and Chainlit-access cases. Independent verification repeated 32 helper tests and 12 regression tests, Ruff check/format passed, and structural safety checks passed; parent spot check repeated 32 tests.
  - Native assessment: unavailable because untracked files require explicit declaration; per returned plan, independent verification was completed.
  - Follow-up: direct Chainlit startup compatibility of the minimal committed TOML remains assigned to S08-T4.
  - Commit evidence: none; commit operation not explicitly authorized.

- [x] **S08-T3 — Turn bridge, cancellation, monitoring, and reconciliation**
  - Route: delegated writer; trigger: multiple non-trivial files and concurrency behavior.
  - Added `ActiveTurn`/`PendingTurnResult`, identity-safe state transitions, one retained `asyncio.Task`, shielded dual deadlines, cooperative cancellation, strong monitor references, pending claims, and late-result reconciliation.
  - Added `on_message` and `on_stop` handlers with the normative admission order and no duplicate orchestrator calls.
  - TDD evidence: RED observed missing `ActiveTurn`; GREEN observed 27 focused tests after stale-identity, late-monitor-exception, and handler-registration triangulation. Independent verification repeated 27 bridge tests and 44 regressions, Ruff check/format passed, and all bounded concurrency invariants were confirmed; parent spot check repeated 27 tests.
  - Native assessment: unavailable because untracked files require explicit declaration; per returned plan, independent verification was completed.
  - Commit evidence: none; commit operation not explicitly authorized.

- [x] **S08-T4 — Chainlit contracts and portable smoke**
  - Route: delegated writer; trigger: multiple test files and process/loopback behavior.
  - Added Chainlit 2.12 API contract tests and a portable isolated-cwd loopback smoke without real Jev, models, network services, or credentials.
  - Startup compatibility: RED reproduced missing Chainlit generated-version metadata and required UI name; `.chainlit/config.toml` received only those required fields while preserving `unsafe_allow_html = false`.
  - Smoke TDD: RED reproduced early child exit and then repository-root `chainlit.md` generation; the child now runs in `tmp_path` with repository import access, bounded readiness/termination, ephemeral loopback port, and dummy credentials. The generated artifact was removed and absence is asserted.
  - GREEN evidence: 5 contract tests, 1 smoke test, and 77 combined app/contract/smoke tests passed; independent verification repeated all checks, confirmed no artifact leak, and Ruff check/format passed. Parent spot check repeated the smoke and artifact-absence check.
  - Warning: existing third-party Traceloop/Pydantic class-based-config deprecation remains.
  - Native assessment: unavailable because untracked files require explicit declaration; per returned plan, independent verification was completed.
  - Commit evidence: none; commit operation not explicitly authorized.

- [x] **S08-T5 — Full quality gate and status update**
  - Route: delegated verifier for full commands; writer used only for verified fixes and the final status update.
  - Final GREEN: 78 focused app/contract/smoke tests and 842 full-suite tests passed; Ruff check, Ruff format, `git diff --check`, and repeated artifact-absence checks passed.
  - Updated `docs/STATUS.md` with verified scope, the in-memory durability limitation, and the existing third-party Traceloop/Pydantic deprecation warning.
  - Native review: medium-tier `review-reliability` approved and acknowledged; authority burned for target `sha256:cb04a0b90abef443ea9e76f42e1bf9453319844e14ff2fde3f84de0235005ef5`. Informational advisory `R3-smoke-port-race` remains non-blocking follow-up work.
  - Commit evidence: none; commit operation not explicitly authorized.

## Acceptance criteria

- Every normative requirement in `docs/specs/spec_08.md` has behavior-level coverage or an explicitly justified structural check.
- Required focused app, contract, and smoke tests pass.
- Full `uv run pytest -q` passes.
- `uv run ruff check app/ tests/unit/app/ tests/contract/app/ tests/smoke/` passes.
- `uv run ruff format --check app/ tests/unit/app/ tests/contract/app/ tests/smoke/` passes.
- No real Jev/network/model/credential dependency is used by unit or contract tests.
- `docs/STATUS.md` reflects only verified completion.

## Progress and evidence

- 2026-04-02: Read-only mapping completed. Exact runner is `uv run pytest`; Spec v5 reports no open product decisions.
- 2026-04-02: TypeSafe live documentation and Python SDK reference consulted; implementation will reuse the existing Jev integration rather than invent API calls.
- 2026-04-02: Chainlit docs confirmed `user_session` reserves `id` as the session ID and async handlers send via `await cl.Message(...).send()`.
- 2026-04-02: Final quality gate passed with 78 focused and 842 full-suite tests; Ruff and structural checks passed.
- 2026-04-02: Native reliability review approved and exact acknowledgement burned the authority; one informational smoke-port race advisory remains non-blocking.
- Commits: none; commit operations require explicit user authorization.

## Next step

Await explicit authorization for commit/delivery planning. Because the candidate is approximately 2,497 changed lines, choose a chained delivery strategy before any commit or PR work.
