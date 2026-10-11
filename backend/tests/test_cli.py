import importlib.util
import json
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from llm_benchmark import cli
from llm_benchmark import interactive

ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def mock_server():
    port = _free_port()
    spec = importlib.util.spec_from_file_location(
        "mock_server_cli", ROOT / "scripts" / "mock_server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mock_server_cli"] = mod
    spec.loader.exec_module(mod)
    config = uvicorn.Config(mod.app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "mock server failed to start"
    yield f"http://127.0.0.1:{port}/v1"
    server.should_exit = True
    thread.join(timeout=5)


def _fixed_argv(mock_server: str, extra: list[str] | None = None) -> list[str]:
    argv = [
        "--base-url", mock_server,
        "--model", "mock-gpt",
        "--mode", "fixed",
        "--concurrency", "2",
        "--requests", "4",
        "--input-tokens", "32",
        "--max-output-tokens", "16",
        "--timeout", "30",
        "--json",
    ]
    if extra:
        argv += extra
    return argv


def test_cli_fixed_json(mock_server, capsys):
    rc = cli.main(_fixed_argv(mock_server))
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "done"
    assert data["summary"]["completed"] == 4
    assert data["summary"]["errors"] == 0
    assert data["summary"]["ttft_ms"]["avg"] > 0
    assert data["summary"]["tpot_ms"]["avg"] > 0
    assert data["summary"]["tokens_total"] > 0


def test_cli_does_not_leak_api_key(mock_server, capsys):
    rc = cli.main(_fixed_argv(mock_server, ["--api-key", "super-secret-key"]))
    assert rc == 0
    out = capsys.readouterr().out
    assert "super-secret-key" not in out
    json.loads(out)


def test_cli_step_produces_analysis(mock_server, capsys):
    argv = [
        "--base-url", mock_server,
        "--model", "mock-gpt",
        "--mode", "step",
        "--levels", "1,2",
        "--step-requests", "3",
        "--input-tokens", "32",
        "--max-output-tokens", "16",
        "--timeout", "30",
        "--json",
    ]
    rc = cli.main(argv)
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["steps"]) == 2
    assert data["steps"][0]["concurrency"] == 1
    assert data["analysis"]["ok"] is True
    assert data["analysis"]["recommended_concurrency"] is not None


def test_cli_config_file(mock_server, tmp_path, capsys):
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(
        json.dumps(
            {
                "protocol": "openai",
                "base_url": mock_server,
                "model": "mock-gpt",
                "mode": "fixed",
                "concurrency": 1,
                "total_requests": 2,
                "input_tokens": 32,
                "max_output_tokens": 16,
                "timeout": 30,
            }
        ),
        encoding="utf-8",
    )
    rc = cli.main(["--config", str(cfg_path), "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["completed"] == 2


def test_cli_fail_over_exit_code(mock_server, capsys):
    rc = cli.main(_fixed_argv(mock_server, ["--fail-over", "0.0"]))
    assert rc in (0, 3)
    capsys.readouterr()
    assert rc == 0  # mock returns no errors, so 0 error rate, not > 0.0


def test_cli_interactive_wizard(monkeypatch, mock_server, capsys):
    # 所有输入回车 -> 采用默认值；确保基础信息由 args 预填
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    monkeypatch.setattr(interactive, "_ask_secret", lambda *a, **k: "")
    monkeypatch.setattr(interactive, "_list_models", lambda cfg: [])
    monkeypatch.setattr(interactive, "_probe", lambda cfg: None)

    args = cli.build_parser().parse_args(
        [
            "--interactive",
            "--base-url", mock_server,
            "--model", "mock-gpt",
            "--mode", "fixed",
            "--requests", "2",
            "--concurrency", "1",
            "--input-tokens", "32",
            "--max-output-tokens", "8",
            "--timeout", "30",
        ]
    )
    rc = interactive.run_wizard(args)
    assert rc == 0
