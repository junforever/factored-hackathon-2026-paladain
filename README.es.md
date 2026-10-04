[Leer en inglés](README.md)

# Guía del repositorio

Esta página facilita la navegación del repositorio y reúne comandos operativos verificados. Ejecute todos los comandos desde la raíz del repositorio.

## Preparar el entorno

Prepare el entorno:

```bash
uv sync --frozen
```

Complete la [configuración canónica del repositorio](AGENTS.md) antes de iniciar la aplicación o una evaluación.

## Iniciar la aplicación

```bash
uv run chainlit run app/chainlit_app.py --headless --host 127.0.0.1 --port 8000 --ci
```

Después, abra <http://127.0.0.1:8000>. Para conocer las pautas de interacción, consulte la [guía de la demostración](chainlit.md).

## Ejecutar las verificaciones del repositorio

Ejecute la suite completa de pruebas:

```bash
uv run pytest -q
```

Compruebe el linting y el formato del código Python:

```bash
uv run ruff check .
uv run ruff format --check .
```

## Ejecutar la evaluación offline

```bash
uv run python -m ai_banking_customer_service.evaluation --config configs/eval.yaml
```

## Índice de documentación

- [Contexto estable del proyecto y reglas para contribuir](AGENTS.md)
- [Uso de la demostración, pautas de seguridad y limitaciones](chainlit.md)
- [Estado actual de implementación y hoja de ruta](docs/STATUS.md)
- [Especificaciones de implementación](docs/specs/)
- [Configuración de evaluación](configs/eval.yaml)
- [Contrato de eventos de auditoría](docs/observability.md)
- [Hallazgos de calidad de datos](docs/findings/data_quality.md)
- [Notas de integración de Jev](docs/typesafe_jev/README.md)
