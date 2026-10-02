# SPEC #6 — Adaptador de Gobierno y Hooks de Strands con Jev (v5)

Método: TDD estricto — RED → GREEN → TRIANGULATE → REFACTOR.
La lista de tests es el BACKLOG; se ejecuta en microciclos (UN test RED → mínimo GREEN → TRIANGULATE → REFACTOR). Los casos parametrizados cuentan como triangulación.

## 0. Contexto obligatorio antes de implementar

Leer en este orden:

1. `AGENTS.md` — decisiones de diseño, no-negociables, stack.
2. `docs/observability.md` — contrato de auditoría. El adaptador de gobierno emite eventos `governance` para las cuatro etapas. El orquestador emite `input`, `tool_call`, `response`, `escalation`.
3. Spec #1 (`docs/specs/spec_01.md`) — `JevClient`, schemas, excepciones.
4. Spec #2 (`docs/specs/spec_02.md`) — `screen_input`, `route_banking_intent`, `EXPECTED_INTENTS`.
5. Spec #3 (`docs/specs/spec_03.md`) — `decide_screening`, `decide_routing`, `GovernanceThresholds`, `GovernanceDecision`.
6. Spec #4 (`docs/specs/spec_04.md`) — `gate_tool_call`, `screen_agent_output`, `decide_tool_gating`, `decide_output_screening`, `ToolGatingThresholds`, `OutputScreeningThresholds`, `TOOL_ARG_CONTRACTS`, `ALLOWED_TOOLS`, `JEV_STATE_ARG_ALLOWLIST`, trust boundaries, `VERIFIED_FACTS_ALLOWLIST`, `ACTION_REQUIRED_FIELDS`, `ACTION_VERIFICATIONS`.
7. Spec #5 (`docs/specs/spec_05.md`) — `REGISTERED_TOOLS`, contrato de API de Strands 1.57.1.
8. `docs/typesafe_jev/README.md` §7 — integración como hooks de gobierno, reglas duras en código.
9. `src/ai_banking_customer_service/governance/jev/exceptions.py` — jerarquía de excepciones (`JevValidationError` es subclase de `JevError`).
10. `src/ai_banking_customer_service/governance/jev/evaluations.py` — constantes reales:
    - `ACTION_REQUIRED_FIELDS = {"action_name", "executed", "verification"}` (sin `target_id`).
    - `ACTION_VERIFICATIONS` es un dict anidado: `{action_name: {verification: expected_executed_bool}}`.
11. API de hooks de Strands 1.57.1: inspeccionar `.venv/Lib/site-packages/strands/hooks/events.py` y `registry.py`. `ToolUse.input` es `Any`, no se asume dict sin validar.
12. Strands usa `ConcurrentToolExecutor` por defecto: múltiples `BeforeToolCallEvent` del mismo batch comparten el mismo `invocation_state`.

Este componente se construye SOBRE Spec #1–#5. No modifica las evaluaciones, decisiones ni tools. NO modifica Spec #4.

## 1. Objetivo y alcance

### Objetivo

Crear el **adaptador de gobierno** (framework-agnostic) que orquesta el pipeline completo de gobierno —screening, routing, tool gating, output screening— midiendo latencia, emitiendo eventos de auditoría y aplicando fail-closed ante errores de Jev. Crear los **hooks de Strands** (eventos tipados, `HookProvider` con `register_hooks`) que integran el adaptador con el ciclo de vida del agente, con soporte para tools concurrentes. Crear el **módulo de observabilidad** (`contract.py`, `sink.py`) según `observability.md`.

### Incluye

