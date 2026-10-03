import inspect
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import chainlit as cl
import literalai
import requests


def test_chainlit_does_not_create_repository_translations_directory() -> None:
    assert not Path(".chainlit/translations").exists()


def test_installed_chainlit_literalai_and_requests_import_with_exact_pins() -> None:
    assert cl.__name__ == "chainlit"
    assert literalai.__name__ == "literalai"
    assert requests.__name__ == "requests"
    assert version("chainlit") == "2.12.0"
    assert version("requests") == "2.32.5"


def test_chainlit_handler_decorators_accept_async_handlers() -> None:
    async def message_handler(message: cl.Message) -> None:
        del message

    async def stop_handler() -> None:
        pass

    assert cl.on_message(message_handler) is message_handler
    assert cl.on_stop(stop_handler) is stop_handler


def test_chainlit_message_send_is_async() -> None:
    assert inspect.iscoroutinefunction(cl.Message.send)


def test_chainlit_user_session_exposes_get_and_set() -> None:
    assert callable(cl.user_session.get)
    assert callable(cl.user_session.set)
    inspect.signature(cl.user_session.get).bind("id")
    inspect.signature(cl.user_session.set).bind("key", object())


def test_chainlit_run_help_exposes_required_server_options() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "chainlit", "run", "--help"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )

    for option in ("--headless", "--host", "--port", "--ci"):
        assert option in completed.stdout
