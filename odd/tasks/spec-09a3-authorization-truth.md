# Spec 09A3 — Authorization Evidence Truth

## Objective

Ensure `authorization_verified` reflects only the exact authorization decision returned for the `(principal, product_id)` pair of the same tool occurrence, while every missing, malformed, contradictory, or ambiguously correlated state remains false.

## Problem

The adapter calls the injected provider with exact identity arguments, but downstream observability reconstructs authorization evidence from context fields. The reviewed 09A1/09A2 event and projection contracts preserve that value without proving that each occurrence retained the provider decision and correlation correctly.

## Why

Authorization evidence is security-sensitive. Relationship, admission, tool success, and verified persistence must never synthesize authorization, and one occurrence must never inherit another occurrence's evidence.

## Authorization and readiness

- The user explicitly stated that `docs/specs/spec_09a3.md` is reviewed and ready for implementation.
- Specs 09A1 and 09A2 are accepted and frozen in `docs/STATUS.md`.
- A scoped assumption challenge found that the provider protocol signature alone did not document result binding.
- The user selected the normative contract that `authorize_product(principal, product_id)` returns exclusively the decision for that exact argument pair. Explicit identity fields are not added to the result.
- Missing, malformed, contradictory, duplicated, retried, or ambiguously correlated evidence remains fail-closed.

## Scope

- Freeze the exact-argument provider semantics at the existing adapter boundary.
- Reproduce the first causal authorization divergence through a fake lifecycle without injecting the final event boolean.
- Repair only the minimum authorization transport or association seam proven by RED.
- Preserve the frozen 09A1 event and 09A2 report projection shapes and privacy constraints.
- Update `docs/STATUS.md` with verified evidence.

## Non-goals

- No provider implementation, grant, banking policy, public schema, tool, terminal, missing-data, handoff, persistence, prompt, Jev, model, dependency, threshold, corpus, or evaluation-classification change.
- No development or held-out evaluation, network, model, or real Jev execution.
- No identity, provider payload, free text, or banking identifiers in audit/report output.

## Constraints

- Strict TDD: observe RED, implement minimum GREEN, triangulate, then refactor while focused tests remain green.
- Runner: `uv run pytest`.
- One primary runtime domain: authorization evidence transport/association.
- Pre-RED forecast: 220–310 authored lines. After the first RED, recalculate using concrete changed surfaces. Stop before production writes if the forecast exceeds 300 authored lines or requires a second primary runtime domain.
- Forecast is near but below the ~400-line delivery-risk threshold; delivery strategy remains `ask-on-risk`.
- No commit, push, PR, or merge without separate user authorization.

## Allowed implementation surfaces

- `src/ai_banking_customer_service/governance/adapter.py`
- `src/ai_banking_customer_service/agent/hooks.py`
- `src/ai_banking_customer_service/agent/result_capture.py`
- `src/ai_banking_customer_service/agent/orchestrator.py`
- `tests/unit/governance/test_adapter.py`
- `tests/unit/agent/test_hooks.py`
- `tests/unit/agent/test_result_capture.py`
- `tests/unit/agent/test_orchestrator.py`
- `docs/STATUS.md`
- `odd/tasks/spec-09a3-authorization-truth.md` (parent-maintained tracking only)

## Tasks

