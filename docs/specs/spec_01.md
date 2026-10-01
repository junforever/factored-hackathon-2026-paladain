# SPEC #1 — Schemas Pydantic y Cliente Jev (contrato consolidado)

> Este archivo es el ÚNICO contrato vigente para Spec #1. Reemplaza a V1 y V2.
> Método de implementación: TDD estricto — RED → GREEN → TRIANGULATE → REFACTOR.

---

## 0. Contexto obligatorio antes de implementar

Leer en este orden:

1. `AGENTS.md` — decisiones de diseño, no-negociables, configuración.
2. `docs/typesafe_jev/README.md` — API de Jev, primitivas, wire schemas, límites, errores.
3. Skill `typesafe-ai` — fuente autorizada de la API oficial. Si hay conflicto, manda la skill.
4. `docs/observability.md` — para saber qué NO hace este componente.

---

## 1. Objetivo y alcance

### Objetivo

Capa de transporte tipada para consultar Jev/TypeSafe: definir preguntas, validar respuestas y manejar errores. Solo transporte y validación. Sin decisiones de negocio.

### Incluye

- Schemas Pydantic de preguntas y respuestas (alineados al wire de Jev).
- Cliente Jev (adapter sobre `typesafe-sdk`).
- Excepciones tipadas.
- Bootstrap hermético de tests.
- Tests unitarios sin red.

### NO incluye

- Evaluaciones concretas (`prompt_injection`, `banking_intent`, etc.) → Spec #2.
- Lógica de umbrales ni `GovernanceDecision` → Spec #3.
- Integración con Strands ni hooks → Spec #6.
- Emisión de eventos de auditoría → capa de gobierno (ver `observability.md`).
- Cambios en tools o services existentes.
- Retries propios (el SDK ya los hace).
- Llamar a la API real en tests.

---

## 2. Pre-work

### 2.1 Fuentes de Información

Las fuentes de configuración quedan: `.env` (secretos/rutas) + `configs/policy.yaml` (negocio) + `configs/eval.yaml` (evaluación).

### 2.2 tests/conftest.py (bootstrap hermético)

Fija variables de entorno determinísticas ANTES de importar el paquete. No depende del `.env` local ni de red.
Estas credenciales ficticias están permitidas (son datos de prueba, no secretos reales).

### 2.3 Modelos en AGENTS.md

El ejemplo de `.env` en `AGENTS.md` muestra claves y modelos SEPARADOS:

```text
OPENAI_API_KEY=
TYPESAFE_API_KEY=
OPENAI_MODEL=gpt-4o-mini
TYPESAFE_DEFAULT_MODEL=jev-1.13.0
```

No tocar el `.env` real.

`.env.example` debe contener las mismas siete variables documentadas en `AGENTS.md`: `OPENAI_API_KEY`, `TYPESAFE_API_KEY`, `OPENAI_MODEL`, `TYPESAFE_DEFAULT_MODEL`, `DUCKDB_NAME`, `SANDBOX_PATH`, `STATE_PATH`.

---

## 3. Mapeo interno → wire

Los schemas internos usan los mismos nombres de campo que el wire de Jev.

| Primitiva | Contrato interno (= wire)                                                                                     |
| --------- | ------------------------------------------------------------------------------------------------------------- |
| Noul      | `type:"noul"`, `instructions:str`, `criteria:{true:str, false:str}`                                           |
| Choice    | `type:"choice"`, `instructions:str`, `criteria:dict[option_id,description]`, campo extra `include_other:bool` |
| Score     | `type:"score"`, `instructions:str`, `criteria:list[str]` (2–10, posicionales)                                 |

**Conversiones determinísticas**

- **include_other=True**: al convertir a wire, agregar `criteria["other"]="None of the above options fit."` solo si `other` no existe. Si ya existen 255 opciones, lanzar `JevValidationError` (no truncar en silencio). `include_other` nunca se serializa al wire.
- **Score respuesta**: las claves de `legend` y `probabilities` se normalizan a `int`.

---

## 4. Schemas (contrato objetivo)

### 4.1 Preguntas — extra="forbid"

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


def _require_non_blank(v: str, field_name: str) -> str:
    """Rechaza strings vacíos o compuestos solo por whitespace."""
    if not v.strip():
        raise ValueError(f"{field_name} no puede estar vacío ni contener solo espacios")
    return v


class NoulCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")
    true: str = Field(min_length=1)
    false: str = Field(min_length=1)

    @field_validator("true", "false")
    @classmethod
    def _no_blank(cls, v: str, info: ValidationInfo) -> str:
        return _require_non_blank(v, info.field_name)


class NoulQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["noul"] = "noul"
    instructions: str = Field(min_length=1)
    criteria: NoulCriteria

    @field_validator("instructions")
    @classmethod
    def _no_blank_instructions(cls, v: str) -> str:
        return _require_non_blank(v, "instructions")


class ChoiceQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["choice"] = "choice"
    instructions: str = Field(min_length=1)
    criteria: dict[str, str] = Field(min_length=2, max_length=255)
    include_other: bool = False

    @field_validator("instructions")
    @classmethod
    def _no_blank_instructions(cls, v: str) -> str:
        return _require_non_blank(v, "instructions")

    @field_validator("criteria")
    @classmethod
    def _no_empty(cls, v: dict[str, str]) -> dict[str, str]:
        for k, desc in v.items():
            if not k.strip():
                raise ValueError("option_id vacío o compuesto solo por espacios")
            if not desc.strip():
                raise ValueError(f"descripción vacía o compuesta solo por espacios para '{k}'")
        return v


class ScoreQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["score"] = "score"
    instructions: str = Field(min_length=1)
    criteria: list[str] = Field(min_length=2, max_length=10)

    @field_validator("instructions")
    @classmethod
    def _no_blank_instructions(cls, v: str) -> str:
        return _require_non_blank(v, "instructions")

    @field_validator("criteria")
    @classmethod
    def _no_empty_levels(cls, v: list[str]) -> list[str]:
        for level in v:
            if not level.strip():
                raise ValueError("nivel de Score vacío o compuesto solo por espacios")
        return v


Question = NoulQuestion | ChoiceQuestion | ScoreQuestion
```

**Reglas**

- `NoulCriteria.true` y `.false` son obligatorios y no vacíos.
- `ChoiceQuestion.criteria`: 2–255 entradas, IDs y descripciones no vacíos. La unicidad de IDs está garantizada por el dict (no hay validación ni test de duplicados).
- `ScoreQuestion.criteria`: 2–10 niveles posicionales, ninguno vacío.

### 4.2 Respuestas — extra="allow"

```python
from typing import Annotated, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Probability = Annotated[float, Field(ge=0.0, le=1.0)]
JSONContent = str | dict[str, Any] | list[Any]

class NoulAnswer(BaseModel):
  model_config = ConfigDict(extra="allow")
  type: Literal["noul"] = "noul"
  noul: Probability

class ChoiceAnswer(BaseModel):
  model_config = ConfigDict(extra="allow")
  type: Literal["choice"] = "choice"
  choice: str
  probabilities: dict[str, Probability]
  confidence: Probability

  @model_validator(mode="after")
  def _choice_present(self):
      if self.choice not in self.probabilities:
          raise ValueError("choice no está en probabilities")
      return self

class ScoreAnswer(BaseModel):
  model_config = ConfigDict(extra="allow")
  type: Literal["score"] = "score"
  score: float
  legend: dict[int, JSONContent]
  probabilities: dict[int, Probability]
  confidence: Probability

  @field_validator("legend", "probabilities", mode="before")
  @classmethod
  def _int_keys(cls, v):
      if isinstance(v, dict):
          return {int(k): val for k, val in v.items()}
      return v

class Usage(BaseModel):
  model_config = ConfigDict(extra="allow")
  input_tokens: int | None = None
  output_tokens: int | None = None

Answer = Annotated[
  NoulAnswer | ChoiceAnswer | ScoreAnswer,
  Field(discriminator="type"),
]

class JevResponse(BaseModel):
  model_config = ConfigDict(extra="allow")
  model: str
  answers: dict[str, Answer]
  usage: Usage

  def _get(self, question_id: str, expected: str):
      if question_id not in self.answers:
          raise JevValidationError(f"question_id '{question_id}' no existe")
      ans = self.answers[question_id]
      if ans.type != expected:
          raise JevValidationError(
              f"answer '{question_id}' es '{ans.type}', se esperaba '{expected}'"
          )
      return ans

  def get_noul(self, question_id: str) -> NoulAnswer:
      return self._get(question_id, "noul")

  def get_choice(self, question_id: str) -> ChoiceAnswer:
      return self._get(question_id, "choice")

  def get_score(self, question_id: str) -> ScoreAnswer:
      return self._get(question_id, "score")
