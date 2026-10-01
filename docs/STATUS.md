# STATUS — Estado de implementación

> Última actualización: 2026-10-01
> Contexto estable y decisiones de diseño: [../AGENTS.md](../AGENTS.md)
> Este documento se actualiza después de implementar cada componente.

---

## Resumen

Capa de datos, sandbox validado, tools y servicios mock están **completados y smoke-tested**.
El transporte tipado y las evaluaciones de input screening e intent routing de Jev están **completados**. Las decisiones de gobierno, Strands, el orquestador, la UI y la evaluación offline siguen **pendientes**.

**Siguiente paso:** Spec #3 — Lógica de decisión de gobierno.

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

### Documentación

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
| 4   | Pendiente  | Lógica de decisión de gobierno (`GovernanceDecision`, umbrales, fail-closed) | #3               | Spec #3       |
| 5   | Pendiente  | Evaluaciones Jev: tool gating + output screening                            | #2, #4           | Spec #4       |
| 6   | Pendiente  | Registro de las 4 tools en el agente Strands                                | tools existentes | Spec #5       |
| 7   | Pendiente  | Hooks de Strands con Jev (`before_model_hook`, `before_tool_hook`)          | #4, #5, #6       | Spec #6       |
| 8   | Pendiente  | Orquestador / flujo conversacional (memoria, clarificación, abstención)     | #6, #7           | Spec #7       |
| 9   | Pendiente  | UI Chainlit (capa de presentación delgada, decisión #11)                    | #8               | Spec #8       |
| 10  | Pendiente  | Evaluación offline held-out (métricas del hackathon)                        | #8               | Spec #9       |
| 11  | Pendiente  | Docs finales, slides, video pitch                                           | todo             | Spec #10      |

> La agrupación de specs es tentativa. El orden de dependencias es lo vinculante:
> no construir un componente antes que sus dependencias.

---

## En progreso

- Ninguno actualmente.

---

## Deuda conocida

- Deuda de seguridad: la autorización del usuario sobre el producto no está verificada. Consultar por `product_id` resuelve integridad referencial, NO autorización. Falta validar que el usuario autenticado tenga permiso sobre el producto antes de exponer sus transacciones.
- El adapter de Jev depende de typesafe-sdk 0.7.2 (fijado en uv.lock). Si se actualiza el lock a una versión nueva, revalidar el adapter (nombres de excepciones, estructura de respuestas, comportamiento de retries)

---

## Registro de actualizaciones

- **2026-10-01** — Spec #2 implementada con TDD. Evaluaciones `prompt_injection`, `social_engineering` y `banking_intent` en `governance/jev/evaluations.py`, con sanitización de secretos prohibidos (PAN/CVV/credenciales/tokens) en los formatos enumerados, reducción de falsos positivos mediante indicadores explícitos de asignación, cobertura trilingüe (es/pt/en), batching de `screen_input`, precedencia literal de intents, metadata preservada (`model`/`usage`) y validación de dominio de `probabilities`. Entry points públicos: `screen_input` y `route_banking_intent`. Tests unitarios sin red con mock del cliente de Spec #1.
- **2026-09-30** — Spec #1 implementada con TDD. Schemas alineados al wire de Jev, cliente adapter sobre `typesafe-sdk`, bootstrap hermético, parsing discriminado y mapeo tipado de errores SDK.
- **2026-09-29** — Se completó `config.py` (Settings + Policy). Se definió Chainlit como UI y se agregó la decisión de diseño #11 (UI como capa de presentación delgada). Se crea este documento.
