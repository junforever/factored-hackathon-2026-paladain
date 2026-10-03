# SPEC #7 — Orquestador y flujo conversacional (v5)

Método de implementación futura: TDD estricto, en microciclos RED → GREEN → TRIANGULATE → REFACTOR.

> Esta versión define un único flujo ejecutable para Strands 1.57.1. La revisión
> actual es solo documental; su verificación estructural se registra en
> `odd/tasks/spec-07-v5-readiness.md` y no sustituye el TDD de la implementación.

## 0. Decisiones normativas

| Tema | Contrato v5 |
| --- | --- |
| Agente | Una instancia efímera por turno, con un modelo creado por turno en producción. |
| Captura | Un `ResultCaptureHooks` nuevo por turno; Strands sí ofrece `AfterInvocationEvent`, pero Spec #7 no lo registra. |
| Terminación | Solo se entrega texto del modelo tras una terminación normal y output screening ALLOW. |
| Cancelación | `cancel_signal: threading.Event | None`; Strands cancela con `stop_reason == "cancelled"`. |
| Acciones | Una excepción o una ejecución sin resultado terminal verificable implica side effect incierto. |
| Auditoría | Un único `CompositeAuditSink` compartido por adapter y orquestador; el fallback no vuelve durable una escritura fallida. |
| Sesión | Un lock por sesión cubre snapshot, invocación, decisión y persistencia final. |
| Memoria | Solo se persisten mensajes sanitizados con el schema exacto de Strands. |
| Señales | El JSON debe ocupar toda la respuesta salvo whitespace; cualquier sufijo invalida la señal. |
| Idioma | Heurística determinística por tokens; un indicador inequívoco de portugués basta. |

## 1. Contexto y alcance

### 1.1 Lecturas obligatorias antes de implementar

1. `AGENTS.md`.
2. `docs/observability.md`.
3. `docs/specs/spec_04.md` para `VERIFIED_FACTS_ALLOWLIST`, `ACTION_REQUIRED_FIELDS` y `ACTION_VERIFICATIONS`.
4. `docs/specs/spec_05.md` para `REGISTERED_TOOLS`.
5. `docs/specs/spec_06.md` para `GovernanceAdapter`, `GovernanceHooks` e `invocation_state`.
6. La API instalada de Strands 1.57.1:
   - `Agent.__call__` acepta `cancel_signal: threading.Event | None` y devuelve `AgentResult`;
   - `AgentResult.message` y `AgentResult.stop_reason`;
   - `BeforeToolCallEvent` y `AfterToolCallEvent`;
   - `ToolResult` y el schema `Message`.

Si cambia la versión fijada en `uv.lock`, los tests de contrato deben revalidar estas firmas antes de adaptar la implementación.

`docs/observability.md` describe hoy el estado implementado por Spec #6. Esta Spec #7 introduce de forma intencional campos adicionales para eventos del orquestador. Su implementación futura debe actualizar código, tests y `docs/observability.md` en el mismo cambio atómico; hasta entonces, las extensiones de esta spec son contrato futuro y no una descripción falsa del estado actual.

### 1.2 Incluye

- `BankingOrchestrator` y sus resultados tipados.
- Agente, modelo y captura efímeros por turno.
- Normalización y clasificación conservadora de tools.
- Clarificación, abstención, bloqueo y escalamiento.
- Output screening con respuesta final segura en el resultado de clasificación.
- Sesiones en memoria con lock, TTL y FIFO.
- Eventos `input`, `tool_call`, `escalation` y `response`.
- `CompositeAuditSink` compartido y política explícita ante fallos de auditoría.
- Parser estricto, sanitización de memoria y detección ES/PT.
- Cambios acotados a hooks/adapter necesarios para auditoría y correlación.

### 1.3 No incluye

- Cambiar las tools o servicios bancarios.
- Autenticación, UI, evaluación offline o despliegue.
- Reintentos automáticos de tools.
- Persistencia durable de sesiones.
- Nuevas reglas de negocio en el prompt.

## 2. Módulos y API pública

### 2.1 Módulos del agente

```text
src/ai_banking_customer_service/agent/
├── orchestrator.py
├── result_capture.py
├── session_manager.py
├── signal_parser.py
├── language_detector.py
└── system_prompt.py
```

`agent/tools.py` y las tools de negocio no se modifican.

### 2.2 Observabilidad

`CompositeAuditSink` y `AuditPersistenceError` viven en
`src/ai_banking_customer_service/observability/sink.py`, junto a `AuditSink` y
`JsonlAuditSink`. No se definen ni reexportan desde `orchestrator.py`.

API pública exacta:

```python
from ai_banking_customer_service.agent.language_detector import detect_language
from ai_banking_customer_service.agent.orchestrator import (
    BankingOrchestrator,
    EscalationType,
    OrchestratorResult,
    OutputScreeningOutcome,
    OutputScreeningState,
    TurnAction,
    TurnClassification,
)
from ai_banking_customer_service.agent.result_capture import (
    NormalizedToolResult,
    ResultCaptureHooks,
)
from ai_banking_customer_service.agent.session_manager import (
    SessionManager,
    SessionTurn,
    TurnPersistence,
)
from ai_banking_customer_service.agent.signal_parser import parse_orchestration_signal
from ai_banking_customer_service.agent.system_prompt import SYSTEM_PROMPT
from ai_banking_customer_service.observability.sink import (
    AuditPersistenceError,
    AuditSink,
    CompositeAuditSink,
    JsonlAuditSink,
)
```

## 3. Construcción y propiedad de dependencias

### 3.1 Constructor

Firma de construcción:

```text
BankingOrchestrator(
    adapter: GovernanceAdapter,
    governance_hooks: GovernanceHooks,
    audit_sink: CompositeAuditSink,
    session_manager: SessionManager | None = None,
    model_factory: Callable[[], Any] | None = None,
    model_id: str | None = None,
    model: Any | None = None,
)
```

Firma de procesamiento:

```text
handle_turn(
    message: str,
    session_id: str,
    customer_id: str,
    cancel_signal: threading.Event | None = None,
) -> OrchestratorResult
```

Las secciones 4–14 definen todo el comportamiento de ambas firmas.

Reglas de construcción:

- `model_factory` y `model` son mutuamente excluyentes; suministrar ambos lanza `ValueError`.
- `session_manager=None` construye exactamente `SessionManager()`.
- Producción usa `model_factory` o el factory por defecto. El factory se invoca una vez por turno y debe devolver un modelo nuevo.
- `model` existe solo para tests unitarios secuenciales. Los tests concurrentes usan un factory que devuelve fakes independientes.
- `model_id` solo configura el factory por defecto. Precedencia: `model_id` explícito sobre `settings.openai_model`.
- El factory por defecto construye `OpenAIModel` con el ID resuelto y `client_args={"api_key": settings.openai_api_key.get_secret_value()}`.
- No se comparte un `OpenAIModel` de producción entre turnos; esta spec no asume que sea thread-safe.

### 3.2 Composición del sink

El composition root debe crear exactamente una instancia y suministrar esa misma identidad a ambos consumidores:

