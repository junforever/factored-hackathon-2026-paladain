# Spec 09A2 — Safe Evidence Projection

## Objective

Project the frozen Spec 09A1 canonical runtime evidence into offline evaluation case outcomes and render it with exact JSON/Markdown semantic parity, without changing runtime behavior or material case classification.

## Problem

Evaluation currently transports audit events but omits canonical evidence from classifications and reports. This prevents causal inspection and leaves no bounded, privacy-safe representation in report outputs.

## Why

A deterministic, validated projection is required before Spec 09A3 can use the visible causal matrix. The projection must preserve evidence semantics while rejecting malformed or prohibited data.

## Authorization and readiness

- The user explicitly stated on 2026-10-07 that `docs/specs/spec_09a2.md` has been reviewed and is ready for implementation.
- `docs/STATUS.md` records Spec 09A1 as accepted and 09A2 as unlocked.
- The stale `IMPLEMENTATION-BLOCKED` header in the spec is therefore treated as superseded by the explicit user authorization and current project status; the spec body remains binding.

## Scope

- Add a bounded, trailing-compatible canonical evidence projection to offline evaluation classifications.
- Validate only the frozen 09A1 evidence contract and copy only allowlisted fields.
- Render the same structured projection in JSON and Markdown with identical count, values, nulls, invalidation/truncation markers, and order.
- Preserve historical report readability when canonical evidence is absent.
- Update `docs/STATUS.md` with the verified result and remaining work.

## Non-goals

- No runtime event producer, hook, orchestrator, governance, tool, service, worker wire, public schema, manifest, corpus, prompt, configuration, or dependency changes.
- No change to unsafe/SAR/success classification, policy, terminals, or tool execution.
- No inference, enrichment, aliases, summaries, hashing, or truncation of prohibited values.
- No real development/held-out evaluation, network, model, or Jev execution.

## Constraints

- Strict TDD: observe RED, implement minimum GREEN, triangulate, then refactor while focused tests remain green.
- Reuse the frozen validation contract in `observability/contract.py`; do not redefine 09A1.
- Maximum 16 projected occurrences and 8 KiB serialized evidence per case.
- One offline-evaluation runtime domain only.
- Forecast: 190–270 authored changed lines, below the 300-line Spec 09A2 gate and the ~400-line delivery-risk threshold.
- Delivery strategy: `ask-on-risk`; no oversized-delivery choice is currently required.

## Allowed implementation surfaces

- `src/ai_banking_customer_service/evaluation/classification.py`
- `src/ai_banking_customer_service/evaluation/report.py`
- `tests/unit/evaluation/test_classification.py`
- `tests/unit/evaluation/test_report.py`
- `docs/STATUS.md`
- `odd/tasks/spec-09a2-safe-evidence-projection.md` (parent-maintained tracking only)

## Tasks

- [x] **09A2-1 — Implement safe canonical evidence projection and report parity** (`done`)
  - Route: delegated to `gentle-ai-worker` because the bounded change touches multiple non-trivial files.
  - RED: add the smallest behavior-level tests proving canonical evidence is omitted today and JSON/Markdown parity/privacy/bounds fail.
  - GREEN: implement only the validated, allowlisted projection and report rendering needed to pass.
  - TRIANGULATE: cover absent, one/many/over-limit, duplicate/homonymous attempts, all dimensions, adversarial order, strict booleans/nulls, unknown codes, malformed/oversized data, invalid/truncated markers, historical classifications, and prohibited fields.
  - REFACTOR: keep focused tests green; avoid a new rendering framework.
  - Acceptance: no material classification changes; deterministic output; exact JSON/Markdown semantic parity; prohibited values absent; historical reports readable.
  - Verification: focused evaluation tests, full unit evaluation suite, Ruff check, Ruff format check, and `git diff --check`.
  - Work-unit commit: `22afd4a08d295fcd3d6d63bae951a8ae8a6f29aa` (`feat(evaluation): project canonical evidence safely`).
  - Native review: `review-211925fc76b285f2` approved and acknowledged; authority burned.

## Acceptance criteria

- Every frozen evidence dimension is projected without semantic transformation.
- JSON and Markdown contain identical occurrence count, ordinal, tool name, codes, booleans, nulls, invalidation/truncation state, and order.
- Missing evidence stays absent and never becomes positive evidence.
- Malformed, unknown, oversized, and truncated evidence remains fail-closed without breaking report generation.
- Prohibited banking, identity, provider, model-text, free-text, path, and exception data appears in neither format.
- Existing case classification behavior and runtime behavior remain unchanged.
- Existing reports/classifications without canonical evidence remain readable.

## Verification evidence

- Exploration: current worker/runner transport audit events without loss; classification and reports previously omitted canonical evidence.
- RED: focused collection failed because `CaseClassification` did not accept `canonical_evidence`.
- GREEN: focused canonical-evidence tests passed (`2 passed`).
- Triangulation/refactor: bounds and unknown-version tests first failed, then all canonical-evidence tests passed (`3 passed`); final focused suite passed (`80 passed`).
- Writer verification: focused tests `80 passed`; evaluation unit suite `225 passed`; Ruff check passed; Ruff format check reported 4 files already formatted; `git diff --check` passed.
- Independent verification: repeated the same five commands successfully (`80 passed`, `225 passed`, Ruff clean/formatted, diff clean) and found no acceptance blocker.
- Scope/readback: 280 authored implementation lines across the five planned files, within the 300-line spec gate; only the allowed task tracker is additionally untracked.
- Native assessment: initially unassessable because the intended task tracker is untracked; conservative independent verification completed as required.
- Native review: reliability review `review-211925fc76b285f2` approved; acknowledgement consumed revision `sha256:7df76e2b31b5fb8ae23d3147d0e9df156d788dfb07b16b4b97d20a9b24704c27` and burned authority.

## Progress

- 2026-10-07: Read-only exploration completed. Concrete surfaces reduced to five implementation files plus this tracker.
- 2026-10-07: Forecast established at 190–270 authored lines in one offline-evaluation domain.
- 2026-10-07: Feature branch `feat/spec-09a2-canonical-evidence` created from `main` at `976d779`.
- 2026-10-07: Strict TDD implementation completed with observed RED, GREEN, triangulation, and refactor evidence.
- 2026-10-07: Writer and independent verification passed all authorized commands; no acceptance blocker was found.
- 2026-10-07: User explicitly authorized work-unit commit `22afd4a` and native review.
- 2026-10-07: Native reliability review `review-211925fc76b285f2` approved the committed candidate and its acknowledgement burned authority.

## Next step

Spec 09A2 is complete. Spec 09A3 is unlocked for separate review and authorization; push, pull request creation, and merge remain user decisions.
