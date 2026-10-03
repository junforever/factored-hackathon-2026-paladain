from pathlib import Path

import pytest

from ai_banking_customer_service.config import PROJECT_ROOT
from app.chainlit_app import CHAINLIT_CONFIG_PATH, _validate_startup_config


def test_committed_chainlit_config_is_validated_at_import() -> None:
    assert CHAINLIT_CONFIG_PATH == PROJECT_ROOT / ".chainlit" / "config.toml"
    _validate_startup_config(CHAINLIT_CONFIG_PATH)


def test_startup_config_accepts_explicit_false(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[features]\nunsafe_allow_html = false\n",
        encoding="utf-8",
    )

    _validate_startup_config(config_path)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "[features]\n",
        "[features]\nunsafe_allow_html = true\n",
        '[features]\nunsafe_allow_html = "false"\n',
        "features = false\n",
        "[features\nunsafe_allow_html = false\n",
    ],
    ids=[
        "missing-table",
        "missing-key",
        "enabled",
        "string-false",
        "wrong-table-type",
        "invalid-toml",
    ],
)
def test_startup_config_fails_closed_for_unsafe_content(
    tmp_path: Path,
    content: str,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(content, encoding="utf-8")

    with pytest.raises(RuntimeError, match="^Unsafe Chainlit configuration$") as error:
        _validate_startup_config(config_path)

    assert error.value.__cause__ is None


def test_startup_config_fails_closed_when_file_is_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.toml"

    with pytest.raises(RuntimeError, match="^Unsafe Chainlit configuration$") as error:
        _validate_startup_config(missing_path)

    assert error.value.__cause__ is None
