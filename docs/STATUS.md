# STATUS — Estado de implementación

> Última actualización: 2026-10-03
> Contexto estable y decisiones de diseño: [../AGENTS.md](../AGENTS.md)
> Este documento se actualiza después de implementar cada componente.

---

## Resumen

Capa de datos, sandbox validado, tools y servicios mock están **completados y smoke-tested**.
El transporte tipado, las cuatro etapas de gobierno de Jev, el `GovernanceAdapter`, los hooks y tools de Strands, la observabilidad, el orquestador conversacional, la UI Chainlit delgada y la evaluación offline held-out de Spec #9 están **completados**.

**Siguiente paso:** Spec #10 — documentación final, slides y video pitch.

---

## Completado

### Datos y pipeline

- [x] Vistas raw registradas en DuckDB: `complaints`, `call_center_interactions`, `customers`, `products`, `transactions`.
- [x] Análisis de justificación del flujo (volumen, FCR, SLA breach, resolución).
- [x] Diagnóstico de integridad referencial → hallazgo: `product_id` es el vínculo confiable, no `customer_id`.

### Sandbox y validación

- [x] `agent_sandbox_final.parquet` con contexto completo y `recommended_action` determinística.
- [x] Data Quality Gate con Pandera (`scripts/data_preparation/10_validate_sandbox.py`).

### Tools

- [x] `get_dispute_context.py` — lectura del contexto del caso.
- [x] `get_recent_transactions.py` — lectura filtrada por `product_id`.
- [x] `block_card.py` — acción con policy fuera del prompt + verificación.
- [x] `escalate_case.py` — acción que genera Structured JSON Handoff.
- [x] smoke-tested (caso existente, inexistente, input inválido, idempotencia).

### Services (mock bancarios)

- [x] `card_service.py` — SQLite, atómico, idempotente.
- [x] `escalation_service.py` — SQLite, persiste handoffs.

### Configuración

- [x] `config.py` — `Settings` (.env) + `Policy` (policy.yaml), `SecretStr`, paths derivados.

### Gobierno — Jev

- [x] Schemas Pydantic de Jev (wire format Noul/Choice/Score).
- [x] Cliente Jev (adapter sobre `typesafe-sdk`).
- [x] Evaluaciones Jev: input screening + intent routing.
- [x] Evaluaciones Jev: tool gating + output screening, con reglas determinísticas previas y proyecciones semánticas minimizadas.
- [x] Lógica de decisión de gobierno: cuatro etapas, fail-closed, confidence gating, dominios de acción acotados y configuración tipada fail-fast.
- [x] `GovernanceAdapter` framework-agnostic: pipeline completo, auditoría, fail-closed, encadenamiento y trust boundaries.

### Agente — Strands

- [x] Registro de las 4 tools en el agente Strands.
- [x] Hooks de gobierno con `HookProvider` y `register_hooks`, validación fail-closed y estado concurrente aislado por `toolUseId`.
- [x] `BankingOrchestrator` stateful con Agent/modelo/captura efímeros por turno, cancelación y terminales seguros ES/PT.
- [x] Memoria por sesión con lock, TTL, FIFO, snapshots aislados y persistencia sanitizada.
- [x] Parser estricto de señales, detección determinística de idioma y prompt sin reglas duras.
- [x] Captura normalizada de resultados Strands y clasificación conservadora de acciones, retries y side effects inciertos.
- [x] Cobertura unitaria del flujo y tests de contrato contra Strands 1.57.1 sin red, modelo real ni Jev real.

### Observabilidad

- [x] Contrato de eventos (`contract.py`) y sink JSONL validado (`sink.py`).
- [x] `CompositeAuditSink` con fallback diagnóstico no durable y `AuditPersistenceError`.
- [x] Eventos `input`, `tool_call`, `escalation` y `response` con sanitización, lineage, correlación fallback y descendencia huérfana.

### UI — Chainlit