```

`extra="allow"` en respuestas tolera campos futuros del proveedor.

---

## 5. Cliente Jev (adapter sobre typesafe-sdk)

### Interfaz

```python
from typing import Any, Mapping
from pydantic import SecretStr

class JevClient:
  def __init__(
    self,
    api_key: SecretStr | None = None,
    model: str | None = None,
    timeout_seconds: float = 10.0,
  ): ...

    def evaluate(
        self,
        *,
        state: Mapping[str, Any],
        questions: Mapping[str, Question],
    ) -> JevResponse: ...
```

**Constructor**

- Si `api_key` es None → usar `settings.typesafe_api_key`.
- Si `model` es None → usar `settings.typesafe_default_model`.
- Si la API key está vacía → `JevConfigError`.
- Si `timeout_seconds <= 0` → `JevConfigError`.
- `timeout_seconds` se delega al SDK (`TypeSafeClient(timeout=timeout_seconds)`). No hay timeout propio.
  No imprimir ni loguear la API key.

**evaluate — flujo**

1. Si `questions` vacío → `JevValidationError`.
2. Si `state` no es JSON-serializable → `JevValidationError`.
3. Construir request wire (`state`, `model`, `questions` convertidas, aplicando `include_other`).
4. Llamar `_invoke(request)` dentro de try/except que mapea excepciones SDK (sección 7).
5. Parsear el dict de respuesta con `JevResponse.model_validate`. Si falla → `JevValidationError`.
6. Validar completitud: `set(response.answers) == set(questions)`. Si falta o sobra algún question_id → `JevValidationError`.

**Seam de transporte**

```python
def _invoke(self, request: dict) -> dict: ...
```

- Devuelve un dict con la forma wire de la respuesta (`model`, `answers`, `usage`).
- Producción: construye `TypeSafeClient` con `api_key`, `model` y `timeout`; llama `client.system_one(state=..., questions=...)` pasando las preguntas wire como diccionarios directamente (el SDK acepta dicts; NO se convierten a tipos `Noul`/`Choice`/`Score`); convierte la respuesta `SystemOneResponse` a dict wire; garantiza el cierre del cliente; propaga las excepciones SDK tal cual.
- Tests: monkeypatch de `_invoke` para devolver fixtures o lanzar excepciones SDK. Sin red.
- El arnés inspecciona el SDK 0.7.2 instalado para la conversión exacta. No inventar.

**Retries y timeout**

- NO agregar retries propios. El SDK hace backoff para 429/529 y respeta `Retry-After`.
- Timeout delegado al SDK vía `timeout_seconds`.

`settings.typesafe_api_key` es un `SecretStr`. Para verificar si está vacía usar `.get_secret_value()`. Nunca loguear ni imprimir el valor.

---

## 6. Parsing y discriminación

Unión discriminada por `type`. Reglas:

| Situación                                    | Resultado                         |
| -------------------------------------------- | --------------------------------- |
| `type` ausente                               | `JevValidationError`              |
| `type` desconocido                           | `JevValidationError`              |
| Helper incompatible con el tipo real         | `JevValidationError`              |
| Campo requerido ausente                      | `JevValidationError`              |
| Claves Score str vs int                      | Se normalizan a int (NO es error) |
| `question_id` inexistente en `get\*`         | `JevValidationError`              |
| Respuesta del proveedor malformada           | `JevValidationError`              |
| Respuesta faltante para una pregunta enviada | `JevValidationError`              |
| Respuesta con question_id no solicitado      | `JevValidationError`              |
| usage ausente                                | `JevValidationError`              |

**Aclaración**: solo respuestas malformadas e inputs inválidos terminan en `JevValidationError`. Los errores de transporte (auth, rate limit, indisponibilidad) se mapean según la sección 7.

---

## 7. Excepciones y mapeo

Jerarquía

```python
class JevError(Exception): ...
class JevConfigError(JevError): ...
class JevValidationError(JevError): ...
class JevAuthError(JevError): ...
class JevRateLimitError(JevError): ...
class JevUnavailableError(JevError): ...
```

**Mapeo (excepciones reales del SDK 0.7.2)**
`_invoke` propaga; `evaluate` captura y traduce:

| Excepción del SDK                        | Excepción propia      |
| ---------------------------------------- | --------------------- |
| `TypeSafeAuthenticationError` (401)      | `JevAuthError`        |
| `TypeSafeUnprocessableEntityError` (422) | `JevValidationError`  |
| `TypeSafeRateLimitError` (429)           | `JevRateLimitError`   |
| `TypeSafeInternalServerError` (5xx/529)  | `JevUnavailableError` |
| `TypeSafeAPITimeoutError`                | `JevUnavailableError` |
| `TypeSafeAPIConnectionError`             | `JevUnavailableError` |
| `TypeSafeAPIResponseValidationError`     | `JevValidationError`  |
| `TypeSafeBadRequestError` (400)          | `JevValidationError`  |
| `TypeSafePermissionDeniedError` (403)    | `JevAuthError`        |
| `TypeSafeNotFoundError` (404)            | `JevValidationError`  |
| `TypeSafeError` (base, cualquier otra)   | `JevUnavailableError` |

- Importar estas excepciones del paquete `typesafe_sdk` instalado (inspeccionar ubicación exacta). Ningún mensaje de excepción contiene la API key.
- Ninguna excepción `TypeSafe*` escapa de `evaluate`. El adapter captura `TypeSafeError` (clase base) como catch-all final y la traduce a una subclase de `JevError`. El límite de excepciones públicas queda cerrado: desde `evaluate` solo se propagan subclases de `JevError`.

---

## 8. Seguridad y sanitización

- El wrapper NO loguea bodies (ni `state` ni respuestas). El SDK 0.7.2 sí los registra si su logger está en DEBUG; por tanto el adapter fija el logger del SDK a INFO o superior y se prohíbe `TYPESAFE_LOG_LEVEL=debug` con datos reales. Si se necesita depurar, aplicar redacción/enmascaramiento explícito.
- El cliente NO incluye secretos en excepciones ni logs.
- La sanitización del `state` (enmascarar PAN, CVV, PII) es responsabilidad del llamador (capa de gobierno). Este componente solo garantiza no loguear y no filtrar secretos.
- Este componente NO emite eventos de auditoría. La auditoría de modelo, señales y latencia la hace el adaptador de gobierno de Spec #6, según `observability.md`.

---

## 9. TDD — FASE RED (tests a escribir primero)

La lista siguiente es el BACKLOG de tests. No se escriben todos antes de implementar. Se ejecuta en microciclos TDD: UN test RED → implementación mínima GREEN → TRIANGULATE (segundo ejemplo) → REFACTOR, y se repite para el siguiente test.

**tests/unit/governance/jev/test_import.py**

1. test_public_api_importable: importa `JevClient`, `NoulQuestion`, `ChoiceQuestion`, `ScoreQuestion`, `JevResponse`, `JevError`, `JevConfigError`, `JevValidationError`, `JevAuthError`, `JevRateLimitError`, `JevUnavailableError`.

**tests/unit/governance/jev/test_schemas.py**

2. NoulQuestion acepta instructions + criteria.true/false válidos.
3. NoulQuestion rechaza instructions vacío.
4. NoulQuestion rechaza instructions compuesto solo por espacios.
5. NoulCriteria rechaza true/false compuestos solo por espacios.
6. NoulQuestion rechaza criteria.true (o .false) vacío.
7. ChoiceQuestion rechaza < 2 opciones.
8. ChoiceQuestion rechaza > 255 opciones.
9. ChoiceQuestion rechaza descripción de opción vacía.
10. ChoiceQuestion rechaza `option_id` vacío (clave vacía en el dict de criteria).
11. ScoreQuestion rechaza < 2 niveles.
12. ScoreQuestion rechaza > 10 niveles.
13. ScoreQuestion rechaza nivel vacío.
14. NoulAnswer rechaza noul < 0.
15. NoulAnswer rechaza noul > 1.
16. ChoiceAnswer rechaza choice ausente en probabilities.
17. ScoreAnswer normaliza claves legend/probabilities de str a int.
18. ScoreAnswer acepta legend con descripción estructurada (dict o list) y normaliza las claves a int.
19. Unión discriminada parsea noul/choice/score por type.
20. Unión discriminada rechaza type desconocido.
21. Unión discriminada rechaza type ausente.

**tests/unit/governance/jev/test_client.py**

22. Constructor lanza JevConfigError si api_key vacía.
23. Constructor lanza JevConfigError si timeout_seconds <= 0.
24. evaluate lanza JevValidationError si questions vacío.
25. evaluate lanza JevValidationError si state no JSON-serializable.
26. evaluate construye request wire correcto (verificar dict pasado a \_invoke).
27. include_other=True agrega "other" si no existe.
28. include_other=True no duplica "other" si ya existe.
29. include_other=True con 255 opciones lanza JevValidationError.
30. evaluate devuelve JevResponse tipado con wire dict válido.
31. get_noul/get_choice/get_score parsean correctamente.
32. get_noul sobre answer choice lanza JevValidationError.
33. get\_\* con question_id inexistente lanza JevValidationError.
34. \_invoke lanza TypeSafeAuthenticationError → JevAuthError.
35. \_invoke lanza TypeSafeUnprocessableEntityError → JevValidationError.
36. \_invoke lanza TypeSafeRateLimitError → JevRateLimitError.
37. \_invoke lanza TypeSafeInternalServerError → JevUnavailableError.
38. \_invoke lanza TypeSafeAPITimeoutError → JevUnavailableError.
39. \_invoke lanza TypeSafeAPIConnectionError → JevUnavailableError.
40. \_invoke lanza TypeSafeAPIResponseValidationError → JevValidationError.
41. Ningún error expone la API key (assert sobre str(exc)).
42. El cliente no loguea state ni respuestas (caplog).
43. Respuesta malformada de \_invoke → JevValidationError.
44. \_invoke real: construye `TypeSafeClient` con `api_key`, `model` y `timeout` correctos.
45. \_invoke real: llama `system_one` con `state` y `questions` wire correctos.
46. \_invoke real: convierte `SystemOneResponse` al dict wire esperado.
47. \_invoke real: cierra el cliente (context manager / `close`).
48. \_invoke lanza TypeSafeBadRequestError → JevValidationError.
49. \_invoke lanza TypeSafePermissionDeniedError → JevAuthError.
50. \_invoke lanza TypeSafeNotFoundError → JevValidationError.
51. \_invoke lanza TypeSafeError (base) → JevUnavailableError (catch-all).
52. evaluate lanza JevValidationError si falta la respuesta para un `question_id` enviado.
53. evaluate lanza JevValidationError si la respuesta contiene un `question_id` no solicitado.
54. evaluate lanza JevValidationError si la respuesta no contiene `usage`.
55. El adapter fija el logger del SDK (`typesafe_sdk` o su nombre real) en INFO o superior, incluso si estaba en DEBUG antes de inicializar. Este test debe:

- Configurar el logger del SDK en DEBUG.
- Inicializar o invocar el adapter.
- Verificar que el nivel efectivo del logger sea ≥ INFO.

---

## 10. GREEN → TRIANGULATE → REFACTOR

- _GREEN_: implementación mínima para que cada test pase.
- _TRIANGULATE_: agregar un segundo ejemplo por comportamiento para forzar generalización (evitar implementaciones hardcodeadas a un caso).
- _REFACTOR_: limpiar duplicación, mantener el contrato público estable. Sin funcionalidad extra.

---

## 11. Archivos a crear

```text
src/ai_banking_customer_service/governance/__init__.py
src/ai_banking_customer_service/governance/jev/__init__.py
src/ai_banking_customer_service/governance/jev/schemas.py
src/ai_banking_customer_service/governance/jev/client.py
src/ai_banking_customer_service/governance/jev/exceptions.py
tests/unit/governance/__init__.py
tests/unit/governance/jev/__init__.py
tests/unit/governance/jev/test_import.py
tests/unit/governance/jev/test_schemas.py
tests/unit/governance/jev/test_client.py
```

`tests/conftest.py` ya fue agregado

---

## 12. Criterios de aceptación

1. `uv run pytest tests/unit/governance/jev -q` pasa en verde (verifica imports bajo conftest).
2. Ningún test llama a la red.
3. No hay secretos reales hardcodeados (credenciales ficticias de conftest.py permitidas).
4. No se implementan evaluaciones, hooks ni decisiones de negocio.
5. No se modifican tools ni services existentes.
6. `configs/settings.yaml` no existe.
7. Un único archivo de spec vigente (este); V1 y V2 eliminados.
8. `docs/STATUS.md` actualizado.

No se usa `python -c` standalone para verificar imports (no carga conftest).

---

## 13. Actualización de STATUS.md (post-implementación)

Marcar como completado:

```text
Schemas Pydantic de Jev (wire format Noul/Choice/Score)
Cliente Jev (adapter sobre typesafe-sdk)
```

Agregar al registro:

```text
[fecha]: Spec #1 implementada con TDD. Schemas alineados al wire de Jev,
cliente adapter sobre typesafe-sdk, bootstrap hermético, parsing discriminado
y mapeo tipado de errores SDK.
```
