# SPEC #09A6 — Persistencia verificada del handoff

> **Estado:** `IMPLEMENTATION-BLOCKED`; planificación normativa, no autorizada.
> **Depende de:** [09A1](spec_09a1.md)–[09A5](spec_09a5.md) implementadas,
> GREEN, revisadas y congeladas.
> **Pregunta única:** ¿un handoff admitido se clasifica como persistido solo
> cuando la escritura exacta fue confirmada sin contradicción ni incertidumbre?

## 0. Resultado y valor funcional

09A6 cerrará la verdad entre admisión, llamada a `escalate_case`, resultado del
service, relectura y evidencia canónica. Un handoff confirmado podrá sostener el
terminal vigente; un fallo conocido o efecto incierto conservará su estado real,
sin retry ni éxito fabricado.

Esta spec no presume que denegación y persistencia fallida compartan defecto. El
boundary y los asserts se derivan de 09A1–09A5 antes del primer cambio.

## 1. Gate de entrada

Se requiere:

- evidencia que distinga admisión, no ejecución, fallo conocido, efecto incierto
  y verificación;
- autorización verdadera de 09A3 y missing-data canónico de 09A4;
- handoff elegible/admitido por 09A5 con service aún no invocado;
- caracterización RED de tool, service y relectura;
- prueba de que no se requieren contratos diferidos de 09B.

Si el objetivo exige razón nueva, cambio de schema o policy terminal, 09A6 se
detiene y remite a revisión de [Spec #09B](spec_09b.md), que permanece diferida.

## 2. Alcance futuro

### Incluye

- Correlacionar una admisión exacta con una ejecución exacta.
- Confirmar persistencia mediante contrato vigente y relectura compatible.
- Separar bloqueo pre-ejecución, fallo conocido y efecto incierto.
- Preservar no-retry para cualquier escritura que pudo ocurrir.
- Propagar estados cerrados a evento y proyección ya congelados.
- Probar con SQLite temporal e inyectado, sin estado compartido.

### Excluye

- vocabulario, límites de texto o precedencia terminal de 09B;
- cambiar firma/schema model-facing o migrar filas históricas;
- cambiar autorización, missing-data o admisión congeladas;
- retocar threshold, prompt, modelo, dependencia, policy o corpus;
- introducir retries, conciliación automática o infraestructura nueva;
- ejecutar evaluación development real o held-out, red, modelos o Jev real.

## 3. Invariantes

1. `allow` no prueba ejecución ni persistencia.
2. Solo escritura exacta, autorizada, admitida y confirmada se verifica.
3. La relectura usa identidad y campos canónicos vigentes, no texto aproximado.
4. Resultado ausente, excepción post-inicio, duplicado, retry, mismatch,
   auditoría fallida o relectura contradictoria nunca produce éxito.
5. Rechazo pre-service no se presenta como side effect incierto.
6. Si la escritura pudo ocurrir, no se reejecuta.
7. Booleanos y estados son type-strict; no hay coerción.
8. No se emiten IDs ni texto libre nuevo.
9. No hay ramas por caso, idioma, escenario o corpus.
10. Schema público no cambia sin detener y revisar.

## 4. Gate anti-mega-spec obligatorio

Antes de la primera escritura de producción, la exploración y el primer RED DEBEN
producir un forecast de líneas authored y una lista concreta de superficies de
edición. El forecast cuenta adiciones más eliminaciones authored y excluye solo
artefactos generados.

Si el forecast supera **300 líneas authored** O la implementación modificaría
más de **un dominio runtime primario**, se DEBE DETENER y dividir el trabajo en
una nueva spec numerada antes de continuar. Tests y docs viajan con su
comportamiento y no cuentan como segundo dominio runtime.

Ninguna tarea, subtarea, commit o división por tipo de archivo puede eludir este
gate. Cada work unit apunta a **≤300 líneas authored** y a un solo dominio runtime
primario. Tool y service forman una unidad solo si el RED prueba un único boundary
de persistencia; propagación independiente exige una nueva spec numerada.

## 5. TDD estricto

Runner: `uv run pytest`; SQLite temporal y reloj/UUID fake cuando corresponda,
sin corpus real, red, modelo ni Jev.

**RED:** un handoff admitido con persistencia ausente o contradictoria queda
indistinguible de éxito, o un éxito exacto pierde verificación al cruzar service
→ tool → captura.

**GREEN:** reparar el boundary más cercano. Reutilizar tool, service, captura y
evento existentes; no crear otro repositorio o workflow.

**TRIANGULATE:** insert/relectura compatible; fila ausente; error antes de write;
excepción antes/después de inicio; ID/estado/shape contradictorio; resultado
ausente; doble intento; retry solicitado; auditoría fallida; concurrencia;
rollback SQLite; autorización falsa; admisión falsa; JSON/Markdown.

**REFACTOR:** solo con foco verde y manteniendo no-retry.

## 6. Superficies probables

El RED debe reducir esta lista antes de producción:

```text
src/ai_banking_customer_service/tools/escalate_case.py
src/ai_banking_customer_service/services/escalation_service.py
src/ai_banking_customer_service/agent/result_capture.py
src/ai_banking_customer_service/agent/orchestrator.py
tests/unit/tools/test_escalate_case.py
tests/unit/services/test_escalation_service.py
tests/unit/agent/test_result_capture.py
tests/unit/agent/test_orchestrator.py
docs/STATUS.md
odd/tasks/<task-09a6>.md
```

No se autorizan cambios en evaluación/reportes, config/policy, prompts/Jev,
fixtures/manifests, schemas públicos o dependencias.

## 7. Aceptación y verificación

La aceptación exacta se congela desde predecesoras. Debe incluir:

- exactamente un éxito confirmado produce verificación positiva;
- ausencia o contradicción nunca produce `TOOL_ESCALATION` ni éxito;
- rechazo pre-service y efecto incierto permanecen distintos;
- cualquier posible efecto impide retry automático;
- arquetipos históricos son explicables con fakes y sin IDs;
- eventos/reportes solo contienen códigos/booleanos permitidos;
- autorización, missing-data, admisión y privacidad no regresan.

Verificación permitida tras desbloqueo y GREEN:

```bash
uv run pytest -q <tests-focales-09A6>
uv run pytest -q <suites-afectadas-congeladas-en-el-gate>
uv run ruff check <archivos-Python-modificados>
uv run ruff format --check <archivos-Python-modificados>
git diff --check
```

No se permite evaluación development real ni held-out, red, modelos o Jev real.

## 8. Stop, rollback y handoff

Detener si no existe relectura compatible, el fix exige contrato de 09B, no se
puede saber si el service inició, se exponen IDs/texto, aparecen dos defectos o se
abre otro dominio runtime. El split crea una nueva spec numerada; no una subtarea.

El rollback revierte verificación, propagación y tests como unidad. Nunca deja
clasificación afirmando persistencia no confirmada ni introduce retry para
efectos inciertos.

Con 09A6 GREEN, revisada y congelada, se entrega el código y la matriz completa a
[Spec #09A7](spec_09a7.md). 09A7 permanece bloqueada y es la única autorizada
para congelar el corpus y realizar una recalibración development.
