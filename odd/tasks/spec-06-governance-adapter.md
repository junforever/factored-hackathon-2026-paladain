# Spec 06 Governance Adapter

## Objective

Implement the reviewed `docs/specs/spec_06.md` v5 contract with strict behavior-level TDD.

## Scope

- Add the observability event contract and JSONL audit sink.
- Add the framework-agnostic governance adapter with fail-closed decisions, audit chaining, latency measurement, and trust-boundary builders.
- Add Strands 1.57.1 governance hooks with per-`toolUseId` concurrent state.
- Update observability ownership details and project status.

## Constraints

- Follow RED → GREEN → TRIANGULATE → REFACTOR with `uv run pytest`.
- Tests must not call the network, real Jev, DuckDB, SQLite, or a live Strands agent.
- Do not modify `governance/jev/*.py`, tools, services, `agent/tools.py`, configuration, or policy.
- Keep production and repository-facing artifacts in English.
- Close each task with a reviewable Conventional Commit on `feat/spec-06-governance-adapter`.

## Tasks

- [x] **T1 — Implement observability contract and JSONL sink**
  - RED observed: contract and sink tests each failed because their target module did not exist.
  - GREEN/TRIANGULATE: added strict envelope validation and a validated single-write JSONL sink; 79 focused tests pass.
  - Checks: focused pytest, scoped Ruff check/format, `git diff --check`, and independent verification passed.
  - Commit: pending.
- [ ] **T2 — Implement GovernanceAdapter and trust boundaries**
  - Evidence: active strict-TDD work.
- [ ] **T3 — Integrate governance through Strands hooks**
  - Evidence: pending.
- [ ] **T4 — Update documentation and run final acceptance**
  - Evidence: pending.

## Acceptance Criteria

- Every criterion in `docs/specs/spec_06.md` section 17 is satisfied.
- Focused tests, the complete unit suite, Ruff check, and Ruff format check pass.
- Concurrent tool calls remain isolated by `toolUseId` and share the stable routing parent.
- Jev failures produce the stage-specific conservative decisions and still emit audit events.
- Public imports and documentation match the reviewed contract.

## Progress

- Completed: T1.
- Active task: T2.
- Branch: `feat/spec-06-governance-adapter`.
- Exploration: completed by `gentle-ai-explore`; no implementation blocker found.
- Review workload: monitor authored diff size per work unit; slice by behavior and record an honest exception if a cohesive unit exceeds 400 lines.
- Engram mirror: synchronized as observation 141.

## Verification Evidence

- Test runner resolved from `pyproject.toml`: pytest via `uv run pytest`.
- Baseline: 431 unit tests and Ruff check passed; whole-repo Ruff format check had 11 pre-existing unformatted files.
- T1 RED: focused collection failed for missing `observability.contract`; sink RED failed for missing `observability.sink`.
- T1 GREEN/TRIANGULATE: `uv run pytest tests/unit/observability/ -q` → 79 passed.
- T1 quality: scoped Ruff check and format check passed; `git diff --check` passed.
- T1 independent verification: PASS; exact type/domain validation and JSONL persistence semantics confirmed.
- T1 runtime harness: N/A because this unit has no application runtime boundary.
- T1 rollback boundary: remove the six new observability source/test files.
- T2 evidence: pending.
- T3 evidence: pending.
- T4 evidence: pending.

## Next Step

Observe T2 RED tests for the missing framework-agnostic adapter, then implement the minimum GREEN behavior.
