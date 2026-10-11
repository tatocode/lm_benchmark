# LLM Benchmark

<p align="center">
  <img src="assets/hero.png" alt="LLM Benchmark — inference load testing console" width="820" />
</p>

A web-based performance benchmarking tool for large language model inference. Point it at any model API endpoint and measure **TTFT (time to first token)**, **effective throughput (tokens/s)**, **TPOT (time per output token)**, and **concurrency behavior** — with sweep testing, run history, and multi-run comparison out of the box.

English | [中文说明](README.zh-CN.md)

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.142-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- **Multiple protocols** — OpenAI-compatible, Anthropic, and Gemini endpoints, selected in the UI.
- **Three load patterns** — fixed concurrency, concurrency sweep (ramp level by level and measure each), and open-loop rate injection.
- **Vision model testing** — attach a built-in sample or an uploaded image to measure multimodal latency.
- **Built-in question bank** — default samples plus custom prompts; input length is generated to a target token count.
- **Automatic analysis** — sweep runs plot a throughput curve and derive the saturation point, SLA-compliant maximum concurrency, and a recommended concurrency.
- **Run history** — tasks and per-request records are stored in SQLite, with multi-run comparison.
- **Presets** — save and restore complete configurations.
- **Single-port deployment** — the backend serves the statically exported frontend and the API on the same port.
- **Command-line mode** — a curl-able script launches an interactive wizard for headless servers, reusing the same measurement engine.
- **Bilingual UI** — English and Chinese, switchable at runtime.

## Metrics

| Metric | Meaning |
| --- | --- |
| TTFT | Time to first token — perceived responsiveness before the model starts replying |
| TPOT | Time per output token — decoding smoothness |
| ITL | Inter-token latency (P50/P95) |
| Throughput | Output tokens per second across the whole run |
| RPS | Request completion rate |
| Error rate | Share of failed (including timed-out) requests |

Percentiles (P50/P95/P99) are reported because averages hide tail latency.

## Tech stack

| Layer | Technology |
| --- | --- |
| Backend | FastAPI + uv (Python 3.12), SQLAlchemy async + SQLite, httpx streaming, tiktoken |
| Frontend | Next.js 15 (static export) + React 19 + Tailwind v4 + ECharts + Zustand |
| Streaming | Server-Sent Events for live progress |
| Security | API keys encrypted at rest with Fernet (`data/.secret.key`) and never returned to the client |

## Quick start (Docker)

The recommended way to run it. Requires Docker with Compose.

```bash
docker compose up -d --build
# Open http://localhost:8000
```

History and keys are kept in the `llmbench-data` volume, so rebuilding the container preserves your data. The image and Dockerfile are multi-architecture and work on Windows, macOS (including Apple Silicon), and Linux.

To use a different host port, or to bind to localhost only:

```bash
LMB_UI_PORT=9000 docker compose up -d --build          # http://localhost:9000
LMB_UI_BIND=127.0.0.1 docker compose up -d --build     # local access only (Linux)
```

Without Compose:

```bash
docker build -t llm-benchmark .
docker run -p 8000:8000 -v llmbench-data:/data llm-benchmark
```

## Quick start (from source)

### Backend

```bash
cd backend
uv sync              # install dependencies (including dev)
uv run llm-benchmark # serve API on 127.0.0.1:8000
```

An optional built-in mock server is handy for trying the tool without a real model:

```bash
uv run python scripts/mock_server.py --port 8765
```

### Frontend

```bash
cd frontend
npm install
npm run build
```

For development, keep the backend running and point the frontend at it:

```bash
# PowerShell
$env:NEXT_PUBLIC_API_BASE="http://127.0.0.1:8000"
npm run dev   # http://localhost:3000
```

For single-port production deployment, merge the static export into the backend:

```bash
# PowerShell
Remove-Item backend/static -Recurse -Force
Copy-Item frontend/out backend/static -Recurse
uv run llm-benchmark   # serves both the UI and the API on port 8000
```

## Command-line usage (no GUI)

For headless servers or plain terminals, a one-line launcher starts an interactive wizard — no web UI required. It reuses the same measurement engine (TTFT, throughput, TPOT, ITL, error rate) and the step-sweep analysis.

```bash
# Interactive wizard: prompts for endpoint and workload, then runs
curl -fsSL -o llm-bench.sh https://raw.githubusercontent.com/tatocode/lm_benchmark/main/llm-bench.sh
sh llm-bench.sh
```

Or pass flags directly for a scriptable, non-interactive run:

```bash
sh llm-bench.sh --base-url http://127.0.0.1:11434/v1 --model llama3 \
  --mode step --levels 1,2,4,8,16 --step-requests 10
```

If you cloned the repo, the same entry point works without the launcher (it reuses the installed package):

```bash
cd backend
uv run llm-bench --interactive
uv run llm-bench --base-url http://127.0.0.1:11434/v1 --model llama3 \
  --mode fixed --concurrency 8 --requests 50
```

Common flags: `--protocol openai|anthropic|gemini`, `--mode fixed|step|open`,
`--concurrency`, `--requests`, `--levels`, `--step-requests`, `--arrival-rate`,
`--duration`, `--input-tokens`, `--max-output-tokens`, `--timeout`, `--image`,
`--json` (machine-readable output), and `--fail-over <rate>` (exits with code 3 for CI).

Notes:

- Requires `python3` 3.12+ (or `uvx`/`uv`, which provision a suitable runtime automatically). The launcher prefers `uvx`/`uv`, then `pipx`, then a temporary `venv`.
- Provide the API key via the `LMB_API_KEY` environment variable to keep it out of shell history.
- Run the downloaded script with `sh llm-bench.sh` (not `curl … | sh`), so the interactive prompts can read your terminal.

## Usage

1. **Connect the model** — choose the protocol, enter the base URL and model name (use *Fetch models* to auto-discover them). Connectivity is checked automatically; the API key is optional for local servers.
2. **Choose a load pattern** — pick a ready-made scene (Single-stream latency, Throughput sweep, Peak probing, Live traffic) or configure a pattern manually.
3. **Adjust advanced options (optional)** — input length, max output tokens, request timeout, SLA limits, and vision testing.
4. **Start the run** — the monitor page streams live progress (throughput, latency, error rate); when it finishes, a summary card reports the recommended concurrency, saturation point, and per-level latency. Past runs are available under History.

## Configuration

### Backend environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `LMB_HOST` | `127.0.0.1` | Bind address (`0.0.0.0` inside Docker) |
| `LMB_PORT` | `8000` | Bind port |
| `LMB_DATA_DIR` | `./data` | Directory for SQLite and the encryption key |
| `LMB_STATIC_DIR` | `./static` | Static frontend directory (served when it contains `index.html`) |
| `LMB_MAP_LOCALHOST_HOST` | empty | When set (e.g. `host.docker.internal`), outgoing `localhost` / `127.0.0.1` requests are mapped to this host |
| `LMB_IN_DOCKER` | empty | `1` / `true` when running in a container; maps localhost automatically unless `LMB_MAP_LOCALHOST_HOST` is set |
| `LMB_UI_PORT` | `8000` | Host port published by Docker Compose |
| `LMB_UI_BIND` | `0.0.0.0` | Host bind address used by Docker Compose |

### Frontend environment variable

| Variable | Description |
| --- | --- |
| `NEXT_PUBLIC_API_BASE` | API base URL; defaults to same-origin. Set to `http://127.0.0.1:8000` in development |

## Benchmarking a local model from the container

The container maps outgoing `localhost` / `127.0.0.1` to the host by default, so you can type a local address such as `http://localhost:11434/v1` in the UI as-is (it is stored and displayed verbatim).

| Platform | How it reaches the host | Notes |
| --- | --- | --- |
| Windows (Docker Desktop) | Native `host.docker.internal` | — |
| macOS (Docker Desktop / OrbStack) | Native `host.docker.internal` | — |
| Linux (Docker ≥ 20.10) | `extra_hosts: host.docker.internal:host-gateway` in Compose | If the local service listens only on `127.0.0.1`, bind it to `0.0.0.0` (e.g. Ollama `OLLAMA_HOST=0.0.0.0`; vLLM/llama.cpp `--host 0.0.0.0`), or point `LMB_MAP_LOCALHOST_HOST` at the host IP |

For remote or cloud endpoints, simply enter their address; the container reaches LAN and internet endpoints normally.

## Testing

```bash
cd backend && uv run pytest -q
cd frontend && npm run lint && npm run build
```

## Acknowledgements

This project was developed with the assistance of [opencode](https://opencode.ai), an open-source AI coding agent. It builds on the excellent work of the open-source community, including FastAPI, SQLAlchemy, httpx, tiktoken, Next.js, React, Tailwind CSS, ECharts, and Radix UI. Thanks to the maintainers and contributors of these projects.

## License

Released under the [MIT License](LICENSE).
