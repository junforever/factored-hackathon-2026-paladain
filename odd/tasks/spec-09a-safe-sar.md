# Spec 09A — Recuperación segura de SAR

Ubicación del documento: `odd/tasks/spec-09a-safe-sar.md`

## Objetivo

Implementar `docs/specs/spec_09a.md` mediante TDD estricto para recuperar Safe Automated Resolution (SAR) en desarrollo con autorización explícita por producto, sin debilitar reglas determinísticas, verificación, privacidad ni el conjunto held-out congelado.

## Problema y justificación

El flujo actual deriva `authenticated=True` y productos autorizados desde la relación de la reclamación. Esa relación identifica el producto correcto, pero no acredita que el principal pueda consultarlo o actuar sobre él. Además, el juicio semántico actual bloquea lecturas preparatorias legítimas, por lo que SAR permanece en 0%.

## Alcance

- Incorporar un seam tipado, inyectable y fail-closed de autorización de producto.
- Aplicar autorización independiente a las cuatro tools antes de Jev.
- Mantener producción deny-by-default y usar grants case-local en evaluación.
- Reformular y calibrar el juicio semántico solo con development.
- Versionar development como `v1.0.3` sin modificar ni ejecutar held-out `v1.0.2`.
- Exigir evidencia de autorización en auditoría, clasificación SAR, unsafe outcomes y reportes acotados.
- Actualizar `docs/STATUS.md` únicamente con evidencia observada.

## Restricciones

- Seguir `docs/specs/spec_09a.md`; no hay una decisión de producto abierta.
- TDD estricto: RED → GREEN → TRIANGULATE → REFACTOR por microciclo.
- Runner autoritativo: `uv run pytest`.
- Tests determinísticos sin red, modelo real, Jev real ni credenciales.
- `product_id` resuelve relación, nunca autorización.
- No cambiar firmas o schemas model-facing de las cuatro tools.
- No agregar dependencias, infraestructura bancaria, allowlists por caso ni bypasses de evaluación.
- No modificar ni ejecutar `evals/cases/held_out_v1.0.2.yaml` ni `evals/held_out_manifest.json`.
- Documentos del proyecto en español neutro; código, identificadores, comentarios técnicos y commits en inglés.
- No realizar commits, push, PR ni merge sin autorización explícita del usuario.

## Ruta y delegación

Todos los microciclos usan un único writer delegado por vez. Disparadores: más de un archivo no trivial, preparación de escritura y lógica de seguridad/evaluación con contexto amplio. La verificación final se delegará según el plan RDD/ASSESS vigente; el parent conservará una comprobación puntual.

## Pronóstico de entrega

El cambio normativo probablemente supera 400 líneas autoradas por incluir seam, composición, fixtures versionados, clasificación, reportes, CLI, documentación y tests. Estrategia elegida: `feature-branch-chain`; los futuros PRs se dividirán en slices revisables desde la rama feature/tracker. El usuario autorizó el commit de S09A-T1; push, PR y merge permanecen sin autorizar.

## Tareas

- [x] **S09A-T1 — Seam de autorización y precedencia fail-closed**
  - Ruta: writer delegado; disparador: múltiples archivos de producción y tests de seguridad.
  - Crear resultado/provider tipados, validar tuplas y booleanos estrictos, resolver reclamación/producto antes del provider y negar por defecto sin llamar a Jev.
  - Cubrir autorizado, no autenticado, producto denegado, provider ausente/excepción/timeout, respuesta malformada, complaint mismatch y producto ausente.
  - Superficies previstas: `src/ai_banking_customer_service/governance/adapter.py`, `src/ai_banking_customer_service/governance/jev/evaluations.py`, `tests/unit/governance/test_adapter.py`, `tests/unit/governance/jev/test_evaluations.py`.
  - TDD: RED por `ImportError` al faltar `ProductAuthorization`; GREEN focal `6 passed, 219 deselected`; triangulación final `225 passed`.
  - Verificación independiente: 225 tests, Ruff check, Ruff format y `git diff --check` pasaron; sin defectos.
  - ASSESS nativo: `unassessable` porque el task ODD nuevo no estaba declarado; el plan exigió verificador independiente y se cumplió.
  - Tamaño autorado del work unit: 531 líneas (445 adiciones + 86 eliminaciones), por encima del umbral orientativo de 400; requiere elegir estrategia de entrega antes del commit.
  - Entrega: commit `4354752` (`feat(governance): add explicit product authorization seam`); primer slice de `feature-branch-chain`.
  - Revisión nativa: ASSESS medio y review due por presupuesto; dos START posteriores a INSPECT explícito devolvieron `consent-binding-expired`, sin lineage creado. Se conserva la verificación independiente aprobada y el outcome nativo queda unavailable para este candidato.

