# Spec 07 v5 Readiness

## Objective

Revise `docs/specs/spec_07.md` so its Strands 1.57.1 lifecycle, governance, audit, session, cancellation, and verification contracts are internally consistent and implementation-ready.

## Scope

- Close the remaining v4 termination, cancellation, action-evidence, and retry ambiguities.
- Make session concurrency, audit sink wiring, event lineage, signal parsing, language detection, and memory sanitization explicit.
- Reconcile the test backlog, allowed file surfaces, and acceptance criteria with the final contract.

## Constraints

- Documentation-only change; no production implementation.
- Preserve Spec #1–#6 contracts unless this spec explicitly updates `docs/observability.md` during its future implementation.
- Use the installed Strands 1.57.1 API as the source of truth.
- Apply the passive-documentation TDD exception: no meaningful RED behavior test exists; use structural readback and consistency checks.
- Do not commit, push, or open a pull request without explicit user authorization.

## Tasks

- [x] **T1 — Rewrite the remaining lifecycle and safety contracts**
  - Route: delegated writer because the substantial document rewrite and task record span multiple non-trivial files.
  - Covered Agent termination, cancellation, partial tool evidence, retry handling, action classification, session turn locking, and model concurrency.
- [x] **T2 — Reconcile observability, parser, memory, and acceptance details**
  - Aligned composite sink wiring, audit failure semantics, event parent fallbacks, strict signal parsing, language detection, sanitization, tests, and file scope.
- [x] **T3 — Verify the specification structurally and independently**
  - The first independent verification returned FAIL with seven focused findings; the second returned FAIL with exactly two blockers.
  - Both focused correction rounds were applied.
  - Final independent read-only verification returned PASS with no remaining contract or product decision.

## Acceptance Criteria

- Every known v4 audit finding has one unambiguous normative resolution.
- Lifecycle order is executable and defines all exception/cancellation paths.
- Session, audit, memory, and event contracts are testable without hidden assumptions.
- Test backlog and acceptance criteria cover the normative behavior.
- No production code is changed.

## Progress

- Completed: T1, T2, and T3.
- Active task: none.
- Branch: `docs/spec-07-v5`.
- Forecast: the untracked specification is over the 400-authored-line review guide; no delivery action is authorized in this task.
- Engram mirror: observation 150.

## Verification Evidence

### Current documentation-only revision

- TDD exception: a meaningful pre-implementation behavior test does not apply to this specification-only rewrite.
- RED: not applicable for passive documentation.
- GREEN: not applicable; structural validation is recorded below instead.
- Structural search: no stale v4 marker, literal ellipsis placeholder, prohibited trace-state identifier, timeout stop-reason assignment, trailing-text acceptance rule, or placeholder token remains in the final spec.
- Complete readback: sections 0–17 checked for lifecycle order, action precedence, audit lineage, API/file lists, backlog, and acceptance consistency.
- Whitespace validation: `git diff --check -- docs/specs/spec_07.md odd/tasks/spec-07-v5-readiness.md` exited 0 with no diagnostics; because both targets remain untracked, a direct trailing-whitespace scan was also run and found none.

### Focused correction after independent FAIL

- Corrected the `AfterInvocationEvent` fact and documented the deliberate non-registration rationale.
- Made retry/duplicate uncertainty precede pre-execution blocking for sensitive tools.
- Marked Spec #7 observability fields as a future atomic extension of the current Spec #6 document.
- Added exact localized templates, exact session-turn API, and normative event envelope/payload construction.
- Direct trailing-whitespace check inspected both untracked files and found none.
- Direct conflict-marker check inspected both untracked files and found none.
- Complete post-correction readback checked sections 0–17 for lifecycle, retry precedence, templates, session API, event payloads, observability transition, tests, and acceptance alignment.
- Known environment limitation: native assess cannot inspect this untracked candidate without an intended-untracked declaration; independent structural verification was still completed.

### Second focused correction

- Defined the exhaustive FAILURE/REVIEW/ALLOW mapping for `OutputScreeningOutcome` and its identical clarification/normal conversion to `TurnClassification`.
- Added the backward-compatible keyword-only `orphaned` extension to all three adapter entry points, with explicit hook/orchestrator propagation and unchanged parent rules.
- Direct trailing-whitespace check inspected both untracked files and found none.
- Direct conflict-marker check inspected both untracked files and found none.
- Complete post-correction readback checked all sections 0–17 and the full task record for cross-section consistency.
- Final independent re-verification: PASS. The verifier read all 1,162 spec lines and 87 task-record lines, confirmed the Strands 1.57.1 contracts, and found no remaining implementation decision.

### Future implementation

- Strict TDD remains required with `uv run pytest` and RED → GREEN → TRIANGULATE → REFACTOR microcycles.
- The test backlog and acceptance commands are normative in `docs/specs/spec_07.md` sections 15 and 17.

## Next Step

The specification is implementation-ready. Implementation remains a separate user-authorized task.
