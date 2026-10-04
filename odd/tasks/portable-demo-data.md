# Datos portables para la demostración local

## Objetivo

Distribuir los artefactos sintéticos mínimos y verificables para que jueces y usuarios del portafolio puedan ejecutar localmente el flujo completo sin descargar los CSV originales.

## Problema

El sandbox Parquet está ignorado por Git y la DuckDB actual contiene una vista `raw_transactions` dependiente de CSV locales. La instalación de dependencias no produce esos activos, por lo que una clonación limpia no es suficiente para ejecutar la demostración.

## Por qué

Una demostración de portafolio debe ser reproducible, autocontenida y verificable, sin publicar el dataset fuente completo ni duplicar millones de transacciones innecesarias.

## Alcance

- Versionar `data/sandbox/agent_sandbox_final.parquet` mediante una excepción específica de `.gitignore`.
- Generar `duckdb/ai_banking.duckdb` como base portable con una tabla `raw_transactions` limitada a los productos del sandbox.
- Crear herramientas testeadas para construir y verificar los artefactos.
- Publicar un manifiesto SHA-256.
- Completar valores seguros de rutas y modelos en `.env.example`.
- Documentar la ejecución local en `README.md` y `README.es.md` sin duplicar contenido canónico de `AGENTS.md` ni `chainlit.md`.
- Actualizar `docs/STATUS.md`.

## Restricciones

- Los datos distribuidos son sintéticos.
- El vínculo confiable sigue siendo `product_id`.
- La base fuente no debe quedar parcialmente modificada ante un fallo.
- La construcción debe usar salida temporal, validación de esquema/conteos y reemplazo atómico.
- `data/state/`, CSV y otros datos locales deben continuar ignorados.
- Strict TDD: observar RED antes de implementar cada comportamiento ejecutable, luego GREEN, triangulación y refactorización.
- Los README deben mantener sus límites de fuente de verdad y el español debe ser neutro.
- Estrategia de entrega: `ask-on-risk`; previsión aproximada de 350 líneas autorales, excluyendo binarios y manifiestos generados.

## Tareas

- [x] **PORTABLE-1 — Construir una DuckDB portable de forma segura**
  - Ruta: delegada mediante `gentle-ai-worker`.
  - Disparador: escritura no trivial en varios archivos.
  - Crear pruebas de comportamiento para exportación filtrada por productos, tabla materializada, preservación del esquema y seguridad ante fallos.
  - Implementar `scripts/data_preparation/11_build_portable_demo.py` con salida temporal y reemplazo atómico.
  - Criterios de aceptación:
    - Se observa RED antes de código de producción.
    - La salida contiene `raw_transactions` como `BASE TABLE`.
    - Solo contiene transacciones asociadas con productos del sandbox.
    - Un fallo no corrompe ni reemplaza la base destino.

- [x] **PORTABLE-2 — Verificar y publicar artefactos reproducibles**
  - Ruta: delegada mediante `gentle-ai-worker`.
  - Crear pruebas de comportamiento para verificación de hashes, archivos faltantes y estructura DuckDB.
  - Implementar `scripts/verify_demo_artifacts.py`.
  - Generar la DuckDB portable y `demo-artifacts.sha256`.
  - Ajustar `.gitignore` para permitir únicamente el Parquet esperado dentro de `data/`.
  - Criterios de aceptación:
    - Ambos artefactos coinciden con sus SHA-256.
    - El verificador falla de forma clara ante ausencia, hash inválido o estructura incorrecta.
    - La base portable conserva el esquema requerido y el conteo esperado.
    - El sandbox queda visible para Git y `data/state/` continúa ignorado.

