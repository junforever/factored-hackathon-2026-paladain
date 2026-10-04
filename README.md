[Read in Spanish](README.es.md)

# Repository guide

Use this page for repository navigation and verified operator commands. Run all commands from the repository root.

## Run the demo locally

Follow these steps in order from a clean clone.

### 1. Install prerequisites

Install Git, Python 3.12 or newer, and `uv`.

### 2. Install dependencies

```bash
uv sync --frozen
```

### 3. Create and configure the environment file

Create `.env` from the versioned template:

```bash
uv run python -c "from pathlib import Path; Path('.env').write_bytes(Path('.env.example').read_bytes())"
```

Before continuing, complete the [canonical repository configuration](AGENTS.md).

### 4. Verify the portable demo artifacts

```bash
uv run python scripts/verify_demo_artifacts.py
```

### 5. Start the application

```bash
uv run chainlit run app/chainlit_app.py --headless --host 127.0.0.1 --port 8000 --ci
```

Open <http://127.0.0.1:8000>.

### 6. Follow the demo interaction guide

Use the scenarios and interaction instructions in the [demo guide](chainlit.md).

## Portable data model

The distributed DuckDB materializes only transactions relevant to the sandbox, which keeps the local demo reproducible without shipping the full source dataset. The canonical full-data preparation instead uses CSV-backed views to avoid duplicating the source data.

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

- [Repository guidance](AGENTS.md)
- [Demo guide](chainlit.md)
- [Current implementation status and roadmap](docs/STATUS.md)
- [Implementation specifications](docs/specs/)
- [Evaluation configuration](configs/eval.yaml)
- [Audit event contract](docs/observability.md)
- [Data quality findings](docs/findings/data_quality.md)
- [Jev integration notes](docs/typesafe_jev/README.md)
