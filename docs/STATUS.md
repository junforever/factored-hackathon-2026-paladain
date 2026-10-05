# STATUS — Estado de implementación

> Última actualización: 2026-10-05
> Contexto estable y decisiones de diseño: [../AGENTS.md](../AGENTS.md)
> Este documento se actualiza después de implementar cada componente.

---

## Resumen

Capa de datos, sandbox validado, tools y servicios mock están **completados y smoke-tested**.
El transporte tipado, las cuatro etapas de gobierno de Jev, el `GovernanceAdapter`, los hooks y tools de Strands, la observabilidad, el orquestador conversacional, la UI Chainlit delgada y la evaluación offline held-out de Spec #9 están **completados**. La evaluación quedó reparada sobre casos reales del sandbox y fue ejecutada 50/50 sin fallos de ejecución; el resultado sigue siendo provisional porque SAR permanece en 0% y persisten fallos de tipo de escalamiento. La demo local cuenta además con un catálogo reproducible de seis casos, reset SQLite acotado y una guía de ejecución para jueces.

**Siguiente paso:** recuperar SAR y corregir los tipos de escalamiento usando evidencia positiva y negativa de desarrollo, reducir latencia y resolver el caso inseguro `EVAL-009`; en paralelo, completar la validación integral y manual del flujo de demo antes de slides y video pitch de Spec #10.

---

## Completado

### Datos y pipeline

- [x] Vistas raw registradas en DuckDB: `complaints`, `call_center_interactions`, `customers`, `products`, `transactions`.
- [x] Análisis de justificación del flujo (volumen, FCR, SLA breach, resolución).
- [x] Diagnóstico de integridad referencial → hallazgo: `product_id` es el vínculo confiable, no `customer_id`.

### Sandbox y validación

- [x] `agent_sandbox_final.parquet` con contexto completo y `recommended_action` determinística.
- [x] Data Quality Gate con Pandera (`scripts/data_preparation/10_validate_sandbox.py`).
- [x] Artefactos portátiles `agent_sandbox_final.parquet` y `ai_banking.duckdb`, generados con `scripts/data_preparation/11_build_portable_demo.py` y validados mediante `scripts/verify_demo_artifacts.py` y su manifiesto SHA-256.

### Tools

- [x] `get_dispute_context.py` — lectura del contexto del caso.
- [x] `get_recent_transactions.py` — lectura filtrada por `product_id`.
- [x] `block_card.py` — acción con policy fuera del prompt + verificación.
- [x] `escalate_case.py` — acción que genera Structured JSON Handoff.
- [x] smoke-tested (caso existente, inexistente, input inválido, idempotencia).

### Services (mock bancarios)

- [x] `card_service.py` — SQLite, atómico, idempotente.
- [x] `escalation_service.py` — SQLite, persiste handoffs.

### Demo local reproducible

- [x] `configs/demo_cases.yaml` — fuente de verdad versionada con seis escenarios, IDs reales, prompts ES/PT y resultados esperados.
- [x] `scripts/data_preparation/12_build_demo_cases.py` — selección determinística y validación del catálogo contra el sandbox actual.
- [x] `scripts/reset_demo_state.py` — dry-run y reset idempotente de un caso o del catálogo completo, limitado al estado SQLite mutable relacionado.
- [x] `README.md` y `chainlit.md` — recorrido para generar, iniciar Chainlit, copiar un prompt, observar, previsualizar el reset, restablecer y repetir.

Comandos operativos exactos:

```bash
uv run python scripts/data_preparation/12_build_demo_cases.py
uv run chainlit run app/chainlit_app.py --headless --host 127.0.0.1 --port 8000 --ci
uv run python scripts/reset_demo_state.py --dry-run --case CMP-04WL95SE9CYXX4A8MSPV
uv run python scripts/reset_demo_state.py --case CMP-04WL95SE9CYXX4A8MSPV
uv run python scripts/reset_demo_state.py --dry-run
uv run python scripts/reset_demo_state.py
```

Antes del reset deben detenerse las escrituras activas de la demo. `configs/demo_cases.yaml` solo garantiza IDs para el sandbox con el que se generó; si el sandbox se regenera o reemplaza, también debe regenerarse el catálogo.

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
- [x] Contratos de side effects corregidos para comparar paths y bytes antes/después sin rechazar traducciones ni `chainlit.md` intencionales.
- [x] Validación histórica de Spec #8: 78 tests enfocados y 842 tests del repositorio; Ruff check, Ruff format y diff check pasaron dentro de ese alcance.

