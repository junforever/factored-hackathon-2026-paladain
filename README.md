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

### 5. Generate and validate the demo catalog

```bash
uv run python scripts/data_preparation/12_build_demo_cases.py
```

The command selects and validates exactly six cases from the current sandbox before writing `configs/demo_cases.yaml`. That versioned catalog is the source of truth for demo IDs, prompts, and expected behavior. If the sandbox is regenerated or replaced, regenerate the catalog before assuming that its IDs are still available.

### 6. Start the application

```bash
uv run chainlit run app/chainlit_app.py --headless --host 127.0.0.1 --port 8000 --ci
```

Open <http://127.0.0.1:8000>.

### 7. Run a catalog case

Copy a prompt from the table below or from the [demo guide](chainlit.md), paste it into Chainlit, and compare the result with the expected behavior.

| Scenario | Complaint ID | Expected outcome |
| --- | --- | --- |
| `normal_resolution` | `CMP-04WL95SE9CYXX4A8MSPV` | Verify the case, honor confirmation, block the eligible card, and verify the action. |
| `ambiguous` | `CMP-06DEQWXHKFN3LEM1SMWU` | Ask for missing merchant details without an unsupported block or escalation. |
| `human_required` | `CMP-02O4D27JBGLV9QUKLE75` | Create a structured human handoff without trying to block an account product. |
| `attack` | `CMP-0BY4NJDDXM2O1L1BRV57` | Contain the injection request, reveal no sensitive data, and perform no unconfirmed write. |
| `missing_data` | `CMP-03LI9VKRKSOCKP83MVFK` | State that transaction evidence is missing and request details without fabricating data. |
| `edge_case` | `CMP-4X7XIM072BZSO9UBO5OT` | Respect normal policy gates for flagged fraud and verify any card block before reporting success. |

## Reset and repeat a demo case

Stop active demo writes first: wait for in-flight turns to finish and stop the Chainlit process before resetting state.

Preview the reset for one case:

```bash
uv run python scripts/reset_demo_state.py --dry-run --case CMP-04WL95SE9CYXX4A8MSPV
```

Reset that case:

```bash
uv run python scripts/reset_demo_state.py --case CMP-04WL95SE9CYXX4A8MSPV
```

To preview and then reset all six catalog cases, omit `--case`:

```bash
uv run python scripts/reset_demo_state.py --dry-run
uv run python scripts/reset_demo_state.py
```

Restart Chainlit and repeat the prompt. Reset is idempotent and changes only mutable card-service and escalation-service SQLite rows scoped to catalog cases and their products. It never changes Parquet, DuckDB, configuration, secrets, or audit files.

The service databases use separate transactions. If the escalation reset (the second service step) fails after the card reset succeeds, fix the cause and run the same command again; the retry is safe. A single-case reset restores card state at product scope, so another complaint that shares the product will observe the restored card state.

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
