# SPEC #8 — UI Chainlit como capa de presentación delgada (v5)

Método de implementación futura: TDD estricto, en microciclos RED → GREEN → TRIANGULATE → REFACTOR.

> Contrato final cerrado contra `chainlit==2.12.0`. Esta revisión es documental:
> no afirma que la UI esté implementada ni cambia el estado del proyecto.

## 0. Decisiones normativas

| Tema | Contrato v5 |
| --- | --- |
| Baseline | `chainlit==2.12.0` y `requests==2.32.5`; ambos pins son obligatorios. `requests` es requerido por el import de Chainlit/LiteralAI de la distribución instalada. |
| UI | Capa delgada: valida entrada, invoca al orquestador y renderiza; no contiene negocio, política, gobierno ni auditoría. |
| Bridge | `asyncio.to_thread`, un `asyncio.Task` retenido y `asyncio.shield` en las dos esperas con deadline. |
| Concurrencia | Un único `ActiveTurn` por sesión. Mientras exista su entrada no se acepta otro turno, aunque `task.done()` sea verdadero. |
| Stop | En Chainlit 2.12.0 el handler de socket cancela primero el `current_task` y después espera `@cl.on_stop`; tanto la rama `CancelledError` como `on_stop` activan idempotentemente el mismo `cancel_signal`. |
| Reconciliación | Resultado tardío en memoria, visible en el próximo mensaje; ese mensaje solo dispara la reconciliación y no se procesa como turno nuevo. |
| Entrega | Todo mensaje propiedad de la UI pasa por `_send_ui_message`; los helpers de envío y render devuelven `bool`. |
| HTML | `.chainlit/config.toml` debe declarar `[features].unsafe_allow_html = false`; la importación/arranque falla si falta o no es exactamente `false`. |
| Pruebas Chainlit | No hay test client oficial soportado en el wheel instalado. Son obligatorios tests de contrato más un smoke portable del servidor. |
| Durabilidad | Turnos activos y resultados pendientes son solo memoria de demo, igual que `SessionManager`; reinicio o pérdida de sesión puede perderlos. |

## 1. Contexto y alcance

### 1.1 Lecturas obligatorias antes de implementar

1. `AGENTS.md`, en especial la decisión #11.
2. `docs/observability.md`; la UI no emite eventos de auditoría.
3. `docs/specs/spec_07.md`, para `BankingOrchestrator.handle_turn`, `OrchestratorResult`, `TurnAction`, `CompositeAuditSink`, `SessionManager` y `detect_language`.
4. `src/ai_banking_customer_service/config.py`, para conservar el patrón `str` + propiedad `*_full_path` de rutas configurables.
5. `pyproject.toml` y `uv.lock`, para conservar los pins de esta spec.

Spec #8 consume el contrato público de Spec #7. `SAFE_TEMPLATES` sigue siendo un detalle interno del orquestador y no es una dependencia de la UI.

### 1.2 Incluye

- Entry point `app/chainlit_app.py`.
- Composition root `app/bootstrap.py`.
- Helpers y templates ES/PT en `app/ui_helpers.py`.
- Identidad demo tipada y sesión de conversación estable.
- Bridge async/sync, timeout, stop cooperativo y reconciliación tardía.
- Validación fail-closed de la configuración HTML en startup.
- Tests unitarios, de bootstrap/startup, de contrato de Chainlit y smoke portable.

### 1.3 No incluye

- Lógica de negocio, política, gobierno, auditoría o llamadas directas a services desde la UI.
- Cambios al orquestador, tools, services o `CompositeAuditSink`.
- Autenticación real, persistencia durable, streaming, archivos o widgets interactivos.
- Sanitización adicional de `OrchestratorResult.response_text`; Spec #7 ya entrega texto aprobado o un template seguro.
- Uso de `cl.context`, import de `SAFE_TEMPLATES` o emisión de eventos de auditoría.
- Un cliente de pruebas privado/no soportado de Chainlit.

## 2. Baseline verificado de Chainlit 2.12.0

La implementación se fija a estas APIs observadas en la distribución instalada:

