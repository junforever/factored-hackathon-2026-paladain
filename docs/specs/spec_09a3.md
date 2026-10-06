# SPEC #09A3 — Verdad de evidencia de autorización

> **Estado:** `IMPLEMENTATION-BLOCKED`; planificación normativa, no autorizada.
> **Depende de:** [09A1](spec_09a1.md) y [09A2](spec_09a2.md) implementadas,
> GREEN, revisadas y con contrato/proyección congelados.
> **Pregunta única:** ¿`authorization_verified` expresa la autorización real de
> la ocurrencia exacta sin confundirse con relación, admisión o ejecución?

## 0. Resultado y valor funcional

09A3 corregirá solo la verdad end-to-end de autorización. `true` significará que
el provider válido autorizó al principal exacto para el producto exacto de esa
llamada. Ausencia, contradicción, correlación ambigua o error permanecerán en
`false`.

La causa y el boundary exactos deben observarse mediante 09A1–09A2. Hasta recibir
ese handoff no se escribe código ni tests para esta spec.

## 1. Gate de entrada

Deben existir como artefactos revisados:

- matriz causal runtime de autorización por ocurrencia de 09A1;
- proyección segura y paritaria de esa matriz por 09A2;
- allowlists, tipos y estados negativos congelados;
- prueba de correlación unívoca o evidencia explícita de detención;
- primer boundary donde la evidencia diverge de la decisión real;
- negativos de privacidad sin IDs en reportes.

Un outcome agregado como `unauthorized_product_access` no sustituye estas
entradas. Si falta una, 09A3 sigue bloqueada.

## 2. Alcance futuro

### Incluye

- Reproducir con fakes la primera divergencia causal observada.
- Corregir el mínimo transporte o asociación de autorización.
- Conservar `false` para missing, mismatch, retry, duplicado, provider inválido,
  auditoría no durable y principal/producto distintos.
- Verificar llamadas homónimas, concurrencia e interleaving.
- Mantener intacto el evento/proyección congelados salvo sus valores verdaderos.

### Excluye

- decidir autorización desde `product_id`, complaint owner o expected outcome;
- modificar providers, grants, policy bancaria o deny-by-default;
- cambiar tools, terminales, missing-data, handoff o persistencia;
- cambiar prompts, Jev, modelo, dependencia, threshold o corpus;
- modificar schemas públicos o model-facing;
- ejecutar evaluación development real o held-out, red, modelos o Jev real;
- implementar [Spec #09B](spec_09b.md), que permanece diferida.

## 3. Invariantes

1. Relación de datos NO es autorización.
2. Principal, reclamación y producto conservan identidad/valor exactos.
3. Solo `bool` estricto es válido; `1`, strings y objetos truthy fallan.
4. Solo adapter/provider inyectado origina evidencia autorizante.
5. `allow`, éxito de tool o resultado verificado no sintetizan autorización.
6. Pérdida de correlación, ausencia o contradicción niega por defecto.
7. IDs, principal, payload/error de provider y texto libre no salen en auditoría.
8. No hay ramas por caso, idioma, escenario, corpus o evaluación.
9. El evento 09A1 y la proyección 09A2 conservan forma y privacidad.
10. Un cambio de schema público obliga a detener y revisar.

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
primario. El boundary causal observado define ese dominio; transporte, emisión y
proyección no pueden agruparse si constituyen dominios independientes.

## 5. TDD estricto

Runner: `uv run pytest`; providers y lifecycle son fakes, sin corpus real,
red, modelo ni Jev.

**RED:** reproducir la primera divergencia donde una ocurrencia no autorizada
queda positiva o una autorizada pierde evidencia. Debe cruzar el lifecycle fake;
no vale inyectar el booleano directamente en el evento final.

**GREEN:** reparar solo ese boundary. No tocar decisiones semánticas, threshold
`0.65`, tools ni clasificación no relacionada.

**TRIANGULATE:** autorizado exacto; no autenticado; producto denegado; provider
unavailable/malformado; complaint/product/principal mismatch; evidencia ausente;
booleano no estricto; duplicado; retry; llamadas homónimas; interleaving; lineage
huérfano; auditoría fallida; JSON/Markdown.

**REFACTOR:** solo con foco verde y sin abstraer providers adicionales.

## 6. Superficies probables

09A1–09A2 deben reducir la lista al primer boundary antes de producción:

```text
src/ai_banking_customer_service/governance/adapter.py
src/ai_banking_customer_service/agent/hooks.py
src/ai_banking_customer_service/agent/result_capture.py
src/ai_banking_customer_service/agent/orchestrator.py
tests/unit/governance/test_adapter.py
tests/unit/agent/test_hooks.py
tests/unit/agent/test_result_capture.py
tests/unit/agent/test_orchestrator.py
docs/STATUS.md
odd/tasks/<task-09a3>.md
```

No se anticipan cambios en evaluación/reportes, fixtures, manifests, config,
policy, tools, services, prompts, Jev ni dependencias.

## 7. Aceptación y verificación

La aceptación exacta se congela desde la matriz predecesora. Como mínimo:

- cada ocurrencia recibe solo su evidencia causal;
- ningún negativo produce `authorization_verified is True`;
- un positivo exacto conserva `true` hasta evento y reporte;
- acceso sensible verificado sin `true` sigue siendo unsafe;
- denegación y fallo de ejecución permanecen causas distintas;
- privacidad y paridad 09A1–09A2 siguen GREEN;
- decisiones, terminales y schemas públicos no cambian.

Verificación permitida tras desbloqueo y GREEN:

```bash
uv run pytest -q <tests-focales-09A3>
uv run pytest -q <suites-afectadas-congeladas-en-el-gate>
uv run ruff check <archivos-Python-modificados>
uv run ruff format --check <archivos-Python-modificados>
git diff --check
```

No se permite evaluación development real ni held-out, red, modelos o Jev real.

## 8. Stop, rollback y handoff

Detener si la causa no es reproducible con fakes, exige inferir autorización,
expone IDs, cambia contrato público, abre otro dominio runtime o revela varias
causas independientes. El gate anti-mega exige una nueva spec numerada, no una
subtarea, para cualquier split.

El rollback revierte transporte/asociación y tests como una unidad, manteniendo
deny-by-default. Nunca restaura `product_id ⇒ autorizado` ni deja consumidores
confiando en evidencia que ya no se emite.

Con 09A3 GREEN, revisada y congelada, se entrega la matriz de autorización real a
[Spec #09A4](spec_09a4.md). 09A4 permanece bloqueada y es la única dueña del
estado canónico de datos faltantes.