```python
audit_sink = CompositeAuditSink(primary_sink, fallback_sink)
adapter = GovernanceAdapter(
    client=jev_client,
    thresholds=thresholds,
    tool_gating_thresholds=tool_gating_thresholds,
    output_screening_thresholds=output_screening_thresholds,
    audit_sink=audit_sink,
    dispute_context_loader=dispute_context_loader,
)
orchestrator = BankingOrchestrator(
    adapter=adapter,
    governance_hooks=GovernanceHooks(adapter),
    audit_sink=audit_sink,
    session_manager=session_manager,
    model_factory=model_factory,
)
```

Crear dos sinks equivalentes pero distintos incumple el contrato. Un test de composición verifica identidad, no solo igualdad.

## 4. Tipos terminales

```python
class TurnAction(str, Enum):
    RESPOND = "respond"
    ESCALATE = "escalate"
    BLOCK = "block"
    ABSTAIN = "abstain"

class EscalationType(str, Enum):
    GOVERNANCE_REVIEW = "governance_review"
    FAILED_ACTION = "failed_action"
    OUTPUT_SCREENING_REVIEW = "output_screening_review"
    TOOL_ESCALATION = "tool_escalation"
    UNCERTAIN_SIDE_EFFECT = "uncertain_side_effect"
    EXTERNAL_CANCELLATION = "external_cancellation"
    INCOMPLETE_INVOCATION = "incomplete_invocation"

class OutputScreeningState(str, Enum):
    ALLOW = "allow"
    REVIEW = "review"
    FAILURE = "failure"

@dataclass(frozen=True)
class OutputScreeningOutcome:
    state: OutputScreeningState
    governance_result: GovernanceResult | None
    escalation_type: EscalationType | None
    safe_response: str
    event_id: str | None

@dataclass(frozen=True)
class TurnClassification:
    action: TurnAction
    response_text: str
    escalation_type: EscalationType | None
    escalation_id: str | None
    terminal_parent_event_id: str | None

@dataclass(frozen=True)
class OrchestratorResult:
    action: TurnAction
    response_text: str
    trace_id: str
    session_id: str
    intent: str | None
    escalation_type: EscalationType | None
    escalation_id: str | None
```

`OutputScreeningOutcome.safe_response` siempre es no vacío: en ALLOW contiene exactamente `proposed_response`; en REVIEW/FAILURE contiene exactamente `SAFE_TEMPLATES[language]["review_failure"]`. `TurnClassification.response_text` copia ese campo sin reconstruirlo. Las reglas completas para clarificación y respuesta normal están en la sección 11.

## 5. Historial, lock y sanitización de memoria

### 5.1 API exacta

```python
@dataclass(frozen=True)
class TurnPersistence:
    action: Literal["respond", "abstain", "block", "escalate"]
    user_text: str
    assistant_text: str | None

class SessionTurn:
    @property
    def history(self) -> list[Message]:
        return deepcopy(self._history_snapshot)

    def persist(self, request: TurnPersistence) -> None:
        self._persist_once(request)
```

Firmas de `SessionManager`:

```text
SessionManager(
    max_messages_per_session: int = 50,
    ttl_seconds: int = 1800,
    clock: Callable[[], float] = time.monotonic,
)

turn(session_id: str) -> ContextManager[SessionTurn]
clear_session(session_id: str) -> None
```

`max_messages_per_session` y `ttl_seconds` deben ser enteros positivos, excluyendo `bool`; `clock` debe ser callable. `session_id` debe ser string no vacío. Input inválido lanza `ValueError` antes de adquirir el lock de sesión.

### 5.2 Entrada, snapshot y liberación

`SessionManager.turn(session_id)`:

1. crea u obtiene el lock bajo un lock interno que protege el mapa de locks;
2. adquiere el lock de `session_id`;
3. calcula `now = clock()` y elimina la sesión si `now - last_activity >= ttl_seconds`;
4. crea un snapshot profundo del historial vigente;
5. entrega exactamente un `SessionTurn` con `history` igual a una copia profunda de ese snapshot;
6. mantiene el lock durante `persist` y hasta que sale el context manager; `persist` nunca lo libera por su cuenta;
7. libera el lock exactamente una vez en el `finally` del context manager, aunque Agent, gobierno, auditoría o persistencia fallen.

Dos sesiones distintas pueden avanzar en paralelo; dos turnos de la misma sesión quedan serializados desde el snapshot hasta la persistencia final. `clear_session` adquiere el mismo lock de sesión, elimina historial y timestamp, y no interrumpe un turno activo.

### 5.3 Solicitud de persistencia

`SessionTurn.persist` puede llamarse como máximo una vez. Una segunda llamada lanza `RuntimeError`. El contrato por acción es:

| `action` | `assistant_text` | Mensajes agregados |
| --- | --- | --- |
| `respond` | string no vacío | usuario + asistente final aprobado |
| `abstain` | string no vacío | usuario + template de abstención |
| `block` | debe ser `None` | solo usuario |
| `escalate` | debe ser `None` | solo usuario |

`user_text` y todo `assistant_text` requerido deben ser strings no vacíos después de `strip`. El método aplica `sanitize_message` tanto a `user_text` como a `assistant_text` antes de construir mensajes. Una salida del modelo rechazada nunca forma parte de `TurnPersistence`; los templates de bloqueo y escalamiento tampoco se almacenan.

El schema persistido es exactamente:

```python
{"role": "user", "content": [{"text": "texto sanitizado"}]}
{"role": "assistant", "content": [{"text": "texto sanitizado"}]}
```

No se persisten tool uses, tool results, metadata, objetos de modelo ni estado de hooks.

### 5.4 TTL, FIFO y fallos

`last_activity` usa `clock()` y se actualiza solo después de una persistencia exitosa. El límite cuenta mensajes, no intercambios. `persist` construye y recorta por FIFO una lista candidata local; elimina los mensajes más antiguos hasta `len(candidate) <= max_messages_per_session` y solo entonces reemplaza atómicamente el estado de la sesión.

Si validación, sanitización o construcción falla, `persist` propaga la excepción, conserva historial y `last_activity` anteriores y el context manager libera el lock. Salir sin llamar `persist` no cambia historial ni timestamp. `handle_turn` no devuelve `OrchestratorResult` cuando la persistencia requerida falla.

### 5.5 Memoria efímera

El mensaje original del turno puede entregarse al Agent y a gobierno solo mientras el contexto de turno está activo; se descarta en `finally`. Nunca entra sin sanitizar en SessionManager, eventos, logs ni fallback de auditoría. La propiedad `history` siempre devuelve una copia profunda para que Strands no mute el estado almacenado.

## 6. Idioma y templates seguros

### 6.1 Detección determinística

`detect_language(text) -> Literal["es", "pt"]` sigue este algoritmo:

1. texto vacío o whitespace devuelve `"es"`;
2. aplica `casefold`, normalización Unicode NFKD y elimina marcas combinantes;
3. tokeniza con límites léxicos, no con búsqueda de substrings;
4. si aparece al menos un token o n-grama inequívoco portugués, devuelve `"pt"`;
5. en otro caso devuelve `"es"`.

Indicadores portugueses mínimos: `nao`, `voce`, `voces`, `obrigado`, `obrigada`, `desculpe`, `cartao`, `cobranca`, `bloquear meu`, `bloquear minha`. Un solo indicador basta. Términos compartidos como `por favor`, nombres propios, números y signos no son decisivos. Por ejemplo, `"Não reconheço esta cobrança"` es portugués y `"Por favor, bloquee mi tarjeta"` permanece español.

El idioma se calcula desde el mensaje original del cliente y selecciona templates y el campo `language`; nunca se infiere desde la respuesta del modelo.

### 6.2 Texto exacto de templates

`SYSTEM_PROMPT` no define estos textos. `SAFE_TEMPLATES` vive en `agent/orchestrator.py`, no forma parte de la API pública y contiene estas constantes exactas:

```python
SAFE_TEMPLATES = {
    "es": {
        "block": "No puedo procesar esta solicitud de forma segura.",
        "abstain": (
            "No puedo resolver esta solicitud de forma segura con la "
            "información disponible."
        ),
        "review_failure": (
            "No puedo completar esta solicitud de forma segura. "
            "La derivaré a un especialista."
        ),
        "tool_escalation": (
            "El caso fue escalado correctamente a un especialista."
        ),
        "uncertain_side_effect": (
            "No puedo confirmar el resultado de la operación. Un especialista "
            "revisará el caso antes de realizar otra acción."
        ),
        "external_cancellation": (
            "La operación se interrumpió antes de completarse. "
            "Un especialista revisará el caso."
        ),
        "incomplete_invocation": (
            "No pude completar la respuesta de forma segura. "
            "Un especialista revisará el caso."
        ),
    },
    "pt": {
        "block": "Não posso processar esta solicitação com segurança.",
        "abstain": (
            "Não posso resolver esta solicitação com segurança com as "
            "informações disponíveis."
        ),
        "review_failure": (
            "Não posso concluir esta solicitação com segurança. "
            "Vou encaminhá-la a um especialista."
        ),
        "tool_escalation": (
            "O caso foi encaminhado com sucesso a um especialista."
        ),
        "uncertain_side_effect": (
            "Não posso confirmar o resultado da operação. Um especialista "
            "revisará o caso antes de realizar outra ação."
        ),
        "external_cancellation": (
            "A operação foi interrompida antes de ser concluída. "
            "Um especialista revisará o caso."
        ),
        "incomplete_invocation": (
            "Não consegui concluir a resposta com segurança. "
            "Um especialista revisará o caso."
        ),
    },
}
```

Mapeo obligatorio:

| Terminal | Clave del template |
| --- | --- |
| `TurnAction.BLOCK` | `block` |
| `TurnAction.ABSTAIN` | `abstain` |
| `ESCALATE(GOVERNANCE_REVIEW)` | `review_failure` |
| `ESCALATE(FAILED_ACTION)` | `review_failure` |
| `ESCALATE(OUTPUT_SCREENING_REVIEW)` | `review_failure` |
| `ESCALATE(TOOL_ESCALATION)` | `tool_escalation` |
| `ESCALATE(UNCERTAIN_SIDE_EFFECT)` | `uncertain_side_effect` |
| `ESCALATE(EXTERNAL_CANCELLATION)` | `external_cancellation` |
| `ESCALATE(INCOMPLETE_INVOCATION)` | `incomplete_invocation` |

No se interpolan razones, excepciones, IDs ni texto del modelo. Solo `RESPOND` usa texto del modelo, después de screening ALLOW.

## 7. Señales de orquestación

### 7.1 Formatos permitidos

```json
{"orchestration_signal":"abstention","reason":"razón"}
```

```json
{"orchestration_signal":"clarification","question":"pregunta"}
```

Contrato:

- El valor completo, después de permitir whitespace inicial/final, debe ser un único objeto JSON.
- Solo se aceptan las dos claves exactas de cada variante.
- `reason` o `question` debe ser string no vacío tras `strip`, máximo 500 caracteres.
- Un segundo objeto, Markdown, comentario o cualquier carácter no-whitespace después del objeto invalida la señal.
- Ante JSON inválido, señal desconocida, campos extra o sufijo, `parse_orchestration_signal` devuelve `None` y el llamador conserva la respuesta original byte por byte para el screening normal.
- El parser no devuelve un “texto restante” y nunca descarta un sufijo.

Implementación normativa: usar `json.JSONDecoder().raw_decode` sobre el texto tras whitespace inicial y aceptar solo si el resto contiene exclusivamente whitespace.

### 7.2 Semántica

- `abstention`: `ABSTAIN` con template fijo localizado; no se entrega `reason` al cliente ni se ejecuta output screening.
- `clarification`: se examina exactamente `question`; ALLOW devuelve `RESPOND` con esa pregunta.
- Sin señal válida: se examina la respuesta original completa.
- `reason` solo puede entrar sanitizado en un evento o log.

El system prompt ordena emitir únicamente uno de esos objetos cuando corresponda, sin texto adicional. Esa instrucción orienta al modelo; el parser sigue siendo la frontera efectiva.

## 8. Captura y normalización de tools

### 8.1 Instancia por turno

Cada llamada a `handle_turn` crea un `ResultCaptureHooks` nuevo. Se registra después de `GovernanceHooks`:

```python
hooks = [self._governance_hooks, result_capture]
```

Registra solo:

- `BeforeToolCallEvent`, para capturar `toolUseId`, nombre, argumentos y si gobierno ya canceló la llamada antes de ejecutar;
- `AfterToolCallEvent`, para capturar el resultado terminal, excepción, cancelación y duración.

Strands 1.57.1 sí define `AfterInvocationEvent`. Spec #7 deliberadamente no lo registra: para la API síncrona, el `AgentResult` retornado o la excepción capturada por `handle_turn` son la fuente autoritativa de terminación, y el cleanup pertenece a su `finally`. Agregar un callback de ese evento sin otra responsabilidad sería un no-op redundante.

El test de contrato debe demostrar que, con ese orden de providers, la captura de `BeforeToolCallEvent` observa el `cancel_tool` y `tool_governance` escritos previamente por `GovernanceHooks`.

### 8.2 Resultado normalizado

```python
@dataclass(frozen=True)
class NormalizedToolResult:
    tool_use_id: str
    tool_name: str
    tool_args: dict
    status: str
    content: object
    exception: str | None
    cancel_message: str | None
    duration_ms: int | None
    blocked_before_execution: bool
    retry_requested: bool
```

Normalización:

- `toolUseId`, `name` e `input` se validan antes de usarse; valores malformados se conservan como correlación inválida, no generan IDs inventados.
- `status` es `result["status"]` si vale `"success"` o `"error"`; cualquier otro valor se normaliza a `"error"`.
- `content` toma el primer bloque `json`; si no existe, el primer bloque `text`; si no existe, `None`.
- `exception` conserva solo el nombre de tipo y un mensaje sanitizado, nunca `repr` arbitrario.
- `duration_ms = max(0, int(duration * 1000))`; `None` permanece `None`.
- `blocked_before_execution` solo es verdadero si la captura previa y `tool_governance[toolUseId]` prueban bloqueo de gobierno antes de ejecución.
- `retry_requested` copia el booleano observado en ese callback. No significa “ya fue reintentado” ni es contador histórico.

### 8.3 Reintentos

Spec #7 no instala ningún hook que establezca `event.retry=True`; por tanto, el camino soportado produce exactamente un resultado terminal por `toolUseId` y `retry_requested=False`.

Si aparece `retry_requested=True` o más de un intento/resultado con el mismo `toolUseId`, se trata como incumplimiento del contrato de composición:

- para `block_card` o `escalate_case`, establece inmediatamente `UNCERTAIN_SIDE_EFFECT`, incluso si otra captura del mismo ID indica `blocked_before_execution=True`;
- para una tool de lectura, establece `INCOMPLETE_INVOCATION`.

No se selecciona un “último resultado exitoso” ni se ofrece soporte parcial de retries. Si se observa un ID duplicado, sus capturas se condensan en un único `tool_call` con error y en el terminal conservador indicado arriba. Una spec futura que agregue retries deberá definir intentos explícitos, deduplicar el resultado terminal por `toolUseId` y conservar como incierto cualquier intento sensible previo sin evidencia terminal.

### 8.4 Snapshot tras la invocación

`handle_turn` captura los snapshots de intentos y resultados una sola vez inmediatamente después de que la invocación del Agent retorna o lanza. Después de ese snapshot no consulta estado mutable del hook. Los snapshots sobreviven a la excepción del Agent y se usan para clasificar posibles side effects.

## 9. Invocación y terminación del Agent

### 9.1 Creación efímera

Por turno se crea:

```python
agent = Agent(
    model=self._model_factory(),
    tools=list(REGISTERED_TOOLS),
    hooks=[self._governance_hooks, result_capture],
    system_prompt=SYSTEM_PROMPT,
    messages=history_snapshot,
)
```

`history_snapshot` no incluye el mensaje actual. La invocación exacta es:

```python
agent_result = agent(
    message,
    invocation_state=invocation_state,
    cancel_signal=cancel_signal,
)
```

### 9.2 Captura de excepción

Antes de invocar se inicializan `agent_result = None` y `agent_exception = None`. Se captura `Exception` alrededor de la invocación del Agent; no se captura `BaseException`. Ante excepción:

- se conserva `agent_result=None`;
- se conserva una descripción sanitizada en `agent_exception` solo para clasificación/auditoría;
- se recuperan los resultados ya capturados;
- no se propaga texto parcial al cliente;
- el flujo continúa por normalización, certeza de acciones y terminal seguro.

### 9.3 Estados de terminación

| Condición | Tratamiento |
| --- | --- |
| `governance_action == "block"` | `BLOCK`; prevalece sobre el texto sintético que Strands pueda retornar. |
| `governance_action == "review"` | `ESCALATE(GOVERNANCE_REVIEW)`. |
| Acción sensible incierta | `ESCALATE(UNCERTAIN_SIDE_EFFECT)`, incluso si hubo cancelación o excepción. |
| `agent_result is None` | `ESCALATE(EXTERNAL_CANCELLATION)` si no hay side effect incierto. |
| `agent_result.stop_reason == "cancelled"` | `ESCALATE(EXTERNAL_CANCELLATION)` si no hay side effect incierto. |
| `stop_reason` en `{"end_turn", "stop_sequence"}` | Puede continuar a señales y output screening. |
| Cualquier otro `stop_reason` | `ESCALATE(INCOMPLETE_INVOCATION)` y descarta el texto. |

Para `agent_result is None` no se exige que `cancel_signal.is_set()`: el Agent no produjo un resultado confiable y se usa el mismo terminal conservador. `cancel_signal` es propiedad del llamador; el orquestador no lo establece, limpia ni reutiliza.

Solo se extraen bloques `text` de `AgentResult.message` después de confirmar terminación normal. Texto vacío en una terminación normal se clasifica como `INCOMPLETE_INVOCATION`. Ningún texto de una cancelación, excepción o terminación incompleta pasa a output screening, sesión o respuesta.

## 10. Certeza y conversión de acciones

`ACTION_TOOLS = {"block_card", "escalate_case"}`. Las tools de lectura no participan en `actions_taken`.

### 10.1 Precedencia por intento sensible

Para cada `toolUseId` sensible, en este orden:

1. `retry_requested=True`, más de un intento o más de un resultado con ese ID → `UNCERTAIN_SIDE_EFFECT`; esta regla prevalece sobre toda evidencia de bloqueo pre-ejecución.
2. `blocked_before_execution=True` por una única captura correlacionada de gobierno → `FAILED_ACTION`; la tool no pudo ejecutar.
3. `exception is not None` → `UNCERTAIN_SIDE_EFFECT`.
4. `cancel_message is not None` sin prueba de bloqueo pre-ejecución → `UNCERTAIN_SIDE_EFFECT`.
5. El intento fue permitido pero no existe resultado terminal correlacionado → `UNCERTAIN_SIDE_EFFECT`.
6. `status != "success"` sin prueba explícita de no ejecución → `UNCERTAIN_SIDE_EFFECT`.
7. `content` no es dict, no tiene `action` correcto o es contradictorio → `UNCERTAIN_SIDE_EFFECT`.
8. `executed=False` con denegación de política explícita y sin `verification` de ejecución → `FAILED_ACTION`.
9. Una verificación de servicio no canónica o que no confirma el efecto → `UNCERTAIN_SIDE_EFFECT`.
10. Un payload canónico se entrega a `build_actions_taken`.

Así se distingue un bloqueo de gobierno anterior a la ejecución de una cancelación o excepción ocurrida cuando el efecto ya pudo suceder.

La regla 10 solo produce `action_payloads`; no llama a `build_actions_taken`. La construcción canónica se ejecuta exactamente una vez dentro del pipeline de la sección 11 cuando corresponde examinar texto del modelo. Una regla anterior de incertidumbre o fallo termina el turno antes de ese pipeline.

### 10.2 Predicado exacto de `escalate_case`

```python
def _is_successful_escalation(result: NormalizedToolResult) -> bool:
    return (
        result.status == "success"
        and isinstance(result.content, dict)
        and result.content.get("action") == "escalate_case"
        and result.content.get("executed") is True
        and result.content.get("verification") in ("confirmed_persisted",)
        and isinstance(result.content.get("escalation_id"), str)
        and result.content.get("escalation_id") != ""
    )
```

Solo este predicado produce `TOOL_ESCALATION` y expone `escalation_id`. Un resultado de `escalate_case` que no lo cumple sigue las reglas de certeza anteriores.

### 10.3 Precedencia terminal completa

1. Bloqueo/review global de gobierno.
2. Side effect incierto.
3. Acción fallida o bloqueada antes de ejecutar.
4. `escalate_case` exitoso, siempre que no coexista otra acción fallida o incierta.
5. Cancelación, ausencia de resultado o terminación incompleta.
6. Señal de abstención.
7. Señal de clarificación y su screening.
8. Screening de respuesta normal.

Los terminales 1–5 usan templates fijos localizados y nunca entregan texto parcial del modelo.

## 11. Output screening y clasificación final

Se ejecuta solo para una pregunta de clarificación válida o para texto normal de una terminación normal. `generic_safe_response` significa exactamente `SAFE_TEMPLATES[language]["review_failure"]`.

### 11.1 Algoritmo único

`_run_output_screening` recibe `proposed_response`, `action_payloads`, resultados de lectura y contexto de auditoría:

1. obtiene `dispute_context` desde resultados de lectura; si no existe, usa `verified_facts={}`;
2. si existe contexto, llama `adapter.build_verified_facts(dispute_context)`;
3. llama exactamente una vez `adapter.build_actions_taken(action_payloads)`;
4. si los pasos 2 o 3 lanzan, o `has_failed_actions=True`, devuelve FAILURE/FAILED_ACTION según la tabla 11.2;
5. llama `adapter.screen_output` con hechos y acciones canónicas, el padre del último `tool_call` durable o `routing_event_id`, y el keyword `orphaned` de la sección 13.3;
6. convierte el resultado o excepción usando exclusivamente la tabla 11.2.

### 11.2 Mapeo exhaustivo de `OutputScreeningOutcome`

| Condición | `state` | `governance_result` | `escalation_type` | `safe_response` | `event_id` |
| --- | --- | --- | --- | --- | --- |
| Falla `build_verified_facts` | `FAILURE` | `None` | `FAILED_ACTION` | `generic_safe_response` | `None` |
| Falla `build_actions_taken` | `FAILURE` | `None` | `FAILED_ACTION` | `generic_safe_response` | `None` |
| `has_failed_actions=True` | `FAILURE` | `None` | `FAILED_ACTION` | `generic_safe_response` | `None` |
| `adapter.screen_output` lanza excepción o `AuditPersistenceError` | `FAILURE` | `None` | `OUTPUT_SCREENING_REVIEW` | `generic_safe_response` | `None` |
| Gobierno devuelve REVIEW | `REVIEW` | resultado de gobierno | `OUTPUT_SCREENING_REVIEW` | `generic_safe_response` | `governance_result.event_id` |
| Gobierno devuelve ALLOW | `ALLOW` | resultado de gobierno | `None` | `proposed_response` exacto | `governance_result.event_id` |

No existe otra combinación válida. En particular, una FAILURE de evidencia canónica nunca se etiqueta como `OUTPUT_SCREENING_REVIEW`, y una excepción o fallo de auditoría dentro de `screen_output` nunca se etiqueta como `FAILED_ACTION`.

### 11.3 Conversión a `TurnClassification`

Para señal de clarificación, `proposed_response` es exactamente `question`. Para respuesta normal, es exactamente la respuesta original completa preservada por el parser. En ambos casos se aplica la misma tabla:

- ALLOW → `TurnAction.RESPOND`, `response_text=outcome.safe_response`, `escalation_type=None`, `escalation_id=None`;
- REVIEW o FAILURE → `TurnAction.ESCALATE`, `response_text=outcome.safe_response`, `escalation_type=outcome.escalation_type`, `escalation_id=None`;
- `terminal_parent_event_id=outcome.event_id` cuando existe; si es `None`, conserva el último padre durable previo.

`_classify_result` no vuelve a leer ni reconstruir `proposed_response`. Por ello una clarificación ALLOW conserva la pregunta examinada, mientras cualquier REVIEW/FAILURE de clarificación o respuesta normal entrega el mismo template genérico exacto.

Templates fijos de bloqueo, escalamiento y abstención son contenido confiable del orquestador y no pasan por output screening. Todo texto entregable originado por el modelo sí pasa por screening.

## 12. Flujo único de `handle_turn`

Orden normativo, sin caminos alternativos:

1. Validar `message`, `session_id` y `customer_id` como strings no vacíos; si no, `ValueError`.
2. Entrar con `with self._session_manager.turn(session_id) as session_turn` y mantener el lock hasta `finally`.
3. Tomar `history_snapshot = session_turn.history`, detectar idioma, generar `trace_id` e inicializar `invocation_state`.
4. Emitir `input`. Si falla la persistencia primaria, guardar `input_event_id=None` y `audit_orphaned=True`.
5. Crear modelo, `ResultCaptureHooks` y Agent efímeros.
6. Invocar el Agent capturando `Exception` y preservando lo capturado.
7. Tomar snapshots del hook y normalizar intentos/resultados.
8. Evaluar terminación y certeza de acciones y producir `action_payloads`; no llamar aún a `build_actions_taken` ni entregar respuesta.
9. Emitir un `tool_call` por ID válido único y uno por intento sin ID, incluidos bloqueos pre-ejecución. Un ID duplicado se condensa como error; un intento sin ID conserva `tool_use_id=""` y usa routing fallback. Un fallo de auditoría posterior a una acción sensible cambia la clasificación a `UNCERTAIN_SIDE_EFFECT`.
10. Si la clasificación aún requiere texto del modelo, parsear señal y ejecutar una sola vez el pipeline de la sección 11; producir `TurnClassification` final desde su outcome.
11. Emitir `escalation` cuando la acción final sea ESCALATE y después emitir `response`. Cada uno usa como padre el último evento durable correspondiente.
12. Construir `TurnPersistence(action=classification.action.value, user_text=message, assistant_text=classification.response_text)` para RESPOND/ABSTAIN, o con `assistant_text=None` para BLOCK/ESCALATE; llamar exactamente una vez `session_turn.persist(request)`.
13. Construir `OrchestratorResult` exclusivamente desde `TurnClassification`.
14. En `finally`, eliminar referencias al Agent, modelo, hook, snapshots, mensaje crudo e `invocation_state`, y liberar el lock del turno.

No se persiste sesión antes de completar los eventos terminales. Si SessionManager falla, el resultado seguro queda clasificado internamente, pero `handle_turn` propaga el error operativo y no devuelve `OrchestratorResult`; no se finge memoria exitosa.

## 13. Auditoría, correlación y fallos

### 13.1 `CompositeAuditSink`

`CompositeAuditSink.emit(event)` intenta primero el sink primario. Si el primario falla:

1. intenta el fallback una sola vez, solo como copia diagnóstica best-effort;
2. lanza siempre `AuditPersistenceError`, aunque el fallback acepte el evento;
3. incluye las excepciones primaria y, si existe, secundaria sin incluir el evento ni secretos en su mensaje.

El fallback no es durable, no confirma persistencia y no convierte la operación en éxito. No hay retries internos.

### 13.2 Semántica de `_emit_event`

Para eventos del orquestador:

```python
def _emit_event(self, event: dict) -> str | None:
    try:
        self._audit_sink.emit(event)
    except AuditPersistenceError:
        return None
    return event["event_id"]
```

El retorno es el `event_id` solo cuando el primario persistió; `None` siempre significa fallo de persistencia primaria. Los llamadores deben comprobarlo. Nunca se devuelve éxito por ser un evento “no sensible”.

`GovernanceAdapter._emit_event` mantiene un contrato más estricto: retorna `event_id` tras persistencia primaria y propaga `AuditPersistenceError` si falla. Así gobierno falla cerrado antes de acciones.

### 13.3 Política según el momento del fallo

| Fallo | Comportamiento obligatorio |
| --- | --- |
| `input` no persistido | Continuar con `input_event_id=None`; marcar todos los eventos descendientes con `payload.orphaned=True`. |
| Auditoría de input screening, routing o tool gating | Propagar al orquestador; impedir nuevas acciones y devolver terminal seguro. |
| Auditoría de output screening | Aplicar `FAILURE + OUTPUT_SCREENING_REVIEW + generic_safe_response` de la tabla 11.2. |
| `tool_call` de lectura no persistido | Marcar descendencia huérfana y continuar al terminal seguro. |
| `tool_call` de acción no persistido después de ejecutarse | No se puede deshacer; clasificar `UNCERTAIN_SIDE_EFFECT`, no iniciar otra acción y emitir terminal best-effort. Las acciones concurrentes ya iniciadas también se clasifican desde su evidencia. |
| `escalation` o `response` no persistido | No reejecutar side effects; usar como padre el último evento durable y marcar el evento posterior como huérfano. |

#### Extensión Spec #7 para descendencia huérfana

Spec #7 amplía de forma retrocompatible las tres entradas públicas relevantes del adapter con un keyword-only cuyo default conserva el contrato de Spec #6:

```python
def screen_and_route(
    self,
    message: str,
    trace_id: str,
    session_id: str,
    customer_id: str,
    parent_event_id: str | None = None,
    *,
    orphaned: bool = False,
) -> ScreeningRoutingResult

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
    *,
    orphaned: bool = False,
) -> GovernanceResult

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
    *,
    orphaned: bool = False,
) -> GovernanceResult
```

`orphaned` debe ser exactamente `bool`; otro tipo lanza `TypeError`. Cada método lo pasa explícitamente a `GovernanceAdapter._emit_event`. En `screen_and_route`, se pasa a todos los eventos de screening/routing emitidos por esa llamada.

Los hooks leen el flag y pasan solo el booleano, nunca el `invocation_state` completo:

```python
orphaned = bool(event.invocation_state.get("audit_orphaned", False))
result = self._adapter.screen_and_route(
    message,
    trace_id,
    session_id,
    customer_id,
    parent_event_id=event.invocation_state.get("input_event_id"),
    orphaned=orphaned,
)
```

`before_tool_call` calcula el mismo booleano y llama `gate_tool_call` con `parent_event_id=routing_event_id` y `orphaned=orphaned`. El orquestador llama `screen_output` con `parent_event_id=screening_parent` y `orphaned=bool(invocation_state.get("audit_orphaned", False))`.

`GovernanceAdapter._emit_event` recibe `orphaned: bool`; construye primero el payload governance normal y añade `payload["orphaned"] = True` solo cuando el argumento es verdadero. Con `False`, la clave se omite. El adapter no recibe, conoce ni consulta `invocation_state`.

Cuando falla `input`, el orquestador establece `invocation_state["audit_orphaned"] = True`; cuando persiste, la clave se omite. Esta extensión no cambia padres: `input_event_id` continúa `None` tras fallo, tool gating conserva `routing_event_id`, y los fallbacks de las secciones 13.5–13.6 permanecen iguales.

### 13.4 Construcción normativa de eventos

#### Envelope común

Todo evento del orquestador se construye antes de llamar `_emit_event` con exactamente este envelope:

```python
{
    "trace_id": trace_id,
    "event_id": str(uuid4()),
    "parent_event_id": parent_event_id,
    "timestamp": datetime.now(UTC).isoformat(),
    "component": "orchestrator",
    "event_type": event_type,
    "customer_id": mask_customer_id(customer_id),
    "session_id": session_id,
    "outcome": outcome,
    "latency_ms": latency_ms,
    "tokens": None,
    "cost_usd": None,
    "payload": payload,
}
```

`latency_ms` es entero no negativo: para `input`, tiempo desde el inicio de `handle_turn` hasta su construcción; para `tool_call`, `NormalizedToolResult.duration_ms` o `0` si es `None`; para `escalation` y `response`, tiempo monotónico desde que empieza a construirse ese evento. `parent_event_id` es `None` solo para `input` o cuando no existe ancestro durable. Antes de emitir, el payload completo pasa por `sanitize_json_structure`; luego cada string limitado se recorta por cantidad de code points. Ningún evento contiene PAN, CVV, credenciales, mensaje crudo, excepción cruda ni handoff completo. Campos opcionales se omiten cuando no aplican; no se rellenan con `None`. Si `audit_orphaned=True`, todo payload descendiente añade `"orphaned": True`.

#### Evento `input`

- `event_type="input"`, `outcome="success"`, `parent_event_id=None`.
- Payload requerido:

```python
{
    "text": sanitize_message(message)[:2000],
    "language": language,
    "channel": "api",
}
```

Si el texto sanitizado excede 2000 caracteres, se añade `"text_truncated": True`; en otro caso se omite.

#### Evento `tool_call`

Outcome: `"blocked"` para bloqueo pre-ejecución, `"success"` para resultado exitoso y `"failure"` para cualquier error, cancelación, ausencia, retry o duplicado.

Payload requerido:

```python
{
    "tool_name": tool_name,
    "tool_use_id": tool_use_id,
    "args": audit_args,
    "result_status": result_status,
    "result_summary": result_summary,
    "verified": verified,
}
```

`result_status` pertenece exactamente a `{"success", "error", "blocked"}`. `correlation="routing_fallback"` es opcional y aparece solo cuando se usa ese fallback.

`tool_name` es el nombre validado o `"unknown"`; `tool_use_id` es el ID validado o `""`. `audit_args` incluye solo campos con el tipo contractual correcto; omite campos inválidos y es una proyección sanitizada y acotada:

| Tool | Campos auditables |
| --- | --- |
| `get_dispute_context` | `complaint_id` sanitizado, máximo 128 caracteres |
| `get_recent_transactions` | `complaint_id` máximo 128, `days_before`, `limit` |
| `block_card` | `complaint_id` máximo 128, `confirmed_by_customer` |
| `escalate_case` | `complaint_id` máximo 128, `reason` máximo 500, `unresolved_questions_count`, `agent_notes_present` |
| Nombre/args malformados | `{}` |

No se auditan la lista de preguntas ni las notas. `result_summary` tiene máximo 500 caracteres y se construye con esta precedencia:

1. retry/duplicado: `"retry_or_duplicate_uncertain"`;
2. bloqueo pre-ejecución: `"blocked_before_execution"`;
3. excepción: `"exception:<NombreDeClase>"`;
4. cancelación: `"cancelled"`;
5. ausencia terminal: `"missing_terminal_result"`;
6. acción: JSON ordenado de la proyección `action`, `executed`, `verification`, `reason`, `error`; valores no escalares se representan como `"<invalid>"`;
7. lectura con error: valor string sanitizado de `error`, o `"error"` si no es string;
8. lectura exitosa: `"success"`.

`verified=True` solo cuando no hay retry, duplicado, excepción ni cancelación y además se cumple una de estas condiciones: resultado de lectura exitoso como dict sin `error`; payload de acción satisface directamente `ACTION_VERIFICATIONS`; o `escalate_case` cumple el predicado exacto de la sección 10.2. En cualquier otro caso es `False`.

#### Evento `escalation`

- `event_type="escalation"`, `outcome="escalated"`.
- Payload base:

```python
{
    "reason": escalation_reason,
    "priority": priority,
    "unresolved_questions_count": unresolved_questions_count,
}
```

Para escalamiento no originado por `escalate_case`, `escalation_reason=escalation_type.value`, `priority="unknown"`, `unresolved_questions_count=0` y se omite `handoff_id`.

Para un `escalate_case` que cumple el predicado exacto:

- `handoff_id` es `sanitize_message(content["escalation_id"])[:128]`;
- `priority` es `sanitize_message(content.get("priority"))[:50]` si `content.get("priority")` es string no vacío, o `"unknown"`;
- `handoff` es `content.get("handoff")` si es dict, o `{}`;
- `unresolved_questions_count` es la longitud de `handoff.get("unresolved_questions")` si es lista, o `0`;
- `metadata` es `handoff.get("handoff_metadata")` si es dict, o `{}`;
- `reason` es `metadata.get("reason")` sanitizado y limitado a 500 caracteres si es string no vacío, o `"tool_escalation"`;
- nunca se incluye el handoff completo.

#### Evento `response`

Outcome por acción: RESPOND → `"success"`, BLOCK → `"blocked"`, ESCALATE → `"escalated"`, ABSTAIN → `"abstained"`.

Payload requerido:

```python
{
    "grounded_in": grounded_in,
    "action_summary": action_summary,
    "language": language,
}
```

`grounded_in` conserva orden de captura, elimina duplicados y admite máximo ocho strings sanitizados de hasta 200 caracteres. Sus únicas fuentes son `model:screened` para texto de modelo aprobado, `orchestrator:template` para templates fijos, `tool:<tool_name>` para lecturas verificadas, `action:<action_name>` para acciones canónicas y `handoff:<handoff_id_sanitizado>` para el escalamiento exitoso.

`action_summary` se sanitiza y limita a 500 caracteres. Para acciones canónicas une en orden `action_name:verification`; sin acción usa `blocked`, `abstained`, `escalation_type.value` o `none`, según el terminal. El texto completo de respuesta no se repite en el payload.

### 13.5 Mapeo de tool gating

Para cada resultado:

```python
governance_info = invocation_state.get("tool_governance", {}).get(tool_use_id)
if isinstance(governance_info, dict):
    parent_event_id = governance_info.get("event_id")
else:
    parent_event_id = None
if not isinstance(parent_event_id, str) or not parent_event_id.strip():
    parent_event_id = invocation_state.get("routing_event_id")
```

La clave es siempre el `toolUseId` exacto. Ante ID ausente, tipo inválido, entrada ausente o `event_id` inválido, el `tool_call` usa `routing_event_id` como fallback y añade `payload.correlation="routing_fallback"`. No se inventa un ID ni se enlaza con otra tool.

El payload incluye `tool_use_id`, argumentos sanitizados y `result_status`:

- `"blocked"` para bloqueo probado antes de ejecución;
- `"success"` para resultado exitoso;
- `"error"` para excepción, cancelación, ausencia o error.

### 13.6 Grafo de eventos

```text
RESPOND
input
└── input_screening
    └── intent_routing
        ├── tool_gating_A
        │   └── tool_call_A
        ├── tool_gating_B
        │   └── tool_call_B
        └── output_screening
            └── response

BLOCK en input screening
input
└── input_screening(blocked)
    └── response(blocked)

BLOCK en routing
input
└── input_screening
    └── intent_routing(blocked)
        └── response(blocked)

ESCALATE por gobierno
input
└── último governance(review)
    └── escalation
        └── response(escalated)

ESCALATE por escalate_case
input
└── intent_routing
    └── tool_gating
        └── tool_call(escalate_case)
            └── escalation
                └── response(escalated)

ABSTAIN
input
└── último evento previo durable
    └── response(abstained)
```

Reglas:

- `input` es la única raíz cuando persiste.
- Los eventos de `tool_gating` concurrentes son hermanos bajo `routing_event_id`.
- Cada `tool_call` es hijo de su propio gating según `toolUseId`; solo usa routing fallback ante correlación malformada o ausente.
- `output_screening` es hijo del último `tool_call` durable emitido; sin tools, de `routing_event_id`.
- Todo `response` es hijo del evento durable que determina el terminal: screening, governance bloqueante, escalation o último evento previo para abstención.
- Si un padre no persistió, se usa el último ancestro durable y `payload.orphaned=True`; nunca se referencia un `event_id` no persistido.

## 14. Seguridad y prompt

`SYSTEM_PROMPT` contiene rol, uso de tools, idiomas, flujo de disputa y formatos de señal. No contiene secretos, umbrales, autorización ni reglas duras. Las reglas de confirmación, elegibilidad y verificación permanecen en código.

Además:

- argumentos, excepciones, razones y resúmenes se sanitizan antes de auditoría;
- `customer_id` se enmascara con el contrato de Spec #6;
- no se registra chain-of-thought;
- no se usa `customer_id` de una queja para consultar transacciones;
- el vínculo confiable sigue siendo `product_id` resuelto por las tools;
- toda acción sensible sin evidencia concluyente termina en `UNCERTAIN_SIDE_EFFECT`.

## 15. TDD de la implementación futura

### 15.1 Runner y ciclo

Runner autoritativo: `uv run pytest`. Cada comportamiento se implementa con un test RED observado, mínimo GREEN, triangulación relevante y refactor con el foco verde. Tests unitarios no usan red, Jev real ni modelo real. Los contratos con Strands usan la versión instalada, modelo/tool falsos y sin red.

### 15.2 Backlog unitario mínimo

**Construcción y modelo**

- Exclusión mutua entre `model_factory` y `model`.
- Factory invocado una vez por turno; dos turnos reciben modelos distintos.
- `model` directo funciona en test secuencial.
- OpenAI usa `client_args` y respeta precedencia de `model_id`.
- Adapter y orquestador reciben la misma identidad de `CompositeAuditSink`.

**Captura, normalización y retries**

- Instancia de `ResultCaptureHooks` nueva por turno.
- Strands expone `AfterInvocationEvent`, pero el provider registra únicamente Before/AfterToolCall.
- Preserva resultados capturados si Agent lanza.
- Duración se convierte a ms; excepción se sanitiza.
- `event.retry` no se interpreta como contador.
- Retry o duplicado inesperado en acción produce incertidumbre.
- Retry/duplicado sensible prevalece sobre `blocked_before_execution=True` para el mismo `toolUseId`.
- Intento permitido sin resultado terminal produce incertidumbre.

**Terminación y acciones**

- Excepción de Agent suprime texto parcial y conserva evidencia de tools.
- `AgentResult is None` y `stop_reason == "cancelled"` producen cancelación externa sin side effects inciertos.
- Side effect incierto prevalece sobre cancelación.
- Stop reason no normal suprime texto y produce invocación incompleta.
- Bloqueo governance pre-ejecución produce `FAILED_ACTION`.
- Excepción/cancelación post-posible-ejecución produce `UNCERTAIN_SIDE_EFFECT`.
- Predicado exacto de `escalate_case` cubierto campo por campo.
- Resultado exitoso de escalamiento conserva `escalation_id`.

**Señales, templates y output**

- Señales válidas de abstención y clarificación.
- Cualquier sufijo no-whitespace invalida la señal y conserva el original completo.
- Claves extra, valor vacío, tipo inválido y longitud excesiva se rechazan.
- Clarificación ALLOW devuelve la pregunta examinada.
- Falla de hechos o acciones canónicas → FAILURE/FAILED_ACTION + `review_failure` exacto.
- Excepción o fallo de auditoría en `screen_output` → FAILURE/OUTPUT_SCREENING_REVIEW + `review_failure` exacto.
- Gobierno REVIEW → REVIEW/OUTPUT_SCREENING_REVIEW + `review_failure` exacto.
- Gobierno ALLOW conserva exactamente `proposed_response`.
- La matriz anterior se parametriza para clarificación y respuesta normal.
- Cada terminal de la tabla 6.2 devuelve exactamente su template ES y PT.
- Los templates no interpolan razones, IDs, excepciones ni texto del modelo.
- Respuesta normal y clarificación pasan por screening; templates fijos no.

**Sesión, idioma y memoria**