- [x] Capa de presentación delgada: valida entrada, invoca al orquestador y renderiza sin lógica de negocio, política, gobierno ni auditoría.
- [x] Configuración de startup fail-closed con HTML inseguro deshabilitado y composition root exacto, lazy e inyectable.
- [x] Render seguro ES/PT con acciones exhaustivas y fallback cerrado ante acciones desconocidas o fallos de entrega.
- [x] Task retenido por turno, cancelación cooperativa, monitor de finalización y reconciliación de resultados tardíos sin ejecución duplicada.
- [x] Cobertura unitaria, de contrato Chainlit 2.12 y smoke portable con aislamiento del app-root entre proceso padre e hijo.
- [x] Validación completada: 78 tests enfocados y 842 tests del repositorio; Ruff check, Ruff format y diff check pasaron.

### Evaluación offline — held-out

- [x] Configuración, casos y manifests tipados con hash SHA-256, cobertura mínima e independencia development/held-out fail-closed.
- [x] Tools enlazadas a dos SQLite aislados por caso sin exponer paths en firmas, schemas, gobierno ni auditoría.
- [x] Un proceso `spawn` no-daemon por caso con timeout, gracia, terminación, join y cleanup poseídos por el padre.
- [x] Clasificación determinística de unsafe outcomes, SAR, containment, escalation quality, segmentos y percentiles inclusivos.
- [x] Reportes JSON/Markdown determinísticos y atómicos, más CLI `python -m` con errores sanitizados.
- [x] Validación completada: 150 tests de evaluación, 65 tests afectados del agente, 984 tests unitarios y 996 tests del repositorio; Ruff check, Ruff format y diff check pasaron.
- [x] Manifests verificados: 50 casos held-out (12 en portugués) y 30 de desarrollo, sin leakage detectado.

### Documentación

- [x] `README.md` y `README.es.md` — punto de entrada bilingüe del repositorio.
- [x] `AGENTS.md` — contexto estable, decisiones de diseño, no-negociables.
- [x] `findings/data_quality.md` — hallazgos de calidad de datos.
- [x] `typesafe_jev/README.md` — investigación de Jev (contratos, límites, umbrales).

---

## Plan (orden por dependencias)

