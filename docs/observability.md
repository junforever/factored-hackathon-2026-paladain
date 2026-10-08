# OBSERVABILITY — Contrato de auditoría de decisiones

> Propósito: reconstruir **QUÉ decidió el agente y POR QUÉ**, a partir de
> fuentes, reglas de política y registros de ejecución.
> Este documento describe el comportamiento implementado por Specs #6 y #7.

---

## 1. Principio

- Cada turno de atención genera **un trace** con una secuencia correlacionada de eventos.
- Se registra lo observable: entrada, gobierno, tools, reglas, acciones verificadas, escalamiento y respuesta.
- **No** se registra el chain-of-thought oculto del modelo.
- Una acción solo se reporta como exitosa cuando existe evidencia terminal verificable.
- La auditoría falla cerrado: un fallback diagnóstico nunca equivale a persistencia durable.

## 2. Trace y envelope común

| Campo | Tipo | Contrato |
| --- | --- | --- |
| `trace_id` | `str` | Identifica un turno; todos sus eventos lo comparten. |
| `event_id` | `str` | Identificador único del evento. |
| `parent_event_id` | `str \| null` | Último evento durable que originó el evento; `null` solo para una raíz o si no existe ancestro durable. |
| `timestamp` | `str` | ISO 8601 en UTC. |
| `component` | `str` | `governance \| orchestrator \| tool \| service`. |
| `event_type` | `str` | `input \| governance \| tool_call \| policy \| action \| escalation \| response`. |
| `customer_id` | `str` | Identificador enmascarado antes de emitir. |
| `session_id` | `str` | Identifica la conversación entre varios turnos. |
| `outcome` | `str` | `success \| blocked \| escalated \| failure \| abstained`. |
| `latency_ms` | `int` | Entero no negativo. |
| `tokens` | `int \| null` | Tokens consumidos; entero no negativo cuando aplica. |
| `cost_usd` | `float \| null` | Costo finito no negativo cuando aplica. |
| `payload` | `obj` | Proyección específica, sanitizada y acotada. |

Los eventos del orquestador usan exactamente este envelope, con
`component="orchestrator"`, `tokens=null` y `cost_usd=null`. `contract.py`
valida campos requeridos, dominios, tipos, finitud y valores no negativos antes
de que `JsonlAuditSink` persista JSONL con `allow_nan=False`.

## 3. Payloads del orquestador

### 3.1 `input`

```text
text           str   mensaje sanitizado, máximo 2000 code points
language       str   es | pt
channel        str   api
text_truncated bool  opcional; solo true cuando el texto sanitizado fue recortado
```

Usa `outcome="success"` y es la única raíz cuando su persistencia primaria tiene
éxito.

### 3.2 `tool_call`

Se emite exactamente un `tool_call` por ID válido único y uno por intento sin ID.
Una tool bloqueada antes de ejecutarse también genera exactamente un evento.
Retries o IDs duplicados inesperados se condensan en un evento de error.

```text
tool_name      str   nombre validado o unknown
tool_use_id    str   ID validado o ""; campo requerido
args           obj   proyección auditable y sanitizada
result_status  str   success | error | blocked
result_summary str   resumen sanitizado, máximo 500 code points
verified       bool  evidencia terminal cumple el contrato de la tool
authorization_verified bool  autorización explícita de producto acreditada por el adapter
correlation    str   opcional; routing_fallback cuando falta correlación válida
orphaned       bool  opcional; solo true para descendencia sin padre durable
evidence       obj   evidencia canónica runtime de la ocurrencia (ver §3.2.1)
```

Proyección permitida de `args`:

| Tool | Campos auditables |
| --- | --- |
| `get_dispute_context` | `complaint_id` (máximo 128) |
| `get_recent_transactions` | `complaint_id` (máximo 128), `days_before`, `limit` |
| `block_card` | `complaint_id` (máximo 128), `confirmed_by_customer` |
| `escalate_case` | `complaint_id` (máximo 128), `reason` (máximo 500), `unresolved_questions_count`, `agent_notes_present` |
| Nombre o argumentos malformados | `{}` |

