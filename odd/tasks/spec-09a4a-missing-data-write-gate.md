# Spec 09A4A — Missing-Data Write Gate

## Objective

After Spec 09A4 is completed and frozen, add the independent pre-service gate that cancels later `block_card` and `escalate_case` calls when the exact canonical read occurrence proves merchant data is missing.

## Scope

Included:

- Observe a new strict-TDD RED for the absent canonical pre-service gate.
- Consume 09A4 canonical occurrence state without creating another positive source.
- Cancel both write tools before service invocation.
- Preserve governance-denial precedence and 09A4 terminal/evidence transport.

Excluded:

- Canonical missing-data derivation, tool/service changes, public schemas, policy, prompt, Jev, thresholds, model, corpus, real evaluation, and network execution.

## Constraints

- Dependency: 09A4 completed, GREEN, reviewed, accepted, and frozen by the user on 2026-10-08.
- Runner: `uv run pytest` with deterministic fakes.
- One primary runtime domain: `agent`.
- One behavioral work unit; tests and closure docs stay with the gate.
- Total forecast: 230–285 authored lines, including eventual non-generated closure deltas; hard maximum 300.
- Historical cancellation behavior is not valid RED evidence for this successor.

## Planned Task

- [ ] **09A4A-1 — Cancel later writes from canonical missing data** (`in_progress`)
  - RED: prove canonical missing data currently lets each later write reach the service seam.
  - GREEN: add the minimum pre-service cancellation producer for both actions.
  - TRIANGULATE: present/missing, allowed/denied, malformed/error, retry/duplicate, read, precedence, terminal/evidence, ES/PT, privacy, and concurrency.
  - REFACTOR: no new module, event, public schema, or parallel positive state.
  - Work-unit commit and native review: pending after implementation.

## Acceptance

- Exact canonical missing data cancels `block_card` and `escalate_case` before service invocation.
- Negative or ambiguous occurrences do not activate the gate.
- Governance denial keeps precedence and its own evidence.
- 09A4 terminal/evidence behavior and unrelated reads remain unchanged.
- Observed authored lines, including closure docs, do not exceed 300.

## Forecast

- Production gate and neutral transport adjustment: 45–70 lines.
- Behavior tests and material negative cases: 155–185 lines.
- Eventual spec/status/tracker closure: 30 lines.
- Total: 230–285 authored lines.

## Verification

```bash
uv run pytest -q tests/unit/agent/test_result_capture.py tests/unit/agent/test_hooks.py tests/unit/agent/test_orchestrator.py
uv run ruff check src/ai_banking_customer_service/agent/hooks.py src/ai_banking_customer_service/agent/result_capture.py tests/unit/agent/test_hooks.py tests/unit/agent/test_result_capture.py tests/unit/agent/test_orchestrator.py
uv run ruff format --check src/ai_banking_customer_service/agent/hooks.py src/ai_banking_customer_service/agent/result_capture.py tests/unit/agent/test_hooks.py tests/unit/agent/test_result_capture.py tests/unit/agent/test_orchestrator.py
git diff --check
```

## Evidence

- 2026-10-08: the user reviewed, accepted, and froze Spec 09A4, unblocking this task.
- RED: the exact focused test failed for both writes because each reached the service seam (`2 failed`).
- GREEN: the same focused test passed for both writes (`2 passed`).
- TRIANGULATE: affected agent suites passed (`185 passed`); full suite passed (`1293 passed`, one unrelated Pydantic warning); Ruff check/format and `git diff --check` passed.
- Canonical records gate writes in capture without shared positivity; 253 authored lines, one runtime domain; task, commit, and review remain pending.
