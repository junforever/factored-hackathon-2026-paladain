# Ruff Format Scope

## Objective

Make the repository-wide Ruff formatting check pass while excluding Markdown from formatter ownership.

## Problem and Why

Ruff 0.16.9 formats Python code fences in Markdown by default. The repository treats Markdown specs and agent instructions as authored documentation, so automatic Python formatting inside those files adds review noise without protecting runtime behavior. Four Python files also contain pre-existing formatter drift that keeps the repository-wide format gate red.

## Scope

- Configure Ruff's formatter-specific exclusion for `*.md` without changing lint scope.
- Format the four Python files reported by the verified RED baseline.
- Verify lint, format, affected tests, and whitespace.

## Constraints

- Use `[tool.ruff.format].exclude`, not a global Ruff exclusion, so the policy applies only to formatting.
- Do not alter Markdown content.
- Formatting-only Python changes must preserve behavior.
- No new dependency.
- No push, pull request, merge, or release is authorized.
- A local commit requires separate explicit user authorization.

## Delivery

- Branch: `chore/ruff-format-scope`, created from merged `main`.
- Delivery strategy: `ask-on-risk`; forecast under 200 authored changed lines.
- Planned work unit: one cohesive formatter-policy and Python-normalization change.

## Tasks

- [x] **T1 — Scope Ruff formatting and normalize Python files**
  - Route: delegated writer; multi-file write trigger.
  - RED: `uv run ruff format --check` exits 1 and reports 8 Markdown plus 4 Python files.
  - GREEN: repository-wide format and lint checks pass; focused affected tests pass.

## Acceptance Criteria and Checks

- `uv run ruff format --check`
- `uv run ruff check`
- `uv run pytest tests/unit/governance/jev/test_evaluations.py tests/unit/governance/jev/test_governance.py -q`
- `uv run python -m py_compile src/ai_banking_customer_service/tools/block_card.py`
- `git diff --check`
- No Markdown file changes.

## Progress

- Ruff documentation verified: Markdown code fences are formatted by default in Ruff 0.16+, and formatter-specific `exclude = ["*.md"]` is supported.
- RED baseline observed: format check failed on 12 files; lint passed.
- Implementation, verification, and native review complete.
- Local work-unit commit explicitly authorized by the user.
- Active task: none; feature complete.
- Engram mirror: observation 154.

## Verification Evidence

- RED — `uv run ruff format --check`: exit 1; 8 Markdown and 4 Python files would be reformatted.
- GREEN — `uv run ruff format --check`: passed; 71 files already formatted.
- `uv run ruff check`: passed.
- Focused governance tests: 284 passed.
- `block_card.py` compilation and `git diff --check`: passed.
- No Markdown file changed.
- Native review: approved and acknowledged (`review-700344b845dce62b`) with no advisory findings.
- Git trees of the merged `main` and the former feature branch were identical before branching.

## Next Step

Create the authorized local work-unit commit; push, merge, and pull-request creation remain separate user decisions.
