# Spec 08 Readiness

## Objective

Revise `docs/specs/spec_08.md` into an implementation-ready Chainlit contract and pin the verified Chainlit version in project dependencies.

## Scope

- Resolve the fourteen remaining async lifecycle, reconciliation, configuration, rendering, and verification findings.
- Select and lock a concrete Chainlit 2.x release using current official documentation and installed API evidence.
- Keep this task limited to the specification, dependency metadata, lockfile, task record, and required configuration template documentation.

## Constraints

- Do not implement the Chainlit UI itself.
- Preserve Spec #1–#7 behavior and public APIs.
- Use passive-documentation TDD exception for the spec; dependency and structural checks remain mandatory.
- Do not commit, push, or open a pull request without explicit user authorization.

## Tasks

- [x] **T1 — Resolve Chainlit version and current API evidence**
  - Selected Chainlit 2.12.0 from current PyPI/docs evidence.
  - Confirmed documented `on_message`, `on_stop`, `Message.send`, `.chainlit/config.toml`, `unsafe_allow_html`, and CLI `--headless`/`--port` contracts pending installed-package verification.
- [x] **T2 — Pin Chainlit and refresh the lockfile**
  - Added exact dependencies `chainlit==2.12.0` and `requests==2.32.5`; the latter is required because the installed Chainlit/LiteralAI import path otherwise raises `ModuleNotFoundError`.
  - Verified installed API signatures, CLI options from package source, safe HTML default, and lock consistency.
- [x] **T3 — Rewrite Spec #8 lifecycle and configuration contracts**
  - Replaced v4 with a shorter normative v5 using `ActiveTurn`/`PendingTurnResult`, strong monitor retention, identity-safe transitions, safe sending, rooted paths, startup HTML validation, and in-memory reconciliation limits.
  - Incorporated the installed Chainlit 2.12.0 stop order: runtime cancels the current message task before awaiting `on_stop`.
- [x] **T4 — Verify the final candidate independently**
  - Dependency/API verification and full regression suite passed.
  - First independent review found three lifecycle gaps; two focused correction passes closed them.
  - Final independent review and final structural verifier both returned PASS with no unresolved implementation decision.

## Acceptance Criteria

- Chainlit is exactly pinned in `pyproject.toml` and `uv.lock`.
- The spec names only verified Chainlit APIs and CLI/configuration behavior.
- Every prior finding has one executable, testable resolution without lifecycle races.
- All required future implementation files, settings, `.env.example` entries, tests, and acceptance commands are internally consistent.
- No Chainlit UI production implementation is added.

## Progress

- Completed: T1, T2, T3, and T4.
- Active task: none.
- Branch: `docs/spec-08-readiness`.
- Engram mirror: pending.

## Verification Evidence

- Current documentation evidence: Chainlit 2.12.0 is the latest stable 2.x release for Python >=3.10,<3.14.
- Official docs expose `@cl.on_stop`, `@cl.on_message`, `cl.Message.send`, `.chainlit/config.toml`, `[features].unsafe_allow_html`, and CLI `--headless`/`--port`.
- Installed Chainlit version: `2.12.0`; `on_message`, `on_stop`, `Message.send`, and `user_session.get/set` signatures inspected successfully.
- Direct `python -m chainlit run --help` succeeds after pinning `requests==2.32.5` and confirms `--headless`, `--port`, `--host`, and `--ci`.
- Default config resolves under `<app-root>/.chainlit/config.toml` and sets `[features].unsafe_allow_html = false`.
- `uv lock --check` passed after dependency resolution.
- First final verifier pass: dependency/API assertions, CLI help, `744` tests, whitespace checks, and `14/14` structural markers passed.
- First independent review: FAIL with three lifecycle gaps—duplicate pending delivery, first-session ID race, and unhandled lazy bootstrap failure.
- Focused correction: added an atomic pending-delivery claim, switched to Chainlit's reserved session `id` with fail-closed validation, and defined safe lazy-factory failure before `ActiveTurn` creation.
- Second independent review found one invalid-session locale/metadata ambiguity and one missing `Language` alias; both were corrected.
- Final independent review: PASS; all prior findings closed and no new blocker.
- Final structural verifier: PASS (`uv lock --check`, whitespace/conflict scans, `12/12` contract markers, no stale provisional/runtime/track-in-git language).
- Regression suite after dependency pinning: `744 passed`.
- Final candidate scope: exact dependency pins plus the v5 spec and this task record; no UI implementation, commit, push, or PR.

## Next Step

Implement Spec #8 v5 in a separate user-authorized task using strict TDD.
