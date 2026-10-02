# SPEC #5 — Registro de las 4 tools en el agente Strands (v3)

Método: TDD estricto — RED → GREEN → TRIANGULATE → REFACTOR.
La lista de tests es el BACKLOG; se ejecuta en microciclos (UN test RED → mínimo GREEN → TRIANGULATE → REFACTOR). Los casos parametrizados cuentan como triangulación.

## 0. Contexto obligatorio antes de implementar

Leer en este orden:

1. `AGENTS.md` — decisiones de diseño, no-negociables, stack (Strands como orquestador).
2. `pyproject.toml` — verificar `strands-agents[openai] >=1.57.1`.
3. Spec #4 (`docs/specs/spec_04.md`) — `TOOL_ARG_CONTRACTS`, `ALLOWED_TOOLS`, `JEV_STATE_ARG_ALLOWLIST`, validadores de tipos/rangos.
4. Tools actuales (`get_dispute_context`, `get_recent_transactions`, `block_card`, `escalate_case`) — firmas reales, docstrings, validaciones internas, retornos reales.
5. `docs/observability.md` — evento `tool_call` y su asignación de emisión.

Este componente se construye SOBRE las tools existentes y Spec #4. No modifica las tools ni la capa de gobierno.

## 1. Objetivo y alcance

### Objetivo

Crear wrappers `@tool` de Strands para las 4 tools existentes, con metadata descriptiva para el LLM, y exportarlos como lista única `REGISTERED_TOOLS`. Garantizar sincronización estructural con las fuentes de verdad correspondientes (sección 6).

### Incluye

- Wrappers `@tool` de las 4 tools (capa delgada, solo delegación).
- Docstrings en inglés que reflejan las categorías REALES de retorno de cada tool.
- Lista exportada `REGISTERED_TOOLS`.
- Test de sincronización con `TOOL_ARG_CONTRACTS`/`ALLOWED_TOOLS` (nombres, exposición) y con las firmas originales (tipos, defaults, nullabilidad).
- Test de delegación parametrizado.
- Actualización de `docs/observability.md` para asignar `tool_call` al orquestador.

### NO incluye

- Creación del agente `Agent(...)` → Spec #7.
- System prompt → Spec #7.
- Hooks de gobierno (`before_model_hook`, `before_tool_hook`) → Spec #6.
- Selección de modelo → Spec #7.
- Flujo conversacional (memoria, clarificación, abstención) → Spec #7.
- Modificación de las tools originales (`tools/*.py`).
- Modificación de la capa de gobierno (`governance/`).
- Modificación de `TOOL_ARG_CONTRACTS` ni `ALLOWED_TOOLS`.
- Corrección de riesgos preexistentes en las tools (se documentan como deuda, sección 17).

## 2. Pre-work

- Spec #1, #2, #3 y #4 implementadas y tests pasando: `uv run pytest tests/unit -q`.
- `strands-agents[openai] >=1.57.1` instalado y en `uv.lock`.
- Las 4 tools originales funcionan correctamente (smoke-tested).

## 3. Contrato de API de Strands 1.57.1

### 3.1 Acceso a la tool decorada

En `strands-agents 1.57.1`, el decorador `@tool` devuelve un `DecoratedFunctionTool`. El acceso a sus propiedades es:

```python
tool.tool_name                            # str: nombre de la tool
tool.tool_spec["description"]             # str: descripción (del docstring)
tool.tool_spec["inputSchema"]["json"]     # dict: JSON Schema de entrada
```

### 3.2 Terminología

En Strands, `Tool` también nombra un `TypedDict`. Para evitar confusión, esta spec usa "tool decorada de Strands" o "DecoratedFunctionTool", NO "objeto Tool".

### 3.3 Importación del decorador

```python
from strands import tool
```

Esta importación es correcta en `strands-agents 1.57.1`. Si una actualización de `uv.lock` cambia la versión de `strands-agents`, el contrato de acceso de la sección 3.1 debe revalidarse. No inventar rutas de importación ni atributos.

## 4. Diseño: wrappers `@tool` como capa delgada

### 4.1 Principio de no-modificación

NO se modifican las funciones originales en `tools/`. Los wrappers se crean en un módulo nuevo (`agent/tools.py`) y delegan a las funciones originales. Esto respeta la decisión de diseño de AGENTS.md y mantiene las tools testables sin Strands.