- [x] **PORTABLE-3 — Documentar la ejecución local completa**
  - Ruta: delegada mediante `gentle-ai-worker`.
  - Completar valores no secretos seguros en `.env.example`.
  - Documentar instalación, configuración enlazada, verificación, arranque y decisión de reproducibilidad en ambos README.
  - Actualizar `docs/STATUS.md`.
  - Criterios de aceptación:
    - Una clonación limpia tiene pasos completos y ordenados para ejecutar la demo.
    - El README enlaza `AGENTS.md` y `chainlit.md` en vez de repetir su contenido.
    - La versión española usa español neutro.
    - Todos los enlaces y comandos documentados están validados.

- [x] **PORTABLE-4 — Clasificar bloqueos de la suite completa**
  - Ruta: delegada mediante `gentle-ai-verify`.
  - Diagnosticar los dos fallos que detectan `.chainlit/translations` y `chainlit.md`.
  - Determinar con evidencia si son preexistentes o causados por este cambio.
  - No corregir alcance ajeno sin autorización.
  - Criterios de aceptación:
    - Los fallos quedan reproducidos con mensajes y ubicaciones exactas.
    - La causalidad respecto de esta funcionalidad queda establecida.
    - La suite queda verde o el bloqueo preexistente queda documentado honestamente.

- [x] **PORTABLE-5 — Resolver contratos preexistentes de Chainlit**
  - Estado: autorizado por el usuario; en curso.
  - Ruta: delegada mediante `gentle-ai-worker` por escritura no trivial en varios archivos.
  - Mantener `chainlit.md` y las traducciones ES/PT versionadas como artefactos intencionales.
  - Corregir los contratos para detectar creación o modificación inesperada durante importación/arranque, no la mera existencia de artefactos canónicos.
  - Actualizar `docs/STATUS.md` mínimamente.
  - Criterios de aceptación:
    - Los dos tests fallidos constituyen el RED observado.
    - Los contratos protegen que Chainlit no genere ni modifique artefactos inesperados.
    - La suite completa queda verde.
    - Ruff y `git diff --check` quedan verdes.

## Evidencia de verificación

### PORTABLE-1

- RED observado por el escritor: la prueba inicial falló porque el script de producción todavía no existía.
- GREEN inicial: el comportamiento principal aprobó con una prueba.
- Triangulación: un sandbox inválido no falló inicialmente; la validación explícita de `product_id` produjo GREEN con dos pruebas.
- Verificación independiente: 2 pruebas aprobadas; Ruff check y format aprobados; `git diff --check` limpio.
- El verificador confirmó fuente adjunta en modo de solo lectura, base temporal, validación y reemplazo atómico.
- Spot check del padre: `uv run pytest -q tests/unit/test_build_portable_demo.py` → 2 aprobadas.
- Evaluación nativa de riesgo no disponible por archivos sin seguimiento; se aplicó verificación independiente conservadora.

### PORTABLE-2

- RED observado por el escritor: la prueba inicial falló durante la colección porque el verificador todavía no existía.
- GREEN inicial: una prueba aprobada.
- Triangulación: 9 pruebas cubren archivos faltantes, hash incorrecto, manifiesto inválido, tabla ausente o vista, falta de `product_id`, tabla vacía y producto fuera del sandbox.
- Verificación del escritor: 11 pruebas aprobadas; Ruff check y format aprobados; verificador real aprobó 2 artefactos y 89.472 filas.
- DuckDB portable: 5.779.456 bytes, `BASE TABLE`, SHA-256 `deab78e1edad300dddd607b850408e50e9eb32de5e8f4bc432c68deef555f6c2`.
- Sandbox: 478.169 bytes, SHA-256 `5b80c6e487a9333f9045632aa66d6636c1d7b896689b85a4f2180289e56a8dd1`.
- Verificación independiente: 11 pruebas, Ruff, format, verificador real, manifiesto, consulta runtime y reglas de ignore aprobados.
- La revisión inicial cuestionó que el verificador no fijara 89.472 filas; la reevaluación confirmó PASS porque el requisito explícito prohíbe convertir ese conteo en política, el hash fija los bytes exactos y la evidencia independiente confirmó el conteo.
- `sha256sum -c` no es la ruta soportada porque CRLF puede afectar nombres; el verificador Python multiplataforma es la ruta canónica y aprobó.
- Spot check del padre: `uv run python scripts/verify_demo_artifacts.py` → 2 artefactos y 89.472 filas verificados.

