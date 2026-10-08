# SPEC #09A4A — Gate de escritura ante datos faltantes

> **Estado:** `IMPLEMENTED`; verificación independiente y revisión nativa aprobadas; aceptación y congelación por el usuario pendientes.
> **Depende de:** [09A4](spec_09a4.md) completada, GREEN, revisada, aceptada y congelada el 2026-10-08.
> **Pregunta única:** ¿el runtime cancela antes del service cada `block_card` o
> `escalate_case` posterior cuando 09A4 demuestra datos faltantes canónicos?

## 0. Resultado y valor funcional

09A4A añade un único gate independiente antes de los services de escritura.
Consume la verdad canónica por ocurrencia de 09A4 y cancela llamadas posteriores
a `block_card` y `escalate_case` cuando falta `merchant_name`, sin reinterpretar
la lectura ni fabricar éxito, persistencia o escalamiento.

La cancelación histórica basada en booleanos compartidos no constituye el RED
ni prueba este contrato. El RED debe observar la ausencia actual del gate para
el estado canónico de 09A4.

## 1. Gate de entrada

09A4 debe estar completada, GREEN, revisada y congelada. Antes del primer cambio
de producción se congelan:

- la ocurrencia autorizada, exitosa y no ambigua que origina missing-data;
- la precedencia vigente de una denegación de gobierno;
- el punto exacto anterior a la invocación del service;
- las superficies y el forecast total dentro del límite de esta spec.

El usuario confirmó la revisión, aceptación y congelación de 09A4 el
2026-10-08, desbloqueando este candidate.

## 2. Alcance

### Incluye

- Consumir exclusivamente el estado canónico ya definido por 09A4.
- Cancelar `block_card` y `escalate_case` antes del service.
- Preservar una denegación de gobierno anterior y su reason code.
- Transportar la cancelación observada hacia terminal y evidencia de 09A4.
- Cubrir ambas acciones y un read permitido que no debe cancelarse.

### Excluye

- volver a derivar missing-data desde texto, IDs, booleanos o sets paralelos;
- cambiar la definición de campo faltante o la identidad de ocurrencia;
- cambiar autorización, policy, prompt, Jev, threshold, modelo o corpus;
- modificar tools, services, schemas públicos o firmas;
- decidir admisión semántica de handoff, propiedad de [09A5](spec_09a5.md);
- ejecutar evaluación real, red, modelo o Jev real.

## 3. Invariantes

1. Solo un positivo canónico de 09A4 activa el gate.
2. El gate aplica únicamente a `block_card` y `escalate_case` posteriores.
3. La cancelación ocurre antes de cualquier service o side effect.
4. Gobierno `block` conserva precedencia y razón propia.
5. Reads, negativos y estados ambiguos no se cancelan por missing-data.
6. No se fabrica ejecución, verificación, persistencia, handoff ni SAR.
7. No hay ramas por case ID, idioma, escenario o modo evaluación.
8. No se registra merchant text, payload, mensaje ni valor sensible.

## 4. Gate anti-mega-spec obligatorio

El work unit completo apunta a **230–285 líneas authored** y no puede superar
**300**. El conteo incluye producción, tests y deltas no generados de cierre en
spec, status y tracking; solo se excluyen artefactos generados.

Un forecast superior a 300 líneas o más de un dominio runtime primario obliga a
detener y crear otra spec numerada. Tests y docs viajan con el comportamiento;
no se permite dividir por tipo de archivo ni comprimir cobertura para caber.

## 5. TDD estricto

Runner: `uv run pytest`; fakes determinísticos, sin corpus real, red, modelo ni
Jev.

**RED:** desde una lectura `get_recent_transactions` autorizada, exitosa y
canónicamente missing según 09A4, demostrar por separado que una llamada
posterior a `block_card` y otra a `escalate_case` todavía alcanzan el seam de
service porque el gate pre-service no existe. Este fallo nuevo debe observarse
antes de producción; no se reutiliza como RED una cancelación histórica GREEN.

