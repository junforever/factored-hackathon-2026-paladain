# SPEC #3 — Lógica de Decisión de Gobierno (v4)

Método: TDD estricto — RED → GREEN → TRIANGULATE → REFACTOR.
La lista de tests es el BACKLOG; se ejecuta en microciclos (UN test RED → mínimo GREEN → TRIANGULATE → REFACTOR). Los casos parametrizados cuentan como triangulación.

## 0. Contexto obligatorio antes de implementar

Leer en este orden:

1. `AGENTS.md` — decisiones de diseño, no-negociables, configuración.
2. `docs/observability.md` — contrato de auditoría (vocabulario `input_screening | intent_routing | tool_gating | output_screening`).
3. Spec #1 (`docs/specs/spec_01.md`) — `JevClient`, schemas (`Usage`, `NoulAnswer`, `ChoiceAnswer`), excepciones.
4. Spec #2 (`docs/specs/spec_02.md`) — `InputScreeningResult`, `IntentRoutingResult`, y la constante pública `EXPECTED_INTENTS`.
5. `docs/typesafe_jev/README.md` §5 y §7 — semántica de umbrales y flujo screening→routing.

Este componente se construye SOBRE Spec #2. No llama a Jev; opera sobre los resultados crudos que Spec #2 ya produjo.

## 1. Objetivo y alcance

### Objetivo

Aplicar umbrales a los resultados crudos de Spec #2 y producir `GovernanceDecision` determinísticas y fail-closed, en DOS ETAPAS que reflejan el flujo real: primero screening, y routing solo si screening pasa. Incorporar confidence gating del intent y validación del dominio del intent.

### Incluye

- API de dos etapas: `decide_screening` y `decide_routing`.
- Extensión tipada de `Policy` (config.py) con la sección `governance`, validada y fail-fast, y mapper a `GovernanceThresholds`.
- Umbrales como estructura tipada, inyectados (sin defaults productivos hardcodeados en `decision.py`).
- Enum `GovernanceAction` (`block | review | allow`) y `GovernanceStage` (`input_screening | intent_routing`).
- Dataclass `GovernanceDecision` con metadata por etapa, probabilidades y umbrales, tolerante a metadata ausente.
- Comportamiento fail-closed con totalidad acotada (sección 7), incluida la validación del dominio del intent.
- Confidence gating del intent (`min_intent_confidence` → `REVIEW`).
- Reasons determinísticas con códigos estables y precedencia definida.
- Tests unitarios sin red ni Jev. Los tests de decisión no hacen I/O; los tests de configuración usan únicamente archivos temporales locales.

### NO incluye

