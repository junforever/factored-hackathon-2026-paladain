[Read in Spanish](README.es.md)

# Repository guide

Use this page for repository navigation and verified operator commands. Run all commands from the repository root.

## Set up the environment

Prepare the environment:

```bash
uv sync --frozen
```

Complete the [canonical repository configuration](AGENTS.md) before starting the application or an evaluation.

## Start the application

```bash
uv run chainlit run app/chainlit_app.py --headless --host 127.0.0.1 --port 8000 --ci
```

Then open <http://127.0.0.1:8000>. For interaction guidance, consult the [demo guide](chainlit.md).

## Run repository checks

Run the complete test suite:

```bash
uv run pytest -q
```

Check Python linting and formatting:

```bash
uv run ruff check .
uv run ruff format --check .
```

## Run the offline evaluation

```bash
uv run python -m ai_banking_customer_service.evaluation --config configs/eval.yaml
```

## Documentation index

- [Stable project context and contributor rules](AGENTS.md)
- [Demo usage, safety guidance, and limitations](chainlit.md)
- [Current implementation status and roadmap](docs/STATUS.md)
- [Implementation specifications](docs/specs/)
- [Evaluation configuration](configs/eval.yaml)
- [Audit event contract](docs/observability.md)
- [Data quality findings](docs/findings/data_quality.md)
- [Jev integration notes](docs/typesafe_jev/README.md)