### 4.2 Estructura del wrapper

Cada wrapper:

1. Importa la función original con alias privado (`as _nombre`).
2. Define una función con la MISMA firma exacta (nombres de parámetros, tipos, defaults) verificable con `inspect.signature`.
3. Aplica el decorador `@tool` de Strands.
4. Tiene un docstring en inglés que refleja las categorías REALES de retorno (sección 5).
5. El cuerpo contiene una ÚNICA sentencia `return`, sin lógica adicional. Puede ocupar múltiples líneas por formato (Ruff 88 caracteres), pero es una sola sentencia.

### 4.3 Tipo de retorno y serialización

Los wrappers retornan `dict` (igual que las funciones originales). Hay DOS caminos de ejecución:

- **Llamada directa** (tests unitarios): retorna un dict Python sin serializar.
- **Ejecución mediante Agent** (producción): Strands convierte el dict al resultado que consume el modelo.

No convertir a `str` manualmente. La serialización es responsabilidad de Strands en el camino de producción.

### 4.4 Código objetivo

```python
# src/ai_banking_customer_service/agent/tools.py
"""Strands @tool wrappers for the 4 banking agent tools.

Thin delegation layer. Each wrapper applies the @tool decorator for
Strands schema generation and delegates to the original implementation.

Direct calls to these wrappers are for unit tests ONLY. In production,
tools MUST be invoked exclusively through the governed Agent (Spec #7),
which enforces tool gating (Spec #4) and hooks (Spec #6).
"""

from strands import tool

from ai_banking_customer_service.tools.block_card import (
    block_card as _block_card,
)
from ai_banking_customer_service.tools.escalate_case import (
    escalate_case as _escalate_case,
)
from ai_banking_customer_service.tools.get_dispute_context import (
    get_dispute_context as _get_dispute_context,
)
from ai_banking_customer_service.tools.get_recent_transactions import (
    get_recent_transactions as _get_recent_transactions,
)


@tool
def get_dispute_context(complaint_id: str) -> dict:
    """Retrieve the full context of a transaction dispute case.

    Use this tool FIRST when a customer reports an unrecognized charge.
    It returns customer info, product details, transaction data, and
    the system's recommended action. Do not skip this step.

    Args:
        complaint_id: Unique complaint ID (e.g., CMP-LMHTOD889KGMUG3RQSAA).

    Returns:
        dict with the full dispute context including customer_id,
        product_id, product_type, transaction_id, amount, currency,
        merchant_name, complaint_date, and recommended_action.
        Returns {"error": "..."} on input validation, missing data or
        storage, or query failure.
    """
    return _get_dispute_context(complaint_id)


@tool
def get_recent_transactions(
    complaint_id: str,
    days_before: int = 30,
    limit: int = 10,
) -> dict:
    """Retrieve recent transactions for the product linked to a complaint.

    Use this tool to show the customer their recent transactions so they
    can identify which one they do not recognize. Transactions are
    filtered by product_id due to data quality constraints.

    Args:
        complaint_id: Unique complaint ID.
        days_before: How many days back to search (default 30, positive int).
        limit: Maximum transactions to return (default 10, between 1 and 50).

    Returns:
        dict with transaction_count, list of transactions (transaction_id,
        transaction_date, transaction_type, amount, currency, merchant_name),
        and case metadata. Returns {"error": "..."} on input validation,
        missing data or storage, or query failure.
    """
    return _get_recent_transactions(complaint_id, days_before, limit)


@tool
def block_card(
    complaint_id: str,
    confirmed_by_customer: bool = False,
) -> dict:
    """Block the card associated with a dispute.

    SENSITIVE ACTION. Only call this tool AFTER the customer has EXPLICITLY
    confirmed they want to block their card. Never call with
    confirmed_by_customer=False. The tool will reject unconfirmed requests.

    Args:
        complaint_id: Unique complaint ID.
        confirmed_by_customer: Must be True. Set True only after the
            customer explicitly confirmed the block.

    Returns:
        dict. Categories of results:
        - Context error: {"error": "..."} on input validation, missing
          data or storage, or query failure.
        - Policy denial (executed=False, reason set):
          * "customer_confirmation_required": customer did not confirm.
          * "product_not_blockable": product type is not a card.
          * "product_not_active": product status is not Active.
          * "already_blocked": card was already blocked (pre-check).
        - Service outcome (executed=True|False, verification set):
          * "confirmed_blocked": card blocked and verified.
          * "already_blocked_no_action_taken": card was blocked by a
            concurrent request after the pre-check (race condition).
          * "block_not_confirmed": block executed but verification failed.
          * "block_failed_db_error": database error during the block.
    """
    return _block_card(complaint_id, confirmed_by_customer)


@tool
def escalate_case(
    complaint_id: str,
    reason: str,
    unresolved_questions: list | None = None,
    agent_notes: str | None = None,
) -> dict:
    """Escalate a case to a human agent with a structured handoff.

    Use this tool when the case CANNOT be resolved automatically:
    old charges outside the blocking window, high-value disputes,
    cases requiring investigation, or when the customer asks for a human.

    Args:
        complaint_id: Unique complaint ID.
        reason: Escalation reason (e.g., 'cargo_antiguo', 'monto_alto',
            'cliente_solicita_humano'). These are examples, not a closed
            vocabulary; any non-empty string is accepted.
        unresolved_questions: Optional list of pending questions for the
            human team. Elements may be of any type (not validated).
        agent_notes: Optional additional notes from the virtual agent.

    Returns:
        dict. Categories of results:
        - Input or context error: {"error": "..."} on input validation,
          missing data or storage, or query failure.
        - Persistence failure (executed=False, verification set):
          * "escalation_not_confirmed": escalation executed but
            verification failed.
          * "escalation_failed_db_error": database error during
            persistence.
        - Success (executed=True): escalation_id, priority, verification
          ("confirmed_persisted"), and the full structured handoff JSON.
    """
    return _escalate_case(
        complaint_id,
        reason,
        unresolved_questions,
        agent_notes,
    )


REGISTERED_TOOLS: list = [
    get_dispute_context,
    get_recent_transactions,
    block_card,
    escalate_case,
]
```

