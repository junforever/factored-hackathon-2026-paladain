# Spec 07 Agent Orchestrator

## Objective

Implement the reviewed `docs/specs/spec_07.md` contract with strict test-driven development.

## Problem and Why

The project has tool wrappers, governance hooks, Jev-backed policy evaluation, and audit primitives, but it does not yet have the stateful Strands turn orchestrator required to safely understand, act, verify, persist, and escalate customer-service turns.

## Scope

- Add the deterministic language, signal, prompt, session, result-capture, and orchestration modules required by Spec 07.
- Extend governance and observability only where Spec 07 explicitly requires backward-compatible orphan propagation, composite audit behavior, and event validation.
- Add unit and Strands contract integration coverage.
- Update `docs/observability.md` and `docs/STATUS.md` atomically with verified behavior.

## Constraints

- Strict TDD: observe RED, implement minimum GREEN, TRIANGULATE material alternate cases, then REFACTOR while focused tests remain green.
- Exact runner: `uv run pytest`; no network, real Jev, or real model calls in unit/contract tests.
- Existing business tools, services, Spec 04 policy rules, and tool return contracts are out of scope.
- Hard policy remains in Python; Jev remains semantic defense in depth and fails closed.
- `product_id` remains the trusted transaction/customer-product link.
- Generated technical artifacts are written in English.
- Route all implementation tasks through one bounded writer at a time because each work unit spans multiple non-trivial files.
- No push, pull request, merge, or release is authorized.

## Delivery

- Branch at start: `docs/spec-07-v5` (already non-default).
- Delivery strategy: `auto-chain` with `chain_strategy=feature-branch-chain`, selected by the user.
- Forecast: approximately 2,000–3,000 authored changed lines, excluding generated files; this necessarily exceeds the 400-line review guide because the reviewed spec requires six production modules, contract extensions, thirteen test modules, and documentation updates.
- Work-unit commits: locally authorized; no push, pull request creation, merge, or release is authorized.
- Planned slices: one reviewable work-unit commit per task, grouped further only if a task cannot stand independently.
- T1 commits: `98f6eb5` (foundations) and `3e11422` (independent-verification corrections).
- T2 commit: `c5a5e91` (locked session memory and tests).
- T3 commit: `eb04d17` (normalized tool-result capture and tests).
- Native review boundaries: each authorized work-unit commit, or each selected PR slice.

## Tasks

- [x] **T1 — Implement deterministic orchestration foundations**
  - Route: delegated writer; multi-file write trigger.
  - Test-first surfaces: language detection, strict signal parsing, and system prompt contract.
  - Acceptance: focused unit tests observe RED then GREEN; no model or network dependency.

- [x] **T2 — Implement locked session memory**
  - Route: delegated writer; multi-file write trigger.
  - Test-first surfaces: per-session locking, TTL, FIFO trimming, deep-copy snapshots, persistence validation, and sanitization.
  - Acceptance: focused session tests observe RED then GREEN, including expiry and mutation-isolation cases.

- [x] **T3 — Capture normalized tool results**
  - Route: delegated writer; multi-file write trigger.
  - Test-first surfaces: Strands before/after tool callbacks, normalization, exceptions, cancellation, retries, and duplicate evidence.
  - Acceptance: focused capture tests observe RED then GREEN and preserve sensitive-action uncertainty.

- [ ] **T4 — Extend audit and governance compatibility**
  - Route: delegated writer; multi-file write trigger.
  - Test-first surfaces: composite audit sink, persistence errors, event validation, and keyword-only `orphaned` propagation through hooks and adapter entry points.
  - Acceptance: focused observability, hook, and adapter tests observe RED then GREEN; existing parent-event semantics remain unchanged.

- [ ] **T5 — Implement the stateful Strands orchestrator**
  - Route: delegated writer; multi-file write trigger.
  - Test-first surfaces: ephemeral Agent lifecycle, cancellation/exception precedence, action certainty, canonical facts/actions, output screening, localization templates, persistence, and terminal result types.
  - Acceptance: focused orchestrator tests observe RED then GREEN for normal, clarification, abstention, escalation, cancellation, and uncertain sensitive-action paths.

- [ ] **T6 — Verify Strands integration and close documentation**
  - Route: delegated writer for integration/docs; verifier routing follows native assessment and RDD state.
  - Test-first surfaces: installed Strands 1.57.1 hook/event contract integration.
  - Acceptance: required focused/full tests, Ruff checks, format check, documentation readback, and `docs/STATUS.md` update all pass.

## Acceptance Criteria and Checks

- `uv run pytest tests/unit/agent/ tests/integration/agent/ -q`
- `uv run pytest tests/unit -q`
- `uv run ruff check`
- `uv run ruff format --check`
- Every action result is verified before success is reported.
- Sensitive-action uncertainty overrides cancellation and pre-execution blocking where the spec requires it.
- Session locking spans snapshot through final persistence.
- Output never exposes PAN, CVV, credentials, raw exceptions, or hidden chain-of-thought.
- Audit and governance failures remain fail-closed.

## Progress

- Exploration complete: Spec 07 is implementation-ready and has no unresolved product decision.
- TypeSafe live documentation checked; the existing Jev integration shape remains valid and Spec 07 only extends internal orphan/audit propagation.
- Completed: T1 — Implement deterministic orchestration foundations.
- Completed: T2 — Implement locked session memory.
- Completed: T3 — Capture normalized tool results.
- Active task: none; T3 native review is pending before T4 starts.
- Engram mirror: observation 152.

## Verification Evidence

- Exploration handoff mapped required modules, current architecture, exact runner, file surfaces, and work-unit boundaries with repository line evidence.
- Spec readiness record reports final independent PASS and no remaining product decision.
- T1 RED: each new module initially failed test collection because it did not exist; focused regression additions later produced 3 expected failures for duplicate keys and prompt-policy leakage.
- T1 GREEN: 37 focused tests passed after minimal implementation and corrections.
- T1 lint/format: Ruff check passed and all 6 files were formatted.
- T1 independent verification: initial FAIL found duplicate-key acceptance and prompt hard-policy leakage; focused corrections were independently re-verified PASS.
- T1 parent spot check: 22 parser/prompt tests passed; `git diff --check` reported no whitespace errors.
- T1 native review: unavailable. Two fresh START attempts created no lineage because each fresh consent binding was immediately reported expired; the native assessment's fail-closed high-risk plan was satisfied by independent verification.
- T2 RED: the first session-manager test failed collection because the module did not exist; the expanded contract suite then exposed 28 expected failures.
- T2 GREEN: 40 session-manager tests passed after implementing validation, TTL, FIFO trimming, deep-copy isolation, sanitization, atomic one-shot persistence, and locking.
- T2 lint/format: Ruff check passed and both files were formatted.
- T2 independent verification: PASS with no contract gaps.
- T2 parent spot check: all 40 session-manager tests passed.
- T2 native review: approved and acknowledged (`review-62ecacb6b6efe3f5`). Two informational follow-ups were reported for late `SessionTurn.persist()` use and retained per-session lock entries; neither opened a correction or expands this feature scope.
- T3 RED: the first result-capture test failed collection because the module did not exist; duplicate-attempt triangulation later exposed an expected identity-order failure.
- T3 GREEN: 19 result-capture tests passed after implementing conservative normalization, callback capture, retry/duplicate preservation, governance-block evidence, and isolated snapshots.
- T3 lint/format: Ruff check passed and both files were formatted.
- T3 parent spot check: all 19 result-capture tests passed.

## Next Step

Run native review for the T3 committed range and follow its exact continuation.
