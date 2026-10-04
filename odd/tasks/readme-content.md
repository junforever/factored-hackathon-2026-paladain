# Contenido bilingüe del README

## Objetivo

Crear un punto de entrada bilingüe para el repositorio: `README.md` en inglés por defecto y `README.es.md` en español neutro, sin duplicar ningún contenido que ya exista en `AGENTS.md` o `chainlit.md`.

## Problema

`README.md` está vacío. El contexto estable del proyecto ya vive en `AGENTS.md`, mientras que el uso, la seguridad y las limitaciones de la demostración ya viven en `chainlit.md`. Repetir esos datos generaría fuentes de verdad paralelas.

## Por qué

El repositorio necesita una portada accesible para lectores en inglés y español que los dirija a las fuentes canónicas y ofrezca únicamente información operativa que todavía no esté documentada allí.

## Alcance

- Crear `README.md` en inglés con un enlace inicial a la versión en español.
- Crear `README.es.md` en español neutro con enlace de regreso a la versión en inglés.
- Incluir solo navegación y pasos operativos ausentes de `AGENTS.md` y `chainlit.md`.
- Actualizar `docs/STATUS.md` sin duplicar el contenido de los README.

## Restricciones

- No repetir, ni siquiera de forma resumida, información presente en `AGENTS.md` o `chainlit.md`.
- Usar enlaces a esos archivos cuando sea necesario mencionar sus temas.
- Mantener `README.md` en inglés y `README.es.md` en español neutro.
- No inventar comandos; validarlos contra la configuración y los puntos de entrada reales.
- No hay una prueba RED significativa para documentación pasiva; se aplicará validación estructural de enlaces, comandos y ausencia de duplicación.
- Estrategia de entrega: `ask-on-risk` (previsión muy inferior a 400 líneas modificadas).

## Tareas

- [x] **README-1 — Crear los README bilingües**
  - Ruta: delegada mediante `gentle-ai-worker`.
  - Disparador: escritura no trivial en varios archivos.
  - Crear la navegación entre idiomas y una guía operativa concisa.
  - Sustituir cualquier tema ya canónico por enlaces a `AGENTS.md` o `chainlit.md`.
  - Criterios de aceptación:
    - La primera línea de `README.md` enlaza a `README.es.md`.
    - La primera línea de `README.es.md` enlaza a `README.md`.
    - El contenido principal de `README.md` está en inglés.
    - El contenido de `README.es.md` usa español neutro.
    - Ninguno repite contenido de `AGENTS.md` o `chainlit.md`.

- [x] **README-2 — Actualizar estado y verificar**
  - Ruta: delegada mediante `gentle-ai-worker`; verificación independiente según evaluación de riesgo.
  - Registrar el cambio de documentación en `docs/STATUS.md`.
  - Verificar enlaces relativos, comandos documentados y límites de fuente de verdad.
  - Criterios de aceptación:
    - Todos los enlaces relativos agregados resuelven a archivos existentes.
    - Los comandos documentados corresponden a entradas o herramientas existentes.
    - La revisión estructural no detecta contenido duplicado con `AGENTS.md` o `chainlit.md`.

## Evidencia de verificación

- El escritor validó 22 enlaces Markdown relativos: todos resuelven a rutas existentes.
- `git diff --check -- README.md README.es.md docs/STATUS.md`: aprobado; solo informó una advertencia no bloqueante sobre conversión LF a CRLF.
- Auditoría manual del escritor contra `AGENTS.md` y `chainlit.md`: sin duplicación sustantiva detectada.
- La evaluación nativa de riesgo no pudo clasificar el cambio porque los archivos sin seguimiento requieren declaración explícita; se activó la verificación independiente conservadora.
- Verificación independiente `muu1grx8-3-2dxn`: aprobó enlaces recíprocos, inglés por defecto, español neutro, ausencia de duplicación sustantiva, enlaces relativos, soporte estático de comandos, actualización mínima de estado y `git diff --check`.

## Progreso

- Exploración completada: `README.md` estaba vacío; `AGENTS.md` y `chainlit.md` son las fuentes canónicas que no deben duplicarse.
- `README.md`, `README.es.md` y `docs/STATUS.md` fueron redactados por el escritor delegado.
- Previsión: menos de 250 líneas modificadas, excluyendo este artefacto de seguimiento.
- Commits de unidad de trabajo: pendientes; no se crearán sin autorización explícita del usuario.

## Siguiente paso

Revisión humana del contenido y, si el usuario lo solicita explícitamente, creación del commit de unidad de trabajo.