- Llamar a Jev ni invocar evaluaciones (Spec #2 ya lo hace).
- Tool gating ni output screening (Spec #4).
- Integración con Strands ni hooks (Spec #6).
- Medición de latencia ni emisión de eventos de auditoría (pertenece al adaptador de gobierno, Spec #6; ver sección 9).

## 2. Pre-work

- Spec #1 y Spec #2 implementadas y tests pasando: `uv run pytest tests/unit/governance/jev -q`.
- Se agrega la sección `governance` a `configs/policy.yaml` y se extiende `Policy` en `config.py` EN EL MISMO CAMBIO, para que `load_policy` no falle (sección 4).

## 3. Flujo de dos etapas

El flujo real es secuencial. Screening se decide primero; routing solo se ejecuta si screening pasa.

```
mensaje → Spec#2.screen_input → InputScreeningResult
        → decide_screening(screening) → GovernanceDecision(stage=INPUT_SCREENING)
             ├─ BLOCK  → Spec#6 rechaza. NO se ejecuta routing.
             ├─ REVIEW → Spec#6 escala. NO se ejecuta routing.
             └─ ALLOW  → screening pasó. Spec#6 ejecuta routing:
                  Spec#2.route_banking_intent → IntentRoutingResult
                  → decide_routing(routing) → GovernanceDecision(stage=INTENT_ROUTING)
                       ├─ BLOCK  → input de routing inválido o intent fuera de dominio (fail-closed). Spec#6 aplica una respuesta bloqueada; cualquier escalamiento posterior no cambia la decisión BLOCK.
                       ├─ REVIEW → baja confianza. Spec#6 escala.
                       └─ ALLOW  → Spec#6 despacha al handler del intent.
```

Reglas:

- `decide_screening` NUNCA requiere routing y NUNCA lanza `ValueError` por routing ausente.
- `decide_routing` solo se llama cuando `decide_screening` devolvió `ALLOW`.
- No existe una función combinada `decide(screening, routing)`. Son dos funciones separadas.

## 4. Umbrales (inyectados, desde configuración tipada y fail-fast)

Los umbrales NO se hardcodean en `decision.py`. Los valores viven exclusivamente en `configs/policy.yaml`; `Policy` los carga tipados y validados; el llamador los convierte a `GovernanceThresholds` y los inyecta. Las funciones `decide_screening` y `decide_routing` reciben `thresholds` como parámetro obligatorio.

### 4.1 Agregado a `configs/policy.yaml`

```yaml
governance:
  prompt_injection:
    block: 0.80
    review: 0.35
  social_engineering:
    block: 0.80
    review: 0.35
  min_intent_confidence: 0.50
```

Estos valores son los defaults de configuración. Cambiarlos no requiere tocar `decision.py`.

### 4.2 Extensión de `Policy` en `config.py` (fail-fast)

```python
import math
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

class ScreeningThresholdPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block: float
    review: float

    @field_validator("block", "review")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("debe ser un número finito")
        return v

    @model_validator(mode="after")
    def _order(self):
        if not (0.0 <= self.review < self.block <= 1.0):
            raise ValueError("se requiere 0 <= review < block <= 1")
        return self

class GovernancePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_injection: ScreeningThresholdPolicy
    social_engineering: ScreeningThresholdPolicy
    min_intent_confidence: float

    @field_validator("min_intent_confidence")
    @classmethod
    def _min_conf(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("min_intent_confidence debe ser finito")
        if not (0.0 <= v <= 1.0):
            raise ValueError("se requiere 0 <= min_intent_confidence <= 1")
        return v

class Policy(BaseModel):
    auto_block: dict = {}
    escalation: dict = {}
    governance: GovernancePolicy   # campo requerido

def load_policy(path: Path = POLICY_PATH) -> Policy:
    if not path.exists():
        raise FileNotFoundError(
            f"policy.yaml no encontrado en {path}; la sección governance es obligatoria"
        )
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Policy(**data)   # Pydantic valida governance requerido, estructura y rangos
```

Comportamiento deseado (fail-fast):

- Si `policy.yaml` no existe → `load_policy` lanza `FileNotFoundError`. NO hay fallback a `Policy()` vacío (eso fallaría porque `governance` es requerido).
- Si el YAML no tiene `governance`, o la sección está incompleta, o tiene valores fuera de rango → Pydantic lanza `ValidationError`.
- El `policy = load_policy()` a nivel de módulo en `config.py` hereda este fail-fast: una configuración inválida impide el arranque. Esto es intencional.
- Nota: `load_policy` construye `Policy(**data)`; Pydantic ignora campos no declarados por su configuración predeterminada. No hay un filtrado explícito por `model_fields`.

La validación de rangos existe en `config.py` (fail-fast al cargar) y también en `decision.py` (sección 4.3) para umbrales construidos directamente en tests. Es defensa en profundidad intencional.

### 4.3 Estructuras runtime y mapper (en `decision.py`)

```python
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_banking_customer_service.config import GovernancePolicy

@dataclass(frozen=True)
class ScreeningThresholds:
    block: float
    review: float

    def __post_init__(self):
        if not (math.isfinite(self.block) and math.isfinite(self.review)):
            raise ValueError(
                "ScreeningThresholds: block y review deben ser finitos"
            )
        if not (0.0 <= self.review < self.block <= 1.0):
            raise ValueError(
                "ScreeningThresholds: se requiere 0 <= review < block <= 1"
            )

@dataclass(frozen=True)
class GovernanceThresholds:
    prompt_injection: ScreeningThresholds
    social_engineering: ScreeningThresholds
    min_intent_confidence: float

    def __post_init__(self):
        if not math.isfinite(self.min_intent_confidence):
            raise ValueError(
                "GovernanceThresholds: min_intent_confidence debe ser finito"
            )
        if not (0.0 <= self.min_intent_confidence <= 1.0):
            raise ValueError(
                "GovernanceThresholds: se requiere 0 <= min_intent_confidence <= 1"
            )

    @classmethod
    def from_policy(cls, governance_policy: "GovernancePolicy") -> "GovernanceThresholds":
        if governance_policy is None:
            raise ValueError("from_policy: governance_policy no puede ser None")
        return cls(
            prompt_injection=ScreeningThresholds(
                block=governance_policy.prompt_injection.block,
                review=governance_policy.prompt_injection.review,
            ),
            social_engineering=ScreeningThresholds(
                block=governance_policy.social_engineering.block,
                review=governance_policy.social_engineering.review,
            ),
            min_intent_confidence=governance_policy.min_intent_confidence,
        )
```

El mapper `from_policy` convierte la configuración tipada en la estructura runtime. El llamador (Spec #6) hace `GovernanceThresholds.from_policy(policy.governance)`. `from_policy` lanza `ValueError` explícito si recibe `None` (guard intencional, no `AttributeError`). `decision.py` no importa `config` en runtime (solo bajo `TYPE_CHECKING`), de modo que la lógica pura no depende de la carga de configuración.

### 4.4 Ubicación de la validación

- Cada `ScreeningThresholds` valida sus propios campos en su `__post_init__`.
- `GovernanceThresholds` valida `min_intent_confidence` y compone los dos `ScreeningThresholds`.
- Unos umbrales inválidos son un error de configuración: lanzan `ValueError` en construcción (fail-fast). Esto es distinto del fail-closed en runtime (sección 7).
- `decision.py` NO contiene valores numéricos de umbral.

## 5. Tipos de decisión

### 5.1 Enums

```python
from enum import Enum

class GovernanceAction(str, Enum):
    BLOCK = "block"    # rechazar la solicitud (alto riesgo o input inválido)
    REVIEW = "review"  # escalar a revisión humana
    ALLOW = "allow"    # screening pasó / despachar al handler del intent

class GovernanceStage(str, Enum):
    INPUT_SCREENING = "input_screening"
    INTENT_ROUTING = "intent_routing"
```

El vocabulario de `GovernanceAction` es `block | review | allow`, idéntico a `docs/observability.md`. Los valores de `GovernanceStage` coinciden con `input_screening | intent_routing` de `docs/observability.md`, de modo que el adaptador no necesita traducción.

### 5.2 GovernanceDecision

```python
@dataclass(frozen=True)
class GovernanceDecision:
    action: GovernanceAction
    stage: GovernanceStage
    reason_codes: tuple[str, ...]               # códigos estables (sección 8)
    reasons: tuple[str, ...]                    # texto humano determinístico (sección 8)
    model: str | None                           # modelo Jev de ESTA etapa
    usage: Usage | None                         # tokens de ESTA etapa (Spec#1 schemas)
    governance_thresholds: GovernanceThresholds # umbrales en vigor (sección 4)
    # Señales de screening (solo stage=INPUT_SCREENING; None en INTENT_ROUTING)
    prompt_injection_signal: float | None = None
    social_engineering_signal: float | None = None
    # Routing (solo stage=INTENT_ROUTING; None en INPUT_SCREENING)
    intent: str | None = None
    intent_confidence: float | None = None
    intent_probabilities: dict[str, float] | None = None
```

Notas de tipos y preservación:

- `model` y `usage` son opcionales para poder representar una decisión `BLOCK` por metadata inválida sin violar el contrato ni inventar datos. Preservación: `model` conserva el string recibido (aunque sea vacío) si es `str`, y `None` si no es `str`; `usage` conserva la instancia `Usage` si lo es, y `None` en caso contrario. Esto es lo más honesto para auditoría.
- El campo se llama `governance_thresholds` (no `applied_thresholds`) porque almacena el conjunto completo de umbrales en vigor, no solo el subconjunto aplicado por la etapa.
- `intent_probabilities` preserva las probabilidades crudas de `routing.intent.probabilities` (requisito de `docs/observability.md`). En una decisión `INTENT_ROUTING` estructuralmente válida, las probabilidades SIEMPRE están presentes (Spec #2 las garantiza); el tipo es opcional solo porque el campo es compartido con la etapa `INPUT_SCREENING`, donde es `None`.
- Se elimina la duplicación `intent` / `intent_choice`: existe un único campo `intent`.

Invariantes (verificadas por tests):

- `stage == INPUT_SCREENING` → `intent`, `intent_confidence`, `intent_probabilities` son `None`; las señales de screening están pobladas.
- `stage == INTENT_ROUTING` → `prompt_injection_signal` y `social_engineering_signal` son `None`; `intent` está poblado si se detectó un intent válido en el dominio (aun con `REVIEW` por baja confianza).
- Cada decisión preserva `model` y `usage` de SU propia llamada Jev. Como screening y routing producen decisiones separadas, la metadata de ambas llamadas se conserva (una por decisión). No hay pérdida de tokens ni de modelo.

## 6. Lógica de decisión (API pública)

Las dos funciones tienen TOTALIDAD ACOTADA (sección 7): para las anomalías de valor enumeradas, dentro de instancias estructuralmente válidas de Spec #2, devuelven siempre una `GovernanceDecision` (fail-closed); no lanzan excepciones por esos datos.

### 6.1 Firmas

```python
def decide_screening(
    screening: InputScreeningResult,
    thresholds: GovernanceThresholds,
) -> GovernanceDecision:
    """Primera etapa: evalúa señales de riesgo. Devuelve BLOCK/REVIEW/ALLOW(stage=INPUT_SCREENING)."""

def decide_routing(
    routing: IntentRoutingResult,
    thresholds: GovernanceThresholds,
) -> GovernanceDecision:
    """Segunda etapa: evalúa intent, su dominio y confianza. Devuelve BLOCK/REVIEW/ALLOW(stage=INTENT_ROUTING)."""
```

`InputScreeningResult` e `IntentRoutingResult` son los tipos definidos por Spec #2. `thresholds` es obligatorio (sin default) para no incrustar política en `decision.py`. `decide_routing` importa `EXPECTED_INTENTS` desde Spec #2 (fuente única, sección 6.4).

### 6.2 Contrato de lectura de Spec #2

`decide_screening` lee: `screening.prompt_injection.noul`, `screening.social_engineering.noul`, `screening.model`, `screening.usage`.
`decide_routing` lee: `routing.intent.choice`, `routing.intent.confidence`, `routing.intent.probabilities`, `routing.model`, `routing.usage`.
Si la estructura real de Spec #2 difiere, adaptar la lectura, no el contrato de salida.

### 6.3 Algoritmo `decide_screening`

1. Validar señales y metadata con la precedencia de la sección 7. Si alguna es inválida → `BLOCK` (fail-closed).
2. Evaluar cada señal contra sus umbrales:
   - `pi_block = pi >= thresholds.prompt_injection.block`; `pi_review = pi >= thresholds.prompt_injection.review`.
   - `se_block = se >= thresholds.social_engineering.block`; `se_review = se >= thresholds.social_engineering.review`.
3. Precedencia `BLOCK > REVIEW > ALLOW`:
   - Si `pi_block or se_block` → `action=BLOCK`.
   - Si no, y `pi_review or se_review` → `action=REVIEW`.
   - Si no → `action=ALLOW` (screening pasó; falta routing).
4. Construir `reason_codes` y `reasons` (sección 8). Para `ALLOW`, `reason_codes=("SCREENING_PASS",)`.
5. `stage=INPUT_SCREENING`; poblar señales; `intent=None`.

### 6.4 Algoritmo `decide_routing`

`decide_routing` importa `EXPECTED_INTENTS` desde el módulo público de Spec #2 (fuente única). NO se mantiene una segunda lista manual en Spec #3.

1. Validar `intent.choice`, su dominio, `intent_confidence` y metadata con la precedencia de la sección 7. Si alguno es inválido → `BLOCK`.
   - `intent.choice` debe ser `str` no vacío tras `.strip()` → si no, `INVALID_INTENT`.
   - `intent.choice` debe pertenecer a `EXPECTED_INTENTS` → si no, `INVALID_INTENT_DOMAIN`.
2. Si `intent_confidence < thresholds.min_intent_confidence` → `action=REVIEW`.
3. Si no → `action=ALLOW`.
4. Construir `reason_codes` y `reasons` (sección 8).
5. `stage=INTENT_ROUTING`; poblar `intent`, `intent_confidence`, `intent_probabilities`; señales de screening en `None`.

Comparación de confianza: `confidence < umbral` usa `<` estricto; estar exactamente en el umbral → `ALLOW`. En screening, `>=` dispara la acción conservadora. Esta asimetría es deliberada: en screening el umbral dispara la acción conservadora (`>=`); en routing el umbral es el mínimo para confiar y alcanzarlo es suficiente. Documentar esta asimetría.

## 7. Comportamiento fail-closed (totalidad acotada)

Alcance exacto de la totalidad: las funciones garantizan fail-closed para las anomalías de VALOR enumeradas abajo, asumiendo instancias estructuralmente válidas de `InputScreeningResult` / `IntentRoutingResult` (Spec #2 garantiza la estructura mediante sus schemas). Estructuras rotas (tipo incorrecto, atributos ausentes) están FUERA del contrato y pueden lanzar excepciones; no se intenta tolerarlas. Esto evita operaciones como `math.isfinite(value)` o `model.strip()` sobre tipos inesperados.

`decide_screening` y `decide_routing` son responsables del fail-closed sobre los VALORES que reciben. Para las anomalías enumeradas devuelven `BLOCK`; no lanzan excepciones.

### 7.1 Validación numérica y de strings

- Usar `math.isfinite()` para señales y `intent_confidence`. `NaN`, `inf` y `-inf` son inválidos. La condición es `math.isfinite(value) and 0.0 <= value <= 1.0`. Una comprobación `value < 0 or value > 1` NO detecta `NaN`.
- Un string `intent.choice` es válido solo si `isinstance(choice, str) and choice.strip() != ""` y `choice in EXPECTED_INTENTS`.
- Metadata válida: `model` es `str` no vacío tras `.strip()` y `usage` es una instancia `Usage` (no `None`).

### 7.2 Precedencia entre múltiples datos inválidos

Screening:

```
INVALID_SIGNAL > INVALID_METADATA > evaluación de umbrales
```

- Primero se validan ambas señales. Si alguna es inválida → `BLOCK` con un `INVALID_SIGNAL` por cada señal inválida (orden fijo) y SE DETIENE (no evalúa metadata ni umbrales).
- Si las señales son válidas pero la metadata es inválida → `BLOCK` con un único `INVALID_METADATA`.
- Si todo es válido → evaluación de umbrales.

Routing:

```
INVALID_INTENT > INVALID_INTENT_DOMAIN > INVALID_CONFIDENCE > INVALID_METADATA > REVIEW_LOW_INTENT_CONFIDENCE > ROUTING_ALLOW
```

- Se valida en ese orden y se devuelve el primer caso que aplique (un único reason).

Precedencia dentro de `INVALID_METADATA` (aplica a AMBAS etapas, screening y routing): `model` tiene precedencia sobre `usage`. Si `model` es inválido, el reason describe `model`; si `model` es válido pero `usage` es `None`, el reason describe `usage`. Si ambos fallan, se reporta solo `model` (el de mayor precedencia).

### 7.3 Casos y acción resultante

| Caso                                                                                   | Capa responsable                     | Acción   |
| -------------------------------------------------------------------------------------- | ------------------------------------ | -------- |
| Señal de screening no finita o fuera de [0,1]                                          | `decide_screening`                   | `BLOCK`  |
| Metadata de screening inválida (model vacío/no-str o usage ausente)                    | `decide_screening`                   | `BLOCK`  |
| `intent.choice` no es `str` o es vacío/whitespace-only                                 | `decide_routing`                     | `BLOCK`  |
| `intent.choice` no pertenece a `EXPECTED_INTENTS`                                      | `decide_routing`                     | `BLOCK`  |
| `intent_confidence` no finita o fuera de [0,1]                                         | `decide_routing`                     | `BLOCK`  |
| Metadata de routing inválida                                                           | `decide_routing`                     | `BLOCK`  |
| `intent_confidence < min_intent_confidence`                                            | `decide_routing`                     | `REVIEW` |
| `JevUnavailableError` / `JevValidationError` / otras `JevError` durante la llamada Jev | Spec #6 (atrapa el error de Spec #2) | `BLOCK`  |

Los errores de transporte de Jev ocurren ANTES de `decide` (durante la llamada Jev en Spec #2). `decide` no puede atraparlos porque recibe resultados ya construidos. La conversión de esos errores a `BLOCK` pertenece a Spec #6. Esta spec documenta la política (cualquier `JevError` en gobierno → `BLOCK`); Spec #6 la aplica. No se usa la expresión "típicamente BLOCK": es `BLOCK` siempre.

## 8. Reasons determinísticas

Cada decisión tiene `reason_codes` (códigos estables) y `reasons` (texto humano), en tuplas paralelas del mismo largo. Formato de cada reason: `"{CODIGO}: {detalle}"`. Los códigos son estables para uso programático; el detalle es determinístico.

Formato numérico: usar la representación exacta y determinística `repr(float(value))`, que conserva suficiente precisión para que el texto nunca contradiga la comparación ejecutada. No redondear a una cantidad fija de decimales.

### Códigos y formatos

| Código                         | Detalle (formato)                                                              |
| ------------------------------ | ------------------------------------------------------------------------------ |
| `BLOCK_PROMPT_INJECTION`       | `prompt_injection={repr(v)} >= block={repr(t)}`                                    |
| `BLOCK_SOCIAL_ENGINEERING`     | `social_engineering={repr(v)} >= block={repr(t)}`                                  |
| `REVIEW_PROMPT_INJECTION`      | `prompt_injection={repr(v)} >= review={repr(t)}`                                   |
| `REVIEW_SOCIAL_ENGINEERING`    | `social_engineering={repr(v)} >= review={repr(t)}`                                 |
| `SCREENING_PASS`               | `all signals below review thresholds`                                              |
| `REVIEW_LOW_INTENT_CONFIDENCE` | `intent_confidence={repr(v)} < min_intent_confidence={repr(t)}`                    |
| `ROUTING_ALLOW`                | `intent='{choice}' intent_confidence={repr(v)} >= min_intent_confidence={repr(t)}` |
| `INVALID_SIGNAL`               | `{field} is not finite or is outside [0, 1]`                                       |
| `INVALID_METADATA`             | `model is not a non-blank string` o `usage is missing`                             |
| `INVALID_INTENT`               | `intent choice is not a non-blank string`                                          |
| `INVALID_INTENT_DOMAIN`        | `intent choice '{choice}' is not in the supported intent domain`                   |
| `INVALID_CONFIDENCE`           | `intent_confidence is not finite or is outside [0, 1]`                             |

### Reglas de inclusión y orden

- Orden fijo de señales: `prompt_injection` antes que `social_engineering`. No se ordena por severidad.
- `decide_screening`:
  - Si hay señales inválidas: un `INVALID_SIGNAL` por cada señal inválida (orden fijo); SE DETIENE ahí (precedencia sección 7.2).
  - `BLOCK` por umbrales: solo los códigos `BLOCK_*` de las señales `>= block` (orden fijo). No incluir señales que solo lleguen a `review`.
  - `REVIEW`: solo los códigos `REVIEW_*` de las señales `>= review` (y `< block`).
  - `ALLOW`: un único `SCREENING_PASS`.
  - Metadata inválida (señales válidas): un único `INVALID_METADATA`.
- `decide_routing`: un único reason según la precedencia de la sección 7.2.

## 9. Propiedad de auditoría y latencia

`decide_screening` y `decide_routing` son lógica PURA: no miden latencia, no emiten eventos de auditoría, no hacen I/O.

La medición de latencia de las llamadas Jev y la emisión de eventos de auditoría pertenecen al ADAPTADOR DE GOBIERNO (componente de la capa `governance/` que se introduce en Spec #6). El adaptador:

1. Invoca a Spec #2 (`screen_input`, `route_banking_intent`) midiendo la latencia de cada llamada.
2. Invoca `decide_screening` / `decide_routing`.
3. Construye y emite los eventos de auditoría (uno por etapa, con `stage` `input_screening` / `intent_routing`), usando `model`, `usage`, señales, probabilidades y `governance_thresholds` que cada `GovernanceDecision` ya preserva.

Esto resuelve la contradicción entre Spec #1 §8, Spec #2 §1/§5.2/§8, Spec #3 y `docs/observability.md`. Actualizaciones de documentos requeridas (ver sección 18).

## 10. Semántica de ALLOW y de los intents

`ALLOW` autoriza ÚNICAMENTE avanzar a la siguiente etapa o despachar al handler del intent. NO autoriza una tool ni una acción bancaria. La autorización de tools y acciones es responsabilidad de Spec #4 (tool gating) y de las reglas duras.

- `decide_screening` → `ALLOW`: significa "screening superado; proceder a routing". No es una aprobación final.
- `decide_routing` → `ALLOW`: significa "despachar al handler del intent detectado". No autoriza ejecutar ninguna acción. Solo se alcanza con un intent dentro de `EXPECTED_INTENTS`.

Tratamiento de intents (documentación para Spec #6, no lógica de esta spec):

- `request_human` → se dirige al flujo de escalamiento.
- `block_card` → NO autoriza bloquear; solo despacha al handler, que aplicará tool gating.
- `dispute_charge` → NO autoriza una acción; despacha al handler.
- `general_inquiry` / `check_status` → despachan al handler correspondiente.
- `other` → probablemente requiere clarificación o abstención (lo decide el handler/Spec #6).
  Esta spec no implementa ese enrutado; solo deja claro que `ALLOW` no implica acción bancaria.

## 11. Manejo de errores

- `ValueError` en construcción de `ScreeningThresholds`/`GovernanceThresholds` si los umbrales son inválidos (error de configuración, fail-fast).
- `ValueError` explícito en `from_policy` si `governance_policy` es `None`.
- `FileNotFoundError` en `load_policy` si `policy.yaml` no existe; `ValidationError` de Pydantic si `governance` falta, está incompleta o fuera de rango.
- `decide_screening`/`decide_routing` NO lanzan excepciones por las anomalías de valor enumeradas (sección 7); devuelven `BLOCK` (fail-closed). Estructuras rotas están fuera del contrato.
- No se capturan `JevError` aquí (Spec #3 no llama a Jev). La conversión de `JevError`→`BLOCK` la hace Spec #6 (sección 7.3).

## 12. Seguridad

- Componente de lógica pura: sin I/O, sin llamadas a Jev, sin logs.
- NO emite eventos de auditoría (preserva la metadata para que el adaptador la emita).
- No sanitiza mensajes (eso lo hace Spec #2 al construir `state`).
- Valida el dominio del intent contra `EXPECTED_INTENTS` para evitar que un intent anómalo (p. ej. inyectado o mutado) produzca `ALLOW`.

## 13. API pública (ruta exacta)

El import público es vía el módulo, sin modificar `governance/jev/__init__.py`:

```python
from ai_banking_customer_service.governance.jev.decision import (
    decide_screening,
    decide_routing,
    GovernanceAction,
    GovernanceStage,
    GovernanceDecision,
    GovernanceThresholds,
    ScreeningThresholds,
)
```

NO se modifica `governance/jev/__init__.py`. El test de import usa esta ruta exacta. `decision.py` importa `EXPECTED_INTENTS` desde Spec #2 (fuente única).

## 14. TDD — FASE RED (backlog de tests)

Archivo principal: `tests/unit/governance/jev/test_governance.py`. Tests de config en el archivo de tests de configuración (p. ej. `tests/unit/test_config.py`). Los tests observan la API pública. No se testean helpers privados como RED principal.

Mecanismo para datos inválidos: los schemas de Spec #2 (`NoulAnswer`, `ChoiceAnswer`) rechazan valores inválidos en construcción. Para probar el fail-closed de Spec #3 sobre valores anómalos, los tests construyen las instancias de Spec #2 con `model_construct` (bypass de validación de Pydantic) o mutación posterior, y las pasan a `decide_*`. No se testean helpers privados ni se pelea contra la validación de Pydantic.

Constante de intents: los tests y `decide_routing` IMPORTAN `EXPECTED_INTENTS` desde Spec #2 (fuente única). NO se redefine una lista manual en Spec #3, para evitar divergencia.

### Import público

- El import de la sección 13 funciona (test de pytest, NO `python -c` standalone).

### Construcción de umbrales (fail-fast)

- `ScreeningThresholds` lanza `ValueError` si `review >= block`.
- `ScreeningThresholds` lanza `ValueError` si `block > 1`.
- `ScreeningThresholds` lanza `ValueError` si `review < 0`.
- `ScreeningThresholds` lanza `ValueError` si `block` o `review` es `NaN`/`inf`.
- `GovernanceThresholds` lanza `ValueError` si `min_intent_confidence` fuera de [0,1] o no finito.

### Configuración tipada y fail-fast (config.py)

- `load_policy` lanza `FileNotFoundError` si `policy.yaml` no existe.
- `load_policy` lanza `ValidationError` si el YAML no tiene sección `governance`.
- `load_policy` lanza `ValidationError` si `governance` está incompleta (falta un campo).
- `load_policy` lanza `ValidationError` si hay valores fuera de rango (`review >= block`, `min_intent_confidence > 1`, etc.).
- `load_policy` lanza `ValidationError` ante campos desconocidos dentro de `governance` o de sus bloques de thresholds (`extra="forbid"`).
- `load_policy` carga correctamente una `governance` válida.
- `GovernanceThresholds.from_policy(policy.governance)` produce los umbrales correctos.
- `GovernanceThresholds.from_policy(None)` lanza `ValueError` (guard explícito).

### decide_screening — BLOCK

- Devuelve `BLOCK` cuando `prompt_injection.noul >= block`.
- Devuelve `BLOCK` cuando `prompt_injection.noul == block` (boundary, `>=`).
- Devuelve `BLOCK` cuando `social_engineering.noul >= block`.
- Devuelve `BLOCK` cuando `social_engineering.noul == block` (boundary).
- Si ambas señales `>= block`, `reason_codes` incluye `BLOCK_PROMPT_INJECTION` y `BLOCK_SOCIAL_ENGINEERING` en ese orden.

### decide_screening — REVIEW

- Devuelve `REVIEW` cuando `prompt_injection.noul >= review` y `< block`.
- Devuelve `REVIEW` cuando `prompt_injection.noul == review` (boundary).
- Devuelve `REVIEW` cuando `social_engineering.noul == review` (boundary).
- Si ambas señales `>= review` y `< block`, incluye ambos `REVIEW_*` en orden fijo.

### decide_screening — precedencia

- Si `prompt_injection` dispara `BLOCK` y `social_engineering` dispara `REVIEW`, la acción es `BLOCK` y `reason_codes` solo contiene el `BLOCK_*`.
- Si `prompt_injection` dispara `REVIEW` y `social_engineering` dispara `BLOCK`, la acción es `BLOCK`.

### decide_screening — ALLOW

- Devuelve `ALLOW` con `reason_codes=("SCREENING_PASS",)` cuando ambas señales `< review`.
- `ALLOW` de screening tiene `intent=None` y `stage=INPUT_SCREENING`.

### decide_screening — fail-closed por input inválido

- Devuelve `BLOCK` (no lanza) si `prompt_injection.noul` es `NaN`.
- Devuelve `BLOCK` si `prompt_injection.noul` es `inf` o `-inf`.
- Devuelve `BLOCK` si `prompt_injection.noul > 1` o `< 0`.
- Devuelve `BLOCK` si `social_engineering.noul` es `NaN`/`inf`/fuera de rango.
- Si ambas señales son inválidas, incluye dos `INVALID_SIGNAL` en orden fijo y NO evalúa metadata.
- Devuelve `BLOCK` con `INVALID_METADATA` si `model` es vacío/whitespace (señales válidas).
- Devuelve `BLOCK` con `INVALID_METADATA` y preserva `model=None` si el modelo recibido no es `str` (por ejemplo, `123`).
- Devuelve `BLOCK` con `INVALID_METADATA` si `usage` es `None` (señales y model válidos).
- Devuelve `BLOCK` con `INVALID_METADATA` y preserva `usage=None` si el valor recibido no es una instancia `Usage` (por ejemplo, `object()`).
- Si `model` es inválido Y `usage` es `None`, el reason describe `model` (precedencia).
- Precedencia: señal inválida gana a metadata inválida.

### decide_routing — ALLOW

- Devuelve `ALLOW` con el intent cuando `confidence >= min_intent_confidence` y el intent está en `EXPECTED_INTENTS`.
- Preserva `intent`, `intent_confidence` e `intent_probabilities` sin transformación.
- `ALLOW` de routing tiene `stage=INTENT_ROUTING` y señales de screening en `None`.

### decide_routing — REVIEW por baja confianza

- Devuelve `REVIEW` cuando `confidence < min_intent_confidence`.
- Devuelve `REVIEW` con el intent igualmente preservado.
- `reason_codes` incluye `REVIEW_LOW_INTENT_CONFIDENCE`.

### decide_routing — fail-closed por input inválido (precedencia)

- Devuelve `BLOCK` si `intent.choice` es string vacío.
- Devuelve `BLOCK` si `intent.choice` es whitespace-only (`"   "`).
- Devuelve `BLOCK` si `intent.choice` no es `str`.
- Devuelve `BLOCK` con `INVALID_INTENT_DOMAIN` si `intent.choice` no está en `EXPECTED_INTENTS` (p. ej. `"execute_wire_transfer"` con confidence alta).
- Devuelve `BLOCK` si `intent_confidence` es `NaN`/`inf`/fuera de [0,1].
- Devuelve `BLOCK` si metadata de routing es inválida.
- Devuelve `BLOCK` con `INVALID_METADATA` y preserva `model=None` si el modelo recibido no es `str`.
- Devuelve `BLOCK` con `INVALID_METADATA` y preserva `usage=None` si el valor recibido no es una instancia `Usage`.
- Precedencia: `INVALID_INTENT` > `INVALID_INTENT_DOMAIN` > `INVALID_CONFIDENCE` > `INVALID_METADATA`. (Si `intent.choice` es vacío, devuelve `INVALID_INTENT` aunque además esté fuera de dominio.)

### Metadata preservada por etapa

- La decisión de screening preserva `model` y `usage` del screening.
- La decisión de routing preserva `model` y `usage` del routing (distintos de los de screening).
- `governance_thresholds` refleja los umbrales inyectados en ambos casos.
- Cuando la metadata es inválida, `model`/`usage` preservan lo recibido según su tipo (sección 5.2).

### Reasons — orden y formato

- El orden de `reason_codes` es `prompt_injection` antes que `social_engineering`.
- El detalle numérico usa `repr(float(value))` sin redondeo fijo.
- Un caso cercano al umbral (por ejemplo, confidence `0.499` frente a `0.5`) conserva una reason matemáticamente correcta: `0.499 < 0.5`.
- `len(reason_codes) == len(reasons)` siempre.

### Todos los intents

- Para cada intent en `EXPECTED_INTENTS` (importado de Spec #2), `decide_routing` con confianza suficiente devuelve `ALLOW` con ese intent. (Esta spec no diferencia el tratamiento posterior; eso es de Spec #6.)

### Umbrales custom

- `decide_screening`/`decide_routing` aceptan `thresholds` custom y los aplican.
- Umbrales custom producen decisiones distintas a otros umbrales cuando corresponde.

## 15. FASES GREEN → TRIANGULATE → REFACTOR

- GREEN: implementación mínima para que cada test pase.
- TRIANGULATE: los casos parametrizados (señales × acciones, boundary values, `EXPECTED_INTENTS`) cuentan como triangulación. No agregar duplicados arbitrarios.
- REFACTOR: limpiar duplicación, extraer helpers. Sin funcionalidad extra.

## 16. Archivos a crear / modificar

```
src/ai_banking_customer_service/governance/jev/decision.py      (crear)
src/ai_banking_customer_service/config.py                       (modificar: GovernancePolicy + Policy.governance + load_policy fail-fast)
configs/policy.yaml                                             (modificar: sección governance)
tests/unit/governance/jev/test_governance.py                    (crear)
tests/unit/test_config.py                                       (crear/extender: tests de governance y load_policy)
docs/specs/spec_01.md                                           (modificar §8: ownership de auditoría → adaptador de gobierno)
docs/specs/spec_02.md                                           (modificar §1/§5.2/§8: ownership de latencia → adaptador de gobierno)
docs/observability.md                                           (modificar: emisor de eventos governance, etapas, vocabulario)
```

No se modifican archivos de producción de Spec #1 ni Spec #2 (solo sus documentos), ni `governance/jev/__init__.py`. Se actualiza `docs/STATUS.md`.

## 17. Criterios de aceptación

- `uv run pytest tests/unit/governance/jev/test_governance.py -q` pasa en verde.
- `uv run pytest tests/unit/governance/jev -q` (suite completa) pasa en verde — detecta regresiones contra Spec #1 y Spec #2.
- `uv run pytest tests/unit/test_config.py -q` pasa en verde (configuración governance tipada y fail-fast).
- Ningún test llama a la red ni a Jev.
- No se implementan tool gating, output screening, hooks, medición de latencia ni emisión de auditoría.
- No se modifican archivos de producción de Spec #1 ni Spec #2.
- La lógica de decisión es pura, de totalidad acotada, y determinística.
- Los boundary values (`signal == umbral`, `confidence == umbral`) están cubiertos.
- Los casos no finitos (`NaN`/`inf`) están cubiertos, construidos con `model_construct`/mutación.
- El dominio del intent está validado contra `EXPECTED_INTENTS` (importado de Spec #2).
- `configs/policy.yaml` contiene la sección `governance`, `Policy` la carga tipada y fail-fast, rechaza campos desconocidos dentro de esa sección, y `decision.py` no contiene valores de umbral.
- Import público verificado por un test de pytest (NO `python -c` standalone), usando la ruta de la sección 13.
- Los documentos `spec_01.md`, `spec_02.md` y `observability.md` actualizados según sección 18.
- `docs/STATUS.md` actualizado.

## 18. Actualización de STATUS.md y de documentos (post-implementación)

Marcar como completado:

- Lógica de decisión de gobierno (dos etapas, fail-closed, confidence gating, dominio de intent, configuración tipada fail-fast).

Agregar al registro:

```
- [fecha]: Spec #3 v4 implementada con TDD. API de dos etapas (decide_screening /
  decide_routing), totalidad acotada fail-closed, validación de dominio de intent
  contra EXPECTED_INTENTS, umbrales tipados en Policy + configs/policy.yaml con
  load_policy fail-fast y mapper from_policy, confidence gating, metadata y
  probabilidades preservadas por etapa, reasons con códigos estables y precedencia.
  Vocabulario block|review|allow; stages input_screening|intent_routing.
```

Actualizaciones de documentos requeridas (resuelven la contradicción de auditoría/latencia, sección 9):

- Spec #1 §8: la auditoría de modelo/señales/latencia pertenece al adaptador de gobierno (Spec #6), no a "Spec #3+".
- Spec #2 §1/§5.2/§8: la latencia pertenece al adaptador de gobierno, no a Spec #3; la metadata se preserva para que el adaptador la emita.
- `docs/observability.md`: los eventos `governance` los emite el adaptador de gobierno (en `governance/`); hay un evento por etapa (`input_screening` y `intent_routing`); vocabulario `block|review|allow`.