### PORTABLE-3

- Excepción TDD justificada: documentación pasiva y plantilla de configuración sin comportamiento ejecutable que permita un RED significativo.
- El usuario autorizó reemplazar `.env.example` sin leer ni exponer valores existentes; las credenciales quedaron vacías y se agregaron valores no secretos.
- Verificación del escritor: artefactos aprobados, enlaces relativos aprobados, 8 comandos documentados respaldados, auditoría sin duplicación aprobada y español neutro aprobado.
- `git diff --check` aprobó con advertencias informativas LF/CRLF.
- Verificación independiente: PASS en configuración segura, flujo de clonación limpia, límites de fuentes canónicas, idioma, explicación portable, 23 enlaces relativos, soporte de comandos, estado, artefactos y `git diff --check`.
- La revisión confirmó que el voseo restante está en `chainlit.md`, fuente canónica fuera del README, mientras `README.es.md` usa español formal neutro.

## Progreso

- Diseño aprobado por el usuario.
- Evidencia inicial: DuckDB fuente de 2,26 MiB con vista de 4.425.008 filas; subconjunto portable de 89.472 transacciones para 8.079 productos; sandbox de 0,46 MiB.
- Rama: `feat/portable-demo-data`.
- Commits de unidad de trabajo: pendientes; no se crearán sin autorización explícita del usuario.

### Validación integrada

- `uv run pytest -q`: 1.005 aprobadas, 2 fallidas y 1 advertencia; los fallos detectan artefactos existentes de Chainlit.
- `uv run ruff check .`: aprobado.
- `uv run ruff format --check .`: 105 archivos con formato correcto.
- Verificador de artefactos: aprobado con 89.472 filas.
- Consulta DuckDB con forma de ejecución real: aprobada sin CSV fuente.
- `git diff --check`: aprobado con advertencias informativas LF/CRLF.
- Fallos completos diagnosticados como preexistentes: `test_chainlit_does_not_create_repository_translations_directory` contradice traducciones ya versionadas y `test_chainlit_server_starts_and_responds_on_loopback` inicia correctamente pero rechaza el `chainlit.md` ya versionado.
- Base de comparación `630b6b5`: los artefactos ya existían; este cambio no toca `.chainlit/`, `chainlit.md` ni esos tests.
- Revisión nativa `review-d5cea085b1072f8f`: aprobada con una sugerencia informativa en `README.md:25`; acuse completado y autoridad consumida.

### PORTABLE-5

- RED confirmado antes de editar: los dos tests enfocados fallaron por exigir ausencia de artefactos canónicos.
- GREEN enfocado: los mismos dos tests aprobaron después de cambiar el contrato a snapshots de rutas y bytes.
- Suite del escritor: 1.007 pruebas aprobadas; una advertencia deprecada de Pydantic de terceros.
- Ruff check, format y `git diff --check` aprobados.
- Los artefactos intencionales de Chainlit no fueron modificados.
- Evaluación nativa de riesgo no disponible por archivos sin seguimiento; verificación independiente conservadora aprobada.
- El verificador confirmó snapshots de rutas y bytes, preservación de artefactos canónicos, aislamiento determinista, 2 tests enfocados aprobados, suite completa con 1.007 aprobadas, Ruff y diff check verdes.
- Advertencia restante: deprecación Pydantic de terceros en Traceloop.
- Spot check del padre: los 2 tests enfocados aprobaron nuevamente en 8,64 s.
- Revisión nativa final `review-5725f99150e7c739`: aprobada sin bloqueos; acuse completado y autoridad consumida.

## Siguiente paso

Revisión humana y, si el usuario lo solicita explícitamente, creación del commit de unidad de trabajo.