- `GovernanceAdapter`: orquestación del pipeline de gobierno, medición de latencia, emisión de eventos de auditoría, fail-closed ante `JevError`.
- Hooks de Strands con eventos tipados: `BeforeInvocationEvent` (screening + routing) y `BeforeToolCallEvent` (tool gating), implementando `HookProvider` con `register_hooks`. Soporte para tools concurrentes mediante resultados por `toolUseId`.
- Contrato explícito de `invocation_state` (claves, tipos, productor, consumidor, comportamiento ante ausencia).
- Integración de output screening como método del adaptador invocado por el orquestador (Spec #7).
- Construcción de trust boundaries: `build_customer_context` (con `complaint_id` de la tool call), `build_verified_facts`, `build_actions_taken` (compatible con Spec #4, sin `target_id`).
- Emisión de eventos `governance` para las cuatro etapas vía `AuditSink`, con `last_event_id` y `routing_event_id` expuestos para encadenamiento.
- Módulo de observabilidad: `contract.py` (envelope, validación) y `sink.py` (`AuditSink`, `JsonlAuditSink`).
- Tests unitarios sin red, sin Jev real, sin Strands real (mocks).

### NO incluye

- Creación del agente `Agent(...)` ni system prompt → Spec #7.
- Flujo conversacional (memoria, clarificación, abstención) → Spec #7.
- Emisión de eventos `input`, `tool_call`, `response`, `escalation` → Spec #7 (orquestador).
- Detección de acciones fallidas para escalamiento directo → Spec #7 (orquestador). El adaptador señala la presencia de acciones fallidas; el orquestador decide escalar.
- UI → Spec #8.
- Evaluación offline → Spec #9.
- Modificación de evaluaciones (Spec #2, #4), decisiones (Spec #3, #4), tools, ni constantes de Spec #4.
- Modificación de `GovernanceDecision` para agregar señales determinísticas.

## 2. Pre-work

- Spec #1–#5 implementadas y tests pasando: `uv run pytest tests/unit -q`.
- `strands-agents[openai]` instalado. La versión efectiva es la fijada en `uv.lock` (actualmente 1.57.1). Si `uv.lock` se regenera con una versión diferente, el contrato de hooks debe revalidarse.
- `pydantic` disponible para validación de eventos.

## 3. Arquitectura del adaptador de gobierno

### 3.1 Principio de separación

El adaptador de gobierno es **framework-agnostic**: no importa Strands ni ningún framework de agente. Los hooks de Strands son wrappers delgados que invocan al adaptador.

### 3.2 Estructura de módulos

```
src/ai_banking_customer_service/governance/
├── __init__.py
├── jev/                    # Spec #1–#4 (no modificar)
│   ├── client.py
│   ├── schemas.py
│   ├── exceptions.py
│   ├── evaluations.py
│   ├── decision.py
│   └── sanitization.py
└── adapter.py              # Spec #6: GovernanceAdapter
src/ai_banking_customer_service/agent/
├── __init__.py
├── tools.py                # Spec #5 (no modificar)
└── hooks.py                # Spec #6: hooks de Strands
src/ai_banking_customer_service/observability/
├── __init__.py
├── contract.py             # Spec #6: envelope, validación de eventos
└── sink.py                 # Spec #6: AuditSink, JsonlAuditSink
```

### 3.3 Dependencias del adaptador (inyección completa)

```python
class GovernanceAdapter:
    def __init__(
        self,
        client: JevClient,
        thresholds: GovernanceThresholds,
        tool_gating_thresholds: ToolGatingThresholds,
        output_screening_thresholds: OutputScreeningThresholds,
        audit_sink: AuditSink,
        dispute_context_loader: Callable[[str], dict],
    ): ...
```

Todas las dependencias se inyectan. El adaptador no construye `JevClient`, no carga `Policy`, no crea `AuditSink`, no accede directamente a `get_dispute_context` ni al filesystem.

## 4. Flujo de gobierno completo (pipeline)

```
mensaje del cliente
        │
        ▼
[BeforeInvocationEvent / adapter.screen_and_route]
   1. screen_input + decide_screening → BLOCK/REVIEW/ALLOW(stage=INPUT_SCREENING)
   2. Si ALLOW: route_banking_intent + decide_routing → BLOCK/REVIEW/ALLOW(stage=INTENT_ROUTING)
   3. Si ALLOW: guardar intent, customer_message, routing_event_id en invocation_state
        │
        ▼
[modelo Strands decide llamar una o más tools (posiblemente concurrentes)]
        │
        ▼
[BeforeToolCallEvent / adapter.gate_tool_call] (una por tool call)
   4. Validar event.tool_use, name, input, complaint_id, contexto.
   5. Extraer complaint_id de event.tool_use["input"].
   6. build_customer_context(complaint_id) → customer_context.
   7. gate_tool_call + decide_tool_gating → BLOCK/ALLOW(stage=TOOL_GATING)
      ├─ BLOCK  → emitir evento governance (parent=routing_event_id), cancelar tool call
      └─ ALLOW  → emitir evento governance (parent=routing_event_id), ejecutar tool
   8. Guardar resultado en invocation_state["tool_governance"][tool_use_id].
        │
        ▼
[modelo Strands genera respuesta]
        │
        ▼
[orquestador / adapter.screen_output]
   9. build_actions_taken(tool_results) → (valid_actions, has_failed_actions).
   10. Si has_failed_actions → el orquestador escala directamente.
   11. screen_agent_output + decide_output_screening → REVIEW/ALLOW(stage=OUTPUT_SCREENING)
```

Reglas:

- Cada llamada a evaluación mide latencia con `time.monotonic()`. Todos los eventos requieren `latency_ms`.
- Cada decisión produce exactamente UN evento `governance` emitido vía `AuditSink`.
- Si una etapa produce BLOCK o REVIEW, las etapas siguientes NO se ejecutan.
- Output screening NO es un hook de Strands; es invocado por el orquestador (Spec #7).
- `BeforeModelCallEvent` NO se usa para screening/routing.
- `customer_context` se construye en `before_tool_call` a partir del `complaint_id` de la tool call, NO en `before_invocation`.
- **Tools concurrentes**: Strands usa `ConcurrentToolExecutor` por defecto. Múltiples `BeforeToolCallEvent` del mismo batch comparten el mismo `invocation_state`. Cada tool call usa `routing_event_id` como padre estable y guarda su resultado en `invocation_state["tool_governance"][tool_use_id]`. NO se sobrescriben claves globales (`last_event_id`, `governance_decision`, `governance_action`) desde hooks concurrentes. Los eventos de tool gating son HERMANOS bajo `routing_event_id`, no una cadena.

## 5. Adaptador de gobierno (GovernanceAdapter)

### 5.1 Tipos de resultado del adaptador

```python
@dataclass(frozen=True)
class ScreeningRoutingResult:
    final_decision: GovernanceDecision   # decisión final (screening o routing)
    intent: str | None                   # intent detectado si routing pasó con ALLOW
    should_continue: bool                # True solo si final_decision.action == ALLOW
    last_event_id: str                   # event_id del último evento emitido (routing si ALLOW)

@dataclass(frozen=True)
class GovernanceResult:
    decision: GovernanceDecision
    event_id: str                        # event_id del evento emitido
```

### 5.2 Método: `screen_and_route`

```python
def screen_and_route(
    self,
    message: str,
    trace_id: str,
    session_id: str,
    customer_id: str,
    parent_event_id: str | None = None,
) -> ScreeningRoutingResult:
    """Ejecuta screening + routing. Emite eventos de auditoría. Fail-closed ante JevError."""
```

#### Algoritmo

1. Medir latencia de `screen_input(client, message)`.
   - Si lanza `JevValidationError` → fail-closed: `GovernanceDecision(action=BLOCK, stage=INPUT_SCREENING, reason_codes=("INPUT_SCREENING_VALIDATION_ERROR",), ...)`. Emitir evento. Devolver con `should_continue=False` y `last_event_id`.
   - Si lanza otra subclase de `JevError` → fail-closed: `GovernanceDecision(action=BLOCK, stage=INPUT_SCREENING, reason_codes=("JEV_ERROR",), ...)`. Emitir evento. Devolver con `should_continue=False` y `last_event_id`.
2. `decide_screening(screening_result, self._thresholds)` → `screening_decision`.
3. Emitir evento `governance` para `input_screening`. Guardar `event_id` como `last_event_id`.
4. Si `screening_decision.action != ALLOW` → devolver con `should_continue=False`.
5. Medir latencia de `route_banking_intent(client, message)`.
   - Si lanza `JevValidationError` → fail-closed: `GovernanceDecision(action=BLOCK, stage=INTENT_ROUTING, reason_codes=("INTENT_ROUTING_VALIDATION_ERROR",), ...)`. Emitir evento con `parent_event_id=last_event_id`. Actualizar `last_event_id`. Devolver con `should_continue=False`.
   - Si lanza otra subclase de `JevError` → fail-closed. Emitir evento. Actualizar `last_event_id`. Devolver con `should_continue=False`.
6. `decide_routing(routing_result, self._thresholds)` → `routing_decision`.
7. Emitir evento `governance` para `intent_routing` con `parent_event_id=last_event_id`. Actualizar `last_event_id`.
8. Si `routing_decision.action != ALLOW` → devolver con `should_continue=False`.
9. Devolver `ScreeningRoutingResult(final_decision=routing_decision, intent=routing_decision.intent, should_continue=True, last_event_id=last_event_id)`. El `last_event_id` aquí es el `event_id` del evento de routing, que se usará como `routing_event_id` (padre estable para tool calls concurrentes).

### 5.3 Método: `gate_tool_call`

```python
def gate_tool_call(
    self,
    tool_name: str,
    tool_args: dict,
    intent: str,
    customer_message: str,
    customer_context: dict,
    trace_id: str,
    session_id: str,
    customer_id: str,
    parent_event_id: str | None = None,
) -> GovernanceResult:
    """Ejecuta tool gating. Emite evento de auditoría. Fail-closed ante JevError."""
```

#### Algoritmo

1. Medir latencia de `gate_tool_call(client, tool_name, tool_args, intent, customer_message, customer_context)` (evaluación de Spec #4). La latencia se mide SIEMPRE.
   - Si lanza `JevValidationError` → fail-closed: `GovernanceDecision(action=BLOCK, stage=TOOL_GATING, reason_codes=("TOOL_GATING_VALIDATION_ERROR",), ...)`. Emitir evento. Devolver `GovernanceResult`.
   - Si lanza otra subclase de `JevError` → fail-closed: `GovernanceDecision(action=BLOCK, stage=TOOL_GATING, reason_codes=("JEV_ERROR",), ...)`. Emitir evento. Devolver `GovernanceResult`.
2. `decide_tool_gating(gating_result, self._tool_gating_thresholds)` → `decision`.
3. Emitir evento `governance` para `tool_gating` con `parent_event_id` (típicamente `routing_event_id`).
4. Devolver `GovernanceResult(decision=decision, event_id=event_id)`.

### 5.4 Método: `screen_output`

```python
def screen_output(
    self,
    proposed_response: str,
    customer_message: str,
    verified_facts: dict,
    actions_taken: list,
    trace_id: str,
    session_id: str,
    customer_id: str,
    parent_event_id: str | None = None,
) -> GovernanceResult:
    """Ejecuta output screening. Emite evento de auditoría. Fail-closed ante JevError."""
```

#### Algoritmo

1. Medir latencia de `screen_agent_output(client, proposed_response, customer_message, verified_facts, actions_taken)` (evaluación de Spec #4). La latencia se mide SIEMPRE.
   - Si lanza `JevValidationError` → fail-closed: `GovernanceDecision(action=REVIEW, stage=OUTPUT_SCREENING, reason_codes=("OUTPUT_SCREENING_VALIDATION_ERROR",), ...)`. Emitir evento. Devolver `GovernanceResult`.
   - Si lanza otra subclase de `JevError` → fail-closed: `GovernanceDecision(action=REVIEW, stage=OUTPUT_SCREENING, reason_codes=("JEV_ERROR",), ...)`. Emitir evento. Devolver `GovernanceResult`.
2. `decide_output_screening(screening_result, self._output_screening_thresholds)` → `decision`.
3. Emitir evento `governance` para `output_screening`.
4. Devolver `GovernanceResult(decision=decision, event_id=event_id)`.

### 5.5 Fail-closed: resumen de acciones por error

| Error                       | Etapa              | Acción fail-closed | Reason code                         |
| --------------------------- | ------------------ | ------------------ | ----------------------------------- |
| `JevValidationError`        | `input_screening`  | `BLOCK`            | `INPUT_SCREENING_VALIDATION_ERROR`  |
| `JevValidationError`        | `intent_routing`   | `BLOCK`            | `INTENT_ROUTING_VALIDATION_ERROR`   |
| `JevValidationError`        | `tool_gating`      | `BLOCK`            | `TOOL_GATING_VALIDATION_ERROR`      |
| `JevValidationError`        | `output_screening` | `REVIEW`           | `OUTPUT_SCREENING_VALIDATION_ERROR` |
| Otra subclase de `JevError` | `input_screening`  | `BLOCK`            | `JEV_ERROR`                         |
| Otra subclase de `JevError` | `intent_routing`   | `BLOCK`            | `JEV_ERROR`                         |
| Otra subclase de `JevError` | `tool_gating`      | `BLOCK`            | `JEV_ERROR`                         |
| Otra subclase de `JevError` | `output_screening` | `REVIEW`           | `JEV_ERROR`                         |

Orden de captura: PRIMERO `JevValidationError`, LUEGO `JevError`.

### 5.6 Métodos de trust boundaries

Ver sección 9.

## 6. Integración con Strands (hooks con eventos tipados)

### 6.1 API de hooks de Strands 1.57.1

En `strands-agents 1.57.1` (versión fijada en `uv.lock`), la API de hooks es:

- `Agent(hooks=[...])`: una lista de `HookProvider` o callbacks tipados.
- `HookProvider` requiere un método `register_hooks(self, registry: HookRegistry) -> None`.
- `BeforeInvocationEvent`: contiene `messages`, `invocation_state`, `cancel`. `cancel` es un atributo `bool | str`, NO un método.
- `BeforeToolCallEvent`: contiene `tool_use` (dict con `name` e `input`), `invocation_state`, `cancel_tool`. `cancel_tool` es un atributo `bool | str`, NO un método. `tool_use["input"]` es `Any`, NO se asume dict sin validar.
- Strands usa `ConcurrentToolExecutor` por defecto: múltiples `BeforeToolCallEvent` del mismo batch comparten el mismo `invocation_state`.

### 6.2 `GovernanceHooks` (HookProvider)

```python
# src/ai_banking_customer_service/agent/hooks.py
"""Strands lifecycle hooks that integrate the GovernanceAdapter."""

from strands.hooks import HookProvider, HookRegistry, BeforeInvocationEvent, BeforeToolCallEvent

from ai_banking_customer_service.governance.adapter import GovernanceAdapter


class GovernanceHooks(HookProvider):
    """Proveedor de hooks de gobierno para Strands."""

    def __init__(self, adapter: GovernanceAdapter):
        self._adapter = adapter

    def register_hooks(self, registry: HookRegistry) -> None:
        """Registra los callbacks de gobierno en el registry de Strands."""
        registry.add_callback(BeforeInvocationEvent, self.before_invocation)
        registry.add_callback(BeforeToolCallEvent, self.before_tool_call)

    def before_invocation(self, event: BeforeInvocationEvent) -> None:
        """Screening + routing. Se ejecuta una vez por invocación del agente."""
        ...

    def before_tool_call(self, event: BeforeToolCallEvent) -> None:
        """Tool gating. Se ejecuta antes de cada llamada a tool.
        Soporta tools concurrentes: resultados por toolUseId."""
        ...


def create_hooks(adapter: GovernanceAdapter) -> list:
    """Crea los hooks de gobierno para Strands.

    Devuelve list[HookProvider], NO dict.
    """
    return [GovernanceHooks(adapter)]
```

### 6.3 `before_invocation` (screening + routing)

Algoritmo:

1. Extraer el último mensaje del usuario de `event.messages`: buscar el último mensaje con `role == "user"`, concatenar los bloques de texto. Si no existe mensaje de usuario o no tiene texto → `event.cancel = "governance:block"`, `invocation_state["governance_action"] = "block"`.
2. Obtener `trace_id`, `session_id`, `customer_id`, `input_event_id` de `event.invocation_state`.
3. Validar contexto: si `trace_id`, `session_id` o `customer_id` faltan o no son `str` no vacío → `event.cancel = "governance:block"`, `invocation_state["governance_action"] = "block"`.
4. Llamar `adapter.screen_and_route(message, trace_id, session_id, customer_id, parent_event_id=input_event_id)`.
5. Guardar en `invocation_state`:
   - `intent`: el intent detectado (o None).
   - `customer_message`: el mensaje del cliente.
   - `routing_event_id`: el `last_event_id` del resultado (event_id del evento de routing si ALLOW). Este es el padre estable para tool calls concurrentes.
   - `governance_decision`: la decisión final.
   - `governance_action`: `"block"`, `"review"` o `"allow"`.
   - `tool_governance`: reinicializar como `{}` para la invocación actual, evitando conservar resultados de una invocación previa.
   - NOTA: NO se construye `customer_context` aquí.
6. Si `result.should_continue` es False → `event.cancel = f"governance:{result.final_decision.action.value}"`.

### 6.4 `before_tool_call` (tool gating) — con validación exhaustiva y soporte concurrente

Algoritmo:

1. **Validar `event.tool_use`**: si no es un `dict` → `event.cancel_tool = "governance:block"` y return. No modificar claves globales de `invocation_state`.
2. **Extraer y validar `toolUseId`**: `tool_use_id = event.tool_use.get("toolUseId")`. Debe ser `str` no vacío. Si falta o es inválido → `event.cancel_tool = "governance:block"` y return. `toolUseId` es obligatorio en Strands; NO se construye un fallback porque podría colisionar entre llamadas concurrentes iguales.
3. **Inicializar estado per-tool**: asegurar que `invocation_state["tool_governance"]` sea un `dict`. Si falta, inicializarlo como `{}`. Si existe con otro tipo → cancelar fail-closed y return.
4. **Helper de cancelación per-tool**: toda validación fallida posterior guarda el bloqueo bajo el `toolUseId` concreto y cancela solo esa llamada:
   ```python
   def cancel_tool(reason: str) -> None:
       invocation_state["tool_governance"][tool_use_id] = {
           "decision": None,
           "action": "block",
           "event_id": None,
           "reason": reason,
       }
       event.cancel_tool = "governance:block"
   ```
   Este helper NO modifica `last_event_id`, `governance_decision` ni `governance_action` globales.
5. **Validar `name`**: extraer `tool_name = event.tool_use.get("name")`. Si no es `str` no vacío → `cancel_tool("invalid_tool_name")` y return.
6. **Validar `input`**: extraer `tool_args = event.tool_use.get("input")`. Si no es un `dict` → `cancel_tool("invalid_tool_input")` y return.
7. **Extraer y validar `complaint_id`**: `complaint_id = tool_args.get("complaint_id")`. Si no es `str` no vacío → `cancel_tool("invalid_complaint_id")` y return.
8. **Validar contexto obligatorio**: obtener `trace_id`, `session_id`, `customer_id`, `intent`, `customer_message`, `routing_event_id` de `event.invocation_state`. `trace_id`, `session_id`, `customer_id`, `intent` y `customer_message` deben ser `str` no vacío. `routing_event_id` debe ser `str` no vacío para conservar el encadenamiento de auditoría. Ante cualquier incumplimiento → `cancel_tool("invalid_invocation_state")` y return.
9. **Construir `customer_context`**: `adapter.build_customer_context(complaint_id)`. Este contexto está ligado al `complaint_id` concreto de ESTA tool call.
10. **Llamar al adaptador**: `adapter.gate_tool_call(tool_name, tool_args, intent, customer_message, customer_context, trace_id, session_id, customer_id, parent_event_id=routing_event_id)`.
11. **Guardar resultado por `toolUseId`** (NO sobrescribir claves globales):
    ```python
    invocation_state["tool_governance"][tool_use_id] = {
        "decision": result.decision,
        "action": result.decision.action.value,
        "event_id": result.event_id,
        "reason": None,
    }
    ```
12. Si `result.decision.action == BLOCK` → `event.cancel_tool = "governance:block"`.
13. Si `result.decision.action == ALLOW` → permitir la ejecución de la tool.

NOTA: ninguna ruta de `before_tool_call` sobrescribe `last_event_id`, `governance_decision` ni `governance_action` globales. Cada tool call guarda su resultado o fallo de validación exclusivamente en `tool_governance[toolUseId]`.

### 6.5 Output screening (no es hook)

Output screening NO es un hook de Strands. Es invocado por el orquestador (Spec #7) después de que el modelo genera una respuesta. El orquestador llama `adapter.screen_output(...)` y actúa según la decisión. El orquestador usa `parent_event_id` del último evento previo para encadenar.

## 7. Contrato de invocation_state

### 7.1 Claves de invocation_state

`invocation_state` es un dict mutable compartido entre hooks y el orquestador durante una invocación del agente. Las claves son:

| Clave                 | Tipo                         | Productor                                    | Consumidor                                          | Obligatorio |
| --------------------- | ---------------------------- | -------------------------------------------- | --------------------------------------------------- | ----------- |
| `trace_id`            | `str`                        | Orquestador (Spec #7) al inicio del turno    | Adaptador                                           | Sí          |
| `session_id`          | `str`                        | Orquestador (Spec #7)                        | Adaptador                                           | Sí          |
| `customer_id`         | `str`                        | Orquestador (Spec #7)                        | Adaptador                                           | Sí          |
| `input_event_id`      | `str \| None`                | Orquestador (Spec #7)                        | Adaptador (como parent_event_id)                    | No          |
| `intent`              | `str \| None`                | Adaptador (después de routing)               | Hooks de tool gating, orquestador                   | No          |
| `customer_message`    | `str`                        | Adaptador (extraído de messages)             | Hooks de tool gating, orquestador                   | No          |
| `routing_event_id`    | `str \| None`                | Adaptador (event_id del evento de routing)   | Hooks de tool gating (como parent_event_id estable) | No          |
| `governance_decision` | `GovernanceDecision \| None` | Adaptador (screening/routing)                | Orquestador                                         | No          |
| `governance_action`   | `str \| None`                | Adaptador (`"block"`, `"review"`, `"allow"`) | Orquestador                                         | No          |
| `tool_governance`     | `dict`                       | Adaptador (before_tool_call, por toolUseId)  | Orquestador                                         | No          |
| `tool_results`        | `list`                       | Orquestador (acumula resultados de tools)    | Adaptador (build_actions_taken)                     | No          |

Notas:

- `customer_context` NO es una clave de `invocation_state`. Se construye localmente en `before_tool_call`.
- `tool_governance` es un dict keyed por el `toolUseId` exacto de Strands. Cada entrada contiene `decision`, `action`, `event_id` y `reason`. Esto soporta tools concurrentes sin sobrescribir claves globales.
- `routing_event_id` es el padre estable para todos los eventos de tool gating del mismo batch. Los eventos de tool gating son HERMANOS bajo `routing_event_id`, no una cadena.

### 7.2 Inicialización

El orquestador (Spec #7) inicializa `trace_id`, `session_id`, `customer_id` y opcionalmente `input_event_id` al inicio de cada turno. `before_invocation` reinicializa `tool_governance = {}` para la invocación actual y evita conservar resultados de una invocación previa.

### 7.3 Comportamiento ante ausencia o tipo incorrecto

- Si `trace_id`, `session_id` o `customer_id` faltan o no son `str` no vacío en `BeforeInvocationEvent` → `event.cancel = "governance:block"`, `governance_action="block"`.
- Si `event.tool_use` no es dict o `toolUseId` falta/no es `str` no vacío → `event.cancel_tool = "governance:block"` sin modificar claves globales ni construir un identificador alternativo.
- Si existe un `toolUseId` válido pero `name`, `input`, `complaint_id`, `intent`, `trace_id`, `session_id`, `customer_id`, `customer_message` o `routing_event_id` son inválidos → guardar el bloqueo en `tool_governance[toolUseId]`, establecer `event.cancel_tool = "governance:block"` y no modificar claves globales.

### 7.4 Distinguir BLOCK de REVIEW después de cancelar

`before_invocation` establece `invocation_state["governance_action"]` para screening/routing. `before_tool_call` nunca modifica esa clave global: cada resultado o cancelación se guarda en `invocation_state["tool_governance"][toolUseId]["action"]`. El orquestador (Spec #7) lee el estado per-tool para decidir cómo proceder.

## 8. Emisión de eventos de auditoría

### 8.1 Evento `governance`

El adaptador emite UN evento `governance` por cada etapa ejecutada. La estructura sigue `observability.md`, con las normalizaciones de esta sección.

```python
event = {
    "trace_id": trace_id,
    "event_id": str(uuid4()),
    "parent_event_id": parent_event_id,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "component": "governance",
    "event_type": "governance",
    "customer_id": mask_customer_id(customer_id),
    "session_id": session_id,
    "outcome": _outcome_from_decision(decision),
    "latency_ms": latency_ms,
    "tokens": tokens_from_usage(usage),
    "cost_usd": None,
    "payload": {
        "stage": decision.stage.value,
        "signals": signals,
        "decision": decision.action.value,
        "reasons": list(decision.reasons),  # list[str], convertido explícitamente desde tuple
        "thresholds": _serialize_thresholds(decision.governance_thresholds),
    },
}
self._audit_sink.emit(event)
```

### 8.2 Normalización del contrato de observabilidad

- `reasons` en el payload es `list[str]`. Se convierte explícitamente con `list(decision.reasons)`.
- `customer_id` se emite enmascarado (sección 8.5).
- `parent_event_id` se pasa explícitamente al adaptador.

### 8.3 Extracción de signals (resultado crudo + decisión)

Los signals se extraen usando TANTO el resultado crudo de la evaluación COMO la decisión.

- Para `INPUT_SCREENING`: `prompt_injection_signal` y `social_engineering_signal` de `GovernanceDecision`.
- Para `INTENT_ROUTING`: `intent`, `intent_confidence`, `intent_probabilities` de `GovernanceDecision`.
- Para `TOOL_GATING`: señal de `intent_matches_tool` del `ToolGatingResult` crudo. Si `deterministic_block=True`, la señal es None y se incluye `deterministic_reason`.
- Para `OUTPUT_SCREENING`: `score`, `confidence` de `OutputScreeningResult.output_safety_semantic`. `secrets_detected` de `OutputScreeningResult.secrets_detected`.

### 8.4 parent_event_id y encadenamiento

- Para `screen_and_route`: el primer evento usa el `parent_event_id` recibido. El segundo evento usa el `event_id` del primer evento.
- Para `gate_tool_call`: el `parent_event_id` es `routing_event_id` (padre estable). Todas las tool calls del mismo batch usan el mismo padre. Los eventos son HERMANOS, no una cadena.
- Para `screen_output`: el `parent_event_id` es pasado por el orquestador.
- El adaptador expone `last_event_id` en `ScreeningRoutingResult` y `event_id` en `GovernanceResult`.

### 8.5 Enmascaramiento de customer_id

```python
def mask_customer_id(customer_id: str) -> str:
    """Enmascara el customer_id para auditoría.

    Conserva los últimos 4 caracteres, reemplaza el resto con '*'.
    Ejemplo: 'CLI-9W3CREKG73Q7' (16 chars) → '************73Q7' (12 asteriscos + 4 chars)
    """
    if len(customer_id) <= 4:
        return "****"
    return "*" * (len(customer_id) - 4) + customer_id[-4:]
```

### 8.6 Mapeo de `outcome`

| `decision.action` | `outcome`   |
| ----------------- | ----------- |
| `BLOCK`           | `blocked`   |
| `REVIEW`          | `escalated` |
| `ALLOW`           | `success`   |

### 8.7 Cálculo de tokens

`tokens_from_usage(usage)`:

- Si `usage` es None → `tokens` es None.
- Si `usage.input_tokens` es None O `usage.output_tokens` es None → `tokens` es None.
- Si ambos están presentes → `tokens = input_tokens + output_tokens`.

### 8.8 Serialización de thresholds

`_serialize_thresholds` convierte el objeto de thresholds a un dict serializable.

### 8.9 Validación del envelope

`JsonlAuditSink` invoca `validate_event` antes de persistir.

## 9. Trust boundaries (construcción y validación)

### 9.1 `build_customer_context`

```python
def build_customer_context(self, complaint_id: str) -> dict:
    """Construye customer_context desde fuentes verificadas (sandbox)."""
```

Algoritmo:

1. Validar que `complaint_id` sea `str` no vacío. Si no lo es → `authenticated=True`, `verified_complaint_ids=()`, `authorized_product_ids=()`.
2. Llamar `self._dispute_context_loader(complaint_id)`.
   - Si lanza excepción, devuelve un valor que no es `dict` o devuelve `{"error": ...}` → `authenticated=True`, `verified_complaint_ids=()`, `authorized_product_ids=()`.
3. Validar que el contexto contiene el MISMO `complaint_id` solicitado como `str` no vacío. Si falta, tiene tipo inválido o no coincide → `authenticated=True`, `verified_complaint_ids=()`, `authorized_product_ids=()`.
4. Si coincide: `authenticated=True`, `verified_complaint_ids=(complaint_id,)`.
5. Extraer `product_id`. Solo agregarlo a `authorized_product_ids` si es `str` no vacío; cualquier valor ausente, vacío o de otro tipo produce `authorized_product_ids=()`.
6. Devolver el dict con las tres claves.

`authenticated=True` es intencional incluso ante fallos del loader: en este hackathon representa autenticación simulada e independiente del sandbox. La autorización permanece fail-closed porque `verified_complaint_ids` y `authorized_product_ids` quedan vacíos ante cualquier contexto no verificable.

### 9.2 `build_verified_facts`

```python
def build_verified_facts(self, dispute_context: dict) -> dict:
    """Construye verified_facts con SOLO las claves de VERIFIED_FACTS_ALLOWLIST (Spec #4)."""
```

### 9.3 `build_actions_taken` (compatible con Spec #4, sin target_id)

```python
def build_actions_taken(self, tool_results: list[dict]) -> tuple[list[dict], bool]:
    """Construye y normaliza actions_taken desde resultados de tools.

    Devuelve (valid_actions, has_failed_actions).
    - valid_actions: lista de dicts con EXACTAMENTE ACTION_REQUIRED_FIELDS
      ({"action_name", "executed", "verification"}), sin target_id.
    - has_failed_actions: True si alguna acción falló.
    """
```

#### Constantes de Spec #4 utilizadas

- `ACTION_REQUIRED_FIELDS = {"action_name", "executed", "verification"}` (sin `target_id`).
- `ACTION_VERIFICATIONS` es un dict anidado: `{action_name: {verification: expected_executed_bool}}`.

#### Algoritmo (orden correcto, sin target_id, ACTION_VERIFICATIONS por action_name)

```python
valid_actions = []
has_failed_actions = False

for result in tool_results:
    if not isinstance(result, dict):
        raise ValueError(f"Resultado de tool no es dict: {type(result)}")

    # 1. Resultados de lectura: sin campo action
    if "action" not in result:
        continue  # Resultado de lectura o error de contexto, omitir

    action_name = result["action"]

    # 2. Validar action_name
    if not isinstance(action_name, str) or action_name not in ACTION_VERIFICATIONS:
        raise ValueError(f"Acción desconocida: {action_name!r}")

    expected = ACTION_VERIFICATIONS[action_name]

    # 3. Idempotencia: reason=already_blocked (solo block_card)
    if result.get("reason") == "already_blocked":
        if action_name != "block_card" or result.get("executed") is not False:
            raise ValueError(
                "already_blocked requiere action=block_card y executed=False"
            )
        if "verification" in result:
            if result["verification"] != "already_blocked_no_action_taken":
                raise ValueError("already_blocked tiene verification contradictoria")
            # La rama canónica siguiente validará la combinación completa.
        else:
            valid_actions.append({
                "action_name": action_name,
                "executed": False,
                "verification": "already_blocked_no_action_taken",
            })
            continue

    # 4. Acciones con verification
    if "verification" in result:
        verification = result["verification"]

        if verification not in expected:
            # Verificación desconocida o fallida para esta acción
            has_failed_actions = True
            continue

        executed = result.get("executed")
        if not isinstance(executed, bool):
            raise ValueError("executed debe ser bool")

        if executed is not expected[verification]:
            raise ValueError("verification contradice executed")

        valid_actions.append({
            "action_name": action_name,
            "executed": executed,
            "verification": verification,
        })
        continue

    # 5. Denegaciones de política: executed=False, reason presente, sin verification
    if result.get("executed") is False and "reason" in result:
        continue  # Denegación de política, omitir

    # 6. Resultado malformado
    raise ValueError(f"Resultado de tool malformado para action '{action_name}'")

return valid_actions, has_failed_actions
```

Nota: la salida canónica contiene EXACTAMENTE `{"action_name", "executed", "verification"}`. NO incluye `target_id` ni ningún otro campo. Esto cumple la igualdad exacta `set(action) == ACTION_REQUIRED_FIELDS` que verifica `screen_agent_output`.

### 9.4 Responsabilidad de construcción

El adaptador construye `customer_context`, `verified_facts` y `actions_taken` desde fuentes verificadas. El modelo NUNCA controla estos objetos. La detección de acciones fallidas (`has_failed_actions=True`) es responsabilidad del orquestador (Spec #7).

## 10. Fail-closed y manejo de errores

### 10.1 Principio

Ante cualquier error de Jev, el adaptador produce una decisión conservadora. NUNCA propaga `JevError` al llamador.

### 10.2 Orden de captura de excepciones

CRÍTICO: capturar PRIMERO `JevValidationError`, LUEGO `JevError`.

### 10.3 Errores no-Jev

Se propagan al llamador. El adaptador no los captura.

### 10.4 Emisión de eventos ante error

Incluso ante `JevError`, el adaptador emite el evento `governance` con la decisión fail-closed.

## 11. Seguridad

- El adaptador NO emite señales de Jev en logs generales. Solo en eventos de auditoría vía `AuditSink`.
- El `customer_id` se emite enmascarado.
- Los trust boundaries se construyen desde fuentes verificadas.
- `customer_context` se construye por tool call con el `complaint_id` concreto.
- Los hooks NO contienen lógica de gobierno.

## 12. API pública (ruta exacta)

```python
from ai_banking_customer_service.governance.adapter import (
    GovernanceAdapter,
    ScreeningRoutingResult,
    GovernanceResult,
)
from ai_banking_customer_service.agent.hooks import create_hooks, GovernanceHooks
from ai_banking_customer_service.observability.sink import AuditSink, JsonlAuditSink
from ai_banking_customer_service.observability.contract import validate_event
```

## 13. Módulo de observabilidad (contract.py, sink.py)

### 13.1 contract.py

```python
REQUIRED_ENVELOPE_FIELDS = frozenset({
    "trace_id", "event_id", "timestamp", "component", "event_type",
    "customer_id", "session_id", "outcome", "latency_ms",
})
VALID_COMPONENTS = frozenset({"governance", "orchestrator", "tool", "service"})
VALID_EVENT_TYPES = frozenset({"input", "governance", "tool_call", "policy", "action", "escalation", "response"})
VALID_OUTCOMES = frozenset({"success", "blocked", "escalated", "failure", "abstained"})

def validate_event(event: dict) -> None:
    """Valida el envelope del evento. Lanza ValueError si es inválido."""
```

Validaciones:

- Campos requeridos presentes.
- `trace_id`, `event_id`, `timestamp`, `customer_id`, `session_id` son `str` no vacío.
- `component` en `VALID_COMPONENTS`, `event_type` en `VALID_EVENT_TYPES`, `outcome` en `VALID_OUTCOMES`.
- `latency_ms` es `int` >= 0, excluyendo `bool`: `isinstance(v, int) and not isinstance(v, bool) and v >= 0`.
- `tokens` es `int` >= 0 o None, excluyendo `bool`.
- `cost_usd` es `float` >= 0 o None.
- `payload` es `dict` o None.

### 13.2 sink.py

```python
class AuditSink(Protocol):
    def emit(self, event: dict) -> None: ...

class JsonlAuditSink:
    def __init__(self, output_path: Path): ...
    def emit(self, event: dict) -> None: ...
```

Comportamiento:

- Valida con `validate_event(event)`. Si inválido → `ValueError`.
- Serializa con `json.dumps(event, ensure_ascii=False, allow_nan=False)`. NO `default=str`. Si no serializable o NaN/Inf → `TypeError` o `ValueError`.
- Crea el directorio si no existe.
- Escribe una línea JSON mediante una única operación append. NO se garantiza coordinación multiproceso.
- Errores se propagan al llamador.

## 14. TDD — FASE RED (backlog de tests)

Archivo principal: `tests/unit/governance/test_adapter.py`.
Archivo de hooks: `tests/unit/agent/test_hooks.py`.
Archivo de observabilidad: `tests/unit/observability/test_contract.py`, `tests/unit/observability/test_sink.py`.

### GovernanceAdapter.screen_and_route

- Screening BLOCK/REVIEW/ALLOW → resultado correcto, `last_event_id` no vacío.
- Screening ALLOW + routing BLOCK/REVIEW/ALLOW → resultado correcto.
- `JevValidationError` durante screening/routing → fail-closed con reason code correcto.
- `JevError` durante screening/routing → fail-closed con reason code `JEV_ERROR`.
- Se emiten eventos `governance` para cada etapa ejecutada.
- Si screening produce BLOCK/REVIEW, NO se llama a `route_banking_intent`.
- El segundo evento tiene `parent_event_id` igual al `event_id` del primero.
- `last_event_id` coincide con el `event_id` del último evento emitido.

### GovernanceAdapter.gate_tool_call

- Bloqueo determinístico → BLOCK, NO se llama a `JevClient.evaluate`.
- Jev ALLOW/BLOCK → decisión correcta, `event_id` no vacío.
- `JevValidationError`/`JevError` → fail-closed.
- Se emite evento `governance` para `tool_gating`.
- La latencia se mide SIEMPRE.

### GovernanceAdapter.screen_output

- Secretos detectados → REVIEW, NO se llama a `JevClient.evaluate`.
- Jev ALLOW/REVIEW → decisión correcta.
- `JevValidationError`/`JevError` → fail-closed REVIEW.
- El evento incluye `secrets_detected`.
- La latencia se mide SIEMPRE.

### Emisión de eventos de auditoría

- Cada decisión produce exactamente UN evento `governance`.
- `payload.reasons` es `list[str]`.
- `payload.thresholds` es serializable.
- `outcome` mapea correctamente.
- `tokens` se extrae correctamente.
- `latency_ms` es `int` >= 0.
- `parent_event_id` se establece correctamente.

### Trust boundaries

- `build_customer_context` con `complaint_id` coincidente → `verified_complaint_ids` y `authorized_product_ids` correctos.
- `build_customer_context` con `complaint_id` inexistente o no coincidente → vacíos.
- `build_customer_context` con loader que devuelve `None`, lista o dict malformado → IDs verificados/autorizados vacíos, sin propagar error.
- `build_customer_context` con `product_id` ausente, vacío o no-string → complaint verificado, `authorized_product_ids` vacío.
- `build_verified_facts` extrae solo claves de `VERIFIED_FACTS_ALLOWLIST`.
- `build_actions_taken` con acción exitosa → incluida en `valid_actions` con EXACTAMENTE `{"action_name", "executed", "verification"}` (sin `target_id`), `has_failed_actions=False`.
- `build_actions_taken` con `already_blocked`, `executed=False` y sin verification (block_card) → normalizada a `already_blocked_no_action_taken`, incluida.
- `build_actions_taken` con `already_blocked`, `executed=False` y `verification="already_blocked_no_action_taken"` → incluida por la validación canónica.
- `build_actions_taken` con `already_blocked` y `executed` ausente o distinto de `False` → lanza `ValueError`, tenga o no verification.
- `build_actions_taken` con `already_blocked` y verification distinta de `already_blocked_no_action_taken` → lanza `ValueError`.
- `build_actions_taken` con `already_blocked` para una acción distinta de block_card → lanza `ValueError`.
- `build_actions_taken` con acción fallida (`block_not_confirmed`) → NO incluida, `has_failed_actions=True`.
- `build_actions_taken` con acción fallida con error → NO incluida, `has_failed_actions=True`.
- `build_actions_taken` con `verification` desconocida para la acción → `has_failed_actions=True`.
- `build_actions_taken` con `executed` que contradice `expected[verification]` → lanza `ValueError`.
- `build_actions_taken` con `executed` no bool → lanza `ValueError`.
- `build_actions_taken` con `action_name` desconocido → lanza `ValueError`.
- `build_actions_taken` con resultado de lectura → omitido.
- `build_actions_taken` con denegación de política → omitida.
- `build_actions_taken` con resultado malformado → lanza `ValueError`.
- `build_actions_taken` con resultado no dict → lanza `ValueError`.

### Hooks de Strands (test_hooks.py)

- `create_hooks` devuelve una lista con un `GovernanceHooks`.
- `GovernanceHooks.register_hooks` registra exactamente `BeforeInvocationEvent` y `BeforeToolCallEvent`.
- `before_invocation` invoca `adapter.screen_and_route` con argumentos correctos.
- `before_invocation` con BLOCK establece `event.cancel = "governance:block"`.
- `before_invocation` con REVIEW establece `event.cancel = "governance:review"`.
- `before_invocation` con ALLOW guarda `intent`, `customer_message`, `routing_event_id` en `invocation_state`.
- `before_invocation` NO guarda `customer_context` en `invocation_state`.
- `before_invocation` con `trace_id` ausente cancela fail-closed.
- `before_invocation` sin mensaje de usuario cancela fail-closed.
- `before_tool_call` con `event.tool_use` no dict cancela fail-closed sin modificar estado global.
- `before_tool_call` usa exclusivamente `event.tool_use["toolUseId"]`; no usa `id` ni construye fallback.
- `before_tool_call` con `toolUseId` ausente, vacío o no-string cancela fail-closed sin modificar estado global.
- `before_tool_call` con `name` no str guarda bloqueo per-tool y cancela fail-closed.
- `before_tool_call` con `input=None` guarda bloqueo per-tool y cancela fail-closed.
- `before_tool_call` con `input` no dict cancela fail-closed.
- `before_tool_call` con `complaint_id` ausente cancela fail-closed.
- `before_tool_call` con contexto obligatorio faltante cancela fail-closed.
- `before_tool_call` extrae `complaint_id` de `event.tool_use["input"]`.
- `before_tool_call` construye `customer_context` con `adapter.build_customer_context(complaint_id)`.
- `before_tool_call` invoca `adapter.gate_tool_call` con argumentos correctos y `parent_event_id=routing_event_id`.
- `before_tool_call` con BLOCK establece `event.cancel_tool = "governance:block"`.
- `before_tool_call` con ALLOW no cancela.
- `before_tool_call` guarda resultado o cancelación en `invocation_state["tool_governance"][tool_use_id]`.
- `before_tool_call` NO sobrescribe `last_event_id`, `governance_decision`, `governance_action` globales en ninguna ruta.
- **Test de tools concurrentes**: dos tool calls del mismo batch → ambas usan el mismo `routing_event_id` como `parent_event_id`, resultados separados en `tool_governance` por `toolUseId`, eventos hermanos (no cadena).
- Dos llamadas concurrentes con el mismo `tool_name` y `complaint_id`, pero distinto `toolUseId`, producen dos entradas independientes sin colisión.

### Observabilidad (test_contract.py, test_sink.py)

- `validate_event` acepta evento válido.
- `validate_event` lanza `ValueError` si falta campo requerido.
- `validate_event` lanza `ValueError` si `latency_ms` es `bool`.
- `validate_event` lanza `ValueError` si `tokens` es `bool`.
- `JsonlAuditSink.emit` escribe una línea JSON.
- `JsonlAuditSink.emit` crea el directorio si no existe.
- `JsonlAuditSink.emit` lanza `ValueError` si evento inválido.
- `JsonlAuditSink.emit` lanza `TypeError`/`ValueError` si NaN (por `allow_nan=False`).
- `JsonlAuditSink.emit` lanza `TypeError` si objeto no serializable (sin `default=str`).
- `JsonlAuditSink.emit` escribe múltiples eventos como múltiples líneas.

### Import

- Test de import de la API pública (sección 12).

## 15. FASES GREEN → TRIANGULATE → REFACTOR

- GREEN: implementación mínima.
- TRIANGULATE: casos parametrizados.
- REFACTOR: limpiar duplicación. Sin funcionalidad extra.

## 16. Archivos a crear / modificar

```
src/ai_banking_customer_service/governance/adapter.py   (crear)
src/ai_banking_customer_service/agent/hooks.py          (crear)
src/ai_banking_customer_service/observability/__init__.py (crear)
src/ai_banking_customer_service/observability/contract.py (crear)
src/ai_banking_customer_service/observability/sink.py   (crear)
tests/unit/governance/test_adapter.py                   (crear)
tests/unit/agent/test_hooks.py                          (crear)
tests/unit/observability/__init__.py                    (crear)
tests/unit/observability/test_contract.py               (crear)
tests/unit/observability/test_sink.py                   (crear)
docs/observability.md                                   (modificar: reasons como list[str])
docs/STATUS.md                                          (modificar: actualizar estado)
```

No se modifican `governance/jev/*.py`, `tools/*.py`, `services/*.py`, `agent/tools.py`, `config.py`, ni `configs/policy.yaml`.

## 17. Criterios de aceptación

- `uv run pytest tests/unit/governance/test_adapter.py tests/unit/agent/test_hooks.py tests/unit/observability/ -q` pasa en verde.
- `uv run pytest tests/unit -q` pasa en verde.
- `uv run ruff check` y `uv run ruff format --check` pasan sin errores para todos los archivos nuevos.
- Ningún test llama a la red, a Jev real ni a Strands real.
- El adaptador es framework-agnostic.
- Los hooks implementan `HookProvider` con `register_hooks`.
- `event.cancel` y `event.cancel_tool` se usan como atributos.
- `before_tool_call` valida `event.tool_use`, `toolUseId`, `name`, `input`, `complaint_id` antes de indexar.
- `toolUseId` es obligatorio y no se reemplaza con identificadores fallback.
- Tools concurrentes: resultados y cancelaciones por `toolUseId` en `tool_governance`, padre estable `routing_event_id`, sin sobrescribir claves globales.
- `build_actions_taken` produce dicts con EXACTAMENTE `ACTION_REQUIRED_FIELDS` (sin `target_id`).
- `build_actions_taken` consulta `ACTION_VERIFICATIONS` por `action_name` primero.
- Fail-closed ante `JevError`. Orden de captura correcto.
- `docs/observability.md` y `docs/STATUS.md` actualizados.

## 18. Actualización de STATUS.md y documentación (post-implementación)

Marcar como completado:

- Hooks de Strands con Jev (HookProvider, register_hooks, soporte concurrente).
- Adaptador de gobierno (pipeline completo, auditoría, fail-closed, encadenamiento).
- Módulo de observabilidad (contract.py, sink.py).

Agregar al registro:

```
- [fecha]: Spec #6 v5 implementada con TDD. GovernanceAdapter framework-agnostic.
  GovernanceHooks implementa HookProvider con register_hooks; cancel/cancel_tool
  como atributos. before_tool_call valida tool_use/name/input/complaint_id antes
  de indexar. Soporte para tools concurrentes: routing_event_id como padre estable,
  resultados por toolUseId en tool_governance, sin sobrescribir claves globales.
  build_actions_taken compatible con Spec #4: salida con EXACTAMENTE
  ACTION_REQUIRED_FIELDS (sin target_id), ACTION_VERIFICATIONS consultado por
  action_name. Serialización con allow_nan=False, reasons como list.
  Módulo de observabilidad. docs/observability.md actualizado.
```
