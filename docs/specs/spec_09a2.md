# SPEC #09A2 — Proyección segura de evaluación y paridad de reportes

> **Estado:** `IMPLEMENTATION-BLOCKED`; no autorizada para implementación.
> **Depende de:** [Spec #09A1](spec_09a1.md) implementada, GREEN, revisada y con
> contrato de evento runtime congelado.
> **Pregunta única:** ¿evaluación proyecta la evidencia canónica sin alterar su
> significado y con paridad exacta entre JSON y Markdown?

## 0. Resultado y valor funcional

09A2 DEBE consumir el evento congelado de 09A1 y producir una proyección segura,
acotada y determinística en `case_outcomes`, JSON y Markdown. Permitirá comparar
causas sin inferirlas desde terminales agregados ni exponer datos sensibles.

Esta spec solo observa y proyecta. NO emite eventos runtime, NO modifica hooks,
captura u orquestador y NO cambia clasificación de éxito/unsafe, comportamiento,
policy, terminales ni ejecución de tools.

## 1. Gate de entrada

Antes de implementar deben existir como artefactos revisados de 09A1:

- schema exacto del evento y versión compatible;
- allowlist finita por dimensión y reglas type-strict;
- orden canónico y semántica de ordinales;
- límites de 16 ocurrencias, 64 code points y 8 KiB;
- matriz de evidencia inválida/fail-closed;
- negativos de privacidad y fixtures fake del contrato;
- prueba de que el evento cruza el boundary de evaluación sin perderse.

Si falta un artefacto o el contrato sigue cambiando, 09A2 permanece bloqueada.
No se redefine el contrato dentro de esta spec.

## 2. Alcance

### 2.1 Incluye

- Caracterizar cómo worker/runner entregan hoy eventos a clasificación.
- Validar y consumir únicamente el evento canónico congelado de 09A1.
- Añadir una proyección sanitizada a cada outcome sin inferir hechos ausentes.
- Mantener una ocurrencia por intento y el orden canónico recibido.
- Representar los mismos valores, estados y truncamiento en JSON y Markdown.
- Hacer legibles reportes históricos sin tratar ausencia como evidencia positiva.
- Probar bounds, determinismo, compatibilidad y privacidad con objetos fake.

### 2.2 Fuera de alcance

09A2 MUST NOT:

- modificar contrato/audit sink, hooks, captura, orquestador o emisión runtime;
- cambiar decisiones de unsafe, SAR, tool-plan, terminal o política;
- corregir autorización, missing-data, admisión o persistencia;
- enriquecer desde payloads de tools, provider, Jev, mensajes o IDs;
- cambiar worker wire, schemas públicos o manifests sin detener y revisar;
- ejecutar evaluación development real o held-out, red, modelos o Jev real;
- modificar corpus, fixtures reales, sandbox, config, prompt o dependencias;
- reabrir [Spec #09B](spec_09b.md), que permanece diferida.

## 3. Contrato de proyección

Cada outcome puede contener una colección `canonical_evidence` derivada solo del
evento validado. La proyección conserva:

- ordinal de ocurrencia;
- nombre allowlisted de tool;
- cinco dimensiones y sus códigos cerrados;
- booleanos estrictos y `null` permitido;
- marca cerrada de invalidación o truncamiento.

No agrega narrativa, causa inferida, score, conteo de éxito ni resumen que pueda
ocultar ocurrencias negativas. Un evento ausente se representa como ausencia de
evidencia, no como estados por defecto favorables.

Un evento de versión desconocida, shape inválido o vocabulario no allowlisted no
rompe el reporte: produce el diagnóstico cerrado previsto por 09A1 y nunca
alimenta una clasificación positiva.

## 4. Bounds, orden y paridad

Los límites congelados por 09A1 se aplican antes de renderizar:

- máximo 16 ocurrencias por caso;
- códigos de hasta 64 code points y solo allowlisted;
- bloque serializado de hasta 8 KiB por caso;
- claves en orden fijo;
- ocurrencias en orden canónico, sin resort heurístico.

JSON es la representación estructurada de referencia y Markdown es una vista
uno-a-uno. Ambos DEBEN contener el mismo número de ocurrencias, ordinales,
nombres, códigos, booleanos, `null`, invalidaciones y truncamientos en el mismo
orden. Markdown no resume, traduce, completa ni omite fallos.

La salida es determinística para el mismo input. No depende de locale, hash-map
order, timestamp, path, case ID ni texto del modelo.

## 5. Privacidad y compatibilidad

La proyección permite solo los campos del contrato 09A1. Los tests deben negar,
tanto en JSON como Markdown:

- IDs bancarios o de handoff/escalation;
- principal, credenciales, PAN o CVV;
- mensajes, argumentos, resultados completos o merchant text;
- paths, excepciones, errores del provider;
- pregunta, state, respuesta, score, metadata o razón libre de Jev.

No se hashean ni truncan datos prohibidos: se rechazan. Los reportes anteriores
sin `canonical_evidence` siguen siendo legibles. Su ausencia nunca prueba
cumplimiento, autorización, ejecución ni verificación.

No cambian hashes, bytes o referencias de development/held-out. No se reescriben
reportes históricos.

## 6. Invariantes

1. La evaluación consume; no reinterpreta ni corrige el evento runtime.
2. `allowed` no implica autorización, ejecución, verificación ni éxito.
3. Un outcome exitoso no rellena evidencia ausente.
4. Evidencia inválida no modifica la clasificación material del caso.
5. JSON y Markdown son semánticamente idénticos y tienen el mismo orden.
6. No se agrupan llamadas homónimas ni retries.
7. No hay ramas por case ID, idioma, corpus o expected outcome.
8. No se crea otro vocabulario ni aliases de presentación.
9. Ningún schema público cambia sin detención y revisión.
10. Reportar mejor no cambia el comportamiento observado.

## 7. Gate anti-mega-spec obligatorio

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
solo dominio runtime primario. Para 09A2, el único dominio permitido es evaluación
offline; cualquier cambio de emisión runtime vuelve a 09A1 o exige nueva spec.

## 8. TDD estricto

Runner: `uv run pytest`; todos los inputs son eventos fake congelados, sin corpus
real, red, modelo ni Jev.

**RED:** demostrar que clasificación/reporte omiten hoy la evidencia, que JSON y
Markdown divergen, o que un payload inválido puede filtrarse o alterar el orden.
El RED consume el contrato 09A1 sin modificar productores.

**GREEN:** añadir la proyección mínima sanitizada y paritaria. No cambiar reglas
de unsafe/SAR, terminales, worker wire ni runtime.

**TRIANGULATE:** cero/una/varias/más de 16 ocurrencias; todos los estados de las
cinco dimensiones; orden adversarial; homónimos; duplicado; evento ausente;
versión desconocida; booleano no estricto; código desconocido; payload oversized;
JSON/Markdown; reportes antiguos; y cada dato prohibido.

**REFACTOR:** solo con foco verde y sin crear un framework de renderizado.

## 9. Superficies probables

La exploración debe reducir esta lista antes de producción:

```text
src/ai_banking_customer_service/evaluation/classification.py
src/ai_banking_customer_service/evaluation/report.py
tests/unit/evaluation/test_classification.py
tests/unit/evaluation/test_report.py
docs/STATUS.md
odd/tasks/<task-09a2>.md
```

`agent/`, `governance/`, `observability/`, tools y services no están autorizados.
Worker/runner solo se agregan mediante revisión de esta spec si un RED demuestra
que el evento congelado no cruza su boundary sin cambiar wire público.

## 10. Aceptación y verificación

09A2 se acepta solo si:

- cada dimensión del evento se proyecta sin transformación semántica;
- JSON y Markdown tienen paridad exacta de valores, cantidad y orden;
- malformed, unknown, oversized y truncado permanecen fail-closed;
- todos los negativos de privacidad pasan en ambos formatos;
- reportes anteriores siguen siendo legibles;
- clasificación material y comportamiento runtime no cambian.

Verificación permitida tras GREEN:

```bash
uv run pytest -q <tests-focales-09A2>
uv run pytest -q <suites-evaluation-afectadas>
uv run ruff check <archivos-Python-modificados>
uv run ruff format --check <archivos-Python-modificados>
git diff --check
```

No se permite evaluación development real ni held-out, red, modelos o Jev real.

## 11. Detención, rollback y handoff

Detener si la proyección exige cambiar el productor, inferir una causa, tocar
clasificación material, exponer datos prohibidos, cambiar wire público o abrir
otro dominio runtime. El gate anti-mega prevalece aunque el cambio parezca menor.

El rollback elimina campos, validación de consumo y renderizado de 09A2 como una
unidad. Conserva intactos los eventos 09A1 y mantiene legibles los reportes
anteriores; no deja Markdown mostrando datos ausentes del JSON.

Con 09A2 GREEN, revisada y congelada, su matriz causal visible se entrega a
[Spec #09A3](spec_09a3.md). 09A3 permanece bloqueada hasta ese handoff y es la
única dueña de corregir la verdad de autorización.
