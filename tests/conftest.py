import os
import tempfile

_CHAINLIT_APP_ROOT = tempfile.TemporaryDirectory(prefix="chainlit-pytest-")

_TEST_ENV = {
    "OPENAI_API_KEY": "test-openai-key",
    "TYPESAFE_API_KEY": "test-jev-key",
    "DUCKDB_NAME": "test_ai_banking.duckdb",
    "SANDBOX_PATH": "data/sandbox/test.parquet",
    "STATE_PATH": "data/state",
    "TYPESAFE_DEFAULT_MODEL": "jev-1.13.0",
    "OPENAI_MODEL": "gpt-4o-mini",
    "CHAINLIT_APP_ROOT": _CHAINLIT_APP_ROOT.name,
}
for key, value in _TEST_ENV.items():
    os.environ[key] = value