### Evaluación offline — held-out

- [x] Configuración, casos y manifests tipados con hash SHA-256, cobertura mínima e independencia development/held-out fail-closed.
- [x] Dataset activo `v1.0.2`: 50 casos held-out (12 en portugués) y 30 de desarrollo usan IDs reales y disjuntos de reclamaciones del sandbox. Ambos manifests quedan vinculados de forma fail-closed al path y al hash SHA-256 exactos del sandbox. Los fixtures `v1.0.0` y `v1.0.1` permanecen históricos e inmutables.
- [x] Tools enlazadas a dos SQLite aislados por caso sin exponer paths en firmas, schemas, gobierno ni auditoría.
- [x] Un proceso `spawn` no-daemon por caso con timeout, gracia, terminación, join y cleanup poseídos por el padre.
- [x] Clasificación determinística de unsafe outcomes, SAR, containment, escalation quality, segmentos y percentiles inclusivos.
- [x] Semántica corregida: un `BLOCK` de gobierno ya no se presenta como bloqueo bancario de tarjeta; el flujo termina en escalamiento seguro sin tools.
- [x] Umbrales provisionales de routing y tool gating calibrados sin relajar gates determinísticos; instrucciones al modelo reforzadas para conservar el ID exacto, leer contexto primero y usar planes y argumentos canónicos de tools.
- [x] Resultados Strands normalizados: los bloques de texto que contienen objetos JSON válidos se capturan como resultados estructurados, preservando el comportamiento fail-closed para texto inválido o no-objeto.
- [x] Reportes JSON/Markdown determinísticos y atómicos, más CLI `python -m` con errores sanitizados. Los reportes futuros incluyen `case_outcomes` acotados y privacy-safe; los reportes históricos ya generados no se modificaron y permanecen locales.
- [x] Validación histórica de implementación de Spec #9: 150 tests de evaluación, 65 tests afectados del agente, 984 tests unitarios y 996 tests del repositorio; Ruff check, Ruff format y diff check pasaron dentro de ese alcance.

#### Medición final held-out `v1.0.2`

Reporte local: `evals/reports/eval_1.0.2_20261005T005146Z.md`.

| Métrica | Resultado |
| --- | ---: |
| Casos completados | 50/50 |
| Fallos de ejecución | 0 |
| SAR | 0% |
| Containment | 60% |
| Escalamientos correctos | 5 |
| Escalamientos innecesarios | 1 |
| Unsafe outcomes | 1/50 (2%) |
| Tool-plan match | 39/50 (78%) |
| Latencia p50 | 10,414 ms |
| Latencia p95 | 20,347.35 ms |

SAR no se recuperó y la latencia p95 empeoró frente al run grounded anterior (~19.29 s); la mejora de containment y seguridad no compensa esas regresiones.

Resumen por escenario:

- Ataques: 5/5 terminaron correctamente en revisión/escalamiento seguro, sin tools.
- Resolución normal: 14/15 casos contenidos; `EVAL-009` fue el único unsafe outcome y escalamiento innecesario.
- Datos faltantes: 5/5 contenidos mediante abstención o solicitud de información, sin escrituras.
- Escalamiento: los casos human-required siguen 10/10 con tipo incorrecto; los ambiguos conservan fallos de omisión o tipo de escalamiento.

Evidencia de desarrollo: `DEV-001`, `DEV-016` y `DEV-030` rutearon con confianza, pero las lecturas esperadas fueron bloqueadas por tool gating semántico con scores de 0.34–0.39. El resultado fue abstención segura y SAR 0. La siguiente calibración necesita evidencia positiva y negativa de development; no debe ajustarse usando held-out por sí solo.

### Documentación

- [x] `README.md` y `README.es.md` — punto de entrada bilingüe del repositorio.
- [x] `README.md` y `chainlit.md` — catálogo de seis escenarios y recorrido local repetible para jueces.
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

### Próximo trabajo de evaluación

- Recuperar SAR con cobertura de calibración positiva y negativa en development, sin entrenar ni ajustar desde held-out solamente.
- Corregir los tipos de escalamiento en escenarios human-required y ambiguous, manteniendo los contratos fail-closed.
- Reducir la latencia p50/p95 sin ocultar la regresión medida de 10,414/20,347.35 ms.
- Resolver y volver a verificar el único caso unsafe restante, `EVAL-009`.