Nota: las firmas largas se formatean en múltiples líneas para cumplir el límite de 88 caracteres de Ruff. Cada cuerpo es una única sentencia `return`.

## 5. Docstrings y metadata para el LLM

### 5.1 Idioma y propósito

Los docstrings de los wrappers están en INGLÉS. Orientan al modelo sobre cuándo y cómo usar cada tool. El schema estructural (tipos, parámetros) se genera desde las firmas y anotaciones de la función, NO desde el idioma del docstring. El inglés no vuelve por sí solo más preciso al schema.

### 5.2 Estructura del docstring

Formato Google-style parseable por Strands:

- Línea 1: descripción corta imperativa ("Retrieve...", "Block...", "Escalate...").
- Párrafo de contexto: cuándo usar la tool y cuándo no.
- `Args:` con descripción de cada parámetro.
- `Returns:` con las categorías REALES del dict de retorno.

### 5.3 Docstrings reflejan categorías reales de retorno

Los docstrings documentan las CATEGORÍAS de retorno de cada tool (errores de contexto, denegaciones de política, resultados del servicio), no una enumeración cerrada de variantes. Esto refleja fielmente el comportamiento real de las tools y sus servicios mock.

Para `block_card`, las categorías son:

- **Errores de contexto**: `{"error": ...}` desde `get_dispute_context`.
- **Denegaciones de política** (`executed=False`, `reason` seteado): `customer_confirmation_required`, `product_not_blockable`, `product_not_active`, `already_blocked` (pre-check).
- **Resultados del servicio** (`executed=True|False`, `verification` seteado): `confirmed_blocked`, `already_blocked_no_action_taken`, `block_not_confirmed`, `block_failed_db_error`. El campo `verification` se copia del servicio mock al resultado superior, por lo que `already_blocked_no_action_taken` SÍ puede ser retorno crudo si hay una carrera después del pre-check.

Para `escalate_case`, las categorías son:

- **Errores de contexto**: `{"error": ...}` desde `get_dispute_context`.
- **Fallo de persistencia** (`executed=False`, `verification` seteado): `escalation_not_confirmed`, `escalation_failed_db_error`.
- **Éxito** (`executed=True`): `escalation_id`, `priority`, `verification="confirmed_persisted"`, handoff completo.

### 5.4 Notas de seguridad en docstrings

