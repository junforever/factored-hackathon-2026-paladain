# SPEC #9C — Atribución y optimización de latencia privacy-safe

> **Estado:** especificación normativa lista para implementar. Su implementación
> permanece bloqueada hasta que el código de 09A y 09B —no solo sus documentos—
> esté implementado, revisado y congelado. Extiende Specs #9, #9A y #9B; no afirma
> que la instrumentación, las optimizaciones, los tests ni los resultados aquí
> definidos ya existan.
> **Método futuro:** TDD estricto en microciclos RED → GREEN → TRIANGULATE →
> REFACTOR.
> **Lenguaje normativo:** `MUST` y `MUST NOT` expresan requisitos obligatorios.
>
> **Baseline activo y precedencia:** Spec #9 es la base histórica v4. La
> implementación activa usa el sucesor congelado `v1.0.2` y los contratos vigentes
> de configuración y manifest; `sandbox_file` y `sandbox_sha256` son campos
> obligatorios de la configuración actual. Los ejemplos `v1.0.0` de Spec #9 son
> históricos y **MUST NOT** restaurarse. Si esos ejemplos entran en conflicto con
> la fuente tipada/configuración vigentes o con 09A–09C, la implementación **MUST**
> detenerse y reconciliar el conflicto explícitamente; **MUST NOT** adivinar.

## 0. Contrato ejecutivo

09C atribuye la latencia de cada turno con evidencia tipada y acotada, y luego
optimiza solo los cuellos de botella demostrados. La velocidad **MUST NOT**
obtenerse omitiendo gobierno, autorización, verificación, auditoría, screening o
aislamiento.

| Tema | Decisión normativa |
| --- | --- |
| Precondición | 09A y 09B **MUST** estar implementadas, revisadas y congeladas antes de crear el baseline 09C. No se optimiza una semántica de seguridad o corrección inestable. |
| Reloj | Toda duración usa reloj monotónico local al proceso; no se restan timestamps de procesos distintos. |
| Atribución | Los spans tienen taxonomía cerrada, límites explícitos y relaciones de nesting. Una suma de spans anidados **MUST NOT** presentarse como wall time. |
| Privacidad | La evidencia temporal contiene solo versiones, etapas cerradas, offsets relativos, duraciones, conteos y percentiles. No contiene texto, argumentos, IDs, paths, excepciones ni chain-of-thought. |
| Baseline | Se congela sobre development versionado, con entorno, modelos, Jev, policy, orden y estado comparables. Held-out **MUST NOT** usarse para profiling o tuning. |
| Optimización | Se aplica la escalera de la sección 6, una unidad revisable por vez, y cada unidad conserva su propio RED/GREEN y boundary de rollback. |
| Concurrencia | Solo operaciones read-only demostrablemente independientes pueden solaparse, con límite explícito. Las escrituras son seriales y nunca especulativas. |
| Gate principal | Sobre un par comparable, p95 development **MUST** mejorar al menos 25% frente al baseline 09C congelado y p50 **MUST NOT** empeorar. |
| Held-out | Tras congelar 09A/09B/09C y pasar development, se permite exactamente una corrida final no reintentada de `v1.0.2`, salvo fallo de infraestructura antes de iniciar cualquier caso. |
| Pitch | Spec #10 consume solo resultados finales medidos. 09C no fabrica ni anticipa claims de pitch. |

### 0.1 Evidencia histórica que motiva el trabajo

La evidencia ya registrada en `docs/STATUS.md` es diagnóstica; no es el baseline
comparable de 09C y **MUST NOT** usarse para ajustar casos held-out.

| Corrida histórica local | p50 | p95 |
| --- | ---: | ---: |
| Held-out final `v1.0.2` | **10,414 ms** | **20,347.35 ms** |
| Corrida grounded anterior | no registrada como comparable | **~19.29 s** |
| Primera corrida grounded | no registrada como comparable | **~12.07 s** |

El p95 final empeoró frente al grounded anterior. Las tres cifras prueban la
necesidad de atribución, pero no prueban causalidad ni comparabilidad de entorno.
El baseline normativo nace solo mediante la sección 5, después del freeze de 09A
y 09B.

### 0.2 Camino corto de implementación

1. Confirmar y registrar que 09A y 09B están implementadas, revisadas, sin gates
   development fallando y congeladas.
2. Instrumentar la taxonomía de la sección 3 con fakes determinísticos y probar
   privacidad, nesting, clocks, timeout y cleanup.
3. Medir y congelar un baseline development comparable según la sección 5.
4. Elegir el primer cuello de botella demostrado y aplicar una sola unidad de la
   escalera de la sección 6.
5. Repetir tests determinísticos y benchmark candidate comparable; revertir la
   unidad si falla cualquier gate funcional, de seguridad o rendimiento.
6. Congelar 09C. Solo entonces aplicar la política held-out de la sección 10.

## 1. Alcance, dependencias y no-objetivos

### 1.1 Dependencias y precedencia

- 09C extiende, no reemplaza, `docs/specs/spec_09.md`,
  `docs/specs/spec_09a.md` y `docs/specs/spec_09b.md`.
- Aunque 09C está normativamente lista, su implementación está bloqueada hasta
  que el código de 09A y 09B —no solo sus especificaciones— esté implementado,
  revisado y congelado.
- 09A **MUST** haber cerrado autorización explícita y evidencia
  `authorization_verified` sin inferir permiso desde `product_id`.
- 09B **MUST** haber cerrado su crosswalk, vocabulario, policy, precedencia
  terminal y verificación de handoff.
- “Congelada” significa: implementación revisada, tests completos verdes,
  development seleccionado y versionado, policy/preguntas/modelos/dependencias
  fijados y ningún defecto abierto que altere corrección, seguridad o evaluación.
- En conflicto, 09C tiene precedencia solo para contrato temporal, protocolo de
  benchmark y optimizaciones. Los contratos funcionales y de seguridad de
  09/09A/09B permanecen vinculantes.
- Esta spec reemplaza únicamente la nota histórica de 09B que decía que
  `spec_09c.md` aún no existía; no altera ninguna otra decisión de 09B.

### 1.2 Incluye

- Taxonomía precisa de spans y cálculo de tiempo inclusivo/exclusivo.
- Evidencia temporal tipada, acotada, versionada y privacy-safe.
- Extensiones mínimas de worker/runner, orquestador, gobierno, auditoría y
  reporte necesarias para medir esa taxonomía.
- Protocolo reproducible de baseline/candidate sobre development.
- Escalera ordenada de optimización y reglas de rollback por unidad.
- Grafo explícito de dependencias para cualquier concurrencia read-only.
- Semántica de error, timeout y cancelación sin efectos huérfanos.
- Gates de aceptación funcionales, de seguridad, privacidad y rendimiento.
- Tests determinísticos sin red/modelo/Jev real antes de cualquier benchmark
  runtime.

### 1.3 No incluye

09C **MUST NOT**:

- implementar o reparar 09A/09B dentro del mismo work unit de rendimiento;
- cambiar terminales, razones de negocio, autorización, clasificación de unsafe,
  definición de SAR o ground truth para obtener mejores tiempos;