| Superficie | Contrato verificado |
| --- | --- |
| Handler de mensaje | `@cl.on_message` sobre un handler async que recibe `cl.Message`. |
| Stop del usuario | `@cl.on_stop` sobre un handler async sin argumentos. El runtime 2.12.0 cancela primero el task del mensaje y luego espera este hook. |
| Envío | `await cl.Message(content=...).send()`. |
| Sesión | `cl.user_session.get(key)` y `cl.user_session.set(key, value)`. |
| CLI | `chainlit run <target>` admite `--headless`, `--host`, `--port` y `--ci`. |
| Configuración | Se carga desde `<app-root>/.chainlit/config.toml`. En este proyecto `<app-root>` es la raíz del repositorio porque el comando se ejecuta desde allí. |
| HTML | La clave efectiva es `[features].unsafe_allow_html`; debe ser `false`. |
| Testing | El wheel no ofrece un test client oficial soportado. No se accede a internals para simular uno. |

Los tests de contrato deben volver a comprobar esta superficie si cambia cualquiera de los pins. No hay lenguaje provisional ni selección condicional de estrategia: para este baseline se implementan siempre contratos y smoke.

## 3. Arquitectura y propiedad

```text
app/
├── __init__.py
├── chainlit_app.py     # handlers, estado de entrega y bridge
├── bootstrap.py        # único composition root
└── ui_helpers.py       # validación, idioma, templates y render

<project-root>/.chainlit/
└── config.toml
```

Reglas:

1. `chainlit_app.py` importa `build_orchestrator`, pero no construye dependencias al importar.
2. `bootstrap.py` es el único lugar que compone dependencias reales.
3. La instancia del orquestador se crea de forma lazy en la primera invocación aceptada.
4. El factory lazy vive detrás de una variable inyectable, por ejemplo `_orchestrator_factory: Callable[[], BankingOrchestrator] = build_orchestrator`; los tests sustituyen esa variable sin red ni credenciales reales.
5. La validación de `.chainlit/config.toml` no pertenece al bootstrap lazy: ocurre en `chainlit_app.py` durante import/startup.

## 4. Configuración y composition root

### 4.1 Campos nuevos de `Settings`

Todos los campos futuros quedan enumerados aquí; no hay configuración implícita:

| Campo | Tipo | Default | Variable en `.env.example` |
| --- | --- | --- | --- |
| `demo_customer_id` | `str` | `"customer-hackathon-demo"` | `DEMO_CUSTOMER_ID` |
| `typesafe_timeout_seconds` | `float` | `10.0` | `TYPESAFE_TIMEOUT_SECONDS` |
| `audit_log_path` | `str` | `"data/state/audit/audit.jsonl"` | `AUDIT_LOG_PATH` |
| `audit_fallback_path` | `str` | `"data/state/audit/audit_fallback.jsonl"` | `AUDIT_FALLBACK_PATH` |
| `session_max_messages` | `int` | `50` | `SESSION_MAX_MESSAGES` |
| `session_ttl_seconds` | `int` | `1800` | `SESSION_TTL_SECONDS` |

Propiedades obligatorias:

```python
@property
def audit_log_full_path(self) -> Path:
    return PROJECT_ROOT / self.audit_log_path

@property
def audit_fallback_full_path(self) -> Path:
    return PROJECT_ROOT / self.audit_fallback_path
```

Como `sandbox_path` y `state_path`, los campos de ruta permanecen como `str`; el acceso de filesystem usa las propiedades resueltas contra `PROJECT_ROOT`.

Validadores obligatorios:

- `demo_customer_id`, `audit_log_path` y `audit_fallback_path`: `str` no vacío después de `strip`.
- `typesafe_timeout_seconds`: número finito y `> 0`; `bool` no es válido.
- `session_max_messages` y `session_ttl_seconds`: `int > 0`; `bool` no es válido.

`.env.example` debe listar las seis variables con los defaults no secretos anteriores.

### 4.2 Construcción exacta

`build_orchestrator() -> BankingOrchestrator` construye, en este orden:

1. `GovernanceThresholds.from_policy(policy.governance)`.
2. `ToolGatingThresholds.from_policy(policy.tool_gating)`.
3. `OutputScreeningThresholds.from_policy(policy.output_screening)`.
4. El loader exacto `ai_banking_customer_service.tools.get_dispute_context.get_dispute_context`.
5. `JsonlAuditSink(settings.audit_log_full_path)` y `JsonlAuditSink(settings.audit_fallback_full_path)`.
6. Un solo `CompositeAuditSink(primary_sink, fallback_sink)`.
7. `JevClient` con `settings.typesafe_api_key`, `settings.typesafe_default_model` y `settings.typesafe_timeout_seconds`.
8. `GovernanceAdapter` y luego `GovernanceHooks`.
9. `SessionManager(max_messages_per_session=settings.session_max_messages, ttl_seconds=settings.session_ttl_seconds)`.
10. `BankingOrchestrator` con el mismo objeto `CompositeAuditSink` entregado al adapter.