**GREEN:** añadir el mínimo productor de cancelación que consuma la ocurrencia
canónica y detenga ambas acciones antes del service.

**TRIANGULATE:** acción block/handoff; dato presente/missing; autorizado/denegado;
error, malformed, retry, duplicado y homónimo; read no cancelado; precedencia de
gobierno; ES/PT; terminal, evidencia, privacidad e interleaving.

**REFACTOR:** solo con foco verde; sin nuevo módulo, schema, evento ni estado
positivo alternativo.

## 6. Superficies probables exactas

```text
src/ai_banking_customer_service/agent/hooks.py
src/ai_banking_customer_service/agent/result_capture.py
tests/unit/agent/test_hooks.py
tests/unit/agent/test_result_capture.py
tests/unit/agent/test_orchestrator.py
docs/specs/spec_09a4a.md
docs/STATUS.md
odd/tasks/spec-09a4a-missing-data-write-gate.md
```

`orchestrator.py`, tools, services, policy/config, prompts, Jev, fixtures,
manifests, dependencias y reportes quedan fuera salvo revisión normativa previa.

## 7. Aceptación y verificación

- Ambos writes se detienen antes del service ante el positivo canónico exacto.
- Missing-data presente, ambiguo o no autorizado no activa el gate.
- Gobierno denegado mantiene precedencia y evidencia propia.
- Reads y comportamiento no relacionado permanecen sin cambios.
- Terminal/evidencia reciben la cancelación sin rederivar missing-data.
- No cambian schemas públicos, firma de tools ni threshold `0.65`.
- El total authored observado, incluido el cierre documental, es ≤300.

Verificación prevista:

```bash
uv run pytest -q tests/unit/agent/test_result_capture.py tests/unit/agent/test_hooks.py tests/unit/agent/test_orchestrator.py
uv run ruff check src/ai_banking_customer_service/agent/hooks.py src/ai_banking_customer_service/agent/result_capture.py tests/unit/agent/test_hooks.py tests/unit/agent/test_result_capture.py tests/unit/agent/test_orchestrator.py
uv run ruff format --check src/ai_banking_customer_service/agent/hooks.py src/ai_banking_customer_service/agent/result_capture.py tests/unit/agent/test_hooks.py tests/unit/agent/test_result_capture.py tests/unit/agent/test_orchestrator.py
git diff --check
```

## 8. Evidencia del candidate

- RED: el test focal dejó que ambos writes alcanzaran el seam (`2 failed`).
- GREEN: el mismo test pasó para `block_card` y `escalate_case` (`2 passed`).
- Verificador independiente: PASS; foco `2 passed`, afectadas `185 passed`, suite completa `1293 passed` con un warning Pydantic ajeno, y Ruff check/format y diff check pasaron.
- El candidate mide 253 líneas authored en un dominio runtime.
- Work-unit commit: `acb091a64ab33d2ab1eba13407e16a631f24770b` (`fix(agent): gate writes on canonical missing data`).
- La revisión nativa `review-aed25f0ecbbab6ca` fue aprobada y su acknowledgement exacto fue completado; la autoridad quedó consumida para el target `sha256:734db8c27df208a44bd632fd61374fc7277fdaf8d0c779fe290fe6bb6a323b3f`.
- Existe un advisory informativo no bloqueante: `R3-001`, reliability, `src/ai_banking_customer_service/agent/result_capture.py:232-242`; no es una corrección.
- No se ejecutaron evaluación real, red, modelo ni Jev.
- La aceptación y congelación de 09A4A por el usuario todavía no están registradas.

## 9. Stop, rollback y handoff

Detener si el gate necesita rederivar el positivo, tocar services, cambiar
policy, abrir otro dominio o superar 300 líneas. El rollback elimina productor,
transporte y tests del gate como una unidad, sin revertir 09A4.

La implementación de 09A4A está GREEN, verificada y revisada. El siguiente paso
es la revisión, aceptación y congelación por el usuario; solo después
[09A5](spec_09a5.md) podrá consumir la cadena completa de canonicalización y
cancelación pre-service y podrán decidirse entregas posteriores.
