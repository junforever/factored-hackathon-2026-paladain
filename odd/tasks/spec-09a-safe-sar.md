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

- [x] **S09A-T3 — Juicio semántico y calibración development-only**
  - Ruta: writer delegado; disparador: cambio Jev y matriz ES/PT con tests.
  - Observar RED para lectura preparatoria legítima frente a llamada irrelevante; ajustar pregunta/state para necesidad y proporcionalidad antes de considerar el umbral.
  - Cambiar policy/decision solo si una frontera RED separa positivos y negativos; cubrir `== threshold`, inmediatamente inferior, señales y metadata inválidas.
  - Superficies previstas: `src/ai_banking_customer_service/governance/jev/evaluations.py`, tests Jev/governance; `configs/policy.yaml`, `src/ai_banking_customer_service/config.py` y `decision.py` únicamente si la evidencia exige policy tipada distinta.
  - TDD: RED semántico `1 failed, 293 passed`; GREEN `294 passed`; RED de minimización `6 failed, 288 passed`; GREEN y matriz final `313 passed`.
  - Resultado: una sola pregunta atómica de necesidad/proporcionalidad; state sin autorización, confirmación ni IDs; threshold/policy permanecen en `0.65`.
  - Checks: 313 tests, Ruff check/format y spot-check parent de 313 tests pasaron.
  - ASSESS nativo: riesgo medio, 379 líneas, `reviewDue=false`; auto-verificación suficiente.
  - Entrega: commit `6928d2b` (`feat(governance): judge necessary tool steps`); tercer slice de `feature-branch-chain`.
  - Revisión nativa: ASSESS medio, 389 líneas committed-only, `reviewDue=false`; diferida al cierre del slice/PR.

- [x] **S09A-T4A — Schema, fixtures development y selector CLI**
  - Ruta: writer delegado; disparador: cambio coordinado de schema, fixture, manifest, factory y CLI.
  - Añadir expectativa explícita de autorización, crear development `v1.0.3`, actualizar solo manifest/config development y exigir selector `development|held-out` sin default.
  - Agregar prueba de hash byte-for-byte para held-out `v1.0.2`; no modificarlo ni ejecutarlo.
  - Superficies previstas: `configs/eval.yaml`, `src/ai_banking_customer_service/evaluation/{cases,factory,cli}.py`, `evals/cases/development_v1.0.3.yaml`, `evals/development_manifest.json` y tests correspondientes.
  - TDD: RED de colección por imports ausentes; GREEN y triangulación final `95 passed`.
  - Verificación independiente: 95 tests, Ruff, format y diff check pasan; held-out fixture/manifest sin cambios contra `6928d2b`; no se ejecutaron casos, modelo, Jev ni red.
  - Evidencia: development 30 casos (18 ES, 12 PT), hash `c33c4494...cc221379`; held-out anclado en `739d6cb7...e0b7e3`; spot-check parent 11 tests pasan.
  - Tamaño estimado: 1,124 líneas autoradas, de las cuales 630 corresponden al fixture development versionado. Es el menor work unit cohesivo porque schema/config/manifest/fixture y sus pruebas deben permanecer consistentes.
  - Entrega: commit `b577e39` (`feat(eval): add authorization-aware development cases`); cuarto slice de `feature-branch-chain`.
  - Revisión nativa: lineage `review-d5c1af6315c7982a`, lente reliability, aprobada y reconocida; autoridad consumida.

- [x] **S09A-T4B — Evidencia canónica, SAR, unsafe y reporting**
  - Ruta: writer delegado; disparador: cambio coordinado de auditoría, captura, clasificación, reporte y tests.
  - Propagar `authorization_verified`, exigirla para SAR, clasificar `unauthorized_product_access` y reportar solo campos acotados.
  - Superficie adicional aprobada por el usuario: `src/ai_banking_customer_service/agent/orchestrator.py`, limitada a propagar `authorization_verified` en el evento canónico de tool.
  - Superficies previstas: `src/ai_banking_customer_service/agent/{orchestrator,result_capture}.py`, `src/ai_banking_customer_service/evaluation/{classification,report}.py`, `docs/observability.md` solo si cambia el contrato, y tests correspondientes.
  - TDD: RED de colección por `authorization_verified`, constantes y unsafe ausentes; GREEN/triangulación final `277 passed`.
  - Checks: Ruff, format y diff check pasan; spot-check parent de clasificación/reporting `76 passed`.
  - Evidencia: las cuatro tools requieren booleano canónico; SAR exige autorización; éxito verificado sin evidencia produce `unauthorized_product_access`; reportes exponen exactamente cuatro campos y preservan orden/privacidad.
  - ASSESS nativo: riesgo medio, 642 líneas, `reviewDue=true`; review requerida después del commit estable.
  - Tamaño: 642 líneas autoradas; el corte es cohesivo porque evento, captura, contrato, clasificación y reporte deben avanzar juntos para evitar estados de rollback inseguros.
  - Entrega: commit `8056910` (`feat(eval): require product authorization evidence`); quinto slice de `feature-branch-chain`.
  - Revisión nativa: lineage `review-3a5b8c7c28074c51`, lente reliability, aprobada y reconocida; autoridad consumida.

