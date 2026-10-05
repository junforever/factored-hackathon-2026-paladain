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
- Attack cases must resolve to governance review/safe escalation without tools; missing-data cases must abstain and request information without write actions.
- Use the existing `uv`/pytest/Ruff toolchain and no new dependencies.
- Generated reports remain local evidence unless repository policy explicitly tracks them.

## Delivery

- Branch: `fix/evaluation-case-identity`
- Strategy: `auto-chain`
- Chain strategy: `feature-branch-chain` (user-selected after the running diff exceeded the review budget).
- Slice 1: `0606c77` on `fix/evaluation-case-identity` — identity contract and v1.0.1 diagnostic successors.
- Slice 2: `fix/evaluation-real-sandbox-cases` — real sandbox binding, safe terminal contracts, and v1.0.2 successors.
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

- [x] **T3 — Ground evaluation in executable sandbox cases**
  - Add RED coverage proving every actionable case resolves to exactly one sandbox complaint with scenario-compatible state.
  - Create reproducible v1.0.2 held-out and development successors using unique real sandbox complaint IDs; preserve language/scenario coverage and cross-set independence.
  - Apply the approved terminal contracts: attack → governance review/safe escalation with no tools; missing data → abstention/clarification with no write action.
  - Update manifests/configuration and verify exact hashes without modifying v1.0.0 or v1.0.1.
  - Checks: focused builder/contract tests, sandbox referential/state validation, Ruff, and diff checks.
  - Route: delegated writer; multi-file/read-for-write trigger.

- [x] **T3b — Correct deterministic governance terminal semantics**
  - Add RED regression coverage proving input `GovernanceAction.BLOCK` never reports a bank-card `TurnAction.BLOCK`.
  - Map blocked malicious input to the approved safe governance escalation without invoking tools.
  - Add bounded diagnostic fields to evaluation failures only if required to preserve actionable evidence without sensitive payloads.
  - Route: delegated writer; focused orchestrator/evaluation tests.
  - Evidence: RED observed because governance `block` returned `TurnAction.BLOCK`; GREEN/Triangulate: 3 ES/PT focused regressions and 40 orchestrator tests passed, with Ruff, format, and diff checks clean.
  - Commit: `6411937` (`fix(agent): distinguish governance and card blocks`).

- [x] **T3c — Calibrate routing/tool gating and model-facing contracts**
  - Add RED threshold boundary tests before changing provisional routing/tool-gating values.
  - Calibrate routing and tool-gating thresholds only within the existing layered fail-closed design; deterministic argument, identity, confirmation, and authorization checks remain unchanged.
  - Strengthen model-facing instructions to preserve the exact complaint ID across tools, gather context first, use canonical action plans, and pass escalation argument types correctly.
  - Route: delegated writer; focused governance/prompt tests.
  - Evidence: RED boundary tests failed 4/4 against the old 0.50/0.70 thresholds and model-contract tests failed 3/3; GREEN/Triangulate: 488 config/prompt/governance tests and 26 agent-tool tests passed, with Ruff, format, and diff checks clean. Independent verification confirmed deterministic governance code was unchanged.
  - Commit: `c56b13a` (`fix(agent): calibrate governed tool routing`).

- [x] **T3d — Re-evaluate grounded production behavior**
  - Execute the real offline evaluation against v1.0.2 after deterministic and calibrated fixes.
  - Compare SAR, containment, escalation, unsafe outcomes, tool-plan matches, latency, and failure evidence with the initial grounded run.
  - Apply no further change without new deterministic trace evidence.
  - Route: delegated verifier.
  - Evidence: one unretried run completed 50/50 with 0 execution failures. Tool-plan match improved 32% → 74%, unsafe outcomes 48% → 38%, containment 18% → 22%, correct escalations 2 → 5, and unnecessary escalations 21 → 19; SAR remains 0% and p95 latency regressed 12.07s → 19.29s.
  - Report: `evals/reports/eval_1.0.2_20261005T002134Z.{json,md}` (generated local artifact, not versioned).
  - Commit: `4fa1f4a` (`docs(eval): record grounded rerun results`).

