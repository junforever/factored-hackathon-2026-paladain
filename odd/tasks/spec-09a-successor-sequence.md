# ODD — Secuencia sucesora de Spec 09A

## Objetivo

Dividir el trabajo posterior al cierre fallido de Spec 09A en specs pequeñas, secuenciales, verificables y funcionales, evitando otra entrega transversal de gran tamaño.

## Restricciones

- Las specs y documentación del proyecto se redactan en español neutro.
- Cada spec tiene un único resultado primario, superficies acotadas y rollback independiente.
- Held-out `v1.0.2` permanece congelado y no se ejecuta.
- No se permite otra corrida development hasta la spec final de calibración y solo después de todos los gates determinísticos.
- No se ajustan thresholds, prompts ni modelos sin evidencia causal determinística.
- No se implementa comportamiento en este trabajo; solo se define la secuencia normativa.

## Tareas

- [x] **S09A-S1 — Separar evidencia runtime y reporting**
  - `spec_09a1.md`: contrato y emisión runtime de evidencia canónica segura.
  - `spec_09a2.md`: proyección segura a clasificación y reportes, dependiente de 09A1.
  - Ninguna de las dos puede cruzar ambos dominios durante implementación.
  - Resultado: 09A1 runtime (224 líneas) y 09A2 reporting (215 líneas), con superficies, aceptación y rollback independientes.

- [x] **S09A-S2 — Delimitar sucesoras dependientes**
  - Crear specs planificadas `spec_09a3.md` a `spec_09a7.md` como contratos acotados y bloqueados por evidencia/predecesores.
  - Separar autorización, missing-data, admisión de handoff, persistencia y calibración final.
  - Evitar detalles prematuros que deban inferirse recién después de sus predecesoras.
  - Cada spec exige una estimación post-RED; si supera 300 líneas autoradas o cruza más de un dominio runtime, debe dividirse en otra spec antes de escribir producción.
  - Resultado: 09A3–09A7 en 160/157/171/159/191 líneas; autorización, missing-data, admisión, persistencia y calibración permanecen separadas y bloqueadas por predecesoras.

- [x] **S09A-S3 — Verificar y cerrar documentación**
  - Validar enlaces, secuencia, ausencia de solapamientos, superficies y criterios de aceptación.
  - Ejecutar `git diff --check` y revisión estructural documental.
  - Solicitar autorización antes del commit documental.
  - Verificación independiente final PASS: sin blockers, riesgo previo cerrado, links/estructura/permisos/whitespace verdes y exactamente ocho archivos intencionales.
  - Requisito anti-mega garantizado por contrato: `>300` líneas o `>1` dominio runtime obliga a una nueva spec numerada; subtareas y commits no pueden evitarlo.

## Evidencia de partida

- Spec 09A cerró con gate determinístico verde, pero aceptación development fallida: SAR `0/30`, unsafe `9/30`, tool-plan `7/30`, autorización insegura en cinco casos únicos y missing-data unsafe `4/5`.
- Los reportes actuales no exponen suficiente evidencia causal para distinguir por qué falló cada decisión sin volver a inspeccionar estado interno.
- La primera sucesora debe mejorar evidencia diagnóstica segura antes de cualquier corrección de comportamiento.

## Evidencia de autoría

- Excepción TDD: documentación normativa pasiva, sin comportamiento ejecutable.
- Writer validó headings, enlaces, límites de 100–300 líneas, permisos de ejecución y `git diff --check`.
- Primera verificación: sin blockers, pero detectó riesgo medio de implementación porque 09A1 mezclaba emisión runtime y reporting, comparable a un slice previo de 642 líneas.
- Decisión aplicada: evidencia dividida en runtime/reporting y calibración movida a 09A7.
- Writer validó siete specs: 224/215/160/157/171/159/191 líneas, enlaces, estados, pregunta única, permisos de corrida, threshold y gate anti-mega; diff check verde.

## Próximo paso

Solicitar autorización para cinco commits documentales revisables: 09A1; 09A2; 09A3–09A4; 09A5–09A6; 09A7 + tracker. No implementar todavía ninguna spec.