No se auditan las preguntas sin resolver ni las notas del agente. El resumen usa,
en orden de precedencia: incertidumbre por retry/duplicado, bloqueo previo,
tipo de excepción sanitizado, cancelación, resultado ausente, proyección escalar
de acción, error de lectura o `success`. Nunca contiene una excepción cruda.

`verified=true` requiere que no haya retry, duplicado, excepción ni cancelación y,
además, evidencia de lectura exitosa, verificación canónica de acción o el
predicado completo de escalamiento persistido. Para las cuatro tools sensibles,
`authorization_verified` siempre está presente y solo es `true` cuando el
contexto creado por el adapter contiene autorización explícita válida; no se
infiere desde la reclamación, el producto ni el resultado de la ejecución.

#### 3.2.1 Evidencia canónica runtime (`evidence`)

A partir de Spec #09A1, cada evento `tool_call` incluye exactamente un bloque de
evidencia canónica (`evidence`) que describe una sola ocurrencia causal de tool.
El resto del contrato del payload no cambia.

El bloque contiene cinco dimensiones causales y metadatos cerrados:

```text
ordinal        int   posición canónica de la ocurrencia (>= 0)
authorization  obj   { state, reason_code, verified }
missing_data   obj   { state, detected }
governance     obj   { stage, action, reason_code }
execution      obj   { state }
verification   obj   { outcome, verified }
truncated      bool  opcional; solo true cuando se excede el límite de ocurrencias
invalid        bool  opcional; solo true cuando el bloque es fail-closed por inconsistencia
```

`evidence` es obligatorio en el payload de `tool_call`. Las claves requeridas son
`ordinal`, `authorization`, `missing_data`, `governance`, `execution` y
`verification`. Las únicas claves opcionales son `truncated` e `invalid`.

**Vocabularios congelados**

Las cadenas deben pertenecer exactamente a las siguientes allowlists (spelling y
 casing idénticos al código en `src/ai_banking_customer_service/observability/contract.py`):

- `authorization.state`: `allowed`, `denied`, `unavailable`, `not_evaluated`, `invalid`.
- `authorization.reason_code`: `authorized`, `not_authenticated`, `product_not_authorized`, `authorization_unavailable`, `invalid_authorization_result`, o `null`.
- `authorization.verified`: `bool` estricto.
- `missing_data.state`: `verified_missing`, `verified_present`, `unknown`, `invalid`.
- `missing_data.detected`: `bool` estricto.
- `governance.stage`: `tool_gating`.
- `governance.action`: `allow`, `block`.
- `governance.reason_code`: `invalid_tool_name`, `invalid_tool_input`, `invalid_complaint_id`, `invalid_invocation_state`, `missing_merchant:clarification`, `TOOL_GATING_VALIDATION_ERROR`, `JEV_ERROR`, `TOOL_GATING_DETERMINISTIC_BLOCK`, `INVALID_METADATA`, `INVALID_SIGNAL`, `TOOL_GATING_ALLOW`, `TOOL_GATING_BLOCK_LOW_INTENT_MATCH`, o `null`.
- `execution.state`: `success`, `failure`, `blocked`, `unknown`, `invalid`.
- `verification.outcome`: `verified`, `unverified`, `not_applicable`, `invalid`.
- `verification.verified`: `bool` estricto.

Cada código tiene como máximo 64 code points. El bloque serializado no puede
superar 8 KiB. Se permite un máximo de 16 ocurrencias por trace; la ocurrencia
17 y siguientes se reemplazan por un bloque cerrado con `truncated: true`
(todos los estados en `invalid`, acción de gobierno `block`, booleanos `False`,
`invalid: true`). El evento `tool_call` igual se emite.

**Correlación**

La decisión de gobierno se une a la ocurrencia por el `toolUseId` exacto de la
entrada `tool_gating` correspondiente. No se correlaciona por nombre de tool,
similitud de argumentos, orden supuesto, `case_id` ni ningún ID bancario.

**Fail-closed**

Cualquiera de las siguientes condiciones produce el bloque cerrado `invalid: true`
(todos los estados en `invalid`, acción de gobierno `block`, booleanos `False`):