Los dos sinks siempre existen. El adapter y el orquestador comparten identidad (`is`), no solo valores equivalentes. La UI nunca hardcodea `demo_customer_id`.

### 4.3 Validación HTML durante startup

`chainlit_app.py` usa únicamente `tomllib` de la stdlib para leer el archivo committed `<project-root>/.chainlit/config.toml`. El algoritmo es:

1. Resolver el path desde `PROJECT_ROOT`.
2. Abrir y parsear TOML.
3. Exigir que `features` sea una tabla y que `features.get("unsafe_allow_html") is False`.
4. Ante archivo ausente, TOML inválido, tabla ausente, clave ausente o cualquier valor distinto del booleano `false`, lanzar `RuntimeError` seguro.
5. Ejecutar la validación al importar `chainlit_app.py`, antes de servir handlers y fuera de `_get_orchestrator()`.

La función acepta un path inyectable para tests unitarios, pero la llamada de startup usa siempre el path committed. La configuración mínima obligatoria contiene:

```toml
[features]
unsafe_allow_html = false
```

## 5. Identidad e idioma

- `session_id` identifica la conversación y usa el valor reservado `cl.user_session.get("id")` que Chainlit 2.12.0 establece para cada chat.
- `customer_id` identifica al cliente demo y proviene de `settings.demo_customer_id`.
- El ID de Chainlit se usa solo como `session_id`, nunca como `customer_id`.

El handler calcula primero el idioma desde el texto recibido. Después, `get_session_id()` exige que el valor reservado sea un `str` no vacío. Si falta o es inválido, responde con `internal_error` en ese idioma mediante el sender seguro con `session_id=None`; el logger omite el campo ausente. No crea UUID, `ActiveTurn` ni llamada al orquestador. Así no existe una secuencia `get`/`set` propia que pueda asignar dos IDs durante primeros mensajes concurrentes. `on_stop` consulta la misma clave reservada y no crea identidad.

`get_customer_id()` no recibe `session_id` y devuelve la Settings tipada. El idioma se conserva durante ejecución, timeout y reconciliación.

## 6. Modelo de estado por sesión

### 6.1 Tipos normativos

```python
type Language = Literal["es", "pt"]

@dataclass
class ActiveTurn:
    task: asyncio.Task[OrchestratorResult]
    cancel_signal: threading.Event
    source_text: str
    language: Language
    monitor: asyncio.Task[None] | None = None

@dataclass
class PendingTurnResult:
    kind: Literal["result", "internal_error"]
    source_text: str
    language: Language
    result: OrchestratorResult | None
    delivery_claimed: bool = False
```

Invariante de `PendingTurnResult`:

- `kind == "result"` exige un `result` retornado normalmente por el orquestador.
- `kind == "internal_error"` exige `result is None` y representa únicamente el outcome seguro localizado; nunca conserva la excepción.

Estado global del proceso:

```python
_active_turns: dict[str, ActiveTurn] = {}
_pending_results: dict[str, PendingTurnResult] = {}
_background_monitors: set[asyncio.Task[None]] = set()
```

El set de monitores es una referencia fuerte. Cada monitor se agrega al crearlo y registra `task.add_done_callback(_background_monitors.discard)`.

### 6.2 Invariantes de propiedad

1. Mientras `_active_turns` contenga `session_id`, todo mensaje nuevo se rechaza con `turn_in_progress`, incluso si `active.task.done()` es verdadero.
2. Solo el owner original o su monitor puede transicionar esa entrada.
3. Toda mutación de cleanup comprueba identidad: `_active_turns.get(session_id) is active`; la remoción de pending comprueba `_pending_results.get(session_id) is pending`.
4. Para entregar un pending, el callback comprueba y cambia `delivery_claimed` de `False` a `True` sin `await`. Otro callback que encuentre el mismo pending reclamado responde `reconciliation_in_progress` y retorna. Ante fallo o cancelación del render, el owner restablece el claim por identidad; ante éxito lo elimina por identidad.
5. Las transiciones de mapas y claims no contienen `await`; son atómicas respecto del event loop.
6. `_ensure_monitor(session_id, active)` crea uno solo cuando la identidad sigue vigente, el task no terminó y `active.monitor is None`; asigna la referencia antes de ceder control.
7. Ningún cleanup antiguo puede borrar o entregar dos veces un turno o resultado posterior de la misma sesión.

### 6.3 Límite de durabilidad

Este estado tiene el mismo alcance in-memory/demo-only de `SessionManager`. Un reinicio del proceso, una desconexión que pierda la sesión o un despliegue con procesos no afines puede perder el turno activo o su resultado pendiente. La spec no promete entrega durable ni reconciliación entre procesos.

## 7. Algoritmo normativo de `on_message`

### 7.1 Orden de admisión

Para cada mensaje:

1. Detectar el idioma del texto recibido.
2. Obtener el `session_id` reservado de Chainlit. Si es inválido, enviar `internal_error` en el idioma detectado con `session_id=None` y retornar sin crear estado.
3. Si existe cualquier `ActiveTurn`, enviar `turn_in_progress` mediante `_send_ui_message` y retornar. No inspeccionar `task.done()` para admitir trabajo.
4. Si existe `PendingTurnResult`, reclamarlo atómicamente. Si ya está reclamado, enviar `reconciliation_in_progress` y retornar. El owner renderiza con el `source_text` e idioma preservados; lo remueve solo si el render devuelve `True`, o libera el claim por identidad si falla/cancela. Retornar siempre: el mensaje recibido actúa únicamente como trigger de reconciliación y nunca se valida ni se entrega al orquestador.
5. Validar el nuevo texto: rechazar vacío/whitespace y longitud mayor que `MAX_MESSAGE_CHARS = 4000`, medido con `len()` sobre el original, sin truncar.
6. Obtener el orquestador lazy dentro de una rama protegida. Si el factory lanza, registrar solo `exception_type`, enviar `internal_error` y retornar sin crear `ActiveTurn`.
7. Crear `threading.Event`, crear exactamente un task con `asyncio.create_task(asyncio.to_thread(orchestrator.handle_turn, ...))` y registrar un `ActiveTurn` antes del primer `await`.
8. Ejecutar las esperas de la sección 7.2.
9. Convertir terminación normal en pending `kind="result"`; convertir excepción normal en pending `kind="internal_error"` sin texto crudo.
10. El owner conserva el `ActiveTurn` durante su intento inmediato de render. Así otro callback solo recibe `turn_in_progress`.
11. Antes del render, publicar y reclamar el pending con identidad vigente. Si el render tiene éxito, retirarlo por identidad; si falla o es cancelado, conservarlo y liberar el claim. Después, retirar el `ActiveTurn` por identidad. `CancelledError` se relanza.

Argumentos exactos de `handle_turn`:

```text
message=active.source_text
session_id=session_id
customer_id=get_customer_id()
cancel_signal=active.cancel_signal
```

### 7.2 Las dos esperas con deadline

Constantes:

```python
TURN_TIMEOUT_SECONDS = 60
THREAD_TERMINATION_TIMEOUT_SECONDS = 5
```

Primera espera:

```python
await asyncio.wait_for(asyncio.shield(active.task), TURN_TIMEOUT_SECONDS)
```

Si vence y el task sigue pendiente:

1. `active.cancel_signal.set()`.
2. Esperar el mismo task, no uno nuevo, con:

```python
await asyncio.wait_for(
    asyncio.shield(active.task),
    THREAD_TERMINATION_TIMEOUT_SECONDS,
)
```

3. Si también vence y el task sigue pendiente, asegurar exactamente un monitor, conservar `ActiveTurn`, enviar `timeout_exceeded` por el sender seguro y retornar.

Un `TimeoutError` lanzado por el propio worker es una excepción normal, no un vencimiento. Cada rama comprueba `active.task.done()`: si ya terminó, consume `task.result()` para recuperar resultado o excepción. El `except Exception` exterior común cubre excepciones normales provenientes tanto de la espera inicial como de la espera de gracia y las convierte en `internal_error` seguro.

### 7.3 Cancelación esperada del handler

En Chainlit 2.12.0 el stop del usuario cancela el task del mensaje antes de invocar `on_stop`; `asyncio.CancelledError` es por tanto una ruta esperada. También cubre cancelaciones externas y se captura por separado:

