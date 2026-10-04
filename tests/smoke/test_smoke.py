import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STARTUP_TIMEOUT_SECONDS = 30
SHUTDOWN_TIMEOUT_SECONDS = 5


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        return int(reservation.getsockname()[1])


def _smoke_environment(app_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["OPENAI_API_KEY"] = "smoke-not-a-real-key"
    environment["TYPESAFE_API_KEY"] = "smoke-not-a-real-key"
    environment["CHAINLIT_APP_ROOT"] = str(app_root)
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(PROJECT_ROOT), environment.get("PYTHONPATH")))
    )
    return environment


def test_chainlit_server_starts_and_responds_on_loopback(tmp_path: Path) -> None:
    port = _free_loopback_port()
    command = [
        sys.executable,
        "-m",
        "chainlit",
        "run",
        "app/chainlit_app.py",
        "--headless",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--ci",
    ]
    process_cwd = PROJECT_ROOT
    child_app_root = tmp_path / "chainlit-app-root"
    child_app_root.mkdir()
    parent_app_root = os.environ.get("CHAINLIT_APP_ROOT")
    environment = _smoke_environment(child_app_root)
    chainlit_markdown = PROJECT_ROOT / "chainlit.md"
    chainlit_markdown_before = (
        chainlit_markdown.exists(),
        chainlit_markdown.read_bytes() if chainlit_markdown.is_file() else None,
    )

    assert os.environ.get("CHAINLIT_APP_ROOT") == parent_app_root
    assert {
        "command": command,
        "cwd": process_cwd,
        "child_app_root": environment.get("CHAINLIT_APP_ROOT"),
    } == {
        "command": [
            sys.executable,
            "-m",
            "chainlit",
            "run",
            "app/chainlit_app.py",
            "--headless",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--ci",
        ],
        "cwd": PROJECT_ROOT,
        "child_app_root": str(child_app_root),
    }

    proc = subprocess.Popen(
        command,
        cwd=process_cwd,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    started = False
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        url = f"http://127.0.0.1:{port}"
        while time.monotonic() < deadline:
            return_code = proc.poll()
            assert return_code is None, (
                f"Chainlit exited before startup with code {return_code}"
            )
            try:
                with urllib.request.urlopen(url, timeout=0.5) as response:
                    if 200 <= response.status < 300 and proc.poll() is None:
                        started = True
                        break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.1)
        assert started, "Chainlit did not respond before the startup deadline"
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)

    assert (
        chainlit_markdown.exists(),
        chainlit_markdown.read_bytes() if chainlit_markdown.is_file() else None,
    ) == chainlit_markdown_before
