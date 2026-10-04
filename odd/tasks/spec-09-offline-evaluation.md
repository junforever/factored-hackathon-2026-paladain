# Spec 09 — Offline held-out evaluation

Repository locator: `odd/tasks/spec-09-offline-evaluation.md`

## Objective

Implement `docs/specs/spec_09.md` as a deterministic, isolated offline held-out evaluation pipeline using strict RED → GREEN → TRIANGULATE → REFACTOR development.

## Problem and why

The banking agent has governed runtime behavior but no reproducible held-out evaluation harness. The hackathon needs measurable safe automated resolution, containment, escalation quality, unsafe-outcome detection, latency, segmentation, and deterministic reports without using production state, real Jev, real models, or network access in tests.

## Scope

- Add typed fail-fast evaluation configuration, case models, manifests, coverage, hashes, and leakage checks.
- Add internal SQLite path injection and bound model-facing tools without exposing filesystem paths.
- Add only the optional `tools` seam to `BankingOrchestrator`.
- Add a recording evaluation sink and one `spawn` worker process per case.
- Add deterministic result classification, aggregate and segmented metrics, reports, and CLI.
- Add held-out/development fixtures that satisfy the normative contracts.
- Update `docs/STATUS.md` only after the acceptance gate passes.

## Constraints

- Follow `docs/specs/spec_09.md` exactly; no product decision is open.
- Strict TDD: observe meaningful RED before production behavior, then GREEN, alternate cases, and refactor while green.
- Use `uv run pytest`; tests must not use network, real Jev, or a real model.
- Keep `app/bootstrap.py`, governance argument contracts, and model-facing tool schemas unchanged.
- Never expose `state_dir`, `db_path`, PAN, CVV, credentials, raw exceptions, or internal paths in schemas, audit payloads, or reports.
- Use `product_id` as the reliable transaction link.
- Prefer stdlib and existing dependencies; add no dependency unless the spec makes it unavoidable.
- Generated technical artifacts are English; existing repository documentation conventions may remain Spanish.
- No commit, push, PR, or merge without explicit user authorization.

## Delivery forecast

Estimated authored change is well above 400 lines because the normative feature includes ten modules, tests, 80 case fixtures, manifests, configuration, and status documentation. Strategy: `ask-on-risk`. Implementation may proceed uncommitted; before any commit/PR, obtain explicit authorization and choose review slices by the work units below.

## Tasks

- [x] **S09-T1 — Configuration, cases, manifests, and independence**
  - Route: delegated writer; trigger: multiple non-trivial production, test, config, and fixture files.
  - Added strict typed config/case/manifests, secure project-root paths, SHA-256 identity, exact coverage, and all development/held-out leakage checks.
  - Added deterministic 50-case held-out and 30-case development fixtures with matching manifests and the normative `configs/eval.yaml`.
  - TDD evidence: RED was missing `evaluation.cases`; GREEN and triangulation finished with 49 focused tests passing.
  - Independent verification: 49 tests passed; Ruff check/format passed after one formatting-only correction; both hashes and fixture counts matched.
  - Runtime harness: N/A; process execution belongs to later work units.
  - Rollback boundary: the nine S09-T1 config/case/manifest/test files listed in the work-unit handoff.
  - Commit evidence: none; pending explicit authorization.

- [x] **S09-T2 — Isolated services, bound tools, and orchestrator seam**
  - Route: delegated writer; trigger: cross-cutting changes across services, tools, registration, orchestrator, and tests.
  - Added optional internal SQLite file injection, closure-bound evaluation tools with identical schemas, and the exact validated immutable orchestrator `tools` seam.
  - TDD evidence: RED was missing the evaluation factory and bound tool builder; GREEN/triangulation finished with 70 focused tests passing.
  - Independent verification: 70 tests passed; Ruff check/format passed after one Ruff-only correction; bootstrap/governance/observability contracts remained unchanged.
  - Runtime harness: N/A; process execution belongs to later work units.
  - Rollback boundary: the ten S09-T2 service/tool/orchestrator/factory/test files listed in the work-unit handoff.
  - Commit evidence: none; pending explicit authorization.

- [x] **S09-T3 — Recording sink and child worker contract**
  - Route: delegated writer; trigger: multiple production/test files and process-safe serialization behavior.
  - Added canonical `tool_call.payload` recording, defensive filtering/copies, secret/path redaction, JSON-safe worker request/result envelopes, and a top-level spawn-picklable child entrypoint.
  - TDD evidence: RED was missing sink/worker modules, then exposed pipe closure and three security/bounds edge cases; GREEN/triangulation finished with 66 focused tests passing.
  - Contract correction: user selected a calculated fail-fast lower bound; `case_id` is capped at 128 characters and `max_result_bytes` is at least 873 bytes, covering 105 fixed bytes plus 128 worst-case six-byte JSON escapes.
  - Independent verification: 66 focused and 71 evaluation tests passed; Ruff passed; envelope math, path/secret redaction, spawn pickling, pipe closure, and exact DB filenames verified.
  - Runtime harness: actual spawn child test passed with fakes; canonical parent harness belongs to S09-T4.
  - Rollback boundary: sink/worker/package exports/tests plus the narrow config/case/spec correction.
  - Commit evidence: none; pending explicit authorization.