- unión ambigua entre la ocurrencia y su entrada de gobierno;
- retry o duplicado del intento;
- lineage huérfano o resultado no durable;
- booleanos no estrictos (`bool` subclases o enteros usados como booleanos);
- combinaciones imposibles entre `state`/`reason_code`/`verified` (por ejemplo,
  `allowed` sin `authorized`/`true`);
- gobierno desconocido o no reconocido (falla a `block`);
- bloque truncado por exceso de ocurrencias.

Este bloque `invalid` nunca cuenta como evidencia positiva.

**Privacidad**

El bloque de evidencia nunca transporta:

- `complaint_id`, `product_id`, `customer_id`;
- IDs de transacción, handoff o escalamiento;
- excepciones, mensajes o textos libres;
- argumentos o resultados completos de tools;
- state, score, probabilidad, metadata o razón de Jev.

`validate_event` rechaza el payload antes de escribir al sink si `evidence`
está presente y no cumple el contrato.

### 3.3 `escalation`

```text
reason                     str   razón sanitizada, máximo 500 code points
priority                   str   máximo 50 code points o unknown
unresolved_questions_count int   cantidad, no contenido
handoff_id                 str   opcional, máximo 128 code points
orphaned                   bool  opcional; solo true
```

Para un terminal no originado por `escalate_case`, `reason` es el tipo de
escalamiento, `priority="unknown"` y el conteo es `0`; `handoff_id` se omite.
Para un `escalate_case` verificado con `confirmed_persisted`, se proyectan
`handoff_id`, prioridad, razón de `handoff_metadata` y cantidad de preguntas.
El handoff completo nunca entra al evento.

### 3.4 `response`

```text
grounded_in   list[str]  máximo 8 fuentes únicas, cada una de hasta 200 code points
action_summary str       resumen sanitizado, máximo 500 code points
language       str       es | pt
orphaned       bool      opcional; solo true
```

Las únicas fuentes admitidas son `model:screened`, `orchestrator:template`,
`tool:<tool_name>`, `action:<action_name>` y `handoff:<handoff_id>`. La respuesta
completa no se repite en el payload. Los outcomes son: `RESPOND → success`,
`BLOCK → blocked`, `ESCALATE → escalated` y `ABSTAIN → abstained`.

## 4. Payload de gobierno y propagación huérfana

El `GovernanceAdapter` emite un evento por etapa ejecutada:
`input_screening`, `intent_routing`, `tool_gating` y `output_screening`.

```text
stage       str        etapa de gobierno
signals     obj        señales minimizadas de Jev
decision    str        block | review | allow
reasons     list[str]  razones normalizadas
thresholds  obj        umbrales efectivos
orphaned    bool       opcional; solo true
```

Las entradas públicas `screen_and_route`, `gate_tool_call` y `screen_output`
aceptan el keyword-only `orphaned: bool = False`. Un valor no booleano lanza
`TypeError`. Los hooks pasan únicamente ese booleano desde `invocation_state`;
el adapter no recibe ni consulta el estado completo.

La correlación interna por tool conserva la observabilidad de autorización solo
como `allowed | denied | unavailable | not_evaluated`, el reason code cerrado
`authorized | not_authenticated | product_not_authorized | authorization_unavailable | invalid_authorization_result`
(o `null` cuando no fue evaluada) y el booleano canónico. No conserva principal,
IDs bancarios, respuesta o error del provider, paths, credenciales, texto libre,
state de Jev ni representación/hash del sentinel. El evento `tool_call` proyecta
únicamente el booleano.

Si el evento `input` no persiste, el orquestador conserva
`input_event_id=None`, activa `audit_orphaned=True` y todos los payloads
descendientes agregan `orphaned=true`. Con `False`, la clave se omite. Esta
marca no inventa ni modifica padres: indica que falta persistencia durable en la
cadena.

## 5. Lineage y fallback de correlación

Reglas de parentesco:

1. `input` es la única raíz durable.
2. `input_screening` deriva de `input`; `intent_routing` deriva del screening.
3. Los `tool_gating` concurrentes son hermanos bajo routing.
4. Cada `tool_call` usa el evento de gating asociado por el `toolUseId` exacto.
5. Si el ID, la entrada de gobierno o su `event_id` faltan o son inválidos, el
   padre vuelve a `routing_event_id` y el payload agrega
   `correlation="routing_fallback"`.