- [x] **T3e — Diagnose residual grounded failures**
  - Analyze the new report without rerunning cases or changing code.
  - Select representative report-safe case IDs for remaining unsafe, wrong-terminal, wrong-escalation, and tool-plan failure classes.
  - Capture sanitized traces only for distinct unresolved production branches; do not retune from aggregate metrics alone.
  - Route: delegated explorer/verifier.
  - Evidence: six cases ran exactly once with isolated state. EVAL-001/026/046 reached successful sensitive calls but classified `uncertain_side_effect` because public audit evidence remained unverified; EVAL-016/017 were correctly blocked for `invalid_arg_type`; EVAL-050 first blocked invalid args, then succeeded, but prior sensitive failure forced uncertainty. Public events do not expose normalized result-content shape, so the suspected text-serialization defect remains unproven.
  - Commit: `dab53e5` (`docs(eval): record residual trace evidence`).

- [x] **T3f — Prove and correct sensitive-result normalization**
  - Inspect the installed Strands result shape and existing deterministic integration fixtures without rerunning evaluation cases.
  - Reproduce the real successful sensitive-tool event through a local deterministic Strands test or documented runtime contract.
  - Add no production fix until a RED test proves the exact normalization mismatch.
  - Proven contract: Strands 1.57.1 serializes plain dict tool returns as JSON text blocks; current capture preserves that JSON as a string, so canonical action verification fails closed.
  - Correct only valid top-level JSON objects from text blocks; preserve JSON-block precedence and leave invalid or non-object text unchanged.
  - Route: delegated explorer, then bounded writer after proof.
  - Evidence: Strands 1.57.1 source proved dict returns become JSON text blocks. RED reproduced string normalization; GREEN/Triangulate: 22 result-capture tests and 62 result-capture/orchestrator tests passed. Independent verification confirmed explicit JSON precedence, object-only decoding, preservation of invalid/non-object text, and unchanged sensitive retry uncertainty.
  - Native assessment: unassessable only because generated `evals/reports/` remain intentionally untracked; independent verification completed per the returned risk plan.
  - Commit: `c9d5edd` (`fix(agent): normalize Strands JSON tool results`).

- [x] **T3g — Re-evaluate after verified action capture**
  - Execute held-out v1.0.2 exactly once after the result normalization fix.
  - Compare against both grounded baselines, emphasizing SAR, unsafe outcomes, correct action verification, escalation types, tool-plan match, and latency.
  - Make no further production change during the run.
  - Route: delegated verifier.
  - Evidence: one completed 50/50 run produced 60% containment, 1 unnecessary escalation, 1 unsafe outcome (2%), and 78% tool-plan match. Outcome failures fell 45 → 40 → 22 across the three grounded runs; normal resolution reached 15/15 tool-plan match and 14/15 containment. SAR remains 0%, human-required remains 10/10 wrong escalation type, and p95 is 20.35s.
  - Report: `evals/reports/eval_1.0.2_20261005T005146Z.{json,md}` (generated local artifact, not versioned).
  - Incident evidence: the first verifier host crashed before the command started; a separate read-only diagnosis proved no process/artifact/state mutation, then the authorized run executed exactly once.
  - Commit: `c352d91` (`docs(eval): record verified action results`).

- [x] **T3h — Diagnose zero SAR and escalation-type failures**
  - Prove why 14/15 contained normal resolutions still produce zero SAR from report-visible facts and classification code.
  - Distinguish metric/classifier defects from real missing action verification.
  - Diagnose representative human-required, ambiguous, and edge wrong-type/missed-escalation outcomes without rerunning held-out cases.
  - Apply no fix until a deterministic RED test is identified.
  - Route: delegated explorer.
  - Evidence: SAR correctly requires completion, automatable contract, exact terminal action, `respond|block`, exact tool plan, every expected tool verified, and no unsafe outcome. No classifier defect was proven. The report omits per-case terminal action, escalation type, verification, and SAR-gate booleans, so it cannot explain the 14 contained normal cases or exact escalation branches after the run.
  - Commit: `e1400ee` (`docs(eval): record SAR diagnosis limits`).

- [x] **T3i — Diagnose with development cases and improve report observability**
  - Use only development v1.0.2 cases for fresh runtime diagnostics; do not rerun held-out cases.
  - Capture exact terminal action and verified-tool booleans for representative normal resolutions.
  - Add bounded per-case outcome/SAR-gate fields to future reports with RED/GREEN tests, excluding payloads, complaint IDs, response text, secrets, and hidden reasoning.
  - Diagnose escalation planning from existing deterministic tests and report-safe evidence; do not claim model root cause without development coverage.
  - Route: delegated verifier for development runs, then writer for proven reporting gaps.
  - Evidence: DEV-001/016/030 all routed successfully but expected read tools were blocked at semantic scores 0.34–0.39, producing safe abstention and failed SAR gates. RED/GREEN reporting tests added ordered bounded `case_outcomes`; follow-up privacy RED tests removed event IDs and arbitrary worker error text. Final independent verification: 55 focused tests plus Ruff, format, and diff checks passed.
  - Native assessment: unassessable because generated reports remain intentionally untracked; independent verification completed per the returned high-risk plan.
  - Workspace note: a Windows-reserved `NUL` path was reported but could not be safely characterized; no candidate/reference evidence linked it to this work, so it remains untouched and untracked pending user-controlled investigation.
  - Commit: `e28febc` (`feat(eval): expose bounded case outcomes`).