- [x] **S09A-T2 — Composición uniforme para cuatro tools**
  - Ruta: writer delegado; disparador: cambios coordinados en bootstrap, hooks, factory/worker y tests.
  - Aplicar autorización a lecturas y escrituras; producción deny-all; evaluación con sentinel y provider case-local creados dentro del hijo.
  - Preservar principal/IDs fuera de Jev, auditoría, reportes y schemas; conservar confirmación y contratos exactos.
  - Superficies previstas: `app/bootstrap.py`, `src/ai_banking_customer_service/agent/hooks.py`, `src/ai_banking_customer_service/evaluation/factory.py`, `src/ai_banking_customer_service/evaluation/worker.py` y tests correspondientes.
  - TDD: RED focal `5 failed, 58 deselected` y privacidad/excepción `1 failed, 8 deselected`; GREEN equivalentes `5 passed` y `1 passed`; triangulación final `143 passed`.
  - Checks del writer: 143 tests, Ruff check y Ruff format pasaron; sin scope expansion.
  - ASSESS nativo: riesgo medio, 386 líneas cambiadas, `reviewDue=false`; la auto-verificación del writer es suficiente. Spot-check parent: `tests/unit/evaluation/test_factory.py` — 14 passed.
  - Entrega: commit `ceabf8a` (`feat(auth): wire product authorization composition`); segundo slice de `feature-branch-chain`.
  - Revisión nativa: ASSESS medio, 393 líneas committed-only, `reviewDue=false`; diferida al cierre del slice/PR.

- [ ] **S09A-T3 — Juicio semántico y calibración development-only** *(en progreso)*
  - Ruta: writer delegado; disparador: cambio Jev y matriz ES/PT con tests.
  - Observar RED para lectura preparatoria legítima frente a llamada irrelevante; ajustar pregunta/state para necesidad y proporcionalidad antes de considerar el umbral.
  - Cambiar policy/decision solo si una frontera RED separa positivos y negativos; cubrir `== threshold`, inmediatamente inferior, señales y metadata inválidas.
  - Superficies previstas: `src/ai_banking_customer_service/governance/jev/evaluations.py`, tests Jev/governance; `configs/policy.yaml`, `src/ai_banking_customer_service/config.py` y `decision.py` únicamente si la evidencia exige policy tipada distinta.
  - TDD: RED semántico `1 failed, 293 passed`; GREEN `294 passed`; RED de minimización `6 failed, 288 passed`; GREEN y matriz final `313 passed`.
  - Resultado: una sola pregunta atómica de necesidad/proporcionalidad; state sin autorización, confirmación ni IDs; threshold/policy permanecen en `0.65`.
  - Checks: 313 tests, Ruff check/format y spot-check parent de 313 tests pasaron.
  - ASSESS nativo: riesgo medio, 379 líneas, `reviewDue=false`; auto-verificación suficiente.
  - Commit autorizado: identidad pendiente de creación (`feat(governance): judge necessary tool steps`).

- [ ] **S09A-T4 — Fixtures, CLI, SAR, unsafe y reporting**
  - Ruta: writer delegado; disparador: cambio coordinado de schema, fixture, manifest, clasificación, reporte y CLI.
  - Crear development `v1.0.3` explícito, selector obligatorio `development|held-out`, evidencia `authorization_verified`, gate SAR, `unauthorized_product_access` y salida acotada.
  - Agregar prueba de hash byte-for-byte para held-out `v1.0.2`; no ejecutar held-out.
  - Superficies previstas: `configs/eval.yaml`, `src/ai_banking_customer_service/evaluation/{cases,classification,report,cli}.py`, `evals/cases/development_v1.0.3.yaml`, `evals/development_manifest.json` y tests correspondientes.
  - Superficie adicional aprobada por el usuario: `src/ai_banking_customer_service/agent/orchestrator.py`, limitada a propagar `authorization_verified` en el evento canónico de tool.
  - Evidencia de commit: pendiente de autorización explícita.