- modificar bytes, manifests, hashes o casos held-out `v1.0.2`;
- usar held-out para profiling, selección de optimización, tuning o repetición;
- omitir, agrupar ficticiamente o marcar como cache hit un gate que no ejecutó;
- aumentar timeouts para ocultar una regresión;
- agregar tracing distribuido, APM, collector, base de series temporales,
  dashboard, servicio de benchmark o dependencia nueva;
- crear caché cross-case, global o persistente de datos sensibles;
- paralelizar escrituras, lanzar escrituras especulativas o debilitar aislamiento
  por proceso;
- exponer prompts, respuestas, argumentos de tools, IDs, paths, excepciones,
  estado de Jev, payloads bancarios o chain-of-thought en evidencia temporal;
- prometer p95 absoluto de 15 s si el entorno no está controlado;
- generar slides, narrativa comercial o resultados de Spec #10.

## 2. Fuentes autoritativas antes del primer RED

El implementador **MUST** releer el árbol posterior al freeze de 09A/09B. Como
mínimo:

```text
docs/specs/spec_09.md
docs/specs/spec_09a.md
docs/specs/spec_09b.md
docs/STATUS.md
docs/observability.md
src/ai_banking_customer_service/evaluation/runner.py
src/ai_banking_customer_service/evaluation/worker.py
src/ai_banking_customer_service/evaluation/report.py
src/ai_banking_customer_service/evaluation/classification.py
src/ai_banking_customer_service/agent/orchestrator.py
src/ai_banking_customer_service/governance/adapter.py
src/ai_banking_customer_service/governance/jev/client.py
src/ai_banking_customer_service/observability/contract.py
src/ai_banking_customer_service/observability/sink.py
src/ai_banking_customer_service/config.py
configs/eval.yaml
```

También **MUST** releer los tests de runner, worker, percentiles/reportes,
orquestador, adapter, contrato/sink de observabilidad y config. Si una
optimización cambia el uso de TypeSafe/Jev, **MUST** cargarse primero la skill
`typesafe-ai`; Jev nunca se reemplaza por una regla de velocidad.

El source actual aporta estas restricciones que 09C conserva:

- `run_case` mide hoy una latencia parent-side con `monotonic()` hasta después de
  join y cleanup;
- cada caso usa un hijo nuevo `spawn`, no daemon, y el padre posee timeout, join,
  pipe y cleanup;
- el worker envía un envelope JSON acotado y sanitiza errores;
- gobierno ya mide sus etapas con reloj monotónico y emite `latency_ms` entero;
- el orquestador ya conserva duración normalizada de tools y auditoría fail-closed;
- percentiles actuales usan interpolación lineal inclusiva;
- auditoría valida `latency_ms` entero no negativo y JSON sin NaN;
- `JevClient` crea hoy un cliente SDK por invocación, dato a medir antes de
  proponer reuse, no permiso para cambiarlo de forma anticipada.

## 3. Taxonomía temporal normativa

### 3.1 Enum cerrado

La instrumentación usa exactamente este dominio V1:

```python
class TimingStageV1(str, Enum):
    END_TO_END = "end_to_end"
    PROCESS_STARTUP_COMPOSITION = "process_startup_composition"
    AGENT_TURN = "agent_turn"
    MODEL_INFERENCE = "model_inference"
    INPUT_SCREENING = "input_screening"
    ROUTING = "routing"
    TOOL_GATE = "tool_gate"
    TOOL_EXECUTION = "tool_execution"
    TOOL_VERIFICATION = "tool_verification"
    OUTPUT_SCREENING = "output_screening"
    IPC_SERIALIZATION = "ipc_serialization"
    IPC_TRANSFER = "ipc_transfer"
    PARENT_JOIN_CLEANUP = "parent_join_cleanup"
```

No se aceptan nombres libres, aliases ni etapas derivadas de mensajes. Cada
`TOOL_GATE`, `TOOL_EXECUTION`, `TOOL_VERIFICATION` y `MODEL_INFERENCE` puede
aparecer varias veces dentro de los límites de 4.3. La ocurrencia se representa
por posición estructural, nunca por `toolUseId`, case ID u otro identificador.

### 3.2 Límites exactos de cada span

| Etapa | Proceso | Inicio inclusivo | Fin exclusivo | Relación |
| --- | --- | --- | --- | --- |
| `end_to_end` | padre | inmediatamente antes de crear estado/pipe/proceso del caso | después de envelope final, join, cierre de pipes y cleanup, justo antes de retornar o elevar error | raíz parent-side; conserva la semántica de Spec #9 |
| `process_startup_composition` | hijo | primera instrucción instrumentada de `execute_case_child` | justo antes de llamar `handle_turn`, después de validar request y construir dependencias | top-level child-side |
| `agent_turn` | hijo | inmediatamente antes de `handle_turn`/invocación del agente | al retornar o capturar su excepción, antes de serializar el resultado worker | contiene gobierno, inferencias y tools del turno |
| `model_inference` | hijo | inmediatamente antes de cada llamada real al boundary del modelo | inmediatamente después de respuesta o excepción | hijo de `agent_turn`; una ocurrencia por llamada |
| `input_screening` | hijo | antes de `screen_input` | después de decisión y emit durable, o después del fallo que impide continuar | hijo de `agent_turn` |
| `routing` | hijo | antes de `route_banking_intent` | después de decisión y emit durable, o fallo | hijo de `agent_turn`; no existe si screening no permite |
| `tool_gate` | hijo | antes del gate determinístico de una propuesta concreta | después de decisión semántica y auditoría durable, o del bloqueo/fallo anterior | hijo de `agent_turn`; una ocurrencia por propuesta |
| `tool_execution` | hijo | solo tras gate `ALLOW`, inmediatamente antes de entrar a la tool | después de retorno/excepción/cancelación normalizada | hijo de `agent_turn`; incluye su verificación anidada |
| `tool_verification` | hijo | inmediatamente antes de la relectura/comprobación terminal de la tool/service | inmediatamente después de confirmar o rechazar el resultado | hijo de la ejecución correspondiente; no se sintetiza si no hubo verificación |
| `output_screening` | hijo | antes de construir/evaluar la proyección permitida de salida | después de decisión y auditoría durable, o del fallo fail-closed | hijo de `agent_turn`; no existe si no hay salida candidata |
| `ipc_serialization` | hijo | inmediatamente antes de codificar el frame de resultado V2 completo | después de producir sus bytes acotados, antes de enviarlos | top-level child-side; su duración viaja en el trailer temporal V2 separado |
| `ipc_transfer` | padre | inmediatamente antes de cada `recv_bytes` de resultado o trailer ya disponible | después de recibir y fijar esos bytes, antes de decodificar/materializar | hijo de `end_to_end`; si ocurre durante finalización, hijo de `parent_join_cleanup`; 1..2 ocurrencias, no mide tiempo previo en cola |
| `parent_join_cleanup` | padre | al observar salida del hijo o declarar timeout e iniciar gracia/terminación | después de join final, cierre de pipes y cleanup poseído por el padre | hijo parent-side de `end_to_end`; puede contener el transfer final |

`process_startup_composition` no pretende medir el bootstrap del intérprete antes
de entrar al target de Python. Ese costo queda visible como tiempo exclusivo/no
atribuido de `end_to_end`. 09C **MUST NOT** agregar un protocolo de readiness o
un servicio de tracing solo para estimarlo.