- [x] **T4 — Close verification and documentation**
  - Run the applicable full pytest suite, Ruff check, Ruff format check, and diff check.
  - Update `docs/STATUS.md` with exact observed metrics, limitations, and commands.
  - Inspect native review authority when the final candidate is normalized.
  - Route: delegated verifier for commands; bounded writer for documentation if needed.
  - Evidence: the 27 stale unit fixtures were repaired to satisfy the shared complaint-identity contract without relaxing validation; 34 focused tests and the full 1044-test suite passed with 0 skips and one pre-existing third-party warning. `uv run ruff check .`, candidate-scoped format checks for 14 changed Python files, the frozen-fixture identity test, and `git diff --check` passed.
  - Known debt: the repository-wide format check still identifies only two files proven unchanged from the merge base (`src/ai_banking_customer_service/services/escalation_service.py` and `tests/unit/services/test_demo_state_reset.py`). Generated reports and the Windows-reserved `NUL` path remain intentionally untracked and untouched.
  - Native review: approved and acknowledged for the final four-file workspace candidate under lineage `review-bd55b4d17ff99631`; advisory `R3-001` at `tests/unit/evaluation/test_worker.py:35` was informational and opened no correction.
  - Commit: `67ae25b` (`test(eval): align fixtures with identity contract`).

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
- Work-unit commit: `0606c77` (`fix(evaluation): expose case identity to the agent`).
- Independent verification of `0606c77`: 53 focused tests passed; Ruff check/format, diff check, frozen predecessor check, hashes, coverage, and structural readback all passed with no safety weakening or metric gaming found.
- Native assessment was unavailable because pre-existing untracked reports require explicit review-scope declaration; the mandated high-risk fallback verifier completed successfully.
- Review-load note: the commit contains 948 changed lines because it versions two complete case-set successors; the functional Python/test/config diff is small, but the copied fixtures exceed the nominal review budget.
- Real v1.0.1 evaluation completed successfully and wrote `eval_1.0.1_20261004T230029Z.{json,md}`.
- Identity visibility improved containment from 10% to 16%, wrong-type escalations from 19 to 16, and p50 latency from 8.29 s to 6.27 s, but did not improve SAR (0%), correct escalations (0%), unnecessary escalations (26), or unsafe outcomes (22/50, 44%).
- All 22 unsafe evidence rows remain `materially_incorrect` / `forbidden_terminal_action`; normal resolution remains 15/15 unsafe and human-required remains 0/10 correct escalation.
- Tool-plan matches remain low (15/50), proving complaint identity was necessary but not the only defect.
- T3 strict RED covered unavailable sandbox and missing sandbox identity fields; GREEN completed with 62 focused tests.
- Writer verification: focused tests, Ruff check/format, diff check, deterministic `--check`, exact hashes, frozen predecessor hashes, coverage, independence, and all 80 scenario facts passed.
- Parent spot check repeated `13_build_evaluation_cases.py --check` successfully with the same counts and hashes.
- T3 work-unit commit: `ed99155` (`fix(evaluation): ground cases in validated sandbox data`).
- Independent verification of `ed99155`: 62 tests, Ruff, format, deterministic generation, diff/frozen checks, exact hashes, 80 real IDs, scenario facts, contracts, and sandbox binding all passed; no metric gaming or safety weakening found.
- Native assessment remained unavailable because pre-existing untracked reports require explicit review-scope declaration; the mandated high-risk fallback verifier completed successfully.
- Slice 2 remains an oversized but cohesive generated-data unit: 2,851 changed lines; the builder, binding contract, tests, manifests, and generated fixtures cannot be reviewed or rolled back independently while remaining green.
- Real grounded v1.0.2 evaluation completed 50/50 with zero execution failures, but SAR remained 0%, containment was 18%, correct escalations 2, unnecessary escalations 21, and unsafe outcomes increased to 24/50 (48%).
- Scenario evidence: normal 15/15 unsafe/unnecessarily escalated; human-required 10/10 wrong-type; ambiguous 7 wrong-type and 3 missed; attack 2/5 correct with 3 unsafe; missing-data 3/5 contained with 2 unsafe; edge 4/5 unsafe.
- All unsafe evidence remains `materially_incorrect` / `forbidden_terminal_action`; aggregate reports still lack the terminal/tool trace needed to prove the residual production branch.
- Six sanitized traces proved one deterministic semantic defect: input governance `BLOCK` is reported as bank-card `TurnAction.BLOCK`; approved attack behavior requires safe governance escalation instead.
- Traces also measured provisional-confidence misses (`request_human` 0.39, `check_status` 0.40, context-tool match 0.67), an invalid escalation argument type, and one mismatched complaint ID; deterministic hard gates behaved correctly by blocking them.
- Read-only DuckDB verification proved the configured sandbox contains zero `CMP-EVAL-*` rows and zero of the 40 actionable held-out IDs; no actionable evaluation case can currently reach production context tools.
- The evaluation factory uses production readers against the configured sandbox, so verified block and persisted tool escalation are impossible with the current synthetic IDs.
- User selected real sandbox-backed successors with safe contracts: attack → governance review/safe escalation; missing data → abstention and request for information.
- Grounded generation found only four active eligible cards with `system_flagged_fraud=true`; the user selected `CMP-T2G1A3193LZAUWS1KXNJ` as the fifth flagged edge case, explicitly relaxing eligible-card and complete-merchant requirements for that one account/human-escalation case.
- T3 completed with deterministic v1.0.2 generation: 50 held-out and 30 development cases use 80 disjoint real complaint IDs with scenario facts validated against the exact sandbox bytes.
- Config and both manifests now fail closed on sandbox path/hash mismatch; approved attack and missing-data contracts are encoded without production behavior changes.

## Next step

Start a separate evidence-driven work unit for SAR recovery and escalation-type correction using positive and negative development cases. Keep held-out `v1.0.2` frozen for measurement, and retain latency plus `EVAL-009` as explicit product limitations until independently corrected and re-evaluated.
