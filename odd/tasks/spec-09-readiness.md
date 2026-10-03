# Spec 09 implementation readiness

## Objective

Revise `docs/specs/spec_09.md` so its evaluation architecture, timeout lifecycle, metrics, reporting API, and acceptance criteria are internally consistent and implementable against the current repository contracts.

## Problem

Spec v3 fixes earlier metric issues but still exposes internal filesystem state through model-facing tools, confuses state directories with SQLite files, leaves timed-out worker cleanup unresolved, and omits deterministic definitions or executable entry points for parts of the evaluation pipeline.

## Why

Implementation against the current document would either break the governed tool schemas or produce unsafe, leaking, or non-reproducible evaluation behavior.

## Scope

- Revise only the implementation contract in `docs/specs/spec_09.md`.
- Preserve the intended offline held-out evaluation feature.
- Do not implement production code, tests, cases, manifests, or configuration in this work unit.

## Constraints

- Keep model-facing tool schemas unchanged.
- Permit only the narrow orchestrator dependency-injection seam required by evaluation.
- Use strict per-case process isolation for a hard timeout and sequential execution.
- Treat unavailable cost telemetry as unavailable rather than estimated from insufficient data.
- Keep technical artifacts in the repository's existing Spanish documentation convention.
- No meaningful RED/GREEN cycle applies to this passive specification-only change; use structural and cross-contract verification.
- No commit, push, PR, or merge is authorized.

## Delivery

- Strategy: `ask-on-risk`.
- Forecast: the untracked specification is over 400 added lines as seen by Git, but no delivery action is authorized in this task.

## Tasks

- [x] **S09R-T1 — Correct dependency isolation and timeout architecture**  
  Route: delegated writer; trigger: preparation plus non-trivial specification rewrite.  
  Defined bound model-facing tools, a narrow injected tool collection, explicit `state_dir`/DB paths, process lifecycle, and guaranteed cleanup without overlapping cases.

- [x] **S09R-T2 — Complete evaluation semantics and public execution contract**  
  Route: delegated writer in the same single-writer task.  
  Defined deterministic unsafe outcomes, escalation nullability, observable cost behavior, report generation/persistence, CLI entry point, type ownership, and held-out independence policy.

- [x] **S09R-T3 — Verify implementation readiness**  
  Route: delegated verifier required because native assessment was unavailable for the untracked specification candidate.  
  Independent reverification confirmed escalation mismatch handling, report evidence inputs, complete process joining, exact metric formulas, and no regression in previously verified contracts.

## Acceptance criteria

- No internal path is exposed in a Strands tool schema.
- The spec explicitly authorizes and defines the minimal orchestrator tool-injection seam.
- Each case runs in an isolated terminable process; timed-out cases cannot overlap subsequent cases.
- Temporary state cleanup has a single owner and deterministic lifecycle.
- Every unsafe predicate has observable inputs and ground truth.
- Escalation type nullability is relationally validated.
- Cost is `None` under current telemetry unless complete authoritative cost evidence exists.
- A canonical command, output directory, report APIs, and file inventory are defined.
- Public imports match the modules that own each type/function.
- The held-out policy addresses both byte identity and development-set independence.

## Progress

- Feature document created after three read-only audits of Spec #9.
- S09R-T1 and S09R-T2 completed by the bounded writer in `docs/specs/spec_09.md`.
- S09R-T3 completed after one correction round and final independent verification.

## Verification evidence

- Documentation-only TDD exception: no meaningful RED/GREEN cycle applies.
- Writer: `git diff --check -- docs/specs/spec_09.md` produced no output.
- Writer: no stale public `state_path`, thread/daemon timeout, action-event, or token-price fallback contract remained.
- Native assessment: unavailable because the candidate is untracked; risk treated as high and independent verification required.
- Independent verifier: contracts for tool schemas, governance arguments, paths, state filenames, cost policy, CLI, and inventory align.
- First independent verifier findings were corrected: wrong escalation type, report evidence inputs, normal child-process joining, and exact metric/percentile formulas.
- Final independent verifier status: `verified`; no blocker/high/medium inconsistency remains in the specification contract.
- Parent spot check: `git diff --no-index --check -- /dev/null docs/specs/spec_09.md` returned exit 1 only because the file is an untracked addition; the only output was the expected LF-to-CRLF warning, with no whitespace defect.
- No tests, builds, or linters ran because this was a passive specification-only change.
- No commit was created because commit authorization was not provided.

## Next step

Review the ready specification, then explicitly authorize implementation and delivery actions when desired.