| #   | Estado    | Componente                                                                   | Depende de       | Spec sugerido |
| --- | --------- | ---------------------------------------------------------------------------- | ---------------- | ------------- |
| 1   | Completado | Schemas Pydantic de Jev (wire format Noul/Choice/Score)                     | —                | Spec #1       |
| 2   | Completado | Cliente Jev (adapter sobre `typesafe-sdk`)                                  | #1               | Spec #1       |
| 3   | Completado | Evaluaciones Jev: input screening + intent routing                          | #2               | Spec #2       |
| 4   | Completado | Lógica de decisión de gobierno (`GovernanceDecision`, umbrales, fail-closed) | #3               | Spec #3       |
| 5   | Completado | Evaluaciones Jev: tool gating + output screening                            | #2, #4           | Spec #4       |
| 6   | Completado | Registro de las 4 tools en el agente Strands                                | tools existentes | Spec #5       |
| 7   | Completado | Hooks de Strands con Jev (`BeforeInvocationEvent`, `BeforeToolCallEvent`)   | #4, #5, #6       | Spec #6       |
| 8   | Completado | Orquestador / flujo conversacional (memoria, clarificación, abstención)     | #6, #7           | Spec #7       |
| 9   | Completado | UI Chainlit (capa de presentación delgada, decisión #11)                    | #8               | Spec #8       |
| 10  | Completado | Evaluación offline held-out (métricas del hackathon)                        | #8               | Spec #9       |
| 11  | Pendiente  | Docs finales, slides, video pitch                                           | todo             | Spec #10      |

> La agrupación de specs es tentativa. El orden de dependencias es lo vinculante:
> no construir un componente antes que sus dependencias.

---

## En progreso

- Ninguno actualmente. Spec #9 está completada; el próximo componente es Spec #10.

---

## Deuda conocida

- Deuda de seguridad: la autorización del usuario sobre el producto no está verificada. Consultar por `product_id` resuelve integridad referencial, NO autorización. Falta validar que el usuario autenticado tenga permiso sobre el producto antes de exponer sus transacciones.
- El adapter de Jev depende de typesafe-sdk 0.7.2 (fijado en uv.lock). Si se actualiza el lock a una versión nueva, revalidar el adapter (nombres de excepciones, estructura de respuestas, comportamiento de retries).
- Los umbrales de tool gating y output screening son provisionales; deben calibrarse con la evaluación offline de Spec #9.
- Los turnos activos y resultados pendientes de la UI se mantienen en memoria: un reinicio, una sesión perdida o procesos no afines pueden perderlos. La UI actual es adecuada para la demo, no ofrece durabilidad de producción.
- La suite emite una advertencia de deprecación preexistente de terceros por la configuración class-based de Pydantic usada por Traceloop; no afecta el GREEN actual, pero depende de una corrección upstream o actualización futura.

1. **`unresolved_questions` es `list | None`, no `list[str] | None`.** La tool y Spec #4 aceptan elementos de cualquier tipo. Riesgo: el modelo podría pasar elementos no-string. Mitigación futura: validar tipo de elementos en la tool o en TOOL_ARG_CONTRACTS.

2. **`days_before` solo exige un entero positivo, sin límite superior.** Un valor muy grande podría causar consultas lentas. Mitigación futura: agregar límite superior en TOOL_ARG_CONTRACTS.

3. **`reason` acepta cualquier string.** Los valores del docstring son ejemplos, no un vocabulario cerrado. Riesgo: el modelo podría pasar razones arbitrarias. Mitigación futura: definir un vocabulario cerrado o validar contra una allowlist.

---

## Registro de actualizaciones

- **2026-10-03** — Spec #9 v4 implementada con TDD. Se completaron configuración/casos/manifests fail-closed, aislamiento por caso con tools enlazadas a SQLite privados, worker y runner `spawn` con lifecycle parent-owned, clasificación/métricas determinísticas, reportes JSON/Markdown atómicos y CLI pública. Pasaron 150 tests de evaluación, 65 tests afectados del agente, 984 tests unitarios y 996 tests del repositorio; Ruff check, Ruff format, diff check, hashes, cobertura, independencia, APIs públicas, schemas de tools y lifecycle real `spawn` quedaron verificados. El comando productivo con modelo/Jev real no se ejecutó; se verificaron el parser, el entry point y el pipeline completo con fakes, sin generar `evals/reports/`.
- **2026-10-02** — Spec #8 v5 verificada. Se completó la UI Chainlit como capa delgada, con startup fail-closed, composition root exacto y lazy, render seguro ES/PT, task retenido, cancelación cooperativa y reconciliación de resultados tardíos. La cobertura incluye contratos de Chainlit y smoke portable con app-roots aislados para padre e hijo. Pasaron 78 tests enfocados, 842 tests del repositorio, Ruff check, Ruff format y diff check. Permanecen explícitos el límite de durabilidad in-memory y la advertencia de deprecación de terceros Traceloop/Pydantic.
- **2026-10-02** — Spec #7 v5 implementada con TDD. Se completaron `BankingOrchestrator`, memoria de sesión bloqueada, captura normalizada de tools, señales estrictas, idioma ES/PT, templates seguros y composición de auditoría fail-closed. El flujo cubre respuesta, clarificación, abstención, bloqueo, escalamiento, cancelación e incertidumbre de side effects; emite eventos sanitizados con lineage durable, fallback de correlación y propagación `orphaned`. La integración valida los contratos instalados de Strands 1.57.1 con modelos y adapters falsos, sin red ni llamadas reales a Jev.
- **2026-10-02** — Advisories de confiabilidad posteriores a Spec #6 resueltos con TDD: el contrato de observabilidad rechaza `cost_usd` no finito (`NaN`, `+Inf`, `-Inf`) y `before_invocation` elimina estado de gobierno derivado de invocaciones previas antes de validar el turno actual, preservando únicamente el contexto propiedad del orquestador. Ambos casos quedan cubiertos por tests de regresión y no son deuda pendiente para specs futuras.
- **2026-10-02** — Spec #6 v5 implementada con TDD. `GovernanceAdapter` framework-agnostic. `GovernanceHooks` implementa `HookProvider` con `register_hooks`; `cancel`/`cancel_tool` como atributos. `before_tool_call` valida `tool_use`/`name`/`input`/`complaint_id` antes de indexar. Soporte para tools concurrentes: `routing_event_id` como padre estable, resultados por `toolUseId` en `tool_governance`, sin sobrescribir claves globales. `build_actions_taken` compatible con Spec #4: salida con EXACTAMENTE `ACTION_REQUIRED_FIELDS` (sin `target_id`), `ACTION_VERIFICATIONS` consultado por `action_name`. Serialización con `allow_nan=False`, `reasons` como `list[str]`. Módulo de observabilidad completado y `docs/observability.md` actualizado.
- **2026-10-02** — Spec #5 v3 implementada con TDD. Wrappers `@tool` de Strands para las 4 tools en `agent/tools.py`, docstrings en inglés que reflejan categorías reales de retorno, sincronización con `TOOL_ARG_CONTRACTS`/`ALLOWED_TOOLS` (nombres, exposición) y con firmas originales (tipos, defaults, nullabilidad via `inspect.signature`), tipos JSON verificados, delegación directa sin lógica adicional. `tool_call` asignado al orquestador en `observability.md`. Llamadas directas declaradas como solo-para-tests.
- **2026-10-01** — Spec #4 v5 implementada con TDD. Se agregó `sanitization.py` con API pública y comparación exacta de claves. Tool gating y output screening combinan una capa determinística (allowlists, tipos, rangos, autenticación, confirmación, verificación de `complaint_id` y detección de secretos) con una capa semántica Jev (`intent_matches_tool_call` Noul y `output_safety_semantic` Score). Los trust boundaries de `customer_context`, `verified_facts` y `actions_taken` usan allowlists internas y proyecciones minimizadas separan ejecución de estado Jev. `decide_tool_gating` limita sus acciones a `BLOCK/ALLOW` y `decide_output_screening` a `REVIEW/ALLOW`; sus reasons tienen precedencia determinística. `GovernanceStage` incluye ambas etapas, se preservan los umbrales efectivos y se validan probabilidades finitas. Los umbrales son provisionales hasta su calibración en Spec #9.
- **2026-10-01** — Spec #3 v4 implementada con TDD. API de dos etapas (`decide_screening` / `decide_routing`), totalidad acotada fail-closed, validación de dominio de intent contra `EXPECTED_INTENTS`, umbrales tipados en `Policy` + `configs/policy.yaml` con `load_policy` fail-fast y mapper `from_policy`, confidence gating, metadata y probabilidades preservadas por etapa, reasons con códigos estables y precedencia. Vocabulario `block|review|allow`; stages `input_screening|intent_routing`.
- **2026-10-01** — Spec #2 implementada con TDD. Evaluaciones `prompt_injection`, `social_engineering` y `banking_intent` en `governance/jev/evaluations.py`, con sanitización de secretos prohibidos (PAN/CVV/credenciales/tokens) en los formatos enumerados, reducción de falsos positivos mediante indicadores explícitos de asignación, cobertura trilingüe (es/pt/en), batching de `screen_input`, precedencia literal de intents, metadata preservada (`model`/`usage`) y validación de dominio de `probabilities`. Entry points públicos: `screen_input` y `route_banking_intent`. Tests unitarios sin red con mock del cliente de Spec #1.
- **2026-09-30** — Spec #1 implementada con TDD. Schemas alineados al wire de Jev, cliente adapter sobre `typesafe-sdk`, bootstrap hermético, parsing discriminado y mapeo tipado de errores SDK.
- **2026-09-29** — Se completó `config.py` (Settings + Policy). Se definió Chainlit como UI y se agregó la decisión de diseño #11 (UI como capa de presentación delgada). Se crea este documento.