6. `output_screening` deriva del último `tool_call` durable; sin tools, de routing.
7. `escalation` deriva del evento durable que determina el terminal y `response`
   deriva de screening, governance bloqueante, escalation o el último ancestro
   durable aplicable.
8. Un `event_id` cuya persistencia primaria falló nunca se usa como padre.

```text
input
└── input_screening
    └── intent_routing
        ├── tool_gating_A
        │   └── tool_call_A
        ├── tool_gating_B
        │   └── tool_call_B
        └── output_screening
            └── response
```

El camino de escalamiento agrega `escalation` antes de `response`. Un bloqueo de
gobierno enlaza `response(blocked)` directamente con el governance bloqueante.

## 6. Sinks y semántica de fallos

```python
class AuditSink(Protocol):
    def emit(self, event: dict) -> None: ...
```

`JsonlAuditSink` valida y escribe una línea JSON por evento.
`CompositeAuditSink(primary_sink, fallback_sink)` se comparte por identidad entre
adapter y orquestador. Su contrato es:

1. intentar el primario una sola vez;
2. si falla, intentar el fallback una sola vez como copia diagnóstica best-effort;
3. lanzar siempre `AuditPersistenceError`, incluso si el fallback acepta el evento;
4. conservar las excepciones primaria/secundaria sin incluir evento ni secretos en
   el mensaje;
5. no hacer retries internos.

El fallback no es durable y no transforma un fallo en éxito. El adapter propaga
`AuditPersistenceError`; el orquestador convierte el fallo de su propio emit en
`None` y solo conserva el ID cuando el primario tuvo éxito.

| Momento del fallo | Semántica implementada |
| --- | --- |
| `input` | Continúa con descendencia huérfana. |
| Input screening, routing o tool gating | Gobierno falla cerrado; no se inicia una nueva acción. |
| Output screening | Escalamiento seguro `OUTPUT_SCREENING_REVIEW`; no se entrega texto del modelo. |
| `tool_call` de lectura | Marca descendencia huérfana y continúa al terminal seguro. |
| `tool_call` de acción después de posible ejecución | `UNCERTAIN_SIDE_EFFECT`; no reejecuta ni inicia otra acción. |
| `escalation` o `response` | No repite side effects; usa el último ancestro durable para eventos posteriores. |

## 7. Sanitización y datos prohibidos

Antes de emitir, el payload completo pasa por `sanitize_json_structure`; después
se aplican los límites por campo medidos en code points. `customer_id` se
enmascara. Solo se conservan proyecciones allowlisted de argumentos, resultados,
hechos y acciones.

Nunca se registran:

- PAN completo, CVV, credenciales, tokens o secretos;
- excepciones crudas;
- mensaje sin sanitizar;
- handoff completo, preguntas o notas completas;
- objetos de modelo, estado completo de hooks o `invocation_state`;
- chain-of-thought oculto.

## 8. Responsabilidad de emisión

| Componente | Emite | Ubicación |
| --- | --- | --- |
| Orquestador | `input`, `tool_call`, `escalation`, `response` | `agent/` |
| Adaptador de gobierno | `governance` | `governance/` |
| Módulo de política | `policy` | `policies/` |
| Servicios mock | `action` | `services/` |

Las tools y sus wrappers no emiten `tool_call`; el orquestador centraliza ese
evento para incluir trace, correlación, latencia, sanitización y verificación sin
duplicados.

## 9. Mapeo a producción

| Contrato | Producción |
| --- | --- |
| `trace_id/event_id/parent_event_id` | OTel `trace_id/span_id/parent_span_id` |
| Evento | span OTel |
| Envelope y payload | atributos del span |
| `AuditSink` | exporter OTel → collector → Loki/Prometheus/Grafana |
| JSONL local | reemplazado por exporter durable |

La interfaz `AuditSink` es el punto de intercambio; cambiar el exporter no cambia
la lógica de decisión ni la semántica fail-closed.
