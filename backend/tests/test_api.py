import importlib.util
import json
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
TERMINAL = {"done", "failed", "cancelled", "interrupted"}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def mock_server():
    port = _free_port()
    spec = importlib.util.spec_from_file_location(
        "mock_server", ROOT / "scripts" / "mock_server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mock_server"] = mod
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


@pytest.fixture(scope="session")
def client(mock_server):
    from llm_benchmark.server import app

    with TestClient(app) as c:
        yield c


def _base_config(mock_server: str, **overrides) -> dict:
    cfg = {
        "protocol": "openai",
        "base_url": mock_server,
        "api_key": "test-key",
        "model": "mock-model",
        "mode": "fixed",
        "concurrency": 3,
        "total_requests": 6,
        "step_levels": [1, 2],
        "step_requests": 3,
        "input_tokens": 64,
        "max_output_tokens": 32,
        "timeout": 30.0,
        "with_image": False,
    }
    cfg.update(overrides)
    return cfg


def _wait(client: TestClient, task_id: str, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    data = {}
    while time.time() < deadline:
        data = client.get(f"/api/tasks/{task_id}").json()
        if data["status"] in TERMINAL:
            return data
        time.sleep(0.2)
    raise AssertionError(f"task did not finish in time: {data['status']}")


def test_health(client):
    assert client.get("/api/health").json()["ok"] is True


def test_fixed_task_runs(client, mock_server):
    resp = client.post(
        "/api/tasks", json={"name": "fixed-test", "config": _base_config(mock_server)}
    )
    assert resp.status_code == 200
    task_id = resp.json()["id"]
    data = _wait(client, task_id)

    assert data["status"] == "done", data.get("error")
    assert len(data["records"]) == 6
    assert data["summary"]["completed"] == 6
    assert data["summary"]["errors"] == 0
    assert data["summary"]["ttft_ms"]["avg"] > 0
    assert data["summary"]["tpot_ms"]["avg"] > 0
    assert data["summary"]["tokens_total"] > 0
    rec = data["records"][0]
    assert rec["input_tokens"] > 0
    assert rec["error_class"] == "ok"
    assert rec["itl_p50_ms"] is not None
    assert data["summary"]["input_tokens_total"] > 0
    assert data["summary"]["itl_ms"]["p50"] >= 0
    api_key_leak = json.dumps(data).find("test-key")
    assert api_key_leak == -1, "api key must not be returned"


def test_step_task(client, mock_server):
    resp = client.post(
        "/api/tasks",
        json={"config": _base_config(mock_server, mode="step", total_requests=5)},
    )
    task_id = resp.json()["id"]
    data = _wait(client, task_id)

    assert data["status"] == "done", data.get("error")
    assert len(data["steps"]) == 2
    assert data["steps"][0]["concurrency"] == 1
    assert data["steps"][1]["concurrency"] == 2
    assert len(data["records"]) == 6
    assert data["summary"]["completed"] == 6


def test_cancel_task(client, mock_server):
    resp = client.post(
        "/api/tasks",
        json={
            "config": _base_config(
                mock_server, concurrency=1, total_requests=500, input_tokens=32
            )
        },
    )
    task_id = resp.json()["id"]
    time.sleep(1.0)
    cancel = client.post(f"/api/tasks/{task_id}/cancel")
    assert cancel.json()["ok"] is True
    data = _wait(client, task_id, timeout=30)
    assert data["status"] == "cancelled"
    assert data["summary"]["completed"] < 500


def test_sse_events(client, mock_server):
    resp = client.post(
        "/api/tasks",
        json={"config": _base_config(mock_server, total_requests=3, concurrency=2)},
    )
    task_id = resp.json()["id"]
    seen_types = set()
    with client.stream("GET", f"/api/tasks/{task_id}/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if line.startswith("data: "):
                event = json.loads(line[6:])
                seen_types.add(event["type"])
                if event["type"] == "status" and event["data"]["status"] in TERMINAL:
                    break
    assert {"status", "records", "steps", "snapshot", "record"} <= seen_types
    _wait(client, task_id)


def test_history_delete_and_presets(client, mock_server):
    tasks = client.get("/api/tasks").json()
    assert len(tasks) >= 1

    preset = client.post(
        "/api/presets",
        json={"name": "my-preset", "config": _base_config(mock_server)},
    )
    assert preset.status_code == 200
    presets = client.get("/api/presets").json()
    assert any(p["name"] == "my-preset" for p in presets)

    preset_id = preset.json()["id"]
    updated = client.post(
        "/api/presets",
        json={"name": "my-preset", "config": _base_config(mock_server, concurrency=9)},
    )
    assert updated.json()["id"] == preset_id
    assert len(client.get("/api/presets").json()) == len(presets)

    assert client.delete(f"/api/presets/{preset_id}").json()["ok"] is True

    target = tasks[0]["id"]
    running = client.delete(f"/api/tasks/{target}")
    assert running.status_code in (200, 409)


def test_probe(client, mock_server):
    resp = client.post(
        "/api/probe",
        json={
            "protocol": "openai",
            "base_url": mock_server,
            "api_key": "k",
            "model": "mock-model",
        },
    )
    body = resp.json()
    assert body["ok"] is True, body
    assert body["ttft_ms"] is not None
    assert body["latency_ms"] >= body["ttft_ms"]


def test_models_endpoint(client, mock_server):
    resp = client.post(
        "/api/models",
        json={"protocol": "openai", "base_url": mock_server, "api_key": "k"},
    )
    body = resp.json()
    assert body["ok"] is True, body
    assert "mock-gpt" in body["models"]

    bad = client.post("/api/models", json={"protocol": "openai", "base_url": "", "api_key": ""})
    assert bad.json()["ok"] is False
    assert bad.json()["error"]


def test_samples_endpoint(client):
    body = client.get("/api/samples").json()
    assert len(body["text"]) >= 3
    assert len(body["vision"]) >= 2


def test_images_endpoint_and_raw(client):
    body = client.get("/api/images").json()
    builtins = [i for i in body if i["source"] == "builtin"]
    assert len(builtins) >= 4
    first = builtins[0]
    assert first["url"].endswith("/raw")
    raw = client.get(first["url"])
    assert raw.status_code == 200
    assert raw.headers["content-type"].startswith("image/")
    assert len(raw.content) > 1000


def test_image_upload_and_delete(client):
    import base64

    from llm_benchmark.bench.workload import get_builtin_image

    data, mime = get_builtin_image("builtin:apple")
    payload = {
        "name": "my-upload.jpg",
        "mime": mime,
        "data_base64": base64.b64encode(data).decode(),
    }
    up = client.post("/api/images", json=payload)
    assert up.status_code == 200, up.text
    meta = up.json()
    assert meta["source"] == "upload"
    assert meta["size"] == len(data)

    listed = client.get("/api/images").json()
    assert any(i["id"] == meta["id"] for i in listed)
    assert client.get(meta["url"]).content == data

    assert client.delete(f"/api/images/{meta['id']}").json()["ok"] is True
    assert not any(i["id"] == meta["id"] for i in client.get("/api/images").json())

    # 内置图片不可删除
    assert client.delete("/api/images/builtin:apple").status_code == 400


def test_fixed_task_with_image_and_custom_questions(client, mock_server):
    resp = client.post(
        "/api/tasks",
        json={
            "config": _base_config(
                mock_server,
                total_requests=3,
                concurrency=1,
                with_image=True,
                image_id="builtin:apple",
                questions=["这是一道自定义问题，请简要作答。", "Second custom question?"],
            )
        },
    )
    task_id = resp.json()["id"]
    data = _wait(client, task_id)

    assert data["status"] == "done", data.get("error")
    assert len(data["records"]) == 3
    assert all(r["input_tokens"] > 0 for r in data["records"])
    assert data["config"]["with_image"] is True
    assert data["config"]["image_id"] == "builtin:apple"


def _mock_config_url(mock_server: str) -> str:
    return mock_server.removesuffix("/v1") + "/mock/config"


def test_open_loop_task(client, mock_server):
    resp = client.post(
        "/api/tasks",
        json={
            "config": _base_config(
                mock_server,
                mode="open",
                arrival_rate=20.0,
                total_requests=6,
                concurrency=4,
            )
        },
    )
    task_id = resp.json()["id"]
    data = _wait(client, task_id, timeout=60)

    assert data["status"] == "done", data.get("error")
    assert len(data["records"]) == 6
    assert data["analysis"] == {}
    starts = sorted(r["t_start"] for r in data["records"])
    # 20 req/s -> 50ms 间隔；6 个请求的注入跨度应明显 > 0（open-loop 不是一次并发爆发）
    span = starts[-1] - starts[0]
    assert span >= 0.15, f"arrival span too short: {span}"


def test_duration_task(client, mock_server):
    resp = client.post(
        "/api/tasks",
        json={
            "config": _base_config(
                mock_server,
                mode="fixed",
                concurrency=2,
                fixed_duration_s=1.5,
                total_requests=1000,
            )
        },
    )
    task_id = resp.json()["id"]
    data = _wait(client, task_id, timeout=60)

    assert data["status"] == "done", data.get("error")
    assert data["summary"]["planned"] == 0
    assert data["summary"]["completed"] >= 1
    assert data["summary"]["elapsed_s"] >= 1.4


def test_step_task_produces_analysis(client, mock_server):
    resp = client.post(
        "/api/tasks",
        json={
            "config": _base_config(
                mock_server, mode="step", total_requests=5, auto_stop=False
            )
        },
    )
    task_id = resp.json()["id"]
    data = _wait(client, task_id)

    assert data["status"] == "done", data.get("error")
    assert len(data["steps"]) == 2
    analysis = data["analysis"]
    assert analysis["ok"] is True
    assert analysis["recommended_concurrency"] is not None
    assert analysis["sla_max_concurrency"] is not None
    assert "saturation" in analysis and "knee" in analysis
    assert analysis["confidence"] in {"high", "medium", "low"}
    assert analysis["sla"]["ttft_p95_s"] == 2.0

    # SSE 重放也应带 analysis
    events = []
    with client.stream("GET", f"/api/tasks/{task_id}/events") as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                ev = json.loads(line[6:])
                events.append(ev["type"])
                if ev["type"] == "status" and ev["data"]["status"] in TERMINAL:
                    break
    assert "analysis" in events


def test_auto_stop_on_error_rate(client, mock_server):
    import httpx

    httpx.post(_mock_config_url(mock_server), json={"error_rate": 1.0}, timeout=5)
    try:
        resp = client.post(
            "/api/tasks",
            json={
                "config": _base_config(
                    mock_server,
                    mode="step",
                    step_levels=[1, 2, 3],
                    step_requests=6,
                    auto_stop=True,
                    total_requests=5,
                )
            },
        )
        task_id = resp.json()["id"]
        data = _wait(client, task_id, timeout=90)

        assert data["status"] == "done", data.get("error")
        assert len(data["steps"]) == 1, "should stop after first step"
        assert data["steps"][0]["error_rate"] == 1.0
        assert data["analysis"]["stop_reason"] == "error_rate"
        assert data["records"][0]["error_class"] == "http_5xx"
        assert data["summary"]["error_breakdown"]["http_5xx"] == 6
    finally:
        httpx.post(_mock_config_url(mock_server), json={"error_rate": 0.0}, timeout=5)