1. Activar `cancel_signal`.
2. Si `active.task.done()`, consumirlo y publicar antes de remover: resultado normal como pending `result`; cancelación/excepción del task como pending `internal_error`.
3. Si sigue pendiente, llamar `_ensure_monitor`; no remover `ActiveTurn`.
4. Relanzar siempre `CancelledError`.

Si la cancelación ocurre durante render, el pending ya fue publicado: se conserva, se retira el `ActiveTurn` solo por identidad y se relanza.

## 8. Stop y monitor tardío

### 8.1 `@cl.on_stop`

El handler de stop:

1. lee la clave reservada `id` con `cl.user_session.get` y valida que sea un `str` no vacío;
2. si es válida, busca el `ActiveTurn` actual;
3. si existe, ejecuta idempotentemente `active.cancel_signal.set()`;
4. no cancela el thread, no inventa un resultado y no remueve estado.

El runtime de Chainlit ya canceló el task async del mensaje antes de esperar este hook. La rama `CancelledError` de la sección 7.3 puede activar primero la misma señal; ambas escrituras son idempotentes. El orquestador interpreta cooperativamente la señal según Spec #7 y el monitor conserva su resultado tardío.

### 8.2 Monitor

El monitor espera el mismo task protegido, nunca ejecuta otro turno ni renderiza directamente. Al terminar:

- retorno normal → construye pending `result` con `active.source_text` y `active.language`;
- excepción normal o task cancelado → construye pending `internal_error` y registra solo el tipo de excepción permitido;
- antes de remover, comprueba que `_active_turns.get(session_id) is active`;
- con identidad vigente, almacena primero el pending y después remueve el `ActiveTurn`, sin `await` entre ambas operaciones;
- nunca reemplaza estado perteneciente a otro `ActiveTurn`.

No se registra el objeto excepción, su mensaje, traceback, texto fuente ni respuesta. El done-callback retira el monitor del set fuerte.

## 9. Render y mensajes de UI

### 9.1 Sender único

```text
_send_ui_message(content: str, *, session_id: str | None, trace_id: str | None) -> bool
_render_result(result, source_text: str, language: Language) -> bool
_render_pending(pending: PendingTurnResult) -> bool
```

Contrato compartido:

- `_send_ui_message` es la única función que instancia y envía `cl.Message`.
- `session_id` y `trace_id` son metadata opcional: las claves se omiten del log cuando su valor es `None`.
- Devuelve `True` solo si ese contenido se entregó; ante excepción normal registra metadata allowlisted y devuelve `False`.
- Propaga `asyncio.CancelledError` sin convertirlo.
- Todos los mensajes propios de UI —validación, turno activo, timeout, error interno, fallback y resultados— pasan por este sender.
- `_render_result` y `_render_pending` también devuelven `bool`.
- Si falla el contenido principal, `_render_result` puede intentar una sola vez `render_error` mediante el mismo sender, sin recursión; aun si el fallback se entrega, devuelve `False` porque el resultado original no fue entregado.
- Un pending se remueve únicamente cuando su render principal/seguro devuelve `True`. Cualquier fallo deja exactamente el mismo pending intacto.

### 9.2 Mapeo de resultados

| `TurnAction` | Contenido |
| --- | --- |
| `RESPOND` | `result.response_text` |
| `ESCALATE` | `template("escalation_prefix", language) + result.response_text` |
| `BLOCK` | `result.response_text` |
| `ABSTAIN` | `result.response_text` |
| Desconocida | `internal_error`; no mostrar `response_text` |

La UI permite Markdown, pero no HTML inseguro. No vuelve a sanitizar la respuesta aprobada por el orquestador.

### 9.3 Templates exactos

```python
UI_TEMPLATES = {
    "empty_input": {
        "es": "Por favor ingresa un mensaje.",
        "pt": "Por favor insira uma mensagem.",
    },
    "too_long_input": {
        "es": "El mensaje es demasiado largo. Por favor acórtalo.",
        "pt": "A mensagem é muito longa. Por favor encurte-a.",
    },
    "internal_error": {
        "es": "Ocurrió un error interno. Por favor intenta de nuevo.",
        "pt": "Ocorreu um erro interno. Por favor tente novamente.",
    },
    "timeout_exceeded": {
        "es": "La solicitud superó el tiempo de espera. La operación todavía está finalizando. Por favor espera el resultado antes de reintentar.",
        "pt": "A solicitação excedeu o tempo de espera. A operação ainda está finalizando. Por favor aguarde o resultado antes de tentar novamente.",
    },
    "turn_in_progress": {
        "es": "Hay una solicitud en curso. Por favor espera a que termine.",
        "pt": "Há uma solicitação em andamento. Por favor aguarde até que termine.",
    },
    "reconciliation_in_progress": {
        "es": "El resultado anterior se está mostrando. Por favor espera.",
        "pt": "O resultado anterior está sendo exibido. Por favor aguarde.",
    },
    "render_error": {
        "es": "Error al mostrar el mensaje.",
        "pt": "Erro ao exibir a mensagem.",
    },
    "escalation_prefix": {
        "es": "🔴 Escalamiento: ",
        "pt": "🔴 Escalonamento: ",
    },
}
```