- `block_card` incluye la advertencia "SENSITIVE ACTION" y la instrucción de solo llamar con `confirmed_by_customer=True`.
- `get_dispute_context` incluye "Use this tool FIRST" para guiar el flujo.
- `escalate_case` lista los escenarios de uso y aclara que `reason` no es un vocabulario cerrado.

Estas notas son orientación para el LLM. NO reemplazan las validaciones determinísticas en las tools ni el tool gating de Spec #4.

### 5.5 Docstrings NO son política

Los docstrings orientan al LLM, pero NO son controles de seguridad. La autorización real vive en:

- Validación determinística de Spec #4 (`validate_tool_call_deterministic`).
- Validaciones internas de las tools (confirmación, tipo de producto, estado).
- Spec #6 (hooks de gobierno).

### 5.6 Restricción de contenido sensible

Los docstrings y fixtures NO contienen PAN, CVV, credenciales ni secretos. Los ejemplos usan IDs genéricos (ej. `CMP-LMHTOD889KGMUG3RQSAA` es un ID de ejemplo del sandbox, no un dato sensible).

## 6. Fuentes de verdad y sincronización

### 6.1 Tres fuentes de verdad separadas

Hay TRES fuentes de información distintas que deben mantenerse consistentes. Cada una tiene un alcance diferente:

1. **`TOOL_ARG_CONTRACTS` y `ALLOWED_TOOLS`** (Spec #4, `governance/jev/evaluations.py`): fuente autoritativa de nombres de tools, argumentos requeridos/opcionales, nombres de validadores y elegibilidad. NO contiene defaults ni anotaciones de tipo.

2. **Firmas originales** (`tools/*.py`): fuente autoritativa de tipos Python, defaults y nullabilidad. Las firmas son la referencia para los wrappers.

3. **Schema JSON generado** (Strands `@tool`): representación JSON resultante de las firmas y anotaciones. Es derivado, no una fuente independiente.

### 6.2 Responsabilidad de sincronización

- Spec #5 sincroniza nombres y required/optional con `TOOL_ARG_CONTRACTS` (fuente 1).
- Spec #5 sincroniza tipos, defaults y nullabilidad con las firmas originales (fuente 2) mediante `inspect.signature`.
- El schema JSON (fuente 3) se verifica como derivado correcto de las firmas.

### 6.3 Sincronización con Spec #4 (nombres y exposición)

- Los nombres de las tools en `REGISTERED_TOOLS` coinciden exactamente con `ALLOWED_TOOLS`.
- Para cada tool, los parámetros del schema de Strands coinciden con `required` y `optional` de `TOOL_ARG_CONTRACTS`.
- Los parámetros `required` en el schema de Strands coinciden con `required` en `TOOL_ARG_CONTRACTS`.

### 6.4 Sincronización con las firmas originales (tipos, defaults, nullabilidad)

- `inspect.signature` del wrapper es idéntica a `inspect.signature` de la función original (nombres, tipos, defaults).
- Los tipos JSON relevantes del schema coinciden con las anotaciones:
  - `complaint_id`, `reason`: `"type": "string"`.
  - `agent_notes`: admite exactamente los tipos JSON `"string"` y `"null"`.
  - `days_before`, `limit`: `"type": "integer"`.
  - `confirmed_by_customer`: `"type": "boolean"`.
  - `unresolved_questions`: admite exactamente los tipos JSON `"array"` y `"null"`.
- Los parámetros `list | None` y `str | None` admiten tanto su tipo no nulo como
  `null` en el schema; un schema que admita solamente `null` es inválido.
- Los defaults Python de la firma coinciden con los defaults de la función original.

Los rangos (p. ej. `limit` entre 1 y 50) se verifican en Spec #4, NO se duplican en el JSON Schema.

### 6.5 Acceso al schema de Strands

El test accede al schema de entrada mediante:

```python
tool.tool_spec["inputSchema"]["json"]
```

Este es el contrato concreto de `strands-agents 1.57.1`. Si la versión cambia, el contrato debe revalidarse.

## 7. Módulo de registro y exportación

### 7.1 Estructura de archivos

```
src/ai_banking_customer_service/agent/
├── __init__.py
└── tools.py       # Wrappers @tool + REGISTERED_TOOLS
```

### 7.2 Exportación

```python
from ai_banking_customer_service.agent.tools import REGISTERED_TOOLS
```

`REGISTERED_TOOLS` es la ÚNICA lista que Spec #7 usa para crear el agente. No se construyen listas alternativas.

### 7.3 Orden de REGISTERED_TOOLS

El orden de `REGISTERED_TOOLS` NO es contractual. Los tests comparan conjuntos más longitud y unicidad, no orden.

### 7.4 `__init__.py` de `agent/`

```python
"""Agente bancario: orquestador, tools registradas y flujo conversacional."""
```

El `__init__.py` NO importa `tools.py` automáticamente (evita importar Strands al importar el paquete). La importación se hace explícitamente desde Spec #7.

## 8. Llamadas directas vs ejecución gobernada

### 8.1 Llamadas directas (solo tests)

Llamar directamente un wrapper decorado (p. ej. `block_card(...)`) ejecuta la función Python SIN pasar por la validación del Agent ni por sus hooks. Esto es válido SOLO para tests unitarios.

### 8.2 No son frontera de seguridad

Las llamadas directas NO son una frontera de seguridad. `block_card` no valida por sí misma autenticación ni pertenencia del complaint al cliente; esas garantías viven en Spec #4 (validación determinística) y Spec #6 (hooks).

### 8.3 Producción

Producción debe ejecutar las tools EXCLUSIVAMENTE mediante el Agent gobernado (Spec #7). Spec #6 debe probar que toda invocación originada por el modelo pasa por tool gating.

## 9. Auditoría de tool_call

### 9.1 Asignación de emisión

La emisión de eventos `tool_call` se asigna al ORQUESTADOR (agent/), NO a las tools individuales ni a los wrappers. El orquestador dispone de trace_id, latencia, argumentos sanitizados y resultado.

### 9.2 Actualización de observability.md

Se actualiza `docs/observability.md` para reflejar esta asignación:

Tabla actualizada de puntos de emisión:

```
| Componente                              | Emite                                  | Ubicación   |
| --------------------------------------- | -------------------------------------- | ----------- |
| Orquestador                             | input, tool_call, response, escalation | agent/      |
| Adaptador de gobierno (Spec #6)         | governance                             | governance/ |
| Módulo de política                      | policy                                 | policies/   |
| Servicios mock                          | action                                 | services/   |
```

Nota agregada: "El orquestador emite exactamente UN evento `tool_call` por invocación de tool ejecutada mediante el Agent. Las tools y los wrappers NO emiten eventos directamente. Esto evita duplicación y garantiza que el evento tenga trace_id, latencia, argumentos sanitizados y resultado."

### 9.3 Responsabilidad de Spec #6/#7

Spec #6 y Spec #7 deben garantizar exactamente un evento `tool_call` por invocación, con todos los campos del payload (`tool_name`, `args`, `result_status`, `result_summary`, `verified`).

## 10. Seguridad

- Los wrappers SOLO delegan. No agregan I/O, no loguean, no capturan excepciones.
- Las validaciones de seguridad viven en las tools originales y en Spec #4.
- Los wrappers no sanitizan ni transforman argumentos.
- Los docstrings son orientación para el LLM, no controles de seguridad.
- Las llamadas directas no son frontera de seguridad (sección 8).
- Este módulo NO emite eventos de auditoría (sección 9).
- Los docstrings y fixtures no contienen PAN, CVV ni credenciales.

## 11. API pública (ruta exacta)

```python
from ai_banking_customer_service.agent.tools import (
    REGISTERED_TOOLS,
    get_dispute_context,
    get_recent_transactions,
    block_card,
    escalate_case,
)
```

Los tests de import usan esta ruta exacta (test de pytest bajo `conftest.py`, NO `python -c` standalone).

## 12. TDD — FASE RED (backlog de tests)

Archivo: `tests/unit/agent/test_tools.py`.

### Import y estructura

- El import de la sección 11 funciona (test de pytest, NO `python -c` standalone).
- `REGISTERED_TOOLS` tiene exactamente 4 elementos.
- Los nombres de `REGISTERED_TOOLS` (como conjunto) coinciden con `ALLOWED_TOOLS` (importado de Spec #4).
- No hay nombres duplicados en `REGISTERED_TOOLS`.

### Contrato de Strands 1.57.1

- Cada elemento de `REGISTERED_TOOLS` tiene `tool_name` (str no vacío).
- Cada elemento de `REGISTERED_TOOLS` tiene `tool_spec["description"]` (str no vacío).
- Cada elemento de `REGISTERED_TOOLS` tiene `tool_spec["inputSchema"]["json"]` (dict).

### Sincronización con Spec #4 (nombres y exposición)

- Para cada tool, los nombres de parámetros del schema (`tool_spec["inputSchema"]["json"]["properties"]`) coinciden con `required + optional` de `TOOL_ARG_CONTRACTS`.
- Para cada tool, los nombres de parámetros `required` del schema coinciden con `required` de `TOOL_ARG_CONTRACTS`.

### Sincronización con firmas originales (tipos, defaults, nullabilidad)

- Para cada tool, `inspect.signature(wrapper)` es idéntica a `inspect.signature(función_original)` (nombres, tipos, defaults).
- `get_dispute_context` requiere exactamente `("complaint_id",)` y no tiene opcionales.
- `get_recent_transactions` requiere `("complaint_id",)`, opcionales `days_before` (default 30) y `limit` (default 10).
- `block_card` requiere `("complaint_id",)`, opcional `confirmed_by_customer` (default False).
- `escalate_case` requiere `("complaint_id", "reason")`, opcionales `unresolved_questions` (default None) y `agent_notes` (default None).

### Tipos JSON explícitos

- `complaint_id` tiene `"type": "string"` en el schema (todas las tools).
- `reason` tiene `"type": "string"` en el schema (`escalate_case`).
- `agent_notes` admite exactamente `"string"` y `"null"` en el schema (`escalate_case`).
- `days_before` tiene `"type": "integer"` en el schema (`get_recent_transactions`).
- `limit` tiene `"type": "integer"` en el schema (`get_recent_transactions`).
- `confirmed_by_customer` tiene `"type": "boolean"` en el schema (`block_card`).
- `unresolved_questions` admite exactamente `"array"` y `"null"` en el schema (`escalate_case`).

### Delegación (test parametrizado único)

Un único test parametrizado que verifica, para cada tool:

- Llamada con defaults: el wrapper delega a la función original con los defaults correctos.
- Llamada con argumentos explícitos: el wrapper delega con los argumentos explícitos.
- El valor retornado por el wrapper es idéntico al valor retornado por la función original (mock).

### Docstrings (verificaciones positivas)

- Cada wrapper tiene un docstring que incluye "Args:" y "Returns:".
- El docstring de `block_card` contiene "SENSITIVE ACTION".
- El docstring de `block_card` menciona los valores de reason: `customer_confirmation_required`, `product_not_blockable`, `product_not_active`, `already_blocked`.
- El docstring de `block_card` menciona los valores de verification: `confirmed_blocked`, `already_blocked_no_action_taken`, `block_not_confirmed`, `block_failed_db_error`.
- El docstring de `block_card` menciona `{"error":` como categoría de error de contexto.
- El docstring de `get_dispute_context` contiene "FIRST".
- El docstring de `escalate_case` menciona los valores de verification de fallo: `escalation_not_confirmed`, `escalation_failed_db_error`.
- El docstring de `escalate_case` menciona `confirmed_persisted` como verification de éxito.
- El docstring de `escalate_case` aclara que `reason` no es un vocabulario cerrado.
- `detect_secrets(wrapper.__doc__)` devuelve una tupla vacía para cada wrapper.
- Los fixtures introducidos por este test no contienen secretos reales ni strings que
  coincidan con los patrones de PAN, CVV o credenciales de Spec #4.

## 13. FASES GREEN → TRIANGULATE → REFACTOR

- GREEN: implementación mínima para que cada test pase.
- TRIANGULATE: los casos parametrizados (4 tools × delegación con defaults/explícitos, sincronización con contratos, tipos JSON, nullabilidad) cuentan como triangulación. No agregar duplicados arbitrarios.
- REFACTOR: limpiar duplicación si la hay. Sin funcionalidad extra.

## 14. Archivos a crear / modificar

```
src/ai_banking_customer_service/agent/__init__.py       (crear)
src/ai_banking_customer_service/agent/tools.py          (crear)
tests/unit/agent/__init__.py                            (crear)
tests/unit/agent/test_tools.py                          (crear)
docs/observability.md                                   (modificar: asignar tool_call al orquestador)
docs/STATUS.md                                          (modificar: actualizar estado y deuda)
```

No se modifican `tools/*.py`, `governance/`, `services/`, `config.py`, ni `configs/policy.yaml`.

## 15. Criterios de aceptación

- `uv run pytest tests/unit/agent/test_tools.py -q` pasa en verde.
- `uv run pytest tests/unit -q` (suite completa) pasa en verde — detecta regresiones contra Spec #1–#4.
- `uv run ruff check src/ai_banking_customer_service/agent/ tests/unit/agent/` pasa sin errores (línea máxima 88 caracteres).
- `uv run ruff format --check src/ai_banking_customer_service/agent/ tests/unit/agent/` pasa sin diferencias.
- Ningún test llama a la red ni a Jev.
- `REGISTERED_TOOLS` tiene exactamente 4 tools (conjunto, sin duplicados).
- Los nombres y required/optional de las tools sincronizan con `TOOL_ARG_CONTRACTS` y `ALLOWED_TOOLS` de Spec #4.
- Los tipos, defaults y nullabilidad de los wrappers coinciden con las firmas originales (verificado con `inspect.signature`).
- Los tipos JSON del schema coinciden con las anotaciones (string, integer, boolean, array/null).
- Los wrappers delegan correctamente a las funciones originales.
- Las tools originales NO se modifican.
- Los docstrings son parseables por Strands (Google-style con Args y Returns) y reflejan las categorías reales de retorno.
- Los docstrings pasan `detect_secrets` sin hallazgos; los fixtures no contienen
  secretos reales ni strings que coincidan con patrones de PAN, CVV o credenciales.
- Import público verificado por un test de pytest (NO `python -c` standalone).
- `docs/observability.md` actualizado (tool_call asignado al orquestador).
- `docs/STATUS.md` actualizado (incluyendo las tres entradas de deuda de la sección 17).

## 16. Actualización de STATUS.md y observability.md (post-implementación)

Marcar como completado:

- Registro de las 4 tools en el agente Strands.

Agregar al registro:

```
- [fecha]: Spec #5 v3 implementada con TDD. Wrappers @tool de Strands para las
  4 tools en agent/tools.py, docstrings en inglés que reflejan categorías reales
  de retorno, sincronización con TOOL_ARG_CONTRACTS/ALLOWED_TOOLS (nombres,
  exposición) y con firmas originales (tipos, defaults, nullabilidad via
  inspect.signature), tipos JSON verificados, delegación directa sin lógica
  adicional. tool_call asignado al orquestador en observability.md. Llamadas
  directas declaradas como solo-para-tests.
```

Agregar a "Deuda conocida" las tres entradas exactas de la sección 17.

Actualizaciones de documentos:

- `docs/observability.md`: `tool_call` asignado al orquestador (sección 9).
- `docs/STATUS.md`: actualizar estado y deuda.

## 17. Riesgos preexistentes documentados (deuda técnica)

Estos riesgos pertenecen a las tools y a Spec #4, NO a Spec #5. Se documentan aquí porque Spec #5 expone las tools al modelo. Spec #5 NO los corrige (prohíbe modificar tools y TOOL_ARG_CONTRACTS). Deben resolverse en una spec futura o aceptarse como riesgo conocido.

Se registran EXACTAMENTE estas tres entradas en "Deuda conocida" de `docs/STATUS.md`:

1. **`unresolved_questions` es `list | None`, no `list[str] | None`.** La tool y Spec #4 aceptan elementos de cualquier tipo. Riesgo: el modelo podría pasar elementos no-string. Mitigación futura: validar tipo de elementos en la tool o en TOOL_ARG_CONTRACTS.

2. **`days_before` solo exige un entero positivo, sin límite superior.** Un valor muy grande podría causar consultas lentas. Mitigación futura: agregar límite superior en TOOL_ARG_CONTRACTS.

3. **`reason` acepta cualquier string.** Los valores del docstring son ejemplos, no un vocabulario cerrado. Riesgo: el modelo podría pasar razones arbitrarias. Mitigación futura: definir un vocabulario cerrado o validar contra una allowlist.

Estas tres entradas deben aparecer en `docs/STATUS.md` bajo la sección "Deuda conocida" como criterio de aceptación explícito.