- [x] **09A3-1 — Preserve exact authorization truth end to end** (`done`)
  - Route: delegated to `gentle-ai-worker`; implementation touched multiple non-trivial files, followed by independent `gentle-ai-verify` verification.
  - RED: exercise the fake provider → adapter → hook → capture → orchestrator lifecycle and observe an exact authorization occurrence become false or an invalid occurrence become positive without directly injecting the final event boolean.
  - Gate: after RED, report concrete edit surfaces and final authored-line/domain forecast; stop if over 300 lines or more than one runtime domain.
  - GREEN: repair only the first proven boundary and document the exact-argument provider contract if needed.
  - TRIANGULATE: exact authorization; unauthenticated; denied product; unavailable/malformed provider; complaint/product/principal mismatch; absent/non-strict evidence; duplicate; retry; homonymous/interleaved calls; orphan lineage; failed audit; JSON/Markdown privacy and parity.
  - REFACTOR: avoid new provider abstractions or schema changes; keep focused checks green.
  - Acceptance: every occurrence carries only its causal authorization evidence; all negative/ambiguous states remain false; exact positive survives through event/report; frozen shapes, privacy, decisions, and terminals remain unchanged.
  - Verification: focused affected tests; frozen affected suites; Ruff check and format check for modified Python; `git diff --check`.
  - Work-unit commit: `c29443e9652e3211a9c073419b9733fedb7a076f` (`fix(agent): preserve per-occurrence authorization evidence`).
  - Native assessment: medium risk, 377 authored commit lines including this tracker, `reviewDue=false` (`under_budget`); review deferred to the PR slice.

## Acceptance criteria

- `ProductAuthorization` is normatively the decision for the exact provider call arguments.
- No relationship, admission, tool success, or persistence result synthesizes authorization.
- Exact positive authorization survives per-occurrence transport to canonical evidence and report projection.
- Missing, malformed, contradictory, duplicated, retried, orphaned, or ambiguous correlation remains false.
- Frozen 09A1/09A2 event/report shapes and privacy guarantees remain unchanged.
- No real evaluation, network, model, or Jev execution occurs.

## Verification evidence

- Exploration mapped the current provider call and downstream reconstruction/correlation seams.
- Independent assumption challenge established the missing semantic contract and prompted the user decision recorded above.
- RED: a denied provider occurrence inherited `authorization_verified=True` after a later allowed occurrence reused its homonymous `toolUseId`.
- Post-RED gate: 172 authored lines forecast, one authorization evidence transport/association runtime domain; implementation was allowed to proceed.
- GREEN: the focused lifecycle regression passed (`1 passed`).
- Triangulation/refactor: strict malformed booleans, bounded denied/unavailable states, exact positive survival, and homonymous overwrite passed (`9 passed`).
- Writer verification: affected suites `252 passed`; frozen evaluation suites `80 passed`; full unit suite `1279 passed`; Ruff check/format and `git diff --check` passed.
- Independent verification repeated every required command with the same passing counts and found no blocker or residual risk.
- Final implementation diff: 271 authored additions plus deletions across six tracked files, excluding this parent-owned tracker; within the 300-line gate and one runtime domain.
- Pre-commit native ASSESS was unassessable only because this intended tracker was untracked; the conservative independent-verifier plan was completed successfully.
- Work-unit commit `c29443e9652e3211a9c073419b9733fedb7a076f` contains the implementation, tests, status, and tracker.
- Post-commit native ASSESS classified the committed range from `125649e` as medium risk with 377 authored lines, `reviewDue=false`, reason `under_budget`; native review is deferred to the PR slice.
- No development/held-out evaluation, network, model, real Jev, push, PR, or merge occurred.

## Progress

- 2026-10-07: Read-only exploration completed; predecessors verified ready.
- 2026-10-07: User chose exact-argument result binding without adding provider-result identity fields.
- 2026-10-07: Created branch `feat/spec-09a3-authorization-truth` from `main` at `125649e`.
- 2026-10-07: ODD tracking initialized before source writes.
- 2026-10-07: Strict TDD observed RED, implemented the occurrence-local authorization snapshot and contradiction rejection, then passed focused, frozen, and full unit verification.
- 2026-10-07: Independent verification passed all six required checks; no blocker or residual risk was found.
- 2026-10-07: User authorized and created work-unit commit `c29443e9652e3211a9c073419b9733fedb7a076f`.
- 2026-10-07: Native assessment classified the commit as medium risk and deferred review to the under-budget PR slice.
- 2026-10-07: Parent-owned closure evidence was committed after explicit user authorization.

## Next step

Spec 09A3 is complete. Spec 09A4 may be reviewed separately. Push, PR creation, merge, and PR-slice native review remain separate user decisions.