`get_template` recibe el idioma ya resuelto. Para el primer mensaje usa el idioma del texto entrante; para pending usa siempre el idioma preservado, no el texto que disparó la reconciliación.

## 10. Seguridad y logging

La UI solo registra códigos estáticos y estos campos opcionales cuando existan: `session_id`, `trace_id` y `exception_type`. No registra texto de usuario, `source_text`, respuesta, argumentos del orquestador, action, escalation type, credenciales, PAN, CVV, tokens, mensaje crudo de excepción ni traceback.

Códigos permitidos: `EMPTY_INPUT`, `TOO_LONG_INPUT`, `ORCHESTRATOR_ERROR`, `TIMEOUT_EXCEEDED`, `TURN_RECONCILED`, `TURN_RECONCILE_ERROR`, `UNKNOWN_ACTION`, `UI_SEND_FAILED` y `RENDER_FAILED`.

Se prohíben `logger.exception(...)`, interpolar la excepción y cualquier `str(error)`/`repr(error)`. La UI no emite eventos del contrato de auditoría; estos logs son diagnósticos operativos minimizados.

## 11. Estrategia TDD y suites obligatorias

Runner autoritativo: `uv run pytest`. La implementación futura deja evidencia RED/GREEN por comportamiento. Tests unitarios y de contrato no usan red, Jev, modelo ni credenciales reales; el smoke solo usa loopback.

### 11.1 Unitarios de app

```text
tests/unit/app/test_ui_helpers.py
tests/unit/app/test_turn_bridge.py
tests/unit/app/test_bootstrap.py
tests/unit/app/test_startup_config.py
```

Cobertura mínima:

- entrada vacía, whitespace, límite 4000 y rechazo >4000 sin truncar;
- templates e idioma ES/PT;
- `Language` definido como `Literal["es", "pt"]`; ID reservado de Chainlit reutilizado; ID ausente/inválido usa el idioma detectado y sender con `session_id=None`, sin crear turno; stop no genera ID;
- dos callbacks sobre el mismo pending producen una sola entrega mediante claim atómico;
- `customer_id` solo desde Settings;
- mapeo exhaustivo de `TurnAction` y fail-closed desconocido;
- sender/render retornan bool, propagan `CancelledError` y usan un único fallback;
- pending permanece ante fallo de render y se elimina por identidad tras entrega;
- mensaje de reconciliación nunca llega al orquestador;
- `ActiveTurn` bloquea otro turno aunque su task esté done;
- ambas esperas usan `shield` y el mismo task;
- timeout activa señal, inicia un solo monitor y conserva el active;
- excepciones normales de la espera inicial y de gracia producen error seguro;
- `CancelledError` preserva task terminado o asegura un monitor y se relanza;
- monitor fuerte publica resultado/error seguro antes de cleanup;
- todos los cleanup fallan de forma segura ante identidad obsoleta;
- bootstrap lazy usa el seam inyectable y no se ejecuta al importar;
- fallo del factory lazy produce `internal_error` localizado sin `ActiveTurn` ni excepción expuesta;
- composition root respeta orden, loader exacto, paths resueltos, sinks no nulos e identidad compartida;
- startup TOML acepta únicamente `unsafe_allow_html = false` explícito y rechaza ausencia, `true`, tipo incorrecto y TOML inválido.

### 11.2 Contratos Chainlit

```text
tests/contract/app/test_chainlit_api.py
```

Debe verificar contra los pins instalados:

- import de Chainlit/LiteralAI con `requests==2.32.5`;
- existencia/utilidad de `cl.on_message` y `cl.on_stop`;
- `cl.Message.send` async;
- `cl.user_session.get` y `.set`;
- ayuda CLI expone `--headless`, `--host`, `--port` y `--ci`;
- versión Chainlit exacta `2.12.0`.