- Constructor valida límites y acepta reloj inyectable.
- `turn` entrega `SessionTurn.history` como copia profunda.
- `persist` acepta exactamente `TurnPersistence` y solo una llamada.
- Matriz action/assistant de la sección 5.3 validada en casos positivos y negativos.
- Lock cubre snapshot hasta persistencia y se libera en éxito o excepción.
- Misma sesión se serializa; sesiones distintas pueden solaparse.
- TTL por reloj monotónico, límite por mensajes y recorte FIFO.
- Fallo de persistencia conserva historial y timestamp anteriores.
- Salir sin persistir no muta la sesión; `clear_session` espera el lock activo.
- PAN, CVV y credenciales se redactan antes de memoria.
- El turno crudo está disponible al modelo pero no queda persistido.
- Un indicador inequívoco PT basta; límites de token evitan substrings.
- Acentos se normalizan y `por favor` no decide idioma.

**Auditoría y grafo**

- Fallback se intenta una vez y aun así se lanza `AuditPersistenceError`.
- `_emit_event` retorna ID solo con primario exitoso y `None` ante fallo.
- Fallo governance pre-acción impide ejecutar la acción.
- Fallo de audit post-side-effect produce terminal incierto sin reejecución.
- Input fallido marca todos los descendientes como huérfanos.
- Las tres entradas públicas del adapter omiten `orphaned` por default y añaden `payload.orphaned=True` cuando se solicita.
- `orphaned` no bool lanza `TypeError` en las tres entradas del adapter.
- Hooks pasan explícitamente el booleano a screening/routing y tool gating; el orquestador lo pasa a output screening.
- El adapter nunca recibe ni consulta `invocation_state`; parents y fallbacks permanecen iguales.
- Envelopes de input/tool_call/escalation/response tienen campos, outcomes y parents exactos.
- Strings, args y summaries se sanitizan y respetan los límites de la sección 13.4.
- Campos opcionales se omiten; `text_truncated`, `correlation`, `handoff_id` y `orphaned` solo aparecen cuando aplican.
- `verified` cubre lectura, acción canónica y predicado exacto de escalamiento.
- Escalamiento exitoso proyecta handoff_id, priority, reason y conteo sin incluir handoff.
- `grounded_in` y `action_summary` usan únicamente las fuentes y formatos permitidos.
- Mapeo por `toolUseId`; correlación inválida usa routing fallback.
- Grafo BLOCK tiene response bajo el governance bloqueante.
- Todos los responses tienen el padre terminal correcto.
- `tool_call` se emite antes de output screening.

### 15.3 Contratos con Strands 1.57.1

- Firma y comportamiento de `cancel_signal: threading.Event | None`.
- Cancelación real devuelve `stop_reason == "cancelled"`.
- `AgentResult.message` usa `Message` con `role` y `content`.
- Orden de providers permite capturar bloqueo governance en BeforeToolCall.
- Strands expone `AfterInvocationEvent`, pero `ResultCaptureHooks` no registra callback para ese evento.
- AfterToolCall expone `tool_use`, `result`, `exception`, `cancel_message`, `duration` y `retry` booleano.
- Agent efímero recibe `messages=history` y el turno actual solo en la invocación.
- Dos sesiones concurrentes no comparten Agent, modelo ni captura.

## 16. Archivos de la implementación futura

### Crear

```text
src/ai_banking_customer_service/agent/orchestrator.py
src/ai_banking_customer_service/agent/result_capture.py
src/ai_banking_customer_service/agent/session_manager.py
src/ai_banking_customer_service/agent/signal_parser.py
src/ai_banking_customer_service/agent/language_detector.py
src/ai_banking_customer_service/agent/system_prompt.py
tests/unit/agent/test_orchestrator.py
tests/unit/agent/test_result_capture.py
tests/unit/agent/test_session_manager.py
tests/unit/agent/test_signal_parser.py
tests/unit/agent/test_language_detector.py
tests/unit/agent/test_system_prompt.py
tests/integration/agent/test_strands_contract.py
```

### Modificar

```text
src/ai_banking_customer_service/agent/hooks.py
src/ai_banking_customer_service/governance/adapter.py
src/ai_banking_customer_service/observability/sink.py
tests/unit/agent/test_hooks.py
tests/unit/governance/test_adapter.py
tests/unit/observability/test_sink.py
docs/observability.md
docs/STATUS.md
```

`docs/observability.md` permanece hoy en el estado implementado por Spec #6. La implementación de Spec #7 debe modificarlo atómicamente junto con código y tests para:

- agregar `blocked` al dominio de `tool_call.result_status`;
- documentar `tool_use_id` como campo requerido de `tool_call`;
- documentar `correlation`, `text_truncated`, `handoff_id` y `payload.orphaned` como campos opcionales según la sección 13.4;
- fijar las proyecciones, límites y reglas de sanitización de los cuatro payloads;
- documentar los campos derivados del `escalate_case` exitoso;
- documentar el keyword `orphaned: bool = False` en las tres entradas públicas del adapter y la clave governance opcional;
- documentar `CompositeAuditSink` y que el fallback es best-effort, no durable;
- indicar que una tool bloqueada también genera exactamente un `tool_call`.

No se acepta implementar esos campos sin actualizar el documento, ni actualizar el documento como si ya estuvieran implementados antes del código. `docs/STATUS.md` se actualiza solo después de implementar y validar el componente. Esta revisión v5 no modifica ninguno de esos archivos.

## 17. Criterios de aceptación de la implementación

- Los microciclos TDD dejan evidencia RED/GREEN para los comportamientos anteriores.
- `uv run pytest tests/unit/agent/ tests/integration/agent/ -q` pasa.
- `uv run pytest tests/unit -q` pasa.
- `uv run ruff check` y `uv run ruff format --check` pasan para los archivos afectados.
- No hay red en tests unitarios o de contrato.
- Cada turno usa Agent, modelo y captura propios en producción.
- Excepciones y cancelaciones nunca entregan texto parcial.
- La clasificación diferencia bloqueo pre-ejecución de side effect incierto y da precedencia a retry/duplicado sensible.
- La tabla 11.2 determina state, escalation type, safe response y event ID para hechos, acciones, excepciones, auditoría, REVIEW y ALLOW.
- Clarificación y respuesta normal convierten el mismo `OutputScreeningOutcome` a `TurnClassification` sin perder el texto ALLOW.
- La respuesta final usa los templates exactos de la sección 6.2.
- El parser conserva intacta toda respuesta con sufijo no-whitespace.
- La API exacta de sesión, TTL, FIFO, lock, atomicidad y sanitización cumple la sección 5.
- Los cuatro eventos del orquestador cumplen envelope, payload, límites y sanitización de la sección 13.4.
- El mismo `CompositeAuditSink` se usa en adapter y orquestador.
- Un fallo de auditoría governance impide acciones posteriores.
- La extensión `orphaned` es keyword-only, retrocompatible, explícita en hooks/orquestador y cubierta por tests.
- El grafo, parentesco y fallback de correlación cumplen la sección 13.
- Código, tests y `docs/observability.md` incorporan atómicamente los mismos campos y dominios futuros.
- No se modifican tools, services, reglas de Spec #4 ni contratos de negocio previos.
- `docs/STATUS.md` se actualiza con el resultado real de la implementación.
