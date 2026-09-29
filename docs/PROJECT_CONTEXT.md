# PROJECT_CONTEXT — Factored AI & Data Hackathon 2026

> Fuente de contexto estable para cualquier agente o desarrollador que trabaje
> en este proyecto. Léelo antes de implementar cualquier componente.
> Este documento contiene solo información que cambia rara vez.
> El estado de implementación (qué hay, qué falta) vive en `docs/STATUS.md`.

---

## 1. Resumen ejecutivo

Construimos un **sistema AI-first de servicio al cliente bancario** para el Factored AI & Data Hackathon 2026. No es un chatbot: es un sistema que entiende → decide → actúa → verifica → escala.
El dataset provisto es **LATAM Bank**, sintético, con ~19M de registros en 13 tablas, cubriendo México, Colombia y Argentina entre junio 2023 y junio 2026. Incluye desafíos de calidad intencionales (~2% duplicados, ~5% nulos, late arrivals, schema evolution).
El sistema debe demostrar resolución automatizada segura, abstención cuando corresponde, y escalamiento estructurado a humanos, en español y portugués.

---

## 2. Flujo de negocio elegido

**Cargo no reconocido → bloqueo de tarjeta → escalamiento a disputa.**
Combina _Card Support_ (caso normal) y _Transaction Dispute_ (caso de escalamiento).

- **Caso normal:** Cliente reporta cargo sospechoso reciente → el sistema verifica, consulta transacciones, identifica la anomalía, bloquea la tarjeta y solicita reposición.
- **Caso ambiguo/escalamiento:** Cliente reporta cargo antiguo con intereses → fuera de ventana de bloqueo automático → abstención segura → Structured JSON Handoff al equipo de investigaciones.

### Justificación con datos

- `Cargo no reconocido` y `Cobro indebido` son las subcategorías más críticas (~12,000 quejas cada una).
- **75%** de estas quejas quedan _abiertas o escaladas_.
- Tiempo promedio de resolución: **15.4 días**.
- **~20%** de incumplimiento de SLA.
- Solo **0.06%** de transacciones son detectadas como fraude por el sistema, lo que confirma que el banco está ciego ante estos cargos y el cliente debe reportarlos.

---

## 3. Hallazgos de datos críticos ⚠️

> Esta sección captura conocimiento que NO puede inferirse del dataset.
> Cualquier componente que consulte o autorice transacciones DEBE respetar estos hallazgos.

### 3.1 El vínculo confiable es `product_id`, NO `customer_id`

- **~26% de las quejas** (2,107 de 8,143 casos del sandbox) tienen **MISMATCH** entre el `customer_id` de la queja y el `customer_id` de la transacción asociada.
- El producto (`affected_product_id` en complaints) es el único vínculo confiable entre la queja y la transacción.
- El dueño del producto en la tabla `products` coincide con el `customer_id` de la transacción, NO con el `customer_id` de la queja.
- **Regla:** cualquier consulta de transacciones o autorización debe filtrar por `product_id`, nunca por `customer_id` de la queja.

### 3.2 `contact_reason` replica `reason_category`

- El campo `contact_reason` en `call_center_interactions` contiene el mismo valor que `reason_category`. Es demasiado genérico para justificar el flujo.
- Usamos `complaints.category` y `complaints.subcategory` como fuente de justificación.

### 3.3 Fraude marcado es mínimo

- Solo 0.06% de las transacciones tienen `is_fraud = true`. La mayoría de disputas NO son detectadas automáticamente. El agente existe para cubrir ese vacío.

### 3.4 `merchant_name` frecuentemente NULL

- Muchas transacciones no tienen `merchant_name`. La política de negocio trata `merchant_name IS NULL` como `ASK_FOR_DETAILS_THEN_DECIDE`.

---

## 4. Stack tecnológico

| Componente                  | Tecnología          | Razón                                              |
| --------------------------- | ------------------- | -------------------------------------------------- |
| Gestión de dependencias     | `uv`                | Rápido, lockfile reproducible                      |
| Data pipeline / consultas   | DuckDB              | Consulta eficiente de CSV particionados por fecha  |
| Data contracts / validación | Pandera             | Data Quality Gate antes del consumo                |
| Estado de acciones          | SQLite              | Atomicidad y concurrencia para jueces simultáneos  |
| Configuración               | `pydantic-settings` | Lee `.env` en un objeto `Settings` tipado          |
| Orquestador de agente       | Strands             | Lifecycle hooks para gobierno                      |
| Capa de gobierno            | Jev (TypeSafe)      | Screening, routing, tool gating, confidence gating |
| UI / demo                   | Chainlit            | Interfaz conversacional con el agente              |

---

## 5. Arquitectura actual

