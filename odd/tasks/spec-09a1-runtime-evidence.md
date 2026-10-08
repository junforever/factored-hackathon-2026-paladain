# ODD — Spec 09A1: Contrato runtime de evidencia canónica y emisión

## Objetivo

El runtime emite evidencia causal canónica, correlacionada, finita y segura para
cada intento de tool, sin cambiar ninguna decisión, respuesta, terminal ni
schema público. Spec normativa: `docs/specs/spec_09a1.md`.

## Restricciones

- TDD estricto con `uv run pytest`; fakes y sinks en memoria; sin red, modelo
  real, Jev real, SQLite productivo ni corpus real.
- Un solo dominio runtime: emisión de observabilidad. Evaluación pertenece a
  09A2 (bloqueada hasta el handoff).
- No tocar clasificación, runner, worker, reportes, policy, prompts, Jev,
  thresholds, tools, fixtures, manifests, sandbox, dependencias ni config.
- Comportamiento observable del agente idéntico (invariante 10).
- Cada work unit ≤300 líneas authored, con tests y docs junto al comportamiento.
- Held-out `v1.0.2` congelado; cero corridas reales de evaluación.

## Caracterización previa al RED (completada)

Contratos vigentes congelados desde código:

- `observability/contract.py`: `AUTHORIZATION_RESULTS = {allowed, denied,
  unavailable, not_evaluated}`; `AUTHORIZATION_REASON_CODES = {authorized,
  not_authenticated, product_not_authorized, authorization_unavailable,
  invalid_authorization_result}`; `SENSITIVE_TOOL_NAMES`; `validate_event`.
- `agent/hooks.py`: `tool_governance[toolUseId]` con `action` allow|block,
  `reason` local cerrado (`invalid_tool_name`, `invalid_tool_input`,
  `invalid_complaint_id`, `invalid_invocation_state`), triple de autorización;
  cancel `MISSING_MERCHANT_CANCEL_REASON = "missing_merchant:clarification"`.
- `agent/result_capture.py`: correlación intento↔resultado por `toolUseId`,
  identidad de objeto y tipo-estricta de argumentos; `missing_merchant_blocked`.
- `agent/orchestrator.py`: `_ToolRecord`, `_tool_event_payload`, `_verified`,
  `_tool_outcome` (success|blocked|failure), `_is_verified_missing_merchant`,
  `_is_canonical_block`, `_is_successful_escalation`.

Colapsos causales vigentes (RED):

1. Bloqueo de gobierno vs bloqueo por clarificación de merchant faltante:
   ambos emergen solo como `result_status: "blocked"` en `tool_call`.
2. `authorization_verified: false` colapsa denied / unavailable / not_evaluated
   sin estado ni reason code.
3. `verified: false` colapsa retry/duplicado, excepción, cancelación, resultado
   ausente y verificación de acción fallida.

## Superficies de edición concretas (post-exploración)

```text
src/ai_banking_customer_service/observability/contract.py
src/ai_banking_customer_service/agent/orchestrator.py
src/ai_banking_customer_service/agent/hooks.py          # solo si el reason code lo exige
tests/unit/observability/test_contract.py
tests/unit/agent/test_orchestrator.py
tests/unit/agent/test_hooks.py                        # solo si hooks cambia
docs/observability.md
docs/STATUS.md
odd/tasks/spec-09a1-runtime-evidence.md
```

## Forecast anti-mega (sección 6 de la spec)

- WU1 contrato: ~210 líneas authored (producción ~90 + tests ~120).
- WU2 emisión: ~280 líneas authored (producción ~110 + tests ~170).
- WU3 docs: ~90 líneas (viajan con el comportamiento).
- Un solo dominio runtime: emisión de observabilidad.

## Tareas

- [x] **T1 — RED + WU1: contrato canónico de evidencia**
  Allowlists congeladas en `contract.py` y validador type-strict del bloque
  `evidence` (cinco dimensiones, ordinal, límites 16/64/8 KiB, marca cerrada de
  truncamiento, fail-closed ante malformado). RED: ImportError por validador
  inexistente. GREEN: 138 tests. Commit `8d11866`. Nota: primera entrega 489
  líneas; comprimida a exactamente 300 authored con parametrización, sin perder
  cobertura (compromiso documentado: `# fmt: off`/`# noqa: E501` en allowlists).
- [x] **T2 — WU2: emisión desde el orquestador**
  WU2 commit `be5cec2` (296i/3d): `_evidence_block` puro, correlación unívoca,
  fail-closed ante join ambiguo/duplicado/retry/huérfano/bool no estricto,
  truncamiento cerrado desde la ocurrencia 17, integración `validate_event`↔
  `validate_evidence`. RED: 11 tests (3 lifecycle por colapsos, 6 builder, 2
  contract). GREEN: 216 focales, 1260 unitarios. WU2b commit `e587c7c` (61i):
  negativos de privacidad (7 categorías prohibidas), auditoría fallida mantiene
  `orphaned` y clasificación, orden adversarial homónimo, duplicado explícito
  fail-closed, reason_code desde decision. 87 tests del archivo verdes.
  Bloque `evidence` por ocurrencia en el payload `tool_call` existente
  (invariante 8: no stream paralelo), correlación unívoca gobierno↔intento↔
  resultado, fail-closed ante duplicado/retry/lineage huérfano, tope de 16
  ocurrencias por trace con marca cerrada. TRIANGULATE: todos los estados de
  autorización, missing-data presente/ausente, allow/block, ejecución
  no-ejecutada/error/éxito, verificación +/-, 0/1/varias/>16 ocurrencias, orden
  adversarial, duplicado, retry, lineage huérfano, booleanos no estrictos,
  oversized, auditoría fallida, negativos de privacidad.
- [x] **T3 — WU3: documentación**
  Commit `e4c06ec` (197i/1d incluye este documento): sección 3.2.1 de
  `docs/observability.md` con dimensiones, vocabularios exactos, límites,
  correlación, fail-closed y privacidad; `docs/STATUS.md` con cierre 09A1,
  siguiente paso y registro fechado. Vocabularios verificados contra código.

## Verificación

```bash
uv run pytest -q <tests-focales-09A1>
uv run pytest -q <suites-runtime-afectadas>
uv run ruff check <archivos-Python-modificados>
uv run ruff format --check <archivos-Python-modificados>
git diff --check
```

## Evidencia de commits

- WU1 `8d11866` — contrato canónico y `validate_evidence` (300 authored).
- WU2 `be5cec2` — emisión `evidence` por ocurrencia (296i/3d).
- WU2b `e587c7c` — triangulación completa (61i).
- WU3 `e4c06ec` — documentación y tracking.

## Cierre

- Verificación independiente final: 330 focales + 1271 unitarios, Ruff check,
  Ruff format y diff check verdes; rama con exactamente 4 commits (+862/−5).
- Revisión nativa RDD `review-8869ce4e1f2ceb41`: aprobada (lente
  review-reliability), acknowledge quemado, revisión consumida. Hallazgos
  informativos no bloqueantes: `R3-evidence-not-required` (contract.py:128-133)
  y `R3-substring-membership` (contract.py:193) — trabajo posterior separado.
- Spec #09A2 desbloqueada para su handoff.