### Verificación independiente final

- [x] `uv run pytest -q` — 1044 tests pasaron, 0 fueron omitidos y se emitió 1 warning de deprecación preexistente de Traceloop/Pydantic.
- [x] La prueba de identidad de fixtures congelados pasó dentro de la suite completa.
- [x] `uv run ruff check .` — pasó.
- [x] Ruff format candidate-scoped — pasó para los 14 archivos Python modificados.
- [x] `git diff --check` — pasó; Git informó únicamente un warning LF/CRLF sobre `odd/tasks/evaluation-case-identity.md`.
- [ ] `uv run ruff format --check .` — el check global todavía falla solo en `src/ai_banking_customer_service/services/escalation_service.py` y `tests/unit/services/test_demo_state_reset.py`; ambos archivos están sin cambios respecto al merge-base, por lo que constituyen deuda preexistente y no un defecto del candidato.
- No se ejecutó una nueva evaluación con modelo después de los cambios exclusivamente de observabilidad; las métricas held-out `v1.0.2` registradas arriba no cambiaron.
- Permanecen pendientes la verificación de artefactos portátiles y el recorrido manual/live de los seis casos en Chainlit. Esta verificación no implica completitud del producto: continúan las limitaciones de SAR, tipos de escalamiento, latencia y `EVAL-009`.

### Estado de verificación del catálogo y reset

- Catálogo: `uv run pytest -q tests/unit/test_demo_cases.py` — 3 tests pasaron en la entrega T1; `uv run ruff check scripts/data_preparation/12_build_demo_cases.py tests/unit/test_demo_cases.py` también pasó.
- Reset: `uv run pytest -q tests/unit/services/test_demo_state_reset.py` — 5 tests pasaron en la entrega T2; la verificación independiente cubrió además 33 tests existentes de factory/tools y Ruff.
- Documentación T3: `python -c "from pathlib import Path; files=[Path('README.md'),Path('chainlit.md'),Path('docs/STATUS.md')]; text='\n'.join(p.read_text(encoding='utf-8') for p in files); ids=[line.split(': ',1)[1] for line in Path('configs/demo_cases.yaml').read_text(encoding='utf-8').splitlines() if line.strip().startswith('complaint_id: ')]; assert len(ids)==6 and all(value in text for value in ids); assert 'CMP-DEMO' not in Path('chainlit.md').read_text(encoding='utf-8')"` — pasó la verificación estructural de IDs y placeholders.
- Documentación T3: `git diff --check -- README.md chainlit.md docs/STATUS.md` — pasó sin errores de whitespace.

### Limitaciones informativas del reset

- Las bases SQLite de tarjetas y escalamiento son independientes. Si el segundo paso falla después de que el primero se confirma, debe corregirse la causa y repetirse el mismo comando; el reset es idempotente y el retry es seguro.
- `--case` restaura el estado de tarjeta a nivel de `product_id`, aunque el estado de escalamiento se acota al `complaint_id`. Otra reclamación que comparta ese producto observará el estado de tarjeta restaurado.

---

## Deuda conocida

- Deuda de seguridad: la autorización del usuario sobre el producto no está verificada. Consultar por `product_id` resuelve integridad referencial, NO autorización. Falta validar que el usuario autenticado tenga permiso sobre el producto antes de exponer sus transacciones.
- El adapter de Jev depende de typesafe-sdk 0.7.2 (fijado en uv.lock). Si se actualiza el lock a una versión nueva, revalidar el adapter (nombres de excepciones, estructura de respuestas, comportamiento de retries).
- Los umbrales de routing y tool gating fueron calibrados provisionalmente, pero la evidencia development muestra bloqueos semánticos de lecturas esperadas con scores de 0.34–0.39. Cualquier ajuste adicional requiere casos positivos y negativos de development y no debe usar held-out como conjunto de tuning.
- Los turnos activos y resultados pendientes de la UI se mantienen en memoria: un reinicio, una sesión perdida o procesos no afines pueden perderlos. La UI actual es adecuada para la demo, no ofrece durabilidad de producción.
- La suite completa pasa 1044 tests sin skips, pero emite 1 advertencia de deprecación preexistente de terceros por la configuración class-based de Pydantic usada por Traceloop; no afecta el GREEN actual, pero depende de una corrección upstream o actualización futura.
- El check global `uv run ruff format --check .` conserva deuda preexistente en `src/ai_banking_customer_service/services/escalation_service.py` y `tests/unit/services/test_demo_state_reset.py`; ambos archivos están sin cambios respecto al merge-base. El check candidate-scoped de los 14 archivos Python modificados sí pasó.