No se crea `tests/runtime/` ni se usa un cliente privado de Chainlit.

## 12. Smoke portable de startup

El smoke inicia el proceso exacto:

```text
<python> -m chainlit run app/chainlit_app.py --headless --host 127.0.0.1 --port <free-port> --ci
```

Contrato de `tests/smoke/test_smoke.py`:

1. reservar un puerto libre en loopback con `socket`, cerrarlo y pasarlo al hijo;
2. iniciar con `subprocess.Popen`, `stdout=DEVNULL` y `stderr=DEVNULL`;
3. hacer polling HTTP acotado a `http://127.0.0.1:<port>`;
4. consultar `proc.poll()` en cada iteración y fallar inmediatamente si el hijo termina;
5. aceptar solo respuesta HTTP exitosa del hijo asociado a ese puerto;
6. usar `finally`: `terminate()`, espera acotada y `kill()` + `wait()` si no termina;
7. funcionar en Windows y POSIX, sin shell ni red externa.

El smoke comprueba únicamente que el servidor inicia y responde. No prueba que un GET construya el orquestador lazy. `test_startup_config.py` verifica el fail-closed HTML y `test_bootstrap.py` verifica composición e inicialización lazy por separado.

Comando manual canónico:

```bash
uv run chainlit run app/chainlit_app.py --headless --host 127.0.0.1 --port 8000 --ci
```

## 13. Archivos de la implementación futura

### Crear

```text
app/__init__.py
app/chainlit_app.py
app/bootstrap.py
app/ui_helpers.py
.chainlit/config.toml
tests/unit/app/test_ui_helpers.py
tests/unit/app/test_turn_bridge.py
tests/unit/app/test_bootstrap.py
tests/unit/app/test_startup_config.py
tests/contract/app/test_chainlit_api.py
tests/smoke/test_smoke.py
```

### Modificar

```text
src/ai_banking_customer_service/config.py
.env.example
docs/STATUS.md
```

La tarea de readiness ya modificó `pyproject.toml` y `uv.lock`; la implementación debe conservar exactamente `chainlit==2.12.0` y `requests==2.32.5`. No se modifica `src/ai_banking_customer_service/agent/`, `governance/`, `tools/` ni `services/`.

`docs/STATUS.md` se modifica solo después de implementar y ejecutar toda la aceptación. Debe registrar únicamente comportamiento observado; esta revisión documental mantiene STATUS futuro y no marca Spec #8 como completada.

## 14. Criterios de aceptación de la implementación

Comandos exactos, obligatorios e incondicionales:

```bash
uv run pytest tests/unit/app/ tests/contract/app/ tests/smoke/ -q
uv run pytest -q
uv run ruff check app/ tests/unit/app/ tests/contract/app/ tests/smoke/
uv run ruff format --check app/ tests/unit/app/ tests/contract/app/ tests/smoke/
```

Además:

- los pins exactos aparecen en `pyproject.toml` y `uv.lock`;
- `.env.example` y Settings contienen todos los campos y validadores de la sección 4.1;
- `.chainlit/config.toml` declara explícitamente `[features].unsafe_allow_html = false`;
- import/startup falla cerrado ante configuración HTML ausente o insegura;
- el orquestador sigue lazy e inyectable, y el loader tiene el nombre exacto de la sección 4.2;
- la UI no contiene negocio, política, gobierno, auditoría ni llamadas directas a services;
- no hay red externa en tests; solo el smoke usa loopback;
- las invariantes de `ActiveTurn`, claim de pending, identidad, monitor fuerte y stop cumplen las secciones 6–8;
- el ID reservado de Chainlit falta cerrado si está ausente/inválido y el factory lazy falla con respuesta segura antes de crear un turno;
- ambos deadlines protegen el mismo task con `asyncio.shield`;
- toda excepción normal de cualquier espera termina en un outcome interno seguro;
- toda salida propia de UI usa `_send_ui_message`, propaga cancelación y conserva pending si no entrega;
- la reconciliación usa el texto/idioma original, se muestra antes de otro turno y consume el mensaje disparador;
- no existe suite `tests/runtime/`, skip permanente ni estrategia condicional;
- el smoke solo acredita startup; los tests separados acreditan configuración y bootstrap;
- `docs/STATUS.md` se actualiza únicamente después del GREEN completo, sin afirmar durabilidad para estado in-memory.
