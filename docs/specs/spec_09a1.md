# SPEC #09A1 — Contrato runtime de evidencia canónica y emisión

> **Estado:** especificación normativa completa y lista para implementar.
> Es la única spec de esta secuencia autorizada para iniciar implementación.
> **Depende de:** cierre medido de [Spec #09A](spec_09a.md),
> [estado observado](../STATUS.md) y ledger
> [`spec-09a-safe-sar.md`](../../odd/tasks/spec-09a-safe-sar.md).
> **Pregunta única:** ¿el runtime emite evidencia causal canónica, correlacionada,
> finita y segura para cada intento de tool sin cambiar ninguna decisión?

## 0. Resultado y valor funcional

09A1 DEBE congelar el contrato de evidencia runtime y emitirlo en los eventos
existentes. La evidencia distinguirá autorización, datos faltantes, gobierno,
ejecución y verificación para diagnosticar por qué una acción avanzó o se detuvo.

Esta spec termina en la emisión durable del evento. NO clasifica casos, NO
proyecta reportes y NO cambia policy, elegibilidad, tool selection, ejecución,
terminales ni respuestas al cliente.

## 1. Alcance

### 1.1 Incluye

- Caracterizar los contratos runtime vigentes antes del primer RED.
- Derivar vocabularios finitos desde constantes, enums y validadores actuales.
- Extender el contrato de auditoría solo si el evento existente no puede expresar
  la evidencia mínima de forma type-strict.
- Emitir desde hooks, captura u orquestador la ocurrencia causal exacta.
- Correlacionar decisión de gobierno, intento y resultado terminal sin heurísticas.
- Aplicar privacidad, límites y validación antes de escribir al sink.
- Fallar cerrado ante evidencia ausente, contradictoria, ambigua o malformada.

### 1.2 Fuera de alcance

09A1 MUST NOT:

- tocar clasificación, runner, worker, JSON/Markdown ni reportes de evaluación;
- cambiar comportamiento, policy, prompts, preguntas Jev, threshold o modelo;
- cambiar firmas, defaults, schemas model-facing ni resultados públicos de tools;
- corregir autorización, missing-data, admisión o persistencia;
- ejecutar evaluación development real o held-out, red, modelos o Jev real;
- modificar corpus, fixtures, manifests, sandbox, dependencias o config;
- reabrir [Spec #09B](spec_09b.md), que permanece diferida.

## 2. Contrato canónico runtime

Cada elemento representa una ocurrencia, no un resumen por nombre. Debe contener
solo las cinco dimensiones causales y metadatos cerrados indispensables:

| Dimensión | Forma segura | Fuente runtime canónica |
| --- | --- | --- |
| Autorización | estado, reason code o `null`, booleano estricto | adapter/provider inyectado |
| Datos faltantes | estado cerrado y booleano estricto | resultado validado de lectura |
| Gobierno | etapa, `allow|block`, reason code cerrado | decisión causal de gobierno |
| Ejecución | estado cerrado | resultado normalizado de tool |
| Verificación | outcome cerrado y booleano estricto | predicado específico de tool |

Antes del RED se congela el spelling exacto desde código y tests. Se reutilizan
los dominios existentes, incluido `allowed|denied|unavailable|not_evaluated`
para autorización cuando siga siendo el contrato vigente. No se inventan
aliases, traducciones, strings de provider ni categorías desde reportes previos.

El evento puede incluir únicamente:

- nombre allowlisted de tool;
- ordinal entero no negativo de la ocurrencia;
- códigos pertenecientes a allowlists congeladas;
- booleanos `bool` estrictos;
- `null` solo donde el schema lo declare;
- posición/lineage interno necesario para correlación, nunca IDs bancarios.

Valores desconocidos, campos requeridos ausentes, enteros usados como booleanos
o combinaciones imposibles producen un estado cerrado de evidencia inválida.
Ese estado nunca cuenta como evidencia positiva.

## 3. Correlación y orden

La cadena causal requerida es:

1. decisión de `tool_gating` del intento exacto;
2. captura del intento y de su resultado terminal exactos;
3. emisión del evento `tool_call` canónico existente.

Los IDs técnicos pueden participar internamente en el join, pero no salen en el
payload seguro. Dos llamadas homónimas permanecen separadas. Retry, duplicado,
fallback o interleaving no se fusionan como éxito.

Si no existe unión unívoca, se emite la ocurrencia fail-closed. Está prohibido
asociar por proximidad textual, orden supuesto, case ID, `complaint_id`,
`product_id` o igualdad parcial de argumentos.

El orden del payload es determinístico: posición canónica del evento y ordinal de
captura como desempate. Una auditoría no durable nunca se promociona a éxito.

## 4. Límites y privacidad

- Máximo 16 ocurrencias por caso en el contrato emitido.
- Cada código tiene como máximo 64 code points y pertenece a su allowlist.
- El bloque canónico serializado mide como máximo 8 KiB por caso.
- El exceso produce una marca cerrada de truncamiento y falla cerrado.
- No se recortan códigos ni se descartan selectivamente fallos.

La evidencia MUST NOT contener, ni truncados ni hasheados:

- `complaint_id`, `product_id`, `customer_id`, transaction/handoff/escalation IDs;
- principal, sentinel, credenciales, PAN, CVV, paths o excepciones;
- mensajes, argumentos completos, respuestas o resultados completos de tools;
- state, pregunta, respuesta, score, probabilidad, metadata o razón libre de Jev;
- respuesta, error o representación del provider.

Los validadores rechazan el payload antes del sink. Los errores usan códigos
cerrados; nunca interpolan el valor rechazado.

## 5. Invariantes

1. Relación por `product_id` NO es autorización.
2. `allow` de gobierno no prueba autorización, ejecución ni verificación.
3. Ejecución aparente no prueba éxito ni persistencia.
4. Missing-data no se deriva de texto, escenario ni expected outcome.
5. Evidencia ausente, contradictoria o no type-strict falla cerrado.
6. No se fabrica SAR, handoff, terminal ni éxito desde auditoría.
7. No hay ramas por case ID, idioma, corpus o modo evaluación.
8. No se crea un stream paralelo si `governance`/`tool_call` pueden ampliarse.
9. Ningún schema público cambia sin detenerse y revisar esta spec.
10. El comportamiento observable del agente permanece idéntico.

## 6. Gate anti-mega-spec obligatorio

Antes de la primera escritura de producción, la exploración y el primer RED DEBEN
producir un forecast de líneas authored y una lista concreta de superficies de
edición. El forecast cuenta adiciones más eliminaciones authored y excluye solo
artefactos generados.

Si el forecast supera **300 líneas authored** O la implementación modificaría
más de **un dominio runtime primario**, se DEBE DETENER y dividir el trabajo en
una nueva spec numerada antes de continuar. Tests y docs viajan con su
comportamiento y no cuentan como segundo dominio runtime.

Ninguna tarea, subtarea, commit o división por tipo de archivo puede eludir este
gate. Cada work unit de implementación apunta a **≤300 líneas authored** y a un
solo dominio runtime primario. Para 09A1, el único dominio permitido es emisión
de observabilidad runtime; evaluación es otro dominio y pertenece a 09A2.

## 7. TDD estricto

Runner autoritativo: `uv run pytest`. Los tests usan fakes y sinks en memoria,
sin red, modelo real, Jev real, SQLite productivo ni corpus real.

**RED:** demostrar que al menos dos causas runtime colapsan hoy, que una llamada
homónima puede perder lineage o que evidencia malformada no queda fail-closed.
El test debe cruzar el lifecycle fake real y congelar valores desde el contrato
vigente, no desde este documento.

**GREEN:** emitir el contrato mínimo en seams existentes. No tocar decisiones,
threshold `0.65`, tools, evaluación ni fixtures.

**TRIANGULATE:** autorización en todos sus estados; missing-data presente/ausente;
gobierno allow/block; no ejecución/error/éxito; verificación positiva/negativa;
cero, una, varias y más de 16 ocurrencias; orden adversarial; duplicado; retry;
lineage huérfano; booleanos no estrictos; payload oversized; auditoría fallida;
y negativos de cada categoría privada.

**REFACTOR:** solo con tests focales verdes y sin crear un framework de eventos.

## 8. Superficies probables

La exploración debe reducir esta lista y declarar la lista concreta antes de
producción:

```text
src/ai_banking_customer_service/observability/contract.py
src/ai_banking_customer_service/agent/hooks.py
src/ai_banking_customer_service/agent/result_capture.py
src/ai_banking_customer_service/agent/orchestrator.py
docs/observability.md
tests/unit/observability/test_contract.py
tests/unit/agent/test_hooks.py
tests/unit/agent/test_result_capture.py
tests/unit/agent/test_orchestrator.py
docs/STATUS.md
odd/tasks/<task-09a1>.md
```

No se anticipan cambios en `evaluation/`, tools, services, policy/config,
prompts, Jev, fixtures, manifests ni dependencias.

## 9. Aceptación y verificación

09A1 se acepta solo si:

- las cinco dimensiones varían independientemente en eventos runtime con fakes;
- cada ocurrencia conserva causalidad bajo homónimos e interleaving;
- evidencia malformada, oversized o no correlacionable queda fail-closed;
- todos los datos prohibidos tienen prueba negativa;
- sinks previos toleran la ampliación o fallan de forma cerrada y explícita;
- no cambia ninguna decisión, respuesta, terminal ni schema público.

Verificación permitida tras GREEN:

```bash
uv run pytest -q <tests-focales-09A1>
uv run pytest -q <suites-runtime-afectadas>
uv run ruff check <archivos-Python-modificados>
uv run ruff format --check <archivos-Python-modificados>
git diff --check
```

No se permite evaluación development real ni held-out, red, modelos o Jev real.

## 10. Detención, rollback y handoff

Detener si la distinción exige texto libre, IDs, scores, state crudo, un schema
público, otro dominio runtime o un cambio de comportamiento. También detener si
el lineage no puede hacerse unívoco dentro del presupuesto del gate anti-mega.

El rollback retira como una unidad schema interno, emisión y tests de 09A1, y
restaura los eventos previos sin tocar comportamiento. No deja productores o
consumidores runtime en versiones incompatibles.

Con 09A1 GREEN, revisada y con contrato/eventos congelados, se entregan schema,
allowlists, orden, límites y negativos de privacidad a
[Spec #09A2](spec_09a2.md). 09A2 permanece bloqueada hasta ese handoff y es la
única dueña de clasificación y proyección de reportes.