1. **`unresolved_questions` es `list | None`, no `list[str] | None`.** La tool y Spec #4 aceptan elementos de cualquier tipo. Riesgo: el modelo podría pasar elementos no-string. Mitigación futura: validar tipo de elementos en la tool o en TOOL_ARG_CONTRACTS.

2. **`days_before` solo exige un entero positivo, sin límite superior.** Un valor muy grande podría causar consultas lentas. Mitigación futura: agregar límite superior en TOOL_ARG_CONTRACTS.

3. **`reason` acepta cualquier string.** Los valores del docstring son ejemplos, no un vocabulario cerrado. Riesgo: el modelo podría pasar razones arbitrarias. Mitigación futura: definir un vocabulario cerrado o validar contra una allowlist.

---

## Registro de actualizaciones

- **2026-10-05** — Se cerró la reparación grounded de evaluación con datasets activos held-out/development `v1.0.2`, IDs reales disjuntos y binding al sandbox. Se corrigieron la semántica de bloqueo de gobierno frente a bloqueo de tarjeta, la calibración provisional de routing/tool gating, las instrucciones exactas/canónicas de tools y la normalización de resultados JSON text de Strands. El run final completó 50/50 sin fallos: SAR 0%, containment 60%, 5 escalamientos correctos, 1 innecesario, 1 unsafe (2%), tool-plan 78%, p50 10,414 ms y p95 20,347.35 ms. Quedan SAR, tipos de escalamiento, latencia, cobertura de calibración development y `EVAL-009`; los reportes futuros agregan `case_outcomes` privacy-safe sin modificar reportes históricos locales.
- **2026-10-04** — Se documentó el flujo local reproducible de seis casos: generación y validación del catálogo, arranque de Chainlit, prompts ES/PT con IDs reales, resultados esperados, dry-run, reset acotado y repetición. La verificación estructural documental y `git diff --check` pasaron; suite completa, Ruff, artefactos portátiles y recorrido live/manual permanecen pendientes de la validación final. Se registraron como límites informativos las transacciones separadas entre servicios y el alcance de tarjeta por producto para `--case`.
- **2026-10-03** — Spec #9 v4 implementada con TDD. Se completaron configuración/casos/manifests fail-closed, aislamiento por caso con tools enlazadas a SQLite privados, worker y runner `spawn` con lifecycle parent-owned, clasificación/métricas determinísticas, reportes JSON/Markdown atómicos y CLI pública. En la verificación histórica y acotada a esa entrega pasaron 150 tests de evaluación, 65 tests afectados del agente, 984 tests unitarios y 996 tests del repositorio; Ruff check, Ruff format, diff check, hashes, cobertura, independencia, APIs públicas, schemas de tools y lifecycle real `spawn` quedaron verificados dentro de ese alcance. El comando productivo con modelo/Jev real no se ejecutó; se verificaron el parser, el entry point y el pipeline completo con fakes, sin generar `evals/reports/`.
- **2026-10-02** — Spec #8 v5 verificada. Se completó la UI Chainlit como capa delgada, con startup fail-closed, composition root exacto y lazy, render seguro ES/PT, task retenido, cancelación cooperativa y reconciliación de resultados tardíos. La cobertura incluye contratos de Chainlit y smoke portable con app-roots aislados para padre e hijo. En la verificación histórica y acotada a esa entrega pasaron 78 tests enfocados, 842 tests del repositorio, Ruff check, Ruff format y diff check. Permanecen explícitos el límite de durabilidad in-memory y la advertencia de deprecación de terceros Traceloop/Pydantic.
- **2026-10-02** — Spec #7 v5 implementada con TDD. Se completaron `BankingOrchestrator`, memoria de sesión bloqueada, captura normalizada de tools, señales estrictas, idioma ES/PT, templates seguros y composición de auditoría fail-closed. El flujo cubre respuesta, clarificación, abstención, bloqueo, escalamiento, cancelación e incertidumbre de side effects; emite eventos sanitizados con lineage durable, fallback de correlación y propagación `orphaned`. La integración valida los contratos instalados de Strands 1.57.1 con modelos y adapters falsos, sin red ni llamadas reales a Jev.
- **2026-10-02** — Advisories de confiabilidad posteriores a Spec #6 resueltos con TDD: el contrato de observabilidad rechaza `cost_usd` no finito (`NaN`, `+Inf`, `-Inf`) y `before_invocation` elimina estado de gobierno derivado de invocaciones previas antes de validar el turno actual, preservando únicamente el contexto propiedad del orquestador. Ambos casos quedan cubiertos por tests de regresión y no son deuda pendiente para specs futuras.
- **2026-10-02** — Spec #6 v5 implementada con TDD. `GovernanceAdapter` framework-agnostic. `GovernanceHooks` implementa `HookProvider` con `register_hooks`; `cancel`/`cancel_tool` como atributos. `before_tool_call` valida `tool_use`/`name`/`input`/`complaint_id` antes de indexar. Soporte para tools concurrentes: `routing_event_id` como padre estable, resultados por `toolUseId` en `tool_governance`, sin sobrescribir claves globales. `build_actions_taken` compatible con Spec #4: salida con EXACTAMENTE `ACTION_REQUIRED_FIELDS` (sin `target_id`), `ACTION_VERIFICATIONS` consultado por `action_name`. Serialización con `allow_nan=False`, `reasons` como `list[str]`. Módulo de observabilidad completado y `docs/observability.md` actualizado.
- **2026-10-02** — Spec #5 v3 implementada con TDD. Wrappers `@tool` de Strands para las 4 tools en `agent/tools.py`, docstrings en inglés que reflejan categorías reales de retorno, sincronización con `TOOL_ARG_CONTRACTS`/`ALLOWED_TOOLS` (nombres, exposición) y con firmas originales (tipos, defaults, nullabilidad via `inspect.signature`), tipos JSON verificados, delegación directa sin lógica adicional. `tool_call` asignado al orquestador en `observability.md`. Llamadas directas declaradas como solo-para-tests.
- **2026-10-01** — Spec #4 v5 implementada con TDD. Se agregó `sanitization.py` con API pública y comparación exacta de claves. Tool gating y output screening combinan una capa determinística (allowlists, tipos, rangos, autenticación, confirmación, verificación de `complaint_id` y detección de secretos) con una capa semántica Jev (`intent_matches_tool_call` Noul y `output_safety_semantic` Score). Los trust boundaries de `customer_context`, `verified_facts` y `actions_taken` usan allowlists internas y proyecciones minimizadas separan ejecución de estado Jev. `decide_tool_gating` limita sus acciones a `BLOCK/ALLOW` y `decide_output_screening` a `REVIEW/ALLOW`; sus reasons tienen precedencia determinística. `GovernanceStage` incluye ambas etapas, se preservan los umbrales efectivos y se validan probabilidades finitas. Los umbrales son provisionales hasta su calibración en Spec #9.
- **2026-10-01** — Spec #3 v4 implementada con TDD. API de dos etapas (`decide_screening` / `decide_routing`), totalidad acotada fail-closed, validación de dominio de intent contra `EXPECTED_INTENTS`, umbrales tipados en `Policy` + `configs/policy.yaml` con `load_policy` fail-fast y mapper `from_policy`, confidence gating, metadata y probabilidades preservadas por etapa, reasons con códigos estables y precedencia. Vocabulario `block|review|allow`; stages `input_screening|intent_routing`.
- **2026-10-01** — Spec #2 implementada con TDD. Evaluaciones `prompt_injection`, `social_engineering` y `banking_intent` en `governance/jev/evaluations.py`, con sanitización de secretos prohibidos (PAN/CVV/credenciales/tokens) en los formatos enumerados, reducción de falsos positivos mediante indicadores explícitos de asignación, cobertura trilingüe (es/pt/en), batching de `screen_input`, precedencia literal de intents, metadata preservada (`model`/`usage`) y validación de dominio de `probabilities`. Entry points públicos: `screen_input` y `route_banking_intent`. Tests unitarios sin red con mock del cliente de Spec #1.
- **2026-09-30** — Spec #1 implementada con TDD. Schemas alineados al wire de Jev, cliente adapter sobre `typesafe-sdk`, bootstrap hermético, parsing discriminado y mapeo tipado de errores SDK.
- **2026-09-29** — Se completó `config.py` (Settings + Policy). Se definió Chainlit como UI y se agregó la decisión de diseño #11 (UI como capa de presentación delgada). Se crea este documento.