En timeout, `parent_join_cleanup` incluye gracia, terminate/kill, join y cleanup.
El `agent_turn` child-side puede quedar incompleto; se registra solo si ambos
límites se observaron. Un span incompleto **MUST NOT** recibir una duración
inventada.

### 3.3 Relojes y conversión

- Se usa `time.monotonic_ns()` o un wrapper inyectable equivalente. No se usa
  `datetime`, reloj wall-clock ni timestamp ISO para calcular duración.
- Cada proceso tiene un dominio de reloj independiente: `parent` o `child`.
  **MUST NOT** restarse un valor parent de uno child.
- Se transmiten solo offsets relativos al origen monotónico local y duraciones;
  nunca el valor monotónico absoluto.
- Para límites válidos, `duration_ms = (end_ns - start_ns) // 1_000_000`.
  `end_ns < start_ns`, tipo inválido u overflow invalida esa evidencia; no se
  aplica `abs`, wrap ni clamp silencioso.
- El truncado a ms es compatible con el contrato actual. Los tests de precisión
  usan ns enteros controlados, no sleeps.

### 3.4 Nesting, solapamiento y tiempo exclusivo

Las relaciones permitidas son:

```text
parent clock domain
end_to_end
├── ipc_transfer (0..2, si ocurre antes de finalización)
└── parent_join_cleanup (1)
    └── ipc_transfer (0..2, si ocurre durante finalización;
        máximo 2 total por caso)

child clock domain
process_startup_composition (1)
agent_turn (1 si inició y terminó)
├── input_screening (1)
├── routing (0..1)
├── model_inference (0..8)
├── tool_gate (0..16)
├── tool_execution (0..16)
│   └── tool_verification (0..1 por ejecución)
└── output_screening (0..1)
ipc_serialization (1 si pudo emitirse resultado)
```

Reglas:

1. Spans de distintos dominios tienen relación lógica, no aritmética; no se
   verifica nesting entre clocks distintos.
2. Sin concurrencia, hijos del mismo parent no se solapan salvo que una llamada
   del SDK mida internamente una región que el contrato documente como anidada.
3. Con la concurrencia permitida por la sección 7, solo siblings read-only
   independientes pueden solaparse. `tool_verification` solo se solapa con su
   propio `tool_execution` porque está anidado.
4. Tiempo inclusivo es `duration_ms` del span.
5. Tiempo exclusivo se deriva como intervalo inclusivo del parent menos la
   **unión** de intervalos de sus hijos directos válidos en el mismo dominio. Se
   resta la unión, no la suma, para no contar dos veces siblings solapados.
6. Los offsets relativos permiten calcular esa unión. Si faltan límites, nesting
   es inválido o el hijo cae fuera del parent, el tiempo exclusivo es `null` y se
   reporta el código cerrado `invalid_span_relationship`.
7. Las sumas de duraciones **MUST NOT** exigirse iguales a wall time: hay nesting,
   redondeo, scheduling, bootstrap, cola IPC y regiones no instrumentadas.
8. El reporte **MUST** mostrar inclusivo y exclusivo con etiquetas distintas; no
   puede presentar uno como el otro.

## 4. Evidencia temporal tipada, acotada y privada

### 4.1 Schema de span V1

Una representación equivalente a la siguiente es normativa:

```python
@dataclass(frozen=True)
class TimingSpanV1:
    stage: TimingStageV1
    start_offset_ms: int
    duration_ms: int
    children: tuple["TimingSpanV1", ...] = ()

@dataclass(frozen=True)
class TimingEvidenceV1:
    timing_schema_version: Literal["timing.v1"]
    parent_spans: tuple[TimingSpanV1, ...]
    child_spans: tuple[TimingSpanV1, ...]
    status: Literal["complete", "partial", "invalid"]
    error_codes: tuple[Literal[
        "clock_error",
        "cardinality_exceeded",
        "invalid_span_relationship",
        "timing_payload_too_large",
    ], ...]
```

Los enteros excluyen `bool` y satisfacen
`0 <= value <= 9_223_372_036_854_775_807`. Los valores de percentiles pueden ser
`float` por interpolación, pero **MUST** ser finitos y no negativos. JSON usa
`allow_nan=False`.

Un fallo de instrumentación no transforma un resultado funcional seguro en
éxito ni permite saltar gates. El caso conserva su resultado funcional y su
latencia end-to-end parent-side; la medición queda `partial|invalid` y no se
descarta. Un `end_to_end` ausente/inválido bloquea el gate de rendimiento. Un
span child inválido permanece incluido dentro del `end_to_end`, bloquea la
aceptación de atribución y se excluye solo del percentil de su propia etapa. El
fallo y su código cerrado se reportan honestamente.

### 4.2 Contenido permitido y prohibido

La evidencia temporal puede contener exclusivamente:

- versión de schema;
- `stage` del enum cerrado;
- `start_offset_ms`, `duration_ms` y tiempo exclusivo derivado;
- estructura de nesting;
- status y códigos cerrados;
- conteos y percentiles agregados;
- fingerprints técnicos allowlisted de la sección 5.

La evidencia temporal y sus agregados **MUST NOT** contener:

- prompts, mensajes del cliente, respuestas del modelo o texto final;
- argumentos, resultados, handoffs o payloads de tools;
- case, complaint, product, customer, transaction, session, trace, event,
  tool-use, escalation o handoff IDs;
- paths, nombres de archivo locales, hostname, username o directorios temporales;
- excepciones, stack traces, errores libres, state/preguntas/respuestas de Jev;
- tokens, credenciales, secretos, PAN, CVV o datos personales;
- chain-of-thought, hidden reasoning, explicaciones libres del modelo;
- hashes de un ID, texto u otro valor prohibido individual. Se permiten solo los
  fingerprints de artefactos completos y versionados definidos en 5.3.

Los envelopes de auditoría existentes conservan sus IDs técnicos de lineage; la
**proyección temporal nueva** no agrega ni copia IDs. El bloque temporal de los
reportes tampoco incluye IDs ni permite join por caso.

### 4.3 Límites de cardinalidad

Por caso:

| Elemento | Máximo V1 |
| --- | ---: |
| Spans totales parent + child | 96 |
| Profundidad | 3 |
| `model_inference` | 8 |
| `tool_gate` | 16 |
| `tool_execution` | 16 |
| `tool_verification` | 16 y máximo 1 por ejecución |
| `ipc_transfer` | 2: resultado y trailer temporal |
| Cada otra etapa no repetible | 1 |
| Códigos de error únicos | 4 |

El payload temporal serializado **MUST** caber dentro de `max_result_bytes`
junto al envelope funcional. No se aumenta ese límite para acomodar
instrumentación. Si excede cardinalidad o bytes, se conserva el envelope acotado
de error de Spec #9 y la corrida no puede aprobar rendimiento.

Los agregados por etapa contienen como máximo las 13 etapas del enum y solo:

```text
stage, sample_count, occurrence_count, complete_count, partial_count,
p50_inclusive_ms, p95_inclusive_ms,
p50_exclusive_ms, p95_exclusive_ms
```

Para una etapa repetible se produce primero una muestra por caso: el tiempo
inclusivo es la unión de sus intervalos válidos en el mismo dominio y el
exclusivo es la unión de los intervalos exclusivos derivados. Así dos lecturas
concurrentes no duplican wall time. `occurrence_count` conserva cuántos spans
reales participaron; `sample_count` cuenta casos donde la etapa ocurrió. Una
etapa legítimamente ausente no se marca parcial.