```text
├── configs/
│   ├── eval.yaml          # Config de evaluación held-out
│   ├── policy.yaml        # Parámetros de negocio y umbrales
│   └── settings.yaml      # Config general (rutas, idiomas, log level)
│
├── docs/
│   ├── PROJECT_CONTEXT.md # Este documento (contexto estable)
│   ├── STATUS.md          # Estado vivo: qué hay, qué falta
│   ├── findings/
│   │   └── data_quality.md
│   └── typesafe_jev/
│       └── README.md      # Investigación de Jev (contratos, límites, umbrales)
│
├── duckdb/
│   └── ai_banking.duckdb  # Base persistente con vistas raw_*
│
├── data/
│   ├── raw/               # CSV descargados de S3
│   ├── sandbox/
│   │   └── agent_sandbox_final.parquet  # Sandbox validado con Pandera
│   └── state/             # Directorio de archivos SQLite de estado
│       ├── card_service.sqlite3
│       └── escalation_service.sqlite3
│
├── scripts/
│   ├── data_preparation/  # Pipeline de datos y sandbox
│   ├── diagnoses/         # Diagnóstico de integridad referencial
│   └── tools_preparation/ # Pruebas de las tools
│
├── src/ai_banking_customer_service/
│   ├── tools/
│   │   ├── get_dispute_context.py       # LECTURA: contexto del caso
│   │   ├── get_recent_transactions.py   # LECTURA: transacciones del producto
│   │   ├── block_card.py                # ACCIÓN: bloquea tarjeta (policy + verificación)
│   │   └── escalate_case.py             # ACCIÓN: genera Structured JSON Handoff
│   ├── services/
│   │   ├── card_service.py              # Mock bancario, SQLite
│   │   └── escalation_service.py        # Mock bancario, SQLite
│   ├── agent/              # PENDIENTE: orquestador Strands
│   ├── api/                # PENDIENTE: FastAPI backend
│   ├── config.py           # PENDIENTE: objeto Settings (pydantic-settings)
│   ├── data_access/        # PENDIENTE: repositorios sobre DuckDB/Parquet
│   ├── domain/             # PENDIENTE: modelos Pydantic de dominio
│   ├── evaluation/         # PENDIENTE: métricas y runner held-out
│   ├── governance/         # PENDIENTE: evaluaciones Jev, hooks, decisión
│   ├── handoff/            # PENDIENTE: generación de handoff estructurado
│   ├── observability/      # PENDIENTE: tracing, auditoría
│   ├── policies/           # PENDIENTE: reglas duras fuera del prompt
│   └── sandbox/            # PENDIENTE: gestión del sandbox del agente
│
├── app/                    # PENDIENTE: UI (Streamlit/Gradio)
├── evals/                  # PENDIENTE: casos held-out y reportes
├── tests/                  # PENDIENTE: tests unitarios e integración
├── .env                    # Secretos y rutas (NO commitear)
└── .env.example            # Plantilla de .env (SÍ commitear)
```

---

## 6. Decisiones de diseño

Estas decisiones son vinculantes. No reintroducir patrones que ya descartamos.

1. **Rules duras en código, nunca en el prompt.** Confirmación del cliente, tipo de producto, estado activo, umbrales monetarios → todo en Python.
2. **Jev es capa de gobierno, no reemplaza rules duras.** Jev aporta señales semánticas (inyección, intención, riesgo difuso) vía hooks de Strands. Las reglas binarias permanecen en código. Es defensa en profundidad.
3. **`product_id` es el vínculo confiable.** Ver sección 3.1. No filtrar transacciones por `customer_id` de la queja.
4. **SQLite para estado de acciones.** No JSON. SQLite garantiza atomicidad bajo concurrencia (varios jueces simultáneos).
5. **Pandera como Data Quality Gate.** El sandbox se valida antes de que las tools lo consuman. Si falla el contrato, el pipeline se detiene.
6. **Retornos de tools como dicts.** Con `error` si falla, o con campos de verificación (`verification`, `executed`) si tiene éxito.
7. **Toda acción verifica su resultado.** No se asume éxito: se relee el estado y se confirma (`confirmed_blocked`, `confirmed_persisted`).
8. **Idempotencia.** Bloquear dos veces no corrompe el estado; devuelve `already_blocked`.
9. **Mock services documentados.** `card_service` y `escalation_service` son sintéticos. En producción serían las APIs reales del banco.
10. **Configuración vía `.env` + `pydantic-settings`.** Secretos y rutas en `.env`; parámetros de negocio en `configs/policy.yaml`. Nunca hardcodear.
11. **UI como capa de presentación delgada.** La lógica del agente (orquestador, tools, gobierno, política) vive en `src/` agnóstica del framework de UI. La UI (Chainlit) recibe la entrada del usuario, invoca al orquestador y renderiza la salida. No contiene lógica de negocio, política ni llamadas directas a servicios. Esto hace la UI intercambiable y el agente testeable sin levantar la interfaz.

---

## 7. Contratos y convenciones

### Separación de configuración

