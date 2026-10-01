# Jev input screening and intent routing

## Objective

Implement `docs/specs/spec_02.md` with strict TDD: sanitize messages before Jev evaluation, batch input screening, route banking intent, preserve response metadata, and validate the returned intent domain.

## Problem and why

The typed Jev transport from Spec #1 exists, but the application still lacks concrete input-screening and intent-routing evaluations. The implementation must enforce the repository's secret-handling boundary and preserve the raw signals required by the later governance decision layer.

## Scope

- Add `src/ai_banking_customer_service/governance/jev/evaluations.py`.
- Add `tests/unit/governance/jev/test_evaluations.py`.
- Update `docs/STATUS.md` after verified completion.
- Do not modify Spec #1 production files or implement thresholds, decisions, hooks, or audit emission.

## Constraints

- Strict TDD is enabled by `C:/Users/User/.pi/agent/AGENTS.md`.
- Exact runner: `uv run pytest` from `pyproject.toml` and the implemented Spec #1 suite.
- Route: delegated direct via `gentle-ai-worker`; trigger: multi-file write rule.
- Use the standard library only for sanitization; add no dependency or speculative abstraction.
- Delivery strategy: `ask-on-risk`; selected chain strategy: `stacked-to-main`.
- Actual staged size: 696 authored changed lines. The smallest honest behavior-plus-tests unit is over budget because the security and contract matrix is integral to the implementation; record `size:exception` rather than separating tests from behavior.
- Branch point: `4822845741586000d340a84c3aea1f075176b8c7`.

## Tasks

- [x] **JEV-1 — Implement Spec #2 with strict TDD**
  - Observe RED for focused behavior-level tests before production code.
  - Implement the minimum sanitization, question constants, batching, typed extraction, metadata preservation, and intent-domain validation.
  - Update `docs/STATUS.md` only after focused and full Jev suites pass.
  - Checks: `uv run pytest tests/unit/governance/jev/test_evaluations.py -q`; `uv run pytest tests/unit/governance/jev -q`; `uv run ruff check src/ai_banking_customer_service/governance/jev/evaluations.py tests/unit/governance/jev/test_evaluations.py`.
  - Runtime harness: N/A because this unit is a typed adapter over a mocked external boundary; focused tests are the executable behavior harness.
  - Rollback boundary: remove the two new evaluation files and revert the Spec #2 status entries only.
  - Writer evidence: RED collection failed with `ModuleNotFoundError`; focused GREEN reached `1 passed`; final focused suite reached `59 passed`; full Jev suite reached `128 passed`; Ruff passed.
  - Commit evidence: work-unit commit `feat(governance): add Jev input evaluations` (exact hash recorded in the Engram mirror after commit creation).
  - Native assessment/review: ambient assessment was unassessable because untracked files require explicit declaration; independent verifier completed with no findings. Committed-range native review remains pending.

## Acceptance criteria

- Both public entry points sanitize supported secret formats before calling Jev.
- `screen_input` sends both Noul questions in exactly one request.
- `route_banking_intent` validates `choice` and the complete probability domain.
- Both result objects preserve `model` and `usage` without transforming raw answers.
- Invalid input, wrong answer types, and public Jev errors follow the spec.
- Focused tests, complete Jev tests, and Ruff pass without network access.
- `docs/STATUS.md` reflects completion.

## Progress and evidence

- Feature branch created: `feat/jev-input-screening`.
- JEV-1 implementation was completed by the bounded writer within the authorized surfaces.
- RED: focused test collection failed with `ModuleNotFoundError` before `evaluations.py` existed.
- GREEN: initial focused behavior passed (`1 passed`).
- Final writer checks: focused `59 passed`; full Jev suite `128 passed`; Ruff `All checks passed!`.
- Parent structural readback and `git diff --check` passed.
- Independent verifier: no findings; focused `59 passed`, full Jev suite `128 passed`, Ruff passed.
- Parent spot check: focused suite `59 passed in 0.44s`.
- Native ambient assessment: `unassessable`; untracked files require explicit review declaration. The independent high-risk fallback verification completed successfully.
- Delivery: `stacked-to-main` selected. One cohesive 696-line slice carries `size:exception`; splitting the security/contract test matrix from its behavior would weaken the work-unit story.

## Next step

Create the work-unit commit, record its exact identity in the Engram mirror, and start native committed-range review from the branch point.