- [x] **S09-T4 — Parent-owned process lifecycle and timeouts**
  - Route: delegated writer; trigger: multiprocessing lifecycle and cleanup correctness.
  - Added one fresh non-daemon Windows-compatible spawn child per case, provisional envelopes, bounded validation, monotonic deadline/grace/terminate/kill, mandatory join/liveness checks, parent-only cleanup, and strict sequential execution.
  - TDD evidence: RED was missing runner; later microcycles exposed missing exports and grace draining; GREEN/triangulation finished with 22 runner tests.
  - Correction: valid bounded Unicode/slash case IDs now round-trip exactly; only malformed unvalidated identities use the sanitized fallback.
  - Independent verification: 95 evaluation tests, Ruff, real spawn lifecycle, identity boundary, and all parent ordering/abort invariants passed.
  - Runtime harness: real spawn test observed fresh distinct PIDs, non-daemon children, exclusive temporary directories, no overlap, and cleanup.
  - Rollback boundary: runner/package export/tests plus the narrow worker identity/spec clarification.
  - Commit evidence: none; pending explicit authorization.

- [x] **S09-T5 — Classification and metrics**
  - Route: delegated writer; trigger: substantial deterministic business logic and tests.
  - Added four deterministic unsafe predicates, exhaustive automation/escalation outcomes, SAR, containment, global/segment metrics, exact inclusive p50/p95, and unavailable cost fields.
  - TDD evidence: RED was missing classification; triangulation exposed floating interpolation drift; exact rational interpolation produced GREEN with 34 focused tests.
  - Independent verification: all formulas, denominators, canonical evidence restrictions, BLOCK handling, edge cases, 129 evaluation tests, and Ruff passed after one lint/format-only correction.
  - Runtime harness: N/A; classification and metrics are pure deterministic in-process logic.
  - Rollback boundary: classification module, exports, and tests.
  - Commit evidence: none; pending explicit authorization.

- [x] **S09-T6 — Reports and CLI**
  - Route: delegated writer; trigger: multiple production/test files and public execution boundary.
  - Added deterministic strict JSON/Markdown generation, aligned evidence/classification validation, paired atomic persistence with rollback, safe CLI overrides/errors, and the module entry point.
  - Added the exact public `EvaluationDependencies`/`build_evaluation_dependencies` API and refactored the worker to use it instead of duplicate private composition.
  - TDD evidence: RED was missing report/CLI modules; a later RED exposed incomplete paired rollback; public factory API tests also began RED. GREEN/triangulation finished with 38 focused tests.
  - Independent verification: 150 evaluation tests, Ruff, public API/identity probes, atomic/report invariants, and canonical fake-only module pipeline passed.
  - Runtime harness: canonical `python -m` boundary and ordered pipeline exercised with fakes; production execution intentionally deferred because it invokes real model/Jev dependencies.
  - Rollback boundary: report/CLI/module/export/tests plus the public dependency factory/worker integration.
  - Commit evidence: none; pending explicit authorization.

- [x] **S09-T7 — Full acceptance gate and status update**
  - Route: delegated verifier for full commands; parent applied only the verified documentation updates.
  - Final GREEN: 150 evaluation tests, 65 affected-agent tests, 984 unit tests, and 996 full repository tests passed; Ruff check, Ruff format, diff check, manifests/hashes/coverage/leakage, public APIs, tool schemas, real spawn lifecycle, and fake canonical pipeline passed.
  - Updated `docs/STATUS.md` only after the gate passed; it records that the production model/Jev command was intentionally not executed and no reports were generated.
  - Native review preflight: no authority was created because the complete uncommitted candidate exceeded the provider lens context budget; the provider requires smaller committed review slices for a retry.
  - Rollback boundary: `docs/STATUS.md` and the exact-inventory line in `docs/specs/spec_09.md` are the final documentation-only changes.
  - Commit evidence: none; commit/delivery operations were not explicitly authorized.

## Acceptance criteria

- Every normative requirement in `docs/specs/spec_09.md` has behavior-level coverage or a justified structural check.
- Each case receives distinct temporary card/escalation SQLite files and a fresh `spawn` child.
- Timeout and every exit path join the child before cleanup or the next case.
- No internal path appears in model-facing schemas, governance payloads, or audit events.
- Held-out identity, minimum coverage, and development leakage checks are deterministic and fail closed.
- Metrics and reports derive from canonical recorded evidence and match the spec formulas.
- `uv run python -m ai_banking_customer_service.evaluation --config configs/eval.yaml` is the public entry point.
- Required focused tests, full unit tests, Ruff checks, and structural checks pass.
- `docs/STATUS.md` reflects only verified completion.

## Progress and evidence

- 2026-10-03: Read-only exploration completed; spec is implementation-ready and exact runner resolved as `uv run pytest`.
- 2026-10-03: Created branch `feature/spec-09-offline-evaluation` before repository writes.
- 2026-10-03: S09-T1 completed with 49 focused tests, Ruff, manifest hashes, fixture composition, and independent verification passing.
- 2026-10-03: S09-T2 completed with 70 focused tests, Ruff, contract-preservation checks, and independent verification passing.
- 2026-10-03: S09-T3 completed with 71 evaluation tests, Ruff, spawn/serialization/security checks, and independent verification passing.
- 2026-10-03: S09-T4 completed with 95 evaluation tests, Ruff, real spawn lifecycle, timeout/cleanup/order checks, and independent verification passing.
- 2026-10-03: S09-T5 completed with 129 evaluation tests, exact metric/percentile checks, Ruff, and independent verification passing.
- 2026-10-03: S09-T6 completed with 150 evaluation tests, Ruff, public API/identity probes, report/CLI checks, and independent verification passing.
- 2026-10-03: S09-T7 completed; 996 full tests and every acceptance/structural gate passed, then `docs/STATUS.md` was updated and independently verified.
- Native review: preflight stopped with `lens_context_budget_exceeded`; no lineage/authority was created. Retry requires smaller reviewable committed slices.
- Commits: none; commit operations require explicit user authorization.

## Next step

Obtain explicit commit authorization and split the oversized candidate into reviewable work-unit commits before retrying native review or preparing delivery.
