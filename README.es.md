[Leer en inglés](README.md)

# Guía del repositorio

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

### 5. Iniciar la aplicación

```bash
uv run chainlit run app/chainlit_app.py --headless --host 127.0.0.1 --port 8000 --ci
```

Abra <http://127.0.0.1:8000>.

### 6. Seguir la guía de interacción de la demostración

Utilice los escenarios y las instrucciones de interacción de la [guía de la demostración](chainlit.md).

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
