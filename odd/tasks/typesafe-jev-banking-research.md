# TypeSafe Jev Banking Research

## Objective

Produce a consolidated Markdown guide for integrating TypeSafe Jev as a governance layer around a Strands banking customer-service agent.

## Problem and rationale

The integration needs current, source-backed API contracts, typed Python examples, confidence guidance, state/question authoring guidance, relevant security and routing patterns, and documented service limits. The guide must distinguish verified contracts from recommendations and unknown limits.

## Scope

- Official TypeSafe documentation and cookbooks for Jev, HTTP API, Python SDK, Noul, Choice, Score, confidence, and state.
- Banking governance examples for input screening, intent routing, response confidence gating, and tool-call safety.
- Copy-ready Pydantic schemas representing documented wire responses.
- One consolidated document under `docs/typesafe_jev/`.

## Constraints

- Use official, live TypeSafe sources as the primary evidence.
- Do not invent Python APIs, response fields, limits, or cookbook claims.
- Examples must reflect documented API/SDK contracts.
- Documentation-only exception to Strict TDD: no meaningful behavioral RED test exists; validate links, code syntax, and consistency instead.
- Delivery strategy: `ask-on-risk`; forecast is below 400 authored lines.
- No commit without explicit user authorization.

## Tasks

- [x] **T1 — Research official Jev contracts and examples** (route: delegated; trigger: broad external research and context compression)
  - Captured authentication, endpoints, request/response contracts, SDK usage, primitive semantics, confidence, nested state references, authoring guidance, cookbooks, and published limits from live official pages.
  - The delegated worker lacked network access; the parent completed the live-source retrieval with the authorized web tools.
- [x] **T2 — Write the consolidated integration guide** (route: inline; one documentation file)
  - Created `docs/typesafe_jev/README.md` with official SDK examples, local copy-ready Pydantic wire schemas, banking governance guidance, and a complete request/response example.
- [x] **T3 — Verify the document** (route: delegated verification)
  - Independent verifier found no blockers or minor findings after one correction pass.
  - All eight Python code blocks compile, and `git diff --check` passes.

## Acceptance criteria

- The guide covers every requested section.
- Every version-sensitive API claim is traceable to an official TypeSafe URL.
- Python examples use documented calls and fields rather than inferred SDK behavior.
- Pydantic models match the documented wire format and are labeled as local validation models if not vendor-provided SDK models.
- Rate, payload, and state limits are either documented with citations or clearly marked as not published in the reviewed sources.
- Validation evidence and any skipped/unavailable checks are recorded below.

## Progress and evidence

- TDD mode: enabled globally, documentation-only exception applies.
- Test runner: no test framework configured in `pyproject.toml`; documentation validation will use syntax/link/contract checks.
- T1 evidence: live official pages reviewed include `/api`, `/sdk/python`, `/sdk/python/usage`, request/response type references, `/models`, `/confidence`, primitive pages, LLM guardrails, intent routing, and function calling.
- T2 evidence: `docs/typesafe_jev/README.md` created.
- T3 evidence: primitive examples are labeled illustrative; SDK routing maps injection, intent confidence, safety score, and safety confidence to block/review/send behavior; eight Python blocks compiled; `git diff --check` passed.
- Current next step: complete; deliver `docs/typesafe_jev/README.md`.
