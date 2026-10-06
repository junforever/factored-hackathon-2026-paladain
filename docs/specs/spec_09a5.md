# SPEC #09A5 — Admisión de gobierno para el handoff deseado

> **Estado:** `IMPLEMENTATION-BLOCKED`; planificación normativa, no autorizada.
> **Depende de:** [09A1](spec_09a1.md)–[09A4](spec_09a4.md) implementadas,
> GREEN, revisadas y congeladas.
> **Pregunta única:** ¿un handoff requerido y determinísticamente elegible llega
> a la decisión de gobierno correcta antes de tocar persistencia?

## 0. Resultado y valor funcional

09A5 aislará la admisión de `escalate_case`: distinguirá regla dura,
autorización, missing-data y gating semántico, y corregirá solo el primer
boundary que bloquee erróneamente un handoff deseado.

La admisión únicamente permite continuar. No afirma ejecución, persistencia,
verificación ni `TOOL_ESCALATION`. Los contratos exactos se finalizan desde la
evidencia causal predecesora.

## 1. Gate de entrada

Debe existir una matriz fake revisada que separe, sin IDs de caso:

- handoff requerido, autorizado y con datos/argumentos válidos;
- denegación de autorización;
- missing-data canónico;
- argumento o identidad inválidos;
- decisión semántica allow/block;
- ejecución y persistencia, todavía fuera de esta spec.

09A1–09A2 deben señalar el primer gate divergente por ocurrencia; 09A3–09A4
deben probar autorización y missing-data. Un terminal agregado no desbloquea 09A5.

## 2. Alcance futuro

### Incluye

- Caracterizar la precedencia exacta antes de `escalate_case`.
- Reproducir un handoff elegible y un negativo material por gate con fakes.
- Corregir el mínimo wiring o decisión determinística demostrada.
- Conservar evidencia por etapa y reason code cerrado.
- Confirmar que el service no se invoca desde esta prueba de admisión.

### Excluye

- persistir o verificar el handoff, responsabilidad de 09A6;
- iniciar [Spec #09B](spec_09b.md), que permanece diferida, o definir sus contratos;
- cambiar firma/defaults de `escalate_case` o aceptar texto nuevo;
- inferir policy desde fixture, escenario, idioma o expected outcome;
- cambiar corpus, modelo, dependencia, prompt o schema público;
- ejecutar evaluación development real o held-out, red, modelos o Jev real.

## 3. Threshold vinculante

El default vinculante es **no cambiar thresholds**. Se preserva
`tool_gating.min_intent_matches_tool == 0.65`.

Primero pasan transporte, precedencia, type strictness y proyección con `0.65`.
No se modifica prompt, pregunta, state ni threshold para acomodar un fake.

Si evidencia determinística demuestra que todos los contratos anteriores son
correctos y la única divergencia es semántica, el trabajo se detiene. Cualquier
excepción requiere revisar esta spec en otro work unit con matriz positiva y
negativa ES/PT, frontera `== 0.65` e inmediatamente inferior, causa exacta,
propietario y prueba de que negativos siguen bloqueados.

Nunca se ajusta desde scores, reportes históricos, promedios, case IDs ni para
maximizar SAR.

## 4. Invariantes

1. Autorización, relación, elegibilidad y coherencia semántica son distintas.
2. Reglas duras y tipos estrictos se resuelven antes de Jev.
3. Un bloqueo determinístico no llama Jev.
4. Un allow semántico no reemplaza policy.
5. Identidad de complaint/tool/args permanece exacta.
6. Missing-data bloquea handoff cuando el contrato vigente lo exige.
7. `allow` no equivale a ejecución, persistencia, verificación ni éxito.
8. Reason codes son cerrados; no se reportan scores ni razones libres.
9. No hay ramas por caso, escenario, idioma o evaluación.
10. Schemas públicos no cambian sin detención y revisión.

## 5. Gate anti-mega-spec obligatorio

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
primario. 09A5 solo puede corregir un gate de admisión; varios gates o tuning son
work units independientes y exigen nuevas specs numeradas.

## 6. TDD estricto

Runner: `uv run pytest`; cliente Jev fake, sin corpus real, red, modelo ni Jev
real.

**RED:** el handoff elegible fake llega al gate incorrecto, recibe una decisión
incorrecta o pierde su reason code. A la vez, un negativo material debe seguir
siendo inseguro de admitir.

**GREEN:** corregir solo el boundary demostrado, manteniendo `0.65`, pregunta,
state, autorización y persistencia intactos.

**TRIANGULATE:** positivo ES/PT; no autenticado; producto denegado; missing-data;
complaint/args/tipos no exactos; señal o metadata inválida; `== 0.65`;
inmediatamente inferior; auditoría fallida; interleaving; duplicado.

**REFACTOR:** solo con foco verde y sin generalizar el gate.

## 7. Superficies probables

La matriz causal debe reducir esta lista antes de producción:

```text
src/ai_banking_customer_service/agent/hooks.py
src/ai_banking_customer_service/governance/adapter.py
src/ai_banking_customer_service/governance/jev/evaluations.py
src/ai_banking_customer_service/governance/jev/decision.py
tests/unit/agent/test_hooks.py
tests/unit/governance/test_adapter.py
tests/unit/governance/jev/test_evaluations.py
tests/unit/governance/jev/test_governance.py
docs/STATUS.md
odd/tasks/<task-09a5>.md
```

Orquestador, tool, service, evaluación/reportes, config/policy, prompts y fixtures
no están autorizados por la planificación base.

## 8. Aceptación y verificación

Antes de implementar se congelan asserts desde 09A1–09A4. Como mínimo:

- cada positivo elegible alcanza el gate semántico exacto;
- cada negativo se detiene en el primer gate y no ejecuta service;
- evidencia distingue stage, allow/block y reason code sin score;
- no se afirma persistencia ni terminal desde admisión;
- `0.65`, prompt, modelo, dependencias, corpus y schemas no cambian;
- autorización, missing-data, paridad y privacidad siguen GREEN.

Verificación permitida tras desbloqueo y GREEN:

```bash
uv run pytest -q <tests-focales-09A5>
uv run pytest -q <suites-de-gobierno-afectadas>
uv run ruff check <archivos-Python-modificados>
uv run ruff format --check <archivos-Python-modificados>
git diff --check
```

No se permite evaluación development real ni held-out, red, modelos o Jev real.

## 9. Stop, rollback y handoff

Detener si la causa exige tuning, diverge más de un gate, falta un negativo, el
fix requiere persistencia/terminales, cambia schema público o abre otro dominio.
El split siempre crea una nueva spec numerada; no se oculta en subtareas.

El rollback revierte admisión y tests como unidad; conserva denegaciones seguras
y `0.65`. No deja un allow sin reason code ni bypass determinístico.

Con 09A5 GREEN, revisada y congelada, se entregan solo handoffs admitidos y su
evidencia a [Spec #09A6](spec_09a6.md). 09A6 permanece bloqueada y es la única
dueña de persistencia verificada.