| Tipo                  | Dónde                 | Ejemplos                                                         |
| --------------------- | --------------------- | ---------------------------------------------------------------- |
| Secretos              | `.env`                | `JEV_API_KEY`, `OPENAI_API_KEY`                                  |
| Rutas                 | `.env`                | `DUCKDB_NAME`, `SANDBOX_PATH`, `STATE_PATH`                      |
| Parámetros de negocio | `configs/policy.yaml` | `HIGH_AMOUNT_THRESHOLD_USD`, umbrales Jev, productos bloqueables |

### Ejemplo de `.env`

```text
# Secretos
OPENAI_API_KEY=
JEV_API_KEY=

# Rutas
DUCKDB_NAME=ai_banking.duckdb
SANDBOX_PATH=data/sandbox/agent_sandbox_final.parquet
STATE_PATH=data/state
```

- `STATE_PATH` es el directorio; cada servicio construye su propio filename (`card_service.sqlite3`, `escalation_service.sqlite3`).

### Loader de configuración

El objeto `Settings` (en `src/ai_banking_customer_service/config.py`) se lee así:

```python
from ai_banking_customer_service.config import policy, settings

settings.duckdb_path         # Path("duckdb/ai_banking.duckdb")
settings.sandbox_full_path   # Path("data/sandbox/agent_sandbox_final.parquet")
settings.state_dir           # Path("data/state")
settings.jev_api_key         # str (desde .env)
policy.high_amount_threshold_usd # 500.0
```

- Los componentes nuevos deben usar `settings`.

### Nombres de archivos

- Scripts de datos: `scripts/data_preparation/NN_nombre.py`
- Scripts de diagnóstico: `scripts/diagnoses/NN_nombre.py`
- Tests de tools: `scripts/tools_preparation/NN_test_tool_nombre.py`
- Tools: `src/.../tools/get_X.py`, `block_X.py`, `escalate_X.py`
- Services: `src/.../services/X_service.py`

### Retorno de tools

```python
# Éxito
{"action": "block_card", "executed": True, "verification": "confirmed_blocked", ...}

# Fallo controlado
{"error": "Disputa no encontrada: CMP-XXX"}
{"action": "block_card", "executed": False, "reason": "customer_confirmation_required", ...}
```

### Manejo de errores

- Validar inputs al inicio de cada tool.
- Verificar existencia de archivos/bases antes de consultar.
- Usar `try/finally` para cerrar conexiones.
- Ante error de BD: `ROLLBACK` y retorno con `error`.

---

## 8. Reglas permanentes

Estas reglas aplican a toda tarea. No se repiten en cada spec.

1. **Actualizar** `docs/STATUS.md` después de implementar cualquier componente: qué se agregó, qué cambió, qué queda pendiente.
2. **Cuando una tarea involucre `Jev`, consultar la skill `typesafe-ai`** como fuente autorizada de la API, primitivas y buenas prácticas. No inventar la API, No usar `Context7`.
3. **Respetar los hallazgos de la sección 3**, especialmente el vínculo por `product_id`.
4. **No hardcodear** rutas, secretos ni umbrales; usar `settings` o `policy`.

---

## 9. No-negociables universales

Aplican a todos los componentes. Cada spec agrega solo sus requisitos específicos.

- La política vive en código, fuera del prompt del modelo.
- Toda acción verifica su resultado antes de reportarla como exitosa.
- El sistema responde en español y portugués.
- `product_id` es el vínculo confiable entre queja y transacción.
- Fail-closed: ante fallo de Jev o timeout en tools de escritura, denegar la acción.
- No exponer PAN completo, CVV ni credenciales en logs, state de Jev o handoffs.

## 10. Glosario

| Término                   | Definición                                                                                                                                                              |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sandbox                   | `agent_sandbox_final.parquet`. Dataset pre-calculado y validado que las tools consumen. Contiene casos de disputa con contexto completo y `recommended_action`.         |
| Structured JSON Handoff   | JSON que el agente genera para el equipo humano: `request`, `verified_facts`, `actions_taken`, `supporting_evidence`, `unresolved_questions`, `recommended_next_steps`. |
| Safe Automated Resolution | Caso elegible resuelto correctamente sin intervención humana. Métrica principal del hackathon.                                                                          |
| Containment               | Caso termina sin transferencia. No implica que se resolvió.                                                                                                             |
| Escalation Quality        | Casos que requieren escalamiento se transfieren correctamente con contexto útil.                                                                                        |
| Unsafe Outcome            | Revelación o acción no autorizada, o resultado materialmente incorrecto.                                                                                                |
| Data Quality Gate         | Validación con Pandera que detiene el pipeline si el sandbox no cumple el contrato.                                                                                     |
| Fail-closed               | Ante fallo de Jev o timeout en tools de escritura, denegar la acción por defecto.                                                                                       |
| Defensa en profundidad    | Rules duras en código + Jev como capa semántica adicional. Ninguna capa sola basta.                                                                                     |
| Gobernanza (governance)   | Capa que decide si una acción es segura antes de ejecutarla. Implementada con Jev vía hooks de Strands.                                                                 |
