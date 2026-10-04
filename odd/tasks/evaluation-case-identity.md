# Repair evaluation case identity

## Objective

Correct the offline evaluation input contract so each actionable held-out case exposes its expected complaint identity to the production orchestrator, then rerun the frozen-version successor evaluation and address only residual defects proven by that run.

## Problem

The v1.0.0 held-out cases store `expected.complaint_id` as hidden ground truth but omit that identifier from `customer_message`. The worker passes only the customer message to `BankingOrchestrator`, while production governance correctly rejects unverified complaint identifiers. This makes successful blocking and persisted tool escalation impossible and invalidates the first run as a product-quality measurement.

## Why

The evaluation must exercise the real customer-facing contract rather than require the model to guess hidden fixture state. Fixing the fixture contract preserves production fail-closed behavior and produces metrics that can support an honest hackathon pitch.

## Scope

- Add a fail-closed case-contract validation requiring a non-null expected complaint ID to appear verbatim in the customer message.
- Create a new immutable evaluation case-set version instead of modifying frozen v1.0.0 inputs.
- Update the minimum manifests/configuration required to select new held-out and development successors while preserving their independence.
- Rerun the focused tests, full applicable evaluation tests, and the real offline evaluation.
- Diagnose and correct only residual behavior or contract mismatches evidenced by the new run.
- Update `docs/STATUS.md` with the new measured outcome and remaining limitations.

## Constraints

- Strict TDD: observe RED before production contract changes, then GREEN and refactor.
- Do not weaken governance, classifier semantics, authorization checks, or fail-closed behavior to improve metrics.
- Preserve `product_id` as the reliable transaction relationship.
- Preserve Spanish and Portuguese coverage and all six scenarios.
- Preserve held-out integrity; never rewrite `held_out_v1.0.0.yaml`.
- Treat attack and missing-data expectations as product contracts to validate, not metrics to game.
- Use the existing `uv`/pytest/Ruff toolchain and no new dependencies.
- Generated reports remain local evidence unless repository policy explicitly tracks them.

## Delivery

- Branch: `fix/evaluation-case-identity`
- Strategy: `ask-on-risk`
- Forecast: 180–320 authored changed lines, excluding copied generated/frozen case data where appropriate.
- Route: delegated direct implementation because the fix spans tests, evaluation contracts, versioned fixtures/manifests, configuration, and documentation.

## Tasks

- [x] **T1 — Enforce the case identity contract**
  - Add the smallest behavior-level test proving a case with hidden `expected.complaint_id` is rejected.
  - Observe RED with the resolved focused pytest runner.
  - Implement fail-closed validation and observe GREEN.
  - Checks: focused `tests/unit/evaluation/test_cases.py`; Ruff on touched Python files.
  - Route: delegated writer; multi-file/read-for-write trigger.

- [x] **T2 — Version valid evaluation fixtures**
  - Create the successor case set with complaint IDs present in every applicable customer message.
  - Update manifests, hashes, and configuration consistently without mutating v1.0.0.
  - Preserve scenario/language coverage and development/held-out independence.
  - Checks: case/config/manifest tests and hash/coverage validation.
  - Route: same delegated writer when coherent with T1.

- [ ] **T3 — Rerun and resolve residual evaluation defects**
  - Execute the real offline evaluation against the successor case set.
  - Compare SAR, containment, escalation, unsafe outcomes, latency, and failure evidence with the invalid v1.0.0 run.
  - If residual defects are deterministic and within the authorized workflow, add RED tests and apply the smallest root-cause correction; otherwise record the blocker without weakening safety.
  - Checks: focused tests for each correction and a final real evaluation run.
  - Route: delegated verifier for the real run; delegated writer only if residual multi-file corrections are required.

- [ ] **T4 — Close verification and documentation**
  - Run the applicable full pytest suite, Ruff check, Ruff format check, and diff check.
  - Update `docs/STATUS.md` with exact observed metrics, limitations, and commands.
  - Inspect native review authority when the final candidate is normalized.
  - Route: delegated verifier for commands; bounded writer for documentation if needed.

## Acceptance criteria

- Invalid cases cannot hide a non-null expected complaint ID outside the customer-visible input.
- The configured held-out set is a new version with verified manifest hashes and unchanged six-scenario coverage.
- The real evaluation consumes identity-bearing messages through the unchanged production orchestrator path.
- Metrics come from a completed report and are reported without cherry-picking or reinterpretation.
- No correction relaxes hard policy, governance, verification, or classifier safety.
- Applicable tests and static checks pass, with every skipped or failed check recorded.

## Progress

- Root cause mapped: fixture/input contract omission prevents verified tools from receiving a trusted complaint ID.
- Branch created from current `main`; pre-existing untracked `evals/reports/` preserved.
- T1 completed: the shared case contract rejects hidden non-null complaint identities while preserving null identities.
- T2 completed: held-out and development v1.0.1 successors expose complaint identities without modifying frozen predecessors; manifests and config select the verified successors.
- The held-out successor preserves 50 cases and six scenarios; the development successor preserves 30 independent cases.

## Verification evidence

- v1.0.0 run: 50/50 completed, 0 execution failures, 0% SAR, 10% containment, 0% correct escalation, 44% unsafe.
- Root-cause evidence: worker passes only `customer_message`; held-out messages omit `expected.complaint_id`; governance rejects unverified complaint IDs.
- RED: `test_eval_case_rejects_hidden_expected_complaint_identity` failed because no `ValidationError` was raised.
- GREEN: the same focused test passed after exact complaint-ID visibility validation was added.
- Focused suite before scope expansion: 49 passed and 4 failed; the remaining committed-fixture failure proved the development set violated the shared contract.
- Final focused suite: 53 passed; parent spot check repeated the same 53 passing tests.
- Ruff check and format checks passed for touched Python files; diff checks passed with only non-blocking line-ending warnings.
- Manifest validation loaded held-out 1.0.1 (50 cases) and development-1.0.1 (30 cases), verified both SHA-256 values, and confirmed visible identities.

## Next step

Commit the completed T1–T2 work unit, then execute the real v1.0.1 offline evaluation for T3.
