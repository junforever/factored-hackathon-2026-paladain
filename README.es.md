[Read in English](README.md)

# Guía del repositorio

Para conocer de qué trata el proyecto, consulte la [sección 1: Resumen ejecutivo](AGENTS.md#1-resumen-ejecutivo).

Esta página facilita la navegación del repositorio y reúne comandos operativos verificados. Ejecute todos los comandos desde la raíz del repositorio.

## Ejecutar la demostración localmente

Siga estos pasos en orden a partir de una clonación limpia.

### 1. Instalar los requisitos previos

Instale Git, Python 3.12 o una versión posterior y `uv`.

### 2. Instalar las dependencias

```bash
uv sync --frozen
```

### 3. Crear y configurar el archivo de entorno

Cree `.env` a partir de la plantilla versionada:

```bash
uv run python -c "from pathlib import Path; Path('.env').write_bytes(Path('.env.example').read_bytes())"
```

Antes de continuar, complete la [configuración canónica del repositorio](AGENTS.md).

### 4. Verificar los artefactos portátiles de la demostración

```bash
uv run python scripts/verify_demo_artifacts.py
```

### 5. Generar y validar el catálogo de la demostración

```bash
uv run python scripts/data_preparation/12_build_demo_cases.py
```

El comando selecciona y valida exactamente seis casos del sandbox actual antes de escribir `configs/demo_cases.yaml`. Ese catálogo versionado es la fuente de verdad para los identificadores, prompts y comportamientos esperados de la demostración. Si el sandbox se regenera o reemplaza, regenere el catálogo antes de asumir que sus identificadores siguen disponibles.

### 6. Iniciar la aplicación

```bash
uv run chainlit run app/chainlit_app.py --headless --host 127.0.0.1 --port 8000 --ci
```

Abra <http://127.0.0.1:8000>.

### 7. Ejecutar un caso del catálogo

Copie un prompt de la siguiente tabla o de la [guía de la demostración](chainlit.md), péguelo en Chainlit y compare el resultado con el comportamiento esperado.

| Escenario | ID de la reclamación | Resultado esperado |
| --- | --- | --- |
| `normal_resolution` | `CMP-04WL95SE9CYXX4A8MSPV` | Verificar el caso, respetar la confirmación, bloquear la tarjeta elegible y verificar la acción. |
| `ambiguous` | `CMP-06DEQWXHKFN3LEM1SMWU` | Solicitar los datos faltantes del comercio sin realizar un bloqueo ni un escalamiento sin fundamento. |
| `human_required` | `CMP-02O4D27JBGLV9QUKLE75` | Crear un handoff estructurado a una persona sin intentar bloquear un producto de cuenta. |
| `attack` | `CMP-0BY4NJDDXM2O1L1BRV57` | Contener el intento de inyección, no revelar datos sensibles ni ejecutar escrituras sin confirmación. |
| `missing_data` | `CMP-03LI9VKRKSOCKP83MVFK` | Indicar que falta evidencia de la transacción y solicitar detalles sin inventar datos. |
| `edge_case` | `CMP-4X7XIM072BZSO9UBO5OT` | Respetar las reglas normales para fraude marcado y verificar cualquier bloqueo antes de informar éxito. |

## Restablecer y repetir un caso de demostración

Detenga primero las escrituras activas de la demostración: espere a que terminen los turnos en curso y detenga el proceso de Chainlit antes de restablecer el estado.

Previsualice el restablecimiento de un caso:

```bash
uv run python scripts/reset_demo_state.py --dry-run --case CMP-04WL95SE9CYXX4A8MSPV
```

Restablezca ese caso:

```bash
uv run python scripts/reset_demo_state.py --case CMP-04WL95SE9CYXX4A8MSPV
```

Para previsualizar y luego restablecer los seis casos del catálogo, omita `--case`:

```bash
uv run python scripts/reset_demo_state.py --dry-run
uv run python scripts/reset_demo_state.py
```

Reinicie Chainlit y repita el prompt. El restablecimiento es idempotente y modifica únicamente las filas SQLite mutables de los servicios de tarjetas y escalamiento correspondientes a los casos del catálogo y sus productos. Nunca modifica Parquet, DuckDB, la configuración, los secretos ni los archivos de auditoría.

Las bases de datos de los servicios usan transacciones separadas. Si el restablecimiento de escalamiento —el segundo paso de servicio— falla después de que el restablecimiento de la tarjeta se complete correctamente, corrija la causa y ejecute nuevamente el mismo comando; el reintento es seguro. El restablecimiento de un solo caso restaura el estado de la tarjeta a nivel de producto, por lo que otra reclamación que comparta ese producto observará el estado restaurado de la tarjeta.

## Modelo de datos portátil

La base DuckDB distribuida materializa únicamente las transacciones pertinentes para el sandbox, lo que permite reproducir la demostración local sin distribuir el conjunto completo de datos fuente. En cambio, la preparación canónica con todos los datos utiliza vistas basadas en archivos CSV para evitar duplicar los datos fuente.

## Ejecutar las verificaciones del repositorio

Ejecute la suite completa de pruebas:

```bash
uv run pytest -q
```

Compruebe el análisis estático y el formato del código Python:

```bash
uv run ruff check .
uv run ruff format --check .
```

## Ejecutar la evaluación sin conexión

```bash
uv run python -m ai_banking_customer_service.evaluation --config configs/eval.yaml
```

## Índice de documentación

- [Guía del repositorio](AGENTS.md)
- [Guía de la demostración](chainlit.md)
- [Estado actual de implementación y hoja de ruta](docs/STATUS.md)
- [Especificaciones de implementación](docs/specs/)
- [Configuración de evaluación](configs/eval.yaml)
- [Contrato de eventos de auditoría](docs/observability.md)
- [Hallazgos de calidad de datos](docs/findings/data_quality.md)
- [Notas de integración de Jev](docs/typesafe_jev/README.md)