No se agregan dimensiones por caso, idioma, mensaje, ID, usuario o argumento.
Una segmentación por escenario solo puede reutilizar el dominio cerrado ya
existente y debe demostrar necesidad; no forma parte del mínimo V1.

### 4.4 Percentiles y conteos

- Los percentiles usan el mismo algoritmo inclusivo exacto de Spec #9: índice
  `h=(n-1)q`, interpolación lineal entre `floor(h)` y el siguiente valor.
- Vacío devuelve `None`; singleton devuelve ese valor como `float`.
- Solo spans completos y válidos entran en percentiles secundarios por etapa.
- `sample_count` cuenta casos donde ocurrió la etapa; `occurrence_count` cuenta
  spans y `complete_count`/`partial_count` permiten ver exclusiones. El bloque
  superior conserva el total de casos del benchmark. Ninguna muestra desaparece
  silenciosamente.
- La latencia end-to-end principal incluye todos los casos, error y timeout,
  como Spec #9. Si falta un `end_to_end` válido, el gate queda bloqueado en vez
  de recalcularse con menos casos. Un outlier se conserva; no hay trimming,
  winsorization ni borrado manual.

### 4.5 Versionado de IPC, auditoría y reporte

- Agregar timing al protocolo exacto del worker exige incrementar su
  `SCHEMA_VERSION` de `1` a `2`. Worker V2 emite como máximo un frame de resultado
  y, si logró serializarlo y ambos frames caben en el límite existente,
  exactamente un trailer temporal pequeño. El trailer contiene solo
  `schema_version`, `frame_type="timing_trailer"` y el span
  `ipc_serialization`; así se mide la codificación real sin auto-referencia ni
  una segunda serialización ficticia. Si la pareja excede el límite, se envía
  solo el error canónico acotado y timing queda parcial.
- Runner V2 acepta únicamente un resultado seguido de cero o un trailer. La
  ausencia del trailer deja timing `partial`; orden inverso, frame extra,
  duplicado, versión desconocida o shape distinto falla cerrado. La suma de
  bytes de ambos frames **MUST** respetar `max_result_bytes`; no se eleva el
  límite. Worker/runner V1 históricos no se reescriben.
- Todo evento nuevo lleva `audit_schema_version: "audit.v2"` en el envelope
  común. Eventos históricos sin ese campo se interpretan como `audit.v1` solo
  al leer históricos; el writer nuevo nunca lo omite ni reescribe archivos V1.
- Un evento que ya corresponde a una etapa medible puede agregar al payload
  solo `audit_timing_schema_version: "audit-timing.v1"` y el `timing_stage`
  allowlisted; su duración sigue en el `latency_ms` canónico. No se crea un evento
  nuevo por span ni se copia el árbol temporal completo a JSONL.
- La evidencia parent/child completa viaja solo en el protocolo de evaluación y
  alimenta el reporte local. El resto de la semántica del envelope de
  `docs/observability.md` se conserva.
- El reporte de evaluación agrega
  `report_schema_version: "evaluation-report.v2"` y un bloque
  `timing_summary` con `timing_schema_version: "timing.v1"`.
- Readers V2 **MUST** rechazar versiones futuras desconocidas. Reportes/eventos
  V1 históricos siguen legibles como históricos y **MUST NOT** reescribirse.
- Cambiar enum, significado, límites, percentil o campos requiere nueva versión;
  agregar silenciosamente una key está prohibido por schemas `extra="forbid"` o
  validación exacta equivalente.

### 4.6 Preservación de seguridad existente

Instrumentar **MUST** preservar:

- sanitización recursiva, masking y JSON sin NaN;
- auditoría durable y `AuditPersistenceError` fail-closed;
- límites del envelope IPC y errors sanitizados;
- no exposición de paths del estado aislado;
- clasificación conservadora de side effects;
- autorización 09A, policy/terminales 09B y verificación de toda acción;
- ausencia de chain-of-thought.

Un fallo al persistir evidencia temporal de una acción sensible **MUST NOT**
permitir afirmar autorización, ejecución, verificación ni SAR. Se usa la
semántica conservadora ya definida por 09A/09B/observabilidad.

## 5. Protocolo de baseline development-only

### 5.1 Precondiciones

El baseline 09C no puede empezar hasta registrar:

- 09A y 09B implementadas, revisadas y congeladas;
- todos sus gates funcionales/security development verdes;
- suite determinística, Ruff y diff check verdes dentro de su alcance;
- versión/hash del development vigente;
- bytes, hash y manifests de held-out `v1.0.2` intactos; las corridas históricas
  registradas en `docs/STATUS.md` se reconocen y nunca se usan para tuning, y no
  ocurre ninguna corrida held-out nueva desde el inicio de la cadena de
  implementación 09A → 09B → 09C hasta la única corrida final posterior al freeze
  definida en la sección 10;
- policy, preguntas Jev, modelos, dependencias y timeouts congelados.

Si una precondición falta, estado `blocked`; no se toma una medición provisional
como baseline.

### 5.2 Benchmark fijo y versionado

V1 usa el conjunto development completo y congelado posterior a 09B, en orden de
manifest. Así el “subset” es explícitamente `all_in_manifest_order`; no se
seleccionan casos rápidos ni se omiten fallos.

`configs/eval.yaml` puede agregar un bloque tipado equivalente a:

```yaml
performance_benchmark:
  version: latency-development-v1
  case_set: development
  selection: all_in_manifest_order
  order_policy: manifest_order
  warmup_policy: none
```

El benchmark **MUST** estar ligado al hash exacto del manifest y bytes exactos de
casos development. Su matriz registrada contiene conteos por idioma, los seis
escenarios, terminal esperado y clases de plan `no_tool|read_only|verified_write`.
No copia mensajes ni IDs al reporte temporal. Si el development congelado no
cubre una clase, se bloquea el benchmark o se crea un sucesor por el proceso de
09A/09B antes del freeze; 09C **MUST NOT** editar fixtures para mejorar latencia.

`warmup_policy: none` es normativa para V1 porque cada caso crea un proceso
`spawn` y estado nuevos. Baseline y candidate observan el mismo camino frío. Un
cambio futuro de warmup exige V2 y un nuevo baseline; no puede mezclarse con V1.

### 5.3 Fingerprints obligatorios

Baseline y candidate registran una proyección allowlisted y su SHA-256 canónico:

| Fingerprint | Contenido permitido |
| --- | --- |
| benchmark | versión, hash del manifest/cases development, hash del sandbox, matriz y política de orden |
| código | revisión exacta del candidato o hash reproducible del source relevante, sin paths |
| dependencias | SHA-256 de `uv.lock` y versiones runtime allowlisted |
| policy | SHA-256 de bytes de `configs/policy.yaml` y versión/schema tipado |
| evaluación | hash canónico de campos de `configs/eval.yaml` que afectan ejecución, incluidos timeout/gracia/max bytes |
| modelos | IDs/versiones configuradas exactas de OpenAI y Jev; parámetros relevantes allowlisted |
| entorno | OS family/version/build, arquitectura, implementación/versión Python, modelo CPU sanitizado, cores físicos/lógicos, tier de memoria y modo de energía; nunca seriales, hostname, usuario o path |
| protocolo | versiones de reporte/timing, orden y warmup |

Secretos y valores de `.env` **MUST NOT** entrar al fingerprint. Tampoco hostname,
username, seriales, paths o variables no allowlisted. Cada mapa canónico exige
igualdad exacta campo por campo; si un campo obligatorio no puede obtenerse o
sanitizarse, la comparación queda bloqueada. Un hash sin la proyección legible no
prueba comparabilidad; el reporte local conserva ambos.

### 5.4 Estado, orden, retries y fallos

- Cada caso conserva el `state_dir` temporal exclusivo y los dos SQLite aislados
  de Spec #9.
- Los casos se ejecutan secuencialmente en orden de manifest. No hay shuffle.
- Se registra un fingerprint del orden sin publicar IDs en `timing_summary`.
- Cada caso se ejecuta una sola vez por baseline o candidate.
- No hay retry por timeout, error de modelo/Jev, rate limit, resultado adverso ni
  outlier.
- Solo puede reiniciarse una corrida si falla infraestructura antes de que
  comience el primer turno. Debe probarse que ningún hijo ejecutó `handle_turn`,
  no quedó estado y no existe resultado parcial.
- Si un caso comenzó, la corrida completa cuenta y todos sus fallos/outliers se
  reportan.

### 5.5 Comparabilidad baseline/candidate

Un par es comparable solo si coinciden exactamente todos los fingerprints de
5.3 salvo `código`, y además:

- misma selección, matriz, orden y warmup;
- mismos modelos/versiones, policy, preguntas, dependencias y parámetros;
- mismo sandbox y development bytes;
- mismo timeout/gracia/max bytes;
- misma clase de hardware/OS/Python y condiciones de energía registradas;
- misma semántica funcional y de clasificación congelada.

La corrida candidate debe ocurrir en una ventana operativa documentada junto al
baseline. Si rate limits, indisponibilidad o variación externa impiden comparar,
el gate queda `blocked`, no `passed`. No se mezclan corridas parciales ni se elige
la mejor de varias.

El artefacto baseline local conserva métricas, fingerprints, conteos, fallos y
outliers. Reports permanecen locales; solo STATUS/task registra evidencia
sanitizada y agregada.

## 6. Escalera obligatoria de optimización

Las categorías se intentan en este orden. Se avanza solo si la atribución prueba
que la categoría actual no aplica, no alcanza el gate o ya fue agotada sin
regresión. Cada peldaño es una unidad separada de RED/GREEN, benchmark y rollback.

| Orden | Optimización permitida | Evidencia mínima | Límite normativo |
| ---: | --- | --- | --- |
| 1 | Eliminar trabajo duplicado | spans/contadores muestran la misma validación, proyección, serialización o cálculo repetido en un turno | No eliminar defensa en profundidad ejecutada en trust boundaries distintos. |
| 2 | Reusar hechos derivados inmutables case-local o turn-local | mismo input verificado produce la misma derivación dentro de un caso/turno | Sin caché cross-case; invalidar al finalizar turno/proceso; nunca reusar autorización o side effects como dato global. |
| 3 | Reducir payloads | tamaño y tiempo de serialización/transporte prueban costo material | Solo proyecciones allowlisted; no omitir evidencia necesaria para clasificación, verificación, auditoría o privacidad. |
| 4 | Concurrencia acotada de lecturas independientes | grafo y tests prueban independencia, ausencia de writes y mejora real | Máximo 2 operaciones; sección 7 completa; deshabilitada si la independencia no puede probarse. |
| 5 | Reducir overhead de proceso/composición | `process_startup_composition` y residual parent-side son cuello demostrado | Se conserva un proceso `spawn` nuevo por caso y cleanup parent-owned. No pool ni proceso compartido. |
| 6 | Reusar conexión/cliente SDK | creación/conexión domina y SDK documenta seguridad de reuse | Solo dentro del mismo caso/proceso; aislamiento, lifecycle y thread/process safety probados; nunca compartir cliente vivo a través de `spawn`. |

09C **MUST NOT**, en ningún peldaño:

- omitir o bypass Jev;
- omitir autenticación/autorización 09A;
- relajar hard gates, policy o contratos 09B;
- omitir verificación de side effects;
- debilitar durabilidad de auditoría;
- omitir output screening;
- reemplazar un error por `ALLOW`;
- eliminar aislamiento por proceso;
- aumentar timeout como “optimización”;
- introducir caché sensible cross-case o persistente.

Reuse de conexión SDK no se presume seguro porque `JevClient` actual crea un
cliente por invocación. Antes de cambiarlo, la implementación **MUST** verificar
la documentación/version exacta, lifecycle, cierre, thread safety y process
safety, y demostrar que el cliente no cruza caso ni proceso. Si eso no puede
probarse, el peldaño se omite con evidencia, no con una suposición.

## 7. Grafo de dependencias y concurrencia

### 7.1 Grafo normativo

```text
A input_screening
└── B routing (solo si A permite)
    └── C contexto exacto de reclamación/producto
        └── D autorización 09A del principal/producto
            ├── E1 gate de lectura 1 ─► F1 ejecución read-only ─► G1 validación
            ├── E2 gate de lectura 2 ─► F2 ejecución read-only ─► G2 validación
            └── H policy/plan con hechos verificados
                ├── I gate de block_card ─► J write serial ─► K verificación
                └── L gate de escalate_case ─► M write serial ─► N verificación

(A..N completados/admitidos según ruta)
└── O clasificación terminal
    └── P output_screening cuando aplica
        └── Q auditoría/respuesta final
```

Reglas:

1. A precede B; routing **MUST NOT** ejecutarse si screening bloquea/revisa.
2. Contexto exacto precede toda operación que dependa de producto, autorización,
   policy o hechos de la disputa.
3. D debe ser durable/admitida antes del gate y ejecución de cualquier tool
   sensible. Autorización nunca se especula ni se resuelve en paralelo con la
   tool que protege.
4. Cada gate precede exclusivamente a su ejecución asociada.
5. Una acción dependiente espera contexto, lecturas requeridas, policy y
   autorización completos.
6. `block_card` y `escalate_case` son writes: se serializan y nunca se solapan.
7. Ningún write se inicia para “ganar tiempo” antes de conocer policy/gate.
8. Verificación termina antes de afirmar éxito, clasificar terminal o iniciar una
   acción dependiente.
9. Output screening ocurre después de reunir solo hechos/acciones verificados.
10. Auditoría durable conserva la precedencia fail-closed existente.

Con el flujo actual, `get_recent_transactions` depende del producto/contexto
autorizado. Por tanto, no es independiente de `get_dispute_context` y **MUST NOT**
paralelizarse en V1. La sección 6.4 solo puede activarse si una revisión futura
demuestra dos lecturas distintas sin arista de dependencia. Ausencia de una
oportunidad real de concurrencia es un resultado válido y preferible a construir
infraestructura especulativa.

### 7.2 Requisitos para concurrencia read-only

Antes de introducirla, un test y una nota de diseño **MUST** probar:

- ambas operaciones son read-only e idempotentes;
- no comparten cursor/conexión mutable ni escriben auditoría fuera del sink
  thread-safe probado;
- no existe arista de datos, autorización, policy o orden entre ellas;
- sus errores pueden reconciliarse sin esconder evidencia;
- el límite es exactamente 2 y está configurado/validado como entero positivo,
  no un pool sin cota;
- el resultado observable no depende del scheduling;
- no cambia orden lógico, plan, verificación ni clasificación.

Si cualquier punto falla, permanecen secuenciales.

### 7.3 Cancelación, timeout y errores

| Situación | Respuesta obligatoria |
| --- | --- |
| Cancelación antes de un gate/write | No iniciar nuevas tools; cancelar lecturas cooperativas; terminal conservador de 09B. |
| Cancelación durante lecturas concurrentes | Señalar ambas, esperar su cierre acotado, descartar resultados tardíos para decisiones y auditar status cerrado. |
| Una lectura falla | Cancelar/esperar siblings read-only; no continuar con facts parciales como si fueran completos; fail-closed. |
| Cancelación antes de write | Cero write; no crear fallback especulativo. |
| Cancelación durante write | No iniciar otro write ni retry; esperar/reconciliar resultado y verificación dentro del contrato existente. Si el efecto puede haber ocurrido, `UNCERTAIN_SIDE_EFFECT`. |
| Error/timeout de write | No retry automático; verificación/relectura determina éxito conocido, fallo conocido o incertidumbre. |
| Timeout del caso | El padre conserva gracia, terminate/kill, join y cleanup de Spec #9; nunca retorna ni limpia mientras el hijo siga vivo. |
| Error de auditoría sensible | No afirmar éxito; conservar fail-closed y no iniciar compensación no especificada. |
| Error de instrumentación | No cambia decisión funcional ni excluye el `end_to_end`; timing `partial|invalid`. Si falta `end_to_end`, el gate se bloquea; si falla un child span, falla la aceptación de atribución. |

La cancelación **MUST** dejar cero tareas, threads, procesos, conexiones o efectos
huérfanos. “Cero efectos huérfanos” no significa borrar un write incierto: exige
no abandonarlo ni repetirlo, reconciliarlo si es posible y clasificarlo de forma
conservadora.

## 8. TDD estricto de la implementación futura

Runner autoritativo: `uv run pytest`, resuelto desde `pyproject.toml`. Tests
determinísticos usan clocks, procesos, pipes, SDK/clientes, modelo y Jev fake. No
usan red, credenciales ni sleeps para afirmar precisión.

La autoría de este documento es una excepción documentation-only: no existe un
RED de comportamiento significativo. La implementación futura no hereda esa
excepción.

### 8.1 Microciclo A — contrato e instrumentación

**RED observado requerido:**

- no existe enum/schema temporal cerrado;
- no se atribuyen startup/composición, agent turn, inferencias, IPC y cleanup;
- timing puede aceptar bool, negativo, overflow, NaN/Inf agregado o stage libre;
- no hay versión/cardinalidad explícita.

**GREEN mínimo:** tipos V1, clock inyectable, límites exactos y serialización
acotada. No optimizar todavía.

**TRIANGULATE:** cero, frontera máxima, clock que retrocede, span incompleto,
cardinalidad 96/97, JSON sin NaN y versión desconocida.

### 8.2 Microciclo B — clocks, nesting y percentiles

**RED observado requerido:** no se detecta hijo fuera de parent, se suman spans
anidados como wall time o se resta entre procesos.

**GREEN mínimo:** offsets locales, dos dominios, nesting permitido, unión de
intervalos para exclusivo y percentil inclusivo compartido.

**TRIANGULATE:** siblings secuenciales, siblings solapados, verificación anidada,
redondeo ns→ms, vacío, singleton, interpolación p50/p95 e inputs no finitos.

### 8.3 Microciclo C — worker/runner, timeout y join

**RED observado requerido:** el envelope no transporta evidencia V1, IPC no está
acotado y timeout/join/cleanup no produce atribución segura.

**GREEN mínimo:** integrar evidencia sin cambiar ownership del lifecycle ni
`max_result_bytes`.

**TRIANGULATE:** éxito, error, envelope inválido/oversize, timeout durante gracia,
late result descartado, terminate, kill, join imposible, cleanup fallido y
segundo caso no iniciado. Probar que no quedan hijos ni estado.

### 8.4 Microciclo D — privacidad, auditoría y reporte

**RED observado requerido:** una entrada maliciosa puede filtrarse a timing o el
reporte carece de versiones/conteos de exclusión.

**GREEN mínimo:** proyección allowlisted, schemas de 4.5 y agregados sin IDs.

**TRIANGULATE:** prompts/respuestas, args/results, todos los IDs enumerados en
4.2, Windows/POSIX paths, secretos, excepción, state Jev y chain-of-thought.
Verificar ausencia tanto en JSON como Markdown y auditoría.

### 8.5 Microciclo E — optimización específica

Para cada unidad:

1. un RED de comportamiento o benchmark determinístico demuestra el trabajo
   duplicado/cuello y protege el output funcional;
2. GREEN aplica el cambio mínimo de un solo peldaño;
3. TRIANGULATE cubre camino alterno, fallo y privacidad;
4. REFACTOR ocurre solo con tests enfocados verdes;
5. benchmark development runtime ocurre únicamente después del GREEN
   determinístico completo.

Un benchmark lento no sustituye un RED de comportamiento. Una diferencia de
tiempo no autoriza cambiar outputs, gates o clasificación.

### 8.6 Microciclo F — concurrencia y cancelación, solo si aplica

**RED observado requerido:** dos lecturas probadamente independientes son
secuenciales y dominan latencia, manteniendo un resultado determinístico.

**GREEN mínimo:** límite 2, solo read-only, sin writes ni aristas del grafo.

**TRIANGULATE:** orden invertido, una/both fallan, cancelación antes/durante,
timeout, auditoría fallida, cierre de tasks/conexiones y cero write. Si el flujo
actual no ofrece dos lecturas independientes, este microciclo se registra como
`not applicable` con el grafo; **MUST NOT** crearse concurrencia artificial.

## 9. Gates de aceptación

09C solo está implementada cuando todos estos gates pasan:

### 9.1 Función y seguridad

- Todos los gates funcionales y de seguridad development de 09A y 09B permanecen
  verdes sobre los mismos bytes/versiones congelados.
- No hay regresión en unsafe outcomes, terminal exacto, tipo/razón de
  escalamiento, tool-plan match, autorización, verificación, SAR, ataques ni
  missing-data.
- No se ejecuta una tool sin autorización y gate; no se afirma write sin
  verificación y auditoría durable.
- Process isolation, timeout, join y cleanup conservan los contratos de Spec #9.
- No se cambia timeout/gracia/max bytes entre baseline y candidate.

### 9.2 Rendimiento principal

Sea `B95` el p95 end-to-end del baseline 09C comparable y `C95` el candidate:

```text
C95 <= 0.75 * B95
```

Es una mejora mínima de 25%. Además:

```text
candidate_p50_ms <= baseline_p50_ms
```

No hay tolerancia oculta, exclusión de outliers ni selección de la mejor corrida.
Si los fingerprints o condiciones no permiten comparabilidad, el estado es
`blocked`, no `passed`.

El p95 absoluto `<= 15_000 ms` es solo target/diagnóstico. **MUST NOT** tratarse
como promesa incondicional salvo que el entorno baseline esté controlado y el
resultado sea medido bajo este protocolo.

### 9.3 Overhead de instrumentación

El overhead end-to-end de instrumentación **MUST** ser `<= 2%` frente al mismo
camino sin persistir timing adicional.

Protocolo mínimo permitido:

1. harness determinístico con modelo/Jev/tools/pipes fake y output idéntico;
2. sin red ni sleeps; workload suficiente para que cada batch dure al menos 1 s;
3. 5 warmups no medidos del harness, no de los casos runtime;
4. 30 pares medidos alternando orden instrumentado/no instrumentado;
5. reportar todos los pares, mediana, p95, dispersión y fórmula
   `(instrumentado - control) / control * 100`;
6. aprobar solo si la mediana es `<=2%` y el protocolo documenta estabilidad.

Puede usarse otro protocolo estadísticamente estable solo si se documenta antes
de medir, conserva todos los resultados y es revisado. No se permite escoger el
método después de ver los números.

### 9.4 Honestidad del reporte

- Toda falla, timeout, muestra parcial/inválida y outlier aparece en conteos.
- El reporte identifica si un percentil de etapa excluyó spans inválidos y por
  qué código cerrado.
- No se aumenta timeout para convertir timeouts en éxitos.
- No se confunde target de 15 s con gate principal de 25%.
- Reportes JSON y Markdown derivan del mismo dict y permanecen locales.

## 10. Política única de held-out final

Las corridas históricas registradas en `docs/STATUS.md` se reconocen, pero nunca
se usan para tuning y no sustituyen esta corrida final. Desde el inicio de la
cadena de implementación 09A → 09B → 09C no ocurre ninguna corrida held-out nueva
hasta este punto.

Después —y solo después— de que 09A, 09B y 09C estén implementadas, revisadas y
congeladas, y todos los gates development pasen, se ejecuta exactamente una
corrida final de held-out `v1.0.2`:

```bash
uv run python -m ai_banking_customer_service.evaluation \
  --config configs/eval.yaml --case-set held-out
```

Reglas:

- el comando, fingerprints, modelo y versiones se registran antes de iniciar;
- no hay profiling por caso held-out, tuning posterior, selección parcial ni
  segunda corrida por mal resultado;
- no hay retry de caso;
- solo puede reintentarse la corrida completa por fallo de infraestructura antes
  de que comience cualquier caso, con evidencia de cero hijo/turno/estado/
  resultado parcial;
- si al menos un caso comenzó, la corrida cuenta;
- todas las métricas, fallos y outliers se reportan honestamente;
- held-out mide el sistema final; nunca lo ajusta;
- reportes JSON/Markdown permanecen locales.

## 11. Respuesta ante fallos

| Fallo | Respuesta obligatoria |
| --- | --- |
| 09A o 09B no implementada/revisada/congelada | `blocked`; no baseline ni optimización. |
| Fingerprint incompleto o distinto | `blocked` por no comparabilidad; no combinar corridas. |
| Clock retrocede/tipo inválido/overflow | timing inválido con `clock_error`; no clamp ni aprobación. |
| Span fuera de parent o nesting ilegal | exclusivo `null`, `invalid_span_relationship`; muestra visible y excluida del percentil de etapa. |
| Cardinalidad o payload excedido | fail-closed según envelope de Spec #9; no aumentar límites. |
| Timing filtra dato prohibido | defecto bloqueante de privacidad; rollback de la unidad. |
| Auditoría no durable | conservar fail-closed; no afirmar éxito/SAR ni ocultar el caso. |
| Candidate empeora p50 | gate fallido aunque p95 mejore. |
| Candidate mejora p95 <25% | gate principal fallido; siguiente unidad solo tras decidir/registrar, sin reinterpretar fórmula. |
| Entorno/modelo/policy no comparable | `blocked`, no `passed`. |
| Overhead >2% o medición inestable | reducir instrumentación o revisar protocolo antes de benchmark runtime. |
| Rate limit/error después de iniciar caso | cuenta como fallo/outlier; no retry. |
| Timeout | se conserva en percentiles end-to-end y lifecycle parent-owned; no aumentar timeout. |
| Cancelación con write posible | `UNCERTAIN_SIDE_EFFECT`; no retry ni write compensatorio inventado. |
| Lecturas no independientes | permanecer secuencial; no introducir concurrencia. |
| SDK reuse no probado seguro | no aplicar ese peldaño; cerrar cliente por caso como hoy. |
| Gate funcional/security regresa | rollback inmediato de la unidad de optimización, aunque sea más rápida. |
| p95 absoluto >15 s pero gate relativo pasa | reportar target no alcanzado; no invalidar ni ocultar el resultado relativo. |

## 12. Rollback por unidad de optimización

Cada cambio de la escalera es un work unit reversible que incluye:

1. test RED específico;
2. cambio productivo mínimo;
3. tests GREEN/triangulación;
4. evidencia candidate comparable;
5. actualización de evidencia local/STATUS/task.

Si falla un gate, se revierte esa unidad completa al último estado revisado y
congelado. **MUST NOT** quedar una combinación parcial donde:

- reporte espera spans que worker no emite;
- cache/reuse opera sin lifecycle case-local;
- concurrencia existe sin cancelación/cleanup;
- cliente compartido sobrevive al caso o cruza `spawn`;
- payload reducido elimina evidencia de autorización/verificación;
- timing V2 se publica como V1;
- candidate rápido usa timeout, modelo, policy u orden distinto.

Instrumentación base V1 puede mantenerse si pasó privacidad y overhead; cada
optimización posterior se revierte independientemente. Reportes históricos,
held-out y baseline congelado no se reescriben.

## 13. Superficies probables e inventario

La implementación confirma el árbol posterior a 09A/09B y reduce esta lista si
una superficie no es necesaria. Ampliarla requiere justificación y aprobación;
no se autorizan refactors laterales ni dependencias nuevas.

### 13.1 Crear, si el diseño mínimo lo requiere

```text
src/ai_banking_customer_service/evaluation/timing.py
tests/unit/evaluation/test_timing.py
```

No se crea un paquete de tracing, exporter, collector, dashboard ni benchmark
service. Un helper temporal puro puede vivir en un módulo existente si evita el
archivo nuevo.

### 13.2 Modificar probablemente

```text
src/ai_banking_customer_service/evaluation/runner.py
src/ai_banking_customer_service/evaluation/worker.py
src/ai_banking_customer_service/evaluation/report.py
src/ai_banking_customer_service/evaluation/classification.py
src/ai_banking_customer_service/agent/orchestrator.py
src/ai_banking_customer_service/governance/adapter.py
src/ai_banking_customer_service/governance/jev/client.py
src/ai_banking_customer_service/observability/contract.py
src/ai_banking_customer_service/observability/sink.py
src/ai_banking_customer_service/config.py
configs/eval.yaml
docs/observability.md
docs/STATUS.md
odd/tasks/<task-de-implementación-09c>.md
tests/unit/evaluation/test_runner.py
tests/unit/evaluation/test_worker.py
tests/unit/evaluation/test_report.py
tests/unit/evaluation/test_classification.py
tests/unit/agent/test_orchestrator.py
tests/unit/governance/test_adapter.py
tests/unit/governance/jev/test_client.py
tests/unit/observability/test_contract.py
tests/unit/observability/test_sink.py
tests/unit/test_config.py
```

`governance/jev/client.py` solo se modifica si la atribución demuestra beneficio
y el peldaño 6 prueba lifecycle/thread/process safety. No se modifica por
anticipación. Del mismo modo, concurrencia no autoriza un archivo nuevo si el
grafo actual no ofrece operaciones independientes.

### 13.3 Superficies prohibidas salvo aprobación separada

```text
uv.lock
pyproject.toml
evals/cases/held_out_v1.0.2.yaml
evals/held_out_manifest.json
reportes históricos locales
datasets/sandbox fuente
Spec #10
```

No se agregan dependencias. El development solo cambia de versión si 09A/09B lo
requieren antes del freeze; 09C no lo reescribe para rendimiento.

## 14. Orden de revisión

Revisar en este orden para evitar reconstruir intención desde el diff:

1. **Precondiciones:** evidencia de freeze 09A/09B y held-out intacto.
2. **Taxonomía:** boundaries, clocks, nesting, inclusive/exclusive y timeout.
3. **Privacidad/versionado:** schema cerrado, cardinalidad, ausencia de datos
   prohibidos, compatibilidad histórica.
4. **Lifecycle:** worker/runner, envelope acotado, spawn, join y cleanup.
5. **Función/seguridad:** todos los gates de 09A/09B y clasificación sin cambios.
6. **Optimización:** cuello demostrado, peldaño correcto y cambio mínimo.
7. **Concurrencia/cancelación:** grafo, límite, writes seriales y cero huérfanos,
   solo si aplica.
8. **Benchmark:** fingerprints, orden, estado, comparabilidad, 25% p95, p50 y
   overhead.
9. **Evidencia:** fallos/outliers completos, STATUS/task y política held-out.

Son bloqueantes: bypass de Jev/autorización/gate/verificación/auditoría/screening,
cache cross-case, write concurrente/especulativo, IDs o texto en timing, clock
cross-process restado, timeout aumentado, muestra descartada, benchmark no
comparable o held-out usado para tuning.

## 15. Evidencia requerida en STATUS y task

Solo después de observar resultados reales, el work unit de implementación
**MUST** registrar:

- confirmación de 09A/09B implementadas, revisadas y congeladas;
- versiones `audit-timing.v1`, `timing.v1` y `evaluation-report.v2`;
- RED y GREEN observados por microciclo, con comando exacto y fallo/pase;
- tests de clock, nesting, percentiles, timeout/join, privacidad y cancelación;
- versión/hash/matriz/orden/warmup del benchmark development;
- fingerprints allowlisted de baseline y candidate, y conclusión de
  comparabilidad;
- p50/p95 baseline y candidate, fórmula y porcentaje de mejora p95;
- overhead de instrumentación con protocolo y todos los pares conservados
  localmente;
- unidad exacta de optimización aplicada y evidencia del cuello;
- gates funcionales/security de 09A/09B sin regresión;
- todos los fallos, timeouts, spans inválidos y outliers;
- resultado del target diagnóstico de 15 s sin convertirlo en promesa;
- confirmación de que no se aumentó timeout, las corridas held-out históricas no
  se usaron para tuning y no ocurrió ninguna corrida held-out nueva durante la
  cadena antes de la corrida final posterior al freeze;
- limitaciones restantes y boundary de rollback.

El task conserva su checklist completo y enlaza review. No reemplaza la lista por
un resumen parcial. Reportes development y held-out permanecen locales.

## 16. Checklist de implementación

### Precondiciones y contrato

- [ ] Confirmar implementación, review y freeze de 09A y 09B.
- [ ] Confirmar todos sus gates development verdes; bytes, hash y manifests
  held-out intactos; corridas históricas reconocidas y nunca usadas para tuning;
  y ninguna corrida held-out nueva desde el inicio de la cadena hasta la única
  corrida final posterior al freeze.
- [ ] Releer fuentes/tests de la sección 2 sobre el árbol congelado.
- [ ] Agregar enum/schema V1 cerrado sin dependencia nueva.
- [ ] Definir boundaries con `monotonic_ns` inyectable y dos dominios de reloj.
- [ ] Implementar nesting y exclusivo por unión de intervalos.
- [ ] Preservar percentil inclusivo exacto de Spec #9.
- [ ] Aplicar límites de cardinalidad y bytes sin aumentar `max_result_bytes`.

### Privacidad, runner y reporte

- [ ] Probar ausencia de textos, args/results, IDs, paths, excepciones, secretos,
  state Jev y chain-of-thought en timing JSON/Markdown/auditoría.
- [ ] Integrar timing al worker/envelope con versión y JSON sin NaN.
- [ ] Conservar `spawn`, proceso por caso, timeout, late-result discard, join y cleanup.
- [ ] Versionar proyección de auditoría y reporte sin reescribir históricos.
- [ ] Reportar completos/parciales/inválidos y todos los outliers.
- [ ] Medir overhead y demostrar `<=2%` con protocolo predefinido.

### Baseline y optimización

- [ ] Congelar benchmark development completo, matriz, orden y `warmup:none`.
- [ ] Registrar fingerprints exactos y privacy-safe.
- [ ] Ejecutar baseline una sola vez bajo el protocolo; conservarlo local.
- [ ] Identificar cuello desde spans, no desde intuición.
- [ ] Aplicar un peldaño por vez en el orden de la sección 6.
- [ ] Abrir RED específico antes de cada cambio productivo.
- [ ] Probar cero bypass de Jev/autorización/hard gates/verificación/auditoría/output screening.
- [ ] Confirmar ausencia de caché cross-case y reuse fuera del hijo.
- [ ] Mantener writes seriales y no especulativos.
- [ ] Aplicar concurrencia solo si el grafo demuestra lecturas independientes; en
  el flujo actual, mantener contexto→transacciones secuencial.
- [ ] Probar cancelación/error/timeout sin tasks, procesos ni efectos huérfanos.

### Aceptación y cierre

- [ ] Ejecutar tests enfocados con fakes; sin red/modelo/Jev real.
- [ ] Ejecutar suite completa, Ruff candidate-scoped y whitespace check.
- [ ] Ejecutar benchmark runtime development solo después de GREEN determinístico.
- [ ] Confirmar p95 candidate `<= 0.75 * baseline` y p50 no regresivo.
- [ ] Marcar `blocked`, no `passed`, si falta comparabilidad.
- [ ] Reportar target p95 `<=15 s` solo como diagnóstico medido.
- [ ] Revisar en el orden de la sección 14.
- [ ] Actualizar STATUS/task solo con evidencia observada.
- [ ] Congelar 09C junto a código, policy, modelos y dependencias.
- [ ] Ejecutar exactamente una corrida final held-out `v1.0.2` solo después del
  freeze conjunto de 09A/09B/09C y de todos los gates development.
- [ ] Entregar a Spec #10 únicamente resultados finales medidos, incluidos fallos
  y limitaciones.

## 17. Criterio de transición a Spec #10

Spec #10 permanece dedicada al pitch. Solo puede consumir:

- resultados de la corrida final única descrita en la sección 10;
- baseline/candidate development claramente etiquetados como development;
- métricas y limitaciones observadas, no objetivos ni extrapolaciones;
- evidencia agregada privacy-safe.

Spec #10 **MUST NOT** presentar el target de 15 s como hecho si no fue medido,
mezclar cifras históricas no comparables con el baseline 09C, ocultar outliers o
atribuir causalidad que los spans no demuestran.
