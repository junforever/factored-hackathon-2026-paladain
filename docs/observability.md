# OBSERVABILITY — Contrato de auditoría de decisiones

> Propósito: reconstruir **QUÉ decidió el agente y POR QUÉ**, a partir de
> fuentes, reglas de política y registros de ejecución.
> Este documento es el contrato. Toda implementación de observabilidad lo sigue.
> Está diseñado para acoplarse a OpenTelemetry/herramientas de producción sin
> reescribir la lógica de emisión.

---

## 1. Principio

- Cada turno de atención (un mensaje del cliente → una respuesta del agente) genera **un trace** con una secuencia de **eventos de auditoría**.
- Se registra lo observable: entrada, señales de gobierno, reglas aplicadas, tools invocadas, acciones ejecutadas y su verificación, y la respuesta final.
- **No** se registra el chain-of-thought oculto del modelo. No es un artefacto de auditoría.

---

## 2. El Trace

| Campo        | Descripción                                                                |
| ------------ | -------------------------------------------------------------------------- |
| `trace_id`   | Identifica un turno de atención. Todos los eventos del turno lo comparten. |
| `session_id` | Identifica la conversación completa (varios turnos).                       |

---

## 3. Envelope común del evento

Todo evento de auditoría tiene estos campos:

```text
trace_id        str   id del turno
event_id        str   id único del evento
parent_event_id str   id del evento que lo originó (null si es raíz)
timestamp       str   ISO 8601 UTC
component       str   governance | orchestrator | tool | service
event_type      str   input | governance | tool_call | policy | action | escalation | response
customer_id     str   id del cliente (enmascarado según sección 7)
session_id      str   id de la conversación
outcome         str   success | blocked | escalated | failure | abstained
latency_ms      int   duración del evento
tokens          int   tokens consumidos (null si no aplica)
cost_usd        float costo estimado (null si no aplica)
payload         obj   campos específicos del event_type
```

- `latency_ms, tokens y cost_usd` alimentan las métricas de **Operating efficiency**.
- `outcome` alimenta **Safe automated resolution, Unsafe outcomes y Escalation quality**.

## 4. Tipos de evento y su payload

| event_type | Qué registra                  | payload                                                  |
| ---------- | ----------------------------- | -------------------------------------------------------- |
| input      | Mensaje recibido del cliente  | text, language (es/pt), channel                          |
| governance | Una decisión de Jev           | stage, signals, decision, reason, thresholds             |
| tool_call  | Invocación de una tool        | tool_name, args, result_status, result_summary, verified |
| policy     | Regla dura aplicada           | rule_id, inputs, decision, reason                        |
| action     | Acción ejecutada y verificada | action_name, target_id, executed, verification           |
| escalation | Handoff a humano              | reason, handoff_id, priority, unresolved_questions_count |
| response   | Respuesta final al cliente    | grounded_in, action_summary, language                    |

### Detalle de payloads

**governance:**

```
stage      str   input_screening | intent_routing | tool_gating | output_screening
signals    obj   señales crudas de Jev (noul, choice, probabilities, score, confidence)
decision   str   allow | block | review
reason     str   por qué se tomó la decisión
thresholds obj   umbrales aplicados
```

**tool_call:**

```
tool_name      str   nombre de la tool
args           obj   argumentos sanitizados
result_status  str   success | error
result_summary str   resumen del resultado (no el resultado completo si es extenso)
verified       bool  si el resultado fue verificado
```

**action:**

```
action_name  str   ej. block_card
target_id    str   product_id afectado
executed     bool
verification str   ej. confirmed_blocked | already_blocked | block_not_confirmed
```

**response:**

```
grounded_in    list  fuentes usadas, ej. ["tool:get_dispute_context", "record:CMP-..."]
action_summary str   qué se hizo por el cliente
language       str   es | pt
```

## 5. Puntos de emisión

Cada componente emite los tipos de evento que le corresponden:

| Componente             | Emite                       | Ubicación   |
| ---------------------- | --------------------------- | ----------- |
| Orquestador            | input, response, escalation | agent/      |
| Capa de gobierno (Jev) | governance                  | governance/ |
| Tools                  | tool_call                   | tools/      |
| Módulo de política     | policy                      | policies/   |
| Servicios mock         | action                      | services/   |

## 6. AuditSink: interfaz única de emisión

Todos los componentes emiten a través de una única interfaz. Esto hace la implementación intercambiable.

```python
class AuditSink(Protocol):
    def emit(self, event: dict) -> None: ...
```

Implementación: JsonlAuditSink, que escribe cada evento como una línea JSON en settings.state_dir / "audit" / "audit.jsonl".

```text
src/ai_banking_customer_service/observability/
├── __init__.py
├── contract.py     # envelope, event_types, validaciones del evento
└── sink.py         # AuditSink (Protocol) + JsonlAuditSink
```

## 7. Lo que NO se registra

- PAN completo, CVV, credenciales, tokens ni secretos.
- Chain-of-thought oculto del modelo.
- PII del cliente más allá del customer_id permitido. Enmascarar antes de emitir.

## 8. Mapeo a producción

El contrato se acopla a OpenTelemetry sin cambiar la lógica de emisión:

| Contrato                          | Producción                                          |
| --------------------------------- | --------------------------------------------------- |
| trace_id/event_id/parent_event_id | OTel trace_id/span_id/parent_span_id                |
| evento                            | span OTel                                           |
| campos del envelope y payload     | atributos del span                                  |
| AuditSink                         | exporter OTel → collector → Loki/Prometheus/Grafana |
| audit.jsonl                       | reemplazado por el exporter                         |

Se usa JsonlAuditSink. La interfaz AuditSink es el punto de intercambio.
