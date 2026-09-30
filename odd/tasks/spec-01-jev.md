# Spec 01 Jev Transport

## Objective

Implement the typed Jev transport and validation layer defined by `docs/specs/spec_01.md` using strict RED → GREEN → TRIANGULATE → REFACTOR cycles.

## Constraints

- No network calls in tests.
- No business decisions, evaluations, Strands hooks, retries, or audit emission.
- Do not modify existing tools or services.
- Never read or modify `.env`; `.env.example` remains host-blocked despite user authorization.
- Keep SDK 0.7.2 behavior behind the adapter boundary.

## Tasks

- [x] 1. Establish public API and typed exception hierarchy.
- [x] 2. Implement and triangulate question schemas.
- [x] 3. Implement and triangulate answer/response schemas.
- [ ] 4. Implement client configuration, input validation, and wire conversion.
- [ ] 5. Implement the real SDK transport seam and deterministic cleanup.
- [ ] 6. Complete SDK error mapping, response completeness, and logging safeguards.
- [ ] 7. Run full verification and update project status.

## Evidence

| Task | Focused RED | Focused GREEN | Runtime | Commit |
| --- | --- | --- | --- | --- |
| 1 | `uv run pytest tests/unit/governance/jev/test_import.py -q` → 1 failed (`ModuleNotFoundError`) | Same command → 1 passed | N/A — import contract only | `cd13e7f` |
| 2 | `uv run pytest tests/unit/governance/jev/test_schemas.py -q` → failed (`NoulQuestion() takes no arguments`) | Same command → 17 passed; import regression → 1 passed | N/A — schema validation only | `a41ce26` |
| 3 | Focused schema tests failed on missing answer-schema imports | `uv run pytest tests/unit/governance/jev/test_schemas.py tests/unit/governance/jev/test_import.py -q` → 33 passed | N/A — response parsing only | `859af7b` |
| 4 | Pending | Pending | N/A — unit-tested adapter logic | Pending |
| 5 | Pending | Pending | Mocked SDK boundary; no network | Pending |
| 6 | Pending | Pending | Mocked SDK boundary; no network | Pending |
| 7 | N/A | Pending | Full focused suite | Pending |

## Review Workload

Expected to exceed 400 authored diff lines because the approved spec requires 55 behavior-level tests. Keep commits split by the seven cohesive work units above; no push or PR is authorized.
