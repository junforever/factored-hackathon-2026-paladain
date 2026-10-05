# Especificar el trabajo de robustecimiento de evaluación

## Objetivo

Definir tres extensiones listas para implementar de la Especificación #9 que recuperen la resolución automatizada segura, hagan determinísticas las decisiones terminales y de escalamiento, y reduzcan la latencia de extremo a extremo sin ajustar a partir de datos held-out ni debilitar los controles bancarios.

## Alcance

- Crear `docs/specs/spec_09a.md` para recuperar SAR con conocimiento de autorización y calibrar el control de herramientas solo con desarrollo.
- Crear `docs/specs/spec_09b.md` para asegurar la corrección determinística de terminales/escalamientos y un análogo development del único caso normal unsafe con escalamiento innecesario medido en el run final histórico, trazado en `docs/STATUS.md`.
- Crear `docs/specs/spec_09c.md` para atribuir y optimizar latencia de forma segura para la privacidad después de estabilizar la corrección.
- Definir una cadena de dependencias entre especificaciones y exactamente una ejecución held-out final después de congelar las tres candidatas.
- Reservar la Especificación #10 para la documentación final, las diapositivas y el trabajo de presentación.

## Restricciones

- Tarea solo de documentación; no pueden cambiar código de producción, pruebas, umbrales, conjuntos de datos, manifiestos ni reportes generados.
- Se deben especificar requisitos de TDD estricto para la implementación posterior, incluida evidencia de RED → GREEN → TRIANGULATE → REFACTOR.
- Held-out v1.0.2 permanece congelado y no se debe usar para ajustes ni ejecutar repetidamente.
- No se pueden debilitar los controles estrictos de identidad, autorización, argumentos, confirmación, verificación, privacidad y denegación ante fallos (`fail-closed`).
- Cada especificación debe declarar alcance, no-objetivos, contratos normativos, plan de pruebas, criterios de aceptación, límites de revisión, reversión y actualizaciones requeridas de STATUS.

## Entrega

- Rama: `docs/evaluation-hardening-specs`
- Estrategia: `feature-branch-chain`
- Idioma de los artefactos: español, consistente con las especificaciones existentes.
- Validación: relectura estructural, comprobación de referencias cruzadas, alcance de archivos modificados y `git diff --check`.

## Tareas

- [x] **T1 — Especificar la recuperación de SAR con conocimiento de autorización**
  - Escribir `docs/specs/spec_09a.md` a partir de la evidencia actual de desarrollo y las restricciones de seguridad.
  - Definir matrices de calibración positivas/negativas, precondiciones de autorización, secuencia TDD y política de held-out congelado.
  - Evidencia: Spec 09A define autorización fail-closed, vocabulario cerrado, principal sintético case-local, matriz development-only, TDD y ejecución held-out única. La verificación independiente y la revisión nativa aprobaron el candidato documental.
  - Commit: `6b43f6c` (`docs(eval): specify safe SAR recovery`).

- [x] **T2 — Especificar la corrección determinística de terminales**
  - Escribir `docs/specs/spec_09b.md` para tipos de escalamiento, ramas ambiguas y un análogo development del único caso normal unsafe con escalamiento innecesario medido en el run final histórico, trazado en `docs/STATUS.md`.
  - Mantener la política binaria en Python y restringir los vocabularios expuestos al modelo sin ocultar fallos.
  - Evidencia: Spec 09B separa terminal, tipo técnico y razón de negocio; define precedencia determinística, contratos de handoff acotados, matriz development-only y política canónica previa a congelar vocabularios. La verificación independiente no encontró ningún bloqueo de seguridad y fue parcial únicamente porque 09C aún no había sido redactada en ese momento. Linaje de revisión nativa: `review-4d91ffb1ced442d9` (`approved/acknowledged`).
  - Commit: `dafa5fc` (`docs(eval): specify terminal decision correctness`).

- [x] **T3 — Especificar la atribución y optimización de latencia**
  - Escribir `docs/specs/spec_09c.md` con tiempos por etapa, restricciones de privacidad, protocolo de medición, presupuesto de rendimiento y criterios de no regresión.
  - Exigir que la corrección se congele antes de optimizar y una única ejecución held-out final después de las tres especificaciones.
  - Evidencia: Spec 09C define taxonomía temporal monotónica, evidencia acotada, protocolo comparable development-only, ladder de optimización, concurrencia segura, gates relativos y política held-out final. La verificación independiente confirmó el contenido; el único incidente fue un artefacto Windows `NUL` recreado por tooling y eliminado de forma segura. Linaje nativo: `review-747870b49111b9b5` (`approved/acknowledged`).
  - Commit: `d1bb9e4` (`docs(eval): specify latency optimization`).

- [x] **T4 — Validar la cadena de especificaciones**
  - Comprobar terminología, dependencias, rutas, comandos, criterios de aceptación y política held-out entre las tres especificaciones.
  - Ejecutar comprobaciones estructurales solo de documentación y registrar todas las identidades de commit.
  - Evidencia: la verificación independiente final confirmó que 09A–09C son implementables, cubren toda la deuda medida, comparten línea base/dependencias/política held-out, no contienen IDs explícitos de casos held-out y pasan `git diff --check`. Revisión nativa final: `review-f207f5ee21508575` (`approved/acknowledged`).
  - Commit: `e7fd00f` (`docs(eval): reconcile hardening spec chain`).
  - Ninguna evaluación en tiempo de ejecución o de modelo resulta aplicable a esta tarea de documentación.

## Criterios de aceptación

- Cada especificación se puede implementar de forma independiente sin reconstruir decisiones desde el historial del chat.
- Las tres especificaciones cubren en conjunto SAR 0%, escalamientos incorrectos/omitidos, el único caso normal unsafe con escalamiento innecesario medido en el run final histórico y trazado en `docs/STATUS.md`, y la regresión de latencia; solo se exigen análogos development, nunca contenido ni ramas por caso held-out.
- La deuda de formato de todo el repositorio sigue siendo trabajo de mantenimiento, no una especificación de comportamiento.
- El orden de implementación es 09A → 09B → 09C → una ejecución held-out final de v1.0.2 → presentación de la Especificación #10.
- Ninguna especificación autoriza ajustes con held-out, relajación de seguridad, campos sensibles en reportes ni eliminación de la verificación.

## Progreso

- Evidencia actual mapeada desde la Especificación #9, `docs/STATUS.md`, clasificación y generación de reportes de evaluación, criterios de gobierno, orquestación y límites de medición temporal.
- La implementación no ha comenzado; estos documentos solo definen trabajo futuro.
