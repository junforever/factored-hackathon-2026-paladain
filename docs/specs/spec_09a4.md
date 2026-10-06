# SPEC #09A4 — Estado canónico de datos faltantes

> **Estado:** `IMPLEMENTATION-BLOCKED`; planificación normativa, no autorizada.
> **Depende de:** [09A1](spec_09a1.md)–[09A3](spec_09a3.md) implementadas,
> GREEN, revisadas y congeladas.
> **Pregunta única:** ¿el runtime representa datos faltantes verificados con un
> único estado canónico sin confundirlos con denegación, fallo o abstención?

## 0. Resultado y valor funcional

09A4 hará que una carencia confirmada por lectura autorizada llegue sin
ambigüedad a captura, terminal y evaluación. Protege la respuesta segura de pedir
detalles y luego decidir, sin convertir missing-data en write, handoff,
autorización fallida o éxito fabricado.

Los detalles exactos se derivan de 09A1–09A3. El reporte histórico puede motivar
la pregunta, pero no prescribe causa ni fix.

## 1. Gate de entrada

Antes de implementar deben existir:

- vocabulario y lineage de missing-data emitidos por 09A1;
- proyección segura y paritaria de 09A2;
- autorización por ocurrencia confiable de 09A3;
- caracterización que separe lectura autorizada con dato ausente de denegación,
  error de lectura y resultado malformado;
- decisión documentada de cuál estado vigente es la fuente canónica.

Sin esos artefactos, 09A4 permanece bloqueada. Las superficies finales y asserts
se congelan antes del primer cambio.

## 2. Alcance futuro

### Incluye

- Canonicalizar el estado ya representable en el seam mínimo.
- Propagarlo con identidad exacta desde resultado validado hasta terminal.
- Impedir writes/handoffs posteriores cuando la regla vigente exige detalles.
- Mantener las plantillas seguras ES/PT vigentes cuando corresponda.
- Exponer únicamente estado y código cerrados en evidencia 09A1–09A2.

### Excluye

- ampliar qué campos cuentan como faltantes sin revisión separada;
- derivar ausencia desde texto, mensaje, escenario o expected outcome;
- tratar error o denegación como dato faltante;
- cambiar autorización, policy, prompt, Jev, threshold, modelo o corpus;
- cambiar schemas públicos o firmas de tools;
- decidir contratos de [Spec #09B](spec_09b.md), que permanece diferida;
- ejecutar evaluación development real o held-out, red, modelos o Jev real.

## 3. Invariantes

1. Solo una lectura exacta, autorizada, exitosa y verificada origina el positivo.
2. Autorización falsa o ausente domina; no se afirma que el dato fue consultado.
3. Error, retry, duplicado, mismatch o shape inválido no son missing-data.
4. Estado y booleanos son type-strict y de dominio cerrado.
5. La carencia bloquea writes/handoffs según la regla vigente.
6. Missing-data no prueba fallo de gobierno, service o persistencia.
7. Identidad de ocurrencia se conserva bajo concurrencia.
8. No se registran valores, IDs, mensajes, payloads ni merchant text.
9. No se fabrica abstención, escalamiento, ejecución, verificación ni SAR.
10. No hay ramas por case ID, idioma o modo evaluación.

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
primario. La canonicalización y propagación forman una unidad solo si el RED
prueba un mismo boundary; un gate de write independiente exige otra spec.

## 5. TDD estricto

Runner: `uv run pytest`; fakes determinísticos, sin corpus real, red, modelo ni
Jev.

**RED:** demostrar que el estado vigente se pierde, duplica o colisiona al cruzar
hooks → captura → orquestador. Incluir el negativo donde una lectura no
autorizada no puede activar la respuesta de datos faltantes.

**GREEN:** elegir una sola fuente canónica y propagarla por seams existentes. No
crear módulo de dominio, estado paralelo ni evento nuevo.

**TRIANGULATE:** presente/ausente; autorizado/denegado; lectura exitosa/error;
resultado malformado; booleanos no estrictos; lecturas homónimas; interleaving;
retry/duplicado; write posterior; handoff posterior; ES/PT; auditoría fallida;
JSON/Markdown y privacidad.

**REFACTOR:** solo con foco verde y sin ampliar la definición de missing-data.

## 6. Superficies probables

Las predecesoras deben reducir esta lista antes de producción:

```text
src/ai_banking_customer_service/agent/hooks.py
src/ai_banking_customer_service/agent/result_capture.py
src/ai_banking_customer_service/agent/orchestrator.py
tests/unit/agent/test_hooks.py
tests/unit/agent/test_result_capture.py
tests/unit/agent/test_orchestrator.py
docs/STATUS.md
odd/tasks/<task-09a4>.md
```

No se autorizan cambios en reportes, tools, services, policy/config, prompts,
Jev, fixtures, manifests o dependencias. La evaluación solo verifica que la
proyección 09A2 refleje el estado ya emitido.

## 7. Aceptación y verificación

La matriz exacta se congela desde 09A1–09A3. Como mínimo:

- un positivo canónico produce exactamente una solicitud permitida de detalles;
- todos los negativos quedan fail-closed y no escriben;
- writes/handoffs posteriores se detienen antes del service;
- denegación de autorización conserva su propia causa;
- evidencia distingue missing-data de gobierno, ejecución y verificación;
- comportamiento no relacionado, schemas y threshold `0.65` no cambian.

Verificación permitida tras desbloqueo y GREEN:

```bash
uv run pytest -q <tests-focales-09A4>
uv run pytest -q <suites-afectadas-congeladas-en-el-gate>
uv run ruff check <archivos-Python-modificados>
uv run ruff format --check <archivos-Python-modificados>
git diff --check
```

No se permite evaluación development real ni held-out, red, modelos o Jev real.

## 8. Stop, rollback y handoff

Detener si no existe estado seguro derivable, la correlación no es exacta,
aparecen varias semánticas, se requiere texto libre, cambia una regla de negocio
o se abre otro dominio runtime. El split requerido siempre crea una nueva spec
numerada; ninguna subtarea evita el gate.

El rollback elimina canonicalización y propagación como unidad, sin reabrir
writes ni reinterpretar denegaciones. No deja consumidores confiando en un
estado que el productor ya no garantiza.

Con 09A4 GREEN, revisada y congelada, se entrega su estado y matriz negativa a
[Spec #09A5](spec_09a5.md). 09A5 permanece bloqueada y es la única dueña de la
admisión de gobierno del handoff deseado.