- [ ] **S09A-T5 — Gate completo, calibración real y documentación** *(en progreso)*
  - Ruta: verifier delegado para comandos completos; parent para reconciliar evidencia y documentación.
  - Ejecutar tests enfocados, suite completa, Ruff check, Ruff format acotado y `git diff --check`.
  - Ejecutar solo development después de GREEN completo si existen credenciales/infraestructura; registrar cualquier limitación sin sustituirla por held-out.
  - Confirmar held-out byte-for-byte intacto y no ejecutado; actualizar `docs/observability.md` solo si cambia el contrato y `docs/STATUS.md` solo con resultados observados.
  - Gate determinístico final: `670 passed` focales; suite completa `1159 passed, 1 warning`; Ruff, format de 27 archivos, diff check, manifests y hashes pasan.
  - Calibración real única: 30/30 completas, pero SAR `0/30`, unsafe `9/30`, authorization-unsafe `6/30` y missing-data unsafe `4/5`; aceptación bloqueada.
  - Corrección de contratos obsoletos lista para cierre como work unit separado; commit bloqueado hasta autorización explícita.

- [ ] **S09A-T6 — Propagación end-to-end de evidencia de autorización**
  - Ruta: writer delegado; disparador: integración coordinada de captura/orquestador y tests.
  - RED: una tool sensible exitosa y autorizada a través del lifecycle fake termina con `authorization_verified:false` en el evento canónico.
  - GREEN: la evidencia exacta sobrevive hooks → capture → orchestrator; missing/denied/duplicate/retry permanecen fail-closed.
  - Superficies previstas: `src/ai_banking_customer_service/agent/{result_capture,orchestrator}.py` y tests unitarios correspondientes.

- [ ] **S09A-T7 — Abstención missing-data y tipos de escalamiento**
  - Ruta: exploración/TDD después de cerrar T6.
  - Reproducir con fakes los cuatro missing-data unsafe y los seis `wrong_type`; preservar ataques en cero unsafe.
  - La decisión sobre el plan canónico de lookup se resolverá solo si sigue afectando SAR después de reparar evidencia.

- [ ] **S09A-T8 — Recalibración final y documentación**
  - Repetir gate determinístico y ejecutar una nueva iteración development exactamente una vez solo después de cambios justificados y GREEN.
  - Actualizar `docs/STATUS.md` con evidencia observada; held-out permanece intacto y no ejecutado.

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
- 2026-10-05: S09A-T3 cerrado en commit `6928d2b`; ASSESS medio bajo presupuesto, revisión diferida al cierre del slice/PR.
- 2026-10-05: S09A-T4 se dividió en T4A (schema/fixtures/CLI) y T4B (evidencia/SAR/unsafe/reporting) para mantener work units cohesivos y revisables; T4A iniciado.
- 2026-10-05: S09A-T4A implementado y verificado independientemente: 95 tests y checks pasan; development v1.0.3 tiene 30 casos explícitos; held-out permanece byte-for-byte intacto y no ejecutado.
- 2026-10-05: el usuario autorizó el commit cohesivo de S09A-T4A dentro de `feature-branch-chain`; push, PR y merge siguen sin autorizar.
- 2026-10-05: S09A-T4A cerrado en commit `b577e39`; review nativa `review-d5c1af6315c7982a` aprobada, reconocida y consumida.
- 2026-10-05: S09A-T4B iniciado para evidencia canónica, SAR, unsafe y reporting acotado.
- 2026-10-05: S09A-T4B implementado: 277 tests y checks pasan; SAR/unsafe/reportes usan evidencia canónica acotada; ASSESS medio y review due al cerrar el slice.
- 2026-10-05: el usuario autorizó el commit cohesivo y la review nativa de S09A-T4B; push, PR y merge siguen sin autorizar.
- 2026-10-05: S09A-T4B cerrado en commit `8056910`; review nativa `review-3a5b8c7c28074c51` aprobada, reconocida y consumida.
- 2026-10-05: S09A-T5 iniciado con gate completo antes de cualquier corrida development real.
- 2026-10-05: gate determinístico bloqueado: 820/821 tests focales y 1152/1159 completos pasaron; siete fallas requieren diagnóstico. Ruff, format acotado, diff check e integridad held-out pasaron. No se ejecutó development real.
- 2026-10-05: diagnóstico aisló seis fixtures/test doubles desactualizados y un timeout Chainlit no reproducible. El writer de corrección editó solo los tres tests autorizados, pero Pi terminó con código 3221226505 antes de `agent_settled`; se inició verificación independiente del diff parcial antes de conservarlo o reintentar.
- 2026-10-05: el diff parcial fue verificado como completo y bien formado: 23 tests, Ruff, format y diff check pasan; se conserva. La modificación adicional del tracker es propiedad del parent y forma parte del task, no del writer fallido.
- 2026-10-05: gate determinístico completo GREEN: 670 tests focales y 1159 tests totales; Ruff, format de 27 archivos, diff check, manifests y hashes development/held-out/sandbox pasan. Chainlit no volvió a fallar. No hubo ejecución development ni held-out durante el gate.
- 2026-10-05: calibración real development-1.0.3 ejecutada exactamente una vez (30/30 completas, sin timeout/error). Gates de aceptación fallaron: SAR 0/30, tool-plan match 8/30, unsafe 9/30, authorization-unsafe 6/30 y missing-data unsafe 4/5. Ataques 0/5 unsafe. Reportes gitignored `eval_development-1.0.3_20261005T180948Z.{json,md}`. No se ejecutó held-out ni se hizo retry.
- 2026-10-05: diagnóstico causal atribuyó los seis authorization-unsafe a pérdida de evidencia entre hooks, result capture y evento canónico; los tests inyectaban el booleano o probaban contratos aislados. Missing-data, terminales y tipos de escalamiento son una iteración posterior separada.

## Próximo paso

Cerrar la corrección de contratos de tests como work unit y luego abrir RED end-to-end para propagación de autorización; no reejecutar development hasta completar las iteraciones justificadas.
