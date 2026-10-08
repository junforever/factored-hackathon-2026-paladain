# Spec 09A4 — Canonical Missing-Data State

## Objective

Implement Spec 09A4 with strict TDD so one exact authorized, successful `get_recent_transactions` occurrence is the canonical missing-merchant truth used by terminal behavior and canonical evidence.

## Gate Resolution

- The user accepted and froze Spec 09A3 on 2026-10-07.
- The original combined candidate measured 386 authored lines including this non-generated tracker, above the mandatory 300-line Spec gate.
- The accepted behavioral split keeps occurrence-local canonical derivation plus terminal/evidence propagation in 09A4.
- New Spec 09A4A owns only independent pre-service cancellation of later `block_card` and `escalate_case` calls.
- Existing Spec 09A5 retains its number and now depends on completed/frozen 09A4A.

## Scope

Included:

- Derive missing/present merchant state only from the exact normalized authorized read occurrence.
- Keep denial, read failure, malformed shape, non-strict booleans, retry, duplicate, mismatch, and ambiguity non-positive.
- Propagate canonical state into the existing ES/PT safe terminal and 09A1–09A2 evidence vocabulary.
- Preserve neutral capture of any observed cancellation marker without producing that cancellation.

Excluded:

- Pre-service cancellation of writes/handoffs, now wholly owned by 09A4A.
- Public tool schemas/signatures, services, policy, prompt, Jev, thresholds, models, corpus, reports, fixtures, manifests, dependencies, real evaluation, or network execution.
- Expansion of which fields count as missing.

## Constraints

- Strict RED → GREEN → TRIANGULATE → REFACTOR with `uv run pytest`.
- One primary runtime domain: `agent`.
- Every positive is occurrence-local; shared booleans and identifier sets are not positive sources.
- 09A4 and 09A4A are behavioral work units; tests and docs are not split by file type.
- Each work unit, including non-generated closure tracking, must remain at or below 300 authored lines.
- Remaining 09A4 currently totals 274 authored lines; reserve 26 closure lines for the 300-line gate.
- Technical artifacts remain in English; existing ES/PT templates remain unchanged.

## Frozen 09A4 Edit Surfaces

Production:

- `src/ai_banking_customer_service/agent/result_capture.py`
- `src/ai_banking_customer_service/agent/orchestrator.py`

Tests:

- `tests/unit/agent/test_result_capture.py`
- `tests/unit/agent/test_orchestrator.py`

Documentation/tracking:

- `docs/specs/spec_09a4.md`
- `docs/STATUS.md`
- `odd/tasks/spec-09a4-canonical-missing-data.md`

## Tasks

- [x] **09A4-SPLIT — Record the accepted behavioral split** (`done`)
  - Created Spec 09A4A and its tracker, re-scoped 09A4, routed 09A5 through 09A4A, and removed uncommitted 09A4A behavior/tests from the candidate.
  - Acceptance: coherent 09A4 and 09A4A behavior boundaries, each forecast or observed at ≤300 authored lines including tracking.
  - Work-unit commit: `cf426d1e827f4650a4aee6d0d9857eabf6a0fc15` (`docs(agent): split canonical missing-data work units`).

- [x] **09A4-1 — Preserve canonical missing-data truth end to end** (`done`)
  - RED: an authorized recent-transaction result with missing merchant data returned model text instead of the safe missing-data terminal; the denied occurrence remained non-positive.
  - GREEN: derive missing-data from the exact normalized `get_recent_transactions` occurrence and use it for terminal/evidence behavior.
  - TRIANGULATE: present/absent, authorized/denied, success/error, malformed and non-strict values, homonyms, interleaving, retry/duplicate, ES/PT, terminal precedence, audit failure, canonical evidence, and privacy.
  - REFACTOR: no new module, event, public schema, or alternate positive source.
  - Acceptance: every positive is tied to one exact authorized verified read occurrence; all negative/ambiguous states remain non-positive; terminal/evidence contracts and unrelated behavior remain unchanged.
  - Work-unit commit: `dc9314168c6d38b8780cbdb6b1e97bd29ba89a02` (`fix(agent): canonicalize missing-merchant state`); reviewed, accepted, and frozen by the user on 2026-10-08.

## Acceptance Criteria

- Exactly one occurrence-local source can originate verified missing-data truth.
- Authorization absence or denial never claims that data was read.
- Error, retry, duplicate, mismatch, malformed shape, and non-strict booleans remain non-positive.
- Occurrence identity survives concurrency and homonymous calls.
- Existing ES/PT safe output and canonical evidence vocabularies remain unchanged.
- Evidence contains no merchant text, payloads, messages, sensitive values, or fabricated action outcomes.
- Pre-service cancellation is absent from 09A4 acceptance and deferred to 09A4A.

## Progress and Evidence

- 2026-10-07: `uv run pytest` was resolved from project configuration as the runner.
- 2026-10-07: RED observed the authorized recent-transaction missing-data occurrence return model text; its denied parameter passed.
- 2026-10-07: GREEN observed the canonical authorized/missing terminal and denied/non-positive case pass before the size split.
- 2026-10-07: broader focused and repository checks passed on the former combined candidate, but those results included behavior now removed for 09A4A and are not closure evidence for either re-scoped work unit.
- 2026-10-07: the user accepted the 09A4/09A4A behavioral split.
- 2026-10-07: split specification work committed as `cf426d1e827f4650a4aee6d0d9857eabf6a0fc15`; re-scoped 09A4 implementation remains open.
- 2026-10-07: RED reproduced the blocker: authorized successful `get_dispute_context` plus legacy shared state remained positive; focused GREEN confirmed capture now neutralizes that state while retaining normalized records.
- 2026-10-07: implementation committed as `dc9314168c6d38b8780cbdb6b1e97bd29ba89a02`; independent final verification passed the focused regression (1), affected agent suites (185), full suite (1293; one unrelated Pydantic deprecation warning), Ruff check/format, and `git diff --check`, with no real evaluation/network/model/Jev.
- 2026-10-07: native ASSESS for `cf426d1..dc93141` was medium risk (`executable_change`), 5 paths and 274 authored lines, with `reviewDue=false` (`under_budget`).
- 2026-10-08: the user reviewed, accepted, and froze 09A4, unblocking 09A4A.

## Verification

```bash
uv run pytest -q tests/unit/agent/test_result_capture.py tests/unit/agent/test_hooks.py tests/unit/agent/test_orchestrator.py
uv run ruff check src/ai_banking_customer_service/agent/hooks.py src/ai_banking_customer_service/agent/result_capture.py src/ai_banking_customer_service/agent/orchestrator.py tests/unit/agent/test_hooks.py tests/unit/agent/test_result_capture.py tests/unit/agent/test_orchestrator.py
uv run ruff format --check src/ai_banking_customer_service/agent/hooks.py src/ai_banking_customer_service/agent/result_capture.py src/ai_banking_customer_service/agent/orchestrator.py tests/unit/agent/test_hooks.py tests/unit/agent/test_result_capture.py tests/unit/agent/test_orchestrator.py
git diff --check
```

## Next Step

Continue 09A4A as the independent in-progress pre-service write gate.
