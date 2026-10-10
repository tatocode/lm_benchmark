import importlib

import pytest

import llm_benchmark.config as cfg


@pytest.fixture
def host_run(monkeypatch):
    monkeypatch.setenv("LMB_MAP_LOCALHOST_HOST", "")
    monkeypatch.setenv("LMB_IN_DOCKER", "")
    importlib.reload(cfg)
    yield
    importlib.reload(cfg)


@pytest.fixture
def docker_default(monkeypatch):
    monkeypatch.setenv("LMB_IN_DOCKER", "1")
    monkeypatch.delenv("LMB_MAP_LOCALHOST_HOST", raising=False)
    importlib.reload(cfg)
    yield
    importlib.reload(cfg)


@pytest.fixture
def docker_custom_host(monkeypatch):
    monkeypatch.setenv("LMB_IN_DOCKER", "1")
    monkeypatch.setenv("LMB_MAP_LOCALHOST_HOST", "172.17.0.1")
    importlib.reload(cfg)
    yield
    importlib.reload(cfg)


def test_host_run_passthrough(host_run):
    assert (
        cfg.resolve_endpoint("http://localhost:11434/v1")
        == "http://localhost:11434/v1"
    )
    assert cfg.resolve_endpoint("http://127.0.0.1:8000/v1") == "http://127.0.0.1:8000/v1"


def test_docker_default_maps_to_host(docker_default):
    assert (
        cfg.resolve_endpoint("http://127.0.0.1:11434/v1")
        == "http://host.docker.internal:11434/v1"
    )
    assert cfg.resolve_endpoint("http://localhost/v1") == "http://host.docker.internal/v1"


def test_docker_keeps_port_and_path(docker_default):
    got = cfg.resolve_endpoint("http://localhost:11434/v1/chat/completions")
    assert got == "http://host.docker.internal:11434/v1/chat/completions"


def test_explicit_custom_host_wins(docker_custom_host):
    assert (
        cfg.resolve_endpoint("http://127.0.0.1:8000/v1")
        == "http://172.17.0.1:8000/v1"
    )


def test_non_localhost_untouched(docker_default):
    assert (
        cfg.resolve_endpoint("http://10.0.0.5:8080/v1") == "http://10.0.0.5:8080/v1"
    )
    assert cfg.resolve_endpoint("https://api.openai.com/v1") == "https://api.openai.com/v1"
    assert cfg.resolve_endpoint("") == ""