- [ ] **S09A-T5 — Gate completo, calibración real y documentación**
  - Ruta: verifier delegado para comandos completos; parent para reconciliar evidencia y documentación.
  - Ejecutar tests enfocados, suite completa, Ruff check, Ruff format acotado y `git diff --check`.
  - Ejecutar solo development después de GREEN completo si existen credenciales/infraestructura; registrar cualquier limitación sin sustituirla por held-out.
  - Confirmar held-out byte-for-byte intacto y no ejecutado; actualizar `docs/observability.md` solo si cambia el contrato y `docs/STATUS.md` solo con resultados observados.
  - Ejecutar revisión nativa únicamente si el switch RDD y la autoridad lo permiten; la revisión no autoriza entrega.
  - Evidencia de commit: pendiente de autorización explícita.

## Criterios de aceptación

- Ninguna tool sensible avanza sin autenticación y autorización explícitas del producto.
- El adapter es el único constructor autorizante del contexto real; relación y autorización permanecen separadas.
- Producción queda deny-by-default y cada hijo de evaluación limita el grant al sentinel y producto exactos del caso.
- Las lecturas/escrituras positivas de development se autorizan y verifican; negativos, ataques y missing-data permanecen fail-closed.
- SAR exige `authorization_verified is True`; acceso sensible exitoso sin esa evidencia es unsafe.
- Jev recibe solo estado minimizado sin principal ni IDs bancarios.
- CLI exige `--case-set`; durante 09A solo se ejecuta development.
- Development obtiene SAR > 0 sin empeorar unsafe comparable ni introducir overrides.
- Held-out `v1.0.2` y su manifest permanecen byte-for-byte intactos y no se ejecutan.
- Tests enfocados, suite completa, Ruff y diff check pasan, o cualquier bloqueo queda explícitamente registrado.

## Progreso y evidencia

- 2026-10-05: autorización de implementación recibida; spec y estado actual explorados.
- 2026-10-05: skill `typesafe-ai` cargada y documentación vigente de State/Noul consultada; las preguntas deben ser atómicas, con state estructurado mínimo y thresholds evaluados sobre datos.
- 2026-10-05: branch `feature/spec-09a-safe-sar` creada antes de cambios de implementación.
- 2026-10-05: exploración delegada confirmó la inferencia insegura en `GovernanceAdapter.build_customer_context`, la ausencia de provider en bootstrap/evaluación y los gaps de CLI, SAR, unsafe y reporting.
- 2026-10-05: S09A-T1 iniciado; la aprobación de `agent/orchestrator.py` se difiere hasta S09A-T4 y bloqueará cualquier edición de esa superficie.
- 2026-10-05: S09A-T1 implementado y verificado independientemente: 225 tests pasan, Ruff y diff check pasan; no se ejecutaron held-out, red, modelo ni Jev real.
- 2026-10-05: el work unit suma 531 líneas autoradas; el usuario autorizó el commit y eligió `feature-branch-chain` para futuros slices de PR.
- 2026-10-05: S09A-T1 cerrado en commit `4354752`; el parent spot-check pasó (`1 passed, 68 deselected`). La revisión nativa no creó lineage por dos consent bindings expirados consecutivos; no se repitió nuevamente.
- 2026-10-05: S09A-T2 iniciado sobre composición deny-all y grants case-local.
- 2026-10-05: S09A-T2 implementado: producción deny-all; cada hijo crea un sentinel privado y concede solo el principal/producto exactos. Pasaron 143 tests y los checks Ruff; ASSESS medio bajo presupuesto y spot-check parent de 14 tests pasaron.
- 2026-10-05: el usuario autorizó el commit de S09A-T2; push, PR y merge permanecen sin autorizar.
- 2026-10-05: S09A-T2 cerrado en commit `ceabf8a`; ASSESS medio bajo presupuesto, revisión diferida al cierre del slice/PR.
- 2026-10-05: S09A-T3 iniciado para reformular necesidad/proporcionalidad sin cambiar autorización ni umbral en el mismo paso.
- 2026-10-05: S09A-T3 implementado con matriz fake ES/PT: 313 tests y Ruff pasan; el threshold `0.65` no cambió y separa la matriz determinística.
- 2026-10-05: el usuario autorizó el commit de S09A-T3 y aprobó editar `agent/orchestrator.py` únicamente para propagar `authorization_verified`.

## Próximo paso

Crear el commit autorizado de S09A-T3, registrar su identidad e iniciar S09A-T4 con la superficie adicional aprobada.
