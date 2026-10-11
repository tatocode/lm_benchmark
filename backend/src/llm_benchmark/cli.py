"""命令行压测入口：无需 Web 界面即可对 LLM 推理端点做并发压测。

复用 providers / bench.workload / bench.metrics / bench.analysis，不依赖数据库、
不启动服务器。既支持一次性参数式运行，也可通过 ``--interactive`` 进入交互向导。
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path
from time import perf_counter

import httpx

from .bench.analysis import analyze_steps
from .bench.metrics import Aggregator, RecordResult, percentile, step_summary
from .bench.workload import (
    DEFAULT_IMAGE_ID,
    SAMPLE_QUESTIONS,
    VISION_QUESTIONS,
    compose_prompt,
    count_tokens,
    get_builtin_image,
)
from .providers import ProviderError, create_provider
from .schemas import TaskConfig

DEFAULT_BASE = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com",
}

TEXTS = {
    "en": {
        "title": "LLM Benchmark - interactive load test",
        "lang_prompt": "Language / \u8bed\u8a00 (en/zh)",
        "hint": "Press Enter to accept the default shown in brackets.",
        "protocol": "Protocol",
        "base_url": "Base URL",
        "api_key": "API Key (leave blank for local servers)",
        "fetch_models": "Fetch available models?",
        "models_fail": "could not fetch models, please enter the model name manually",
        "fetch_ok": "available models",
        "models_available": "Available models:",
        "choose_model": "Choose by number or type a model name",
        "sample": "sample",
        "model": "Model",
        "test_conn": "Test connectivity now?",
        "conn_ok": "Connected",
        "conn_fail": "Connection failed",
        "mode": "Mode",
        "concurrency": "Concurrency",
        "requests": "Total requests",
        "levels": "Concurrency levels (comma-separated)",
        "step_requests": "Requests per level",
        "duration_fixed": "Duration in seconds (0 = by request count)",
        "duration_step": "Seconds per level (0 = by request count)",
        "arrival_rate": "Arrival rate (req/s)",
        "input_tokens": "Input tokens",
        "max_output_tokens": "Max output tokens",
        "timeout": "Request timeout (s)",
        "vision": "Enable vision test (attach an image)?",
        "vision_image": "Image (builtin:<id> or local path)",
        "about": "About to run",
        "l_protocol": "protocol",
        "l_endpoint": "endpoint",
        "l_model": "model",
        "l_mode": "mode",
        "l_conc": "concurrency",
        "l_req": "requests",
        "l_tokens": "tokens",
        "l_input": "input",
        "l_output": "output",
        "l_timeout": "timeout",
        "l_vision": "vision",
        "l_sample": "sample",
        "start": "Start the benchmark?",
        "cancelled": "Cancelled.",
        "err_int": "please enter an integer",
        "err_num": "please enter a number",
        "err_ge": "must be >= {n}",
        "err_choice": "options: {opts}",
        "endpoint": "endpoint",
        "model": "model",
        "status": "status",
        "per_concurrency": "per-concurrency",
        "h_conc": "conc",
        "h_rps": "req/s",
        "h_out": "tok/s",
        "h_ttft": "TTFT p95 (ms)",
        "h_e2e": "E2E p95 (ms)",
        "h_tpot": "TPOT p95 (ms)",
        "h_err": "err (%)",
        "overall": "overall metrics",
        "r_completed": "completed",
        "r_errors": "errors",
        "r_elapsed": "elapsed",
        "latency": "latency (ms)",
        "avg": "avg",
        "throughput": "throughput",
        "r_output": "output",
        "r_input": "input",
        "r_requests": "requests",
        "r_error_rate": "error rate",
        "analysis": "analysis",
        "a_recommended": "recommended concurrency",
        "a_saturation": "saturation concurrency",
        "a_knee": "knee concurrency",
        "a_sla_max": "SLA max concurrency",
        "a_sustainable": "max sustainable req/s",
        "a_confidence": "confidence",
    },
    "zh": {
        "title": "LLM Benchmark - \u4ea4\u4e92\u5f0f\u538b\u6d4b",
        "lang_prompt": "\u8bed\u8a00 Language (en/zh)",
        "hint": "\u76f4\u63a5\u6309\u56de\u8f66\u4f7f\u7528\u65b9\u62ec\u53f7\u4e2d\u7684\u9ed8\u8ba4\u503c\u3002",
        "protocol": "\u534f\u8bae Protocol",
        "base_url": "\u63a8\u7406\u5730\u5740 Base URL",
        "api_key": "API Key\uff08\u672c\u5730\u670d\u52a1\u53ef\u7559\u7a7a\uff09",
        "fetch_models": "\u83b7\u53d6\u53ef\u7528\u6a21\u578b\u5217\u8868",
        "models_fail": "\u672a\u80fd\u83b7\u53d6\uff0c\u8bf7\u624b\u52a8\u8f93\u5165\u6a21\u578b\u540d",
        "models_available": "\u53ef\u7528\u6a21\u578b\uff1a",
        "choose_model": "\u9009\u62e9\u5e8f\u53f7\u6216\u76f4\u63a5\u8f93\u5165\u6a21\u578b\u540d",
        "sample": "\u8fd4\u56de\u793a\u4f8b",
        "model": "\u6a21\u578b\u540d Model",
        "test_conn": "\u73b0\u5728\u6d4b\u8bd5\u8fde\u901a\u6027",
        "conn_ok": "\u8fde\u63a5\u6210\u529f",
        "conn_fail": "\u8fde\u63a5\u5931\u8d25",
        "mode": "\u538b\u6d4b\u6a21\u5f0f Mode (fixed/step/open)",
        "concurrency": "\u5e76\u53d1\u6570 concurrency",
        "requests": "\u603b\u8bf7\u6c42\u6570 requests",
        "levels": "\u9636\u68af\u5e76\u53d1\u7ea7\u522b\uff08\u9017\u53f7\u5206\u9694\uff09",
        "step_requests": "\u6bcf\u6863\u8bf7\u6c42\u6570",
        "duration_fixed": "\u6309\u65f6\u957f\uff08\u79d2\uff0c0 \u8868\u793a\u6309\u8bf7\u6c42\u6570\uff09",
        "duration_step": "\u6bcf\u4e2a\u9636\u6bb5\u79d2\u6570\uff080 \u8868\u793a\u6309\u8bf7\u6c42\u6570\uff09",
        "arrival_rate": "\u5230\u8fbe\u7387 arrival rate (req/s)",
        "input_tokens": "\u8f93\u5165\u957f\u5ea6 input-tokens",
        "max_output_tokens": "\u6700\u5927\u8f93\u51fa max-output-tokens",
        "timeout": "\u5355\u8bf7\u6c42\u8d85\u65f6 timeout\uff08\u79d2\uff09",
        "vision": "\u542f\u7528\u89c6\u89c9\u6d4b\u8bd5\uff08\u9644\u56fe\u7247\uff09",
        "vision_image": "\u56fe\u7247\uff08builtin:<id> \u6216\u672c\u5730\u8def\u5f84\uff09",
        "about": "\u5373\u5c06\u8fd0\u884c",
        "l_protocol": "\u534f\u8bae",
        "l_endpoint": "\u5730\u5740",
        "l_model": "\u6a21\u578b",
        "l_mode": "\u6a21\u5f0f",
        "l_conc": "\u5e76\u53d1",
        "l_req": "\u8bf7\u6c42\u6570",
        "l_tokens": "\u4ee4\u724c",
        "l_input": "\u8f93\u5165",
        "l_output": "\u8f93\u51fa",
        "l_timeout": "\u8d85\u65f6",
        "l_vision": "\u89c6\u89c9",
        "start": "\u5f00\u59cb\u538b\u6d4b",
        "cancelled": "\u5df2\u53d6\u6d88\u3002",
        "err_int": "\u8bf7\u8f93\u5165\u6574\u6570",
        "err_num": "\u8bf7\u8f93\u5165\u6570\u5b57",
        "err_ge": "\u5fc5\u987b >= {n}",
        "err_choice": "\u53ef\u9009\u503c\uff1a{opts}",
        "endpoint": "\u5730\u5740",
        "model": "\u6a21\u578b",
        "status": "\u72b6\u6001",
        "per_concurrency": "\u5404\u5e76\u53d1\u5ea6",
        "h_conc": "\u5e76\u53d1",
        "h_rps": "\u8bf7\u6c42/\u79d2",
        "h_out": "\u8f93\u51fa tok/s",
        "h_ttft": "TTFT p95(\u6beb\u79d2)",
        "h_e2e": "E2E p95(\u6beb\u79d2)",
        "h_tpot": "TPOT p95(\u6beb\u79d2)",
        "h_err": "\u9519\u8bef\u7387(%)",
        "overall": "\u603b\u4f53\u6307\u6807",
        "r_completed": "\u5b8c\u6210",
        "r_errors": "\u9519\u8bef",
        "r_elapsed": "\u8017\u65f6",
        "latency": "\u5ef6\u8fdf (ms)",
        "avg": "\u5e73\u5747",
        "throughput": "\u541e\u5410\u91cf",
        "r_output": "\u8f93\u51fa",
        "r_input": "\u8f93\u5165",
        "r_requests": "\u8bf7\u6c42",
        "r_error_rate": "\u9519\u8bef\u7387",
        "analysis": "\u5206\u6790",
        "a_recommended": "\u63a8\u8350\u5e76\u53d1\u6570",
        "a_saturation": "\u9971\u548c\u5e76\u53d1\u6570",
        "a_knee": "\u62d0\u70b9\u5e76\u53d1\u6570",
        "a_sla_max": "SLA \u6700\u5927\u5e76\u53d1\u6570",
        "a_sustainable": "\u6700\u5927\u53ef\u6301\u7eed req/s",
        "a_confidence": "\u7f6e\u4fe1\u5ea6",
    },
}


def resolve_lang(value):
    lang = (value or "").strip().lower()
    if lang in ("zh", "cn", "zh-cn", "chinese", "\u4e2d\u6587"):
        return "zh"
    return "en"


def tr(lang, key, **kw):
    table = TEXTS.get(lang) or TEXTS["en"]
    text = table.get(key) or TEXTS["en"].get(key, key)
    return text.format(**kw) if kw else text


class _Aborted(Exception):
    pass


# --------------------------------------------------------------------------- #
# 参数解析
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llm-bench",
        description="LLM inference load testing from the command line.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  llm-bench --base-url http://127.0.0.1:11434/v1 --model llama3\n"
            "  llm-bench --mode step --levels 1,2,4,8 --step-requests 10\n"
            "  llm-bench --config mytest.json --json\n"
            "  llm-bench --interactive\n"
        ),
    )
    p.add_argument("--interactive", "-i", action="store_true", help="run the interactive wizard")
    p.add_argument("--config", help="load a TaskConfig JSON file as the baseline")
    p.add_argument(
        "--lang",
        choices=["en", "zh"],
        default=None,
        help="output language (default: en, or the LMB_LANG env var)",
    )

    p.add_argument("--protocol", choices=["openai", "anthropic", "gemini"], default=None)
    p.add_argument("--base-url", dest="base_url", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--api-key", dest="api_key", default=None, help="also honors the LMB_API_KEY env var")

    p.add_argument("--mode", choices=["fixed", "step", "open"], default=None)
    p.add_argument("--concurrency", type=int, default=None, help="concurrency for fixed/open modes")
    p.add_argument("--requests", type=int, default=None, help="total requests (fixed / open)")
    p.add_argument("--levels", default=None, help="step-mode concurrency levels, comma-separated, e.g. 1,2,4,8,16")
    p.add_argument("--step-requests", dest="step_requests", type=int, default=None, help="requests per step level")
    p.add_argument("--arrival-rate", dest="arrival_rate", type=float, default=None, help="open-mode arrival rate in req/s")
    p.add_argument(
        "--duration",
        type=float,
        default=None,
        help="run by duration in seconds (fixed/open use fixed_duration, step uses step_duration; 0 = by request count)",
    )
    p.add_argument("--input-tokens", dest="input_tokens", type=int, default=None)
    p.add_argument("--max-output-tokens", dest="max_output_tokens", type=int, default=None, help="alias for max_tokens")
    p.add_argument("--timeout", type=float, default=None, help="per-request timeout in seconds")
    p.add_argument("--image", default=None, help="vision test image: builtin:<id> or a local file path")
    p.add_argument("--questions", default=None, help="custom prompts, separated by |")

    p.add_argument("--json", action="store_true", help="print the result as JSON to stdout")
    p.add_argument("--quiet", action="store_true", help="hide live progress")
    p.add_argument("--no-color", dest="no_color", action="store_true", help="disable colored output")
    p.add_argument(
        "--fail-over",
        dest="fail_over",
        type=float,
        default=None,
        help="exit with code 3 when the error rate exceeds this value (for CI)",
    )
    return p


def _parse_levels(text: str, default: list[int]) -> list[int]:
    levels = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            n = int(part)
        except ValueError:
            continue
        if n >= 1:
            levels.append(n)
    return levels[:12] or default


def _config_from_args(args: argparse.Namespace) -> tuple[TaskConfig, str | None]:
    cfg = TaskConfig()
    if args.config:
        path = Path(args.config)
        if not path.is_file():
            raise SystemExit(f"config file not found: {args.config}")
        cfg = TaskConfig.model_validate_json(path.read_text(encoding="utf-8"))

    protocol = args.protocol or cfg.protocol
    base_url = args.base_url if args.base_url is not None else cfg.base_url
    if not base_url:
        base_url = DEFAULT_BASE[protocol]
    api_key = args.api_key or os.environ.get("LMB_API_KEY", "") or cfg.api_key
    model = args.model if args.model is not None else cfg.model

    mode = args.mode or cfg.mode
    levels = _parse_levels(args.levels, cfg.step_levels) if args.levels else cfg.step_levels
    if not levels:
        levels = [1, 2, 4, 8, 16]

    duration = args.duration
    fixed_duration = cfg.fixed_duration_s
    step_duration = cfg.step_duration_s
    if duration is not None:
        if mode == "step":
            step_duration = duration
        else:
            fixed_duration = duration

    questions: list[str] = cfg.questions
    if args.questions:
        questions = [q.strip() for q in args.questions.split("|") if q.strip()]

    image_spec = args.image
    if image_spec is None and cfg.with_image:
        image_spec = cfg.image_id or DEFAULT_IMAGE_ID
    with_image = bool(image_spec) or cfg.with_image

    cfg = TaskConfig(
        protocol=protocol,
        base_url=base_url,
        api_key=api_key,
        model=model,
        mode=mode,
        concurrency=args.concurrency if args.concurrency is not None else cfg.concurrency,
        total_requests=args.requests if args.requests is not None else cfg.total_requests,
        step_levels=levels,
        step_requests=args.step_requests if args.step_requests is not None else cfg.step_requests,
        arrival_rate=args.arrival_rate if args.arrival_rate is not None else cfg.arrival_rate,
        fixed_duration_s=fixed_duration,
        step_duration_s=step_duration,
        auto_stop=cfg.auto_stop,
        sla_ttft_p95_s=cfg.sla_ttft_p95_s,
        sla_e2e_p95_s=cfg.sla_e2e_p95_s,
        sla_error_rate=cfg.sla_error_rate,
        input_tokens=args.input_tokens if args.input_tokens is not None else cfg.input_tokens,
        max_output_tokens=(
            args.max_output_tokens if args.max_output_tokens is not None else cfg.max_output_tokens
        ),
        timeout=args.timeout if args.timeout is not None else cfg.timeout,
        with_image=with_image,
        image_id=(image_spec if image_spec and image_spec.startswith("builtin:") else cfg.image_id),
        questions=questions,
    )
    return cfg, image_spec


# --------------------------------------------------------------------------- #
# 运行引擎（无 DB / 无 SSE）
# --------------------------------------------------------------------------- #
def _classify_exception(exc: Exception) -> str:
    if isinstance(exc, ProviderError):
        code = getattr(exc, "status_code", None)
        if code is not None:
            if 400 <= code < 500:
                return "http_4xx"
            if code >= 500:
                return "http_5xx"
        msg = str(exc)
        for token, cls in (
            ("ConnectError", "connect"),
            ("ConnectTimeout", "connect"),
            ("ReadTimeout", "read_timeout"),
            ("TimeoutException", "timeout"),
            ("ProxyError", "connect"),
            ("RemoteProtocolError", "connect"),
            ("ReadError", "connect"),
            ("WriteError", "connect"),
        ):
            if token in msg:
                return cls
        return "other"
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ProxyError)):
        return "connect"
    if isinstance(exc, (httpx.ReadTimeout, asyncio.TimeoutError)):
        return "read_timeout"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPError):
        return "connect"
    return "other"


def _question_pool(cfg: TaskConfig) -> list[str]:
    custom = [q.strip() for q in cfg.questions if q and q.strip()]
    if custom:
        return custom
    return VISION_QUESTIONS if cfg.with_image else SAMPLE_QUESTIONS


def _resolve_image(image_spec: str | None) -> tuple[str | None, str]:
    if not image_spec:
        return None, "image/jpeg"
    if image_spec.startswith("builtin:"):
        got = get_builtin_image(image_spec)
        if got is None:
            raise SystemExit(f"unknown builtin image: {image_spec}")
        data, mime = got
    elif Path(image_spec).is_file():
        data = Path(image_spec).read_bytes()
        mime = mimetypes.guess_type(image_spec)[0] or "image/jpeg"
    else:
        got = get_builtin_image(image_spec)
        if got is None:
            raise SystemExit(f"image not found: {image_spec}")
        data, mime = got
    return base64.b64encode(data).decode(), mime


def _planned_for(cfg: TaskConfig) -> int:
    if cfg.mode in ("fixed", "open"):
        if cfg.fixed_duration_s > 0:
            return 0
        return cfg.total_requests
    if cfg.step_duration_s > 0:
        return 0
    return len(cfg.step_levels) * cfg.step_requests


async def _run_one(
    provider,
    cfg: TaskConfig,
    idx: int,
    step: int,
    question: str,
    image_b64: str | None,
    image_mime: str,
    t0: float,
    cancel: asyncio.Event,
) -> RecordResult:
    prompt = compose_prompt(cfg.input_tokens, question, idx)
    start = perf_counter()
    ttft: float | None = None
    token_times: list[float] = []
    parts: list[str] = []
    usage = None
    status = "ok"
    error = ""
    error_class = "ok"

    async def consume() -> None:
        nonlocal ttft, usage
        async for chunk in provider.stream(
            prompt, cfg.max_output_tokens, cfg.timeout, image_b64, image_mime
        ):
            if cancel.is_set():
                raise _Aborted
            now = perf_counter()
            if ttft is None:
                ttft = now
            elif chunk.text:
                token_times.append(now)
            if chunk.text:
                parts.append(chunk.text)
            if chunk.usage is not None:
                usage = chunk.usage

    try:
        await asyncio.wait_for(consume(), timeout=cfg.timeout + 15)
    except _Aborted:
        status = "cancelled"
        error_class = "cancel"
    except asyncio.TimeoutError:
        status = "timeout"
        error = f"timeout after {cfg.timeout}s"
        error_class = "read_timeout"
    except ProviderError as exc:
        status = "error"
        error = str(exc)[:1000]
        error_class = _classify_exception(exc)
    except Exception as exc:  # noqa: BLE001
        status = "error"
        error = f"{type(exc).__name__}: {exc}"[:1000]
        error_class = _classify_exception(exc)

    end = perf_counter()
    text = "".join(parts)
    if usage is not None and usage.completion_tokens:
        output_tokens = int(usage.completion_tokens)
    else:
        output_tokens = count_tokens(text) if text else 0
    if usage is not None and usage.prompt_tokens:
        input_tokens = int(usage.prompt_tokens)
    else:
        input_tokens = count_tokens(prompt)

    itls = [
        round((token_times[i] - token_times[i - 1]) * 1000, 3)
        for i in range(1, len(token_times))
    ]
    itl_p50 = round(percentile(sorted(itls), 50), 3) if itls else None
    ttft_ms = round((ttft - start) * 1000, 2) if ttft else None
    e2e_ms = round((end - start) * 1000, 2)
    tpot_ms = None
    tok_per_s = None
    if status == "ok" and ttft is not None and output_tokens >= 2:
        span = end - ttft
        if span > 0:
            tpot_ms = round(span / (output_tokens - 1) * 1000, 3)
            tok_per_s = round((output_tokens - 1) / span, 2)

    return RecordResult(
        idx=idx,
        step=step,
        status=status,
        ttft_ms=ttft_ms,
        e2e_ms=e2e_ms,
        tpot_ms=tpot_ms,
        output_tokens=output_tokens,
        input_tokens=input_tokens,
        tok_per_s=tok_per_s,
        itl_p50_ms=itl_p50,
        error_class=error_class,
        error=error,
        t_start=round(start - t0, 3),
        t_end=round(end - t0, 3),
        itls=itls,
    )


class _Progress:
    """在 stderr 上原地刷新的一行实时进度。"""

    def __init__(self, agg: Aggregator, enabled: bool) -> None:
        self.agg = agg
        self.enabled = enabled

    def _line(self) -> str:
        s = self.agg.snapshot()
        planned = s["planned"] or 0
        total = str(planned) if planned else "∞"
        return (
            f"\r[{int(s['elapsed_s']):>4}s] {s['completed']}/{total} req  "
            f"{s['rps']:.2f} req/s  {s['output_tps']:.0f} tok/s  "
            f"TTFT p95 {s['ttft_ms']['p95']:.0f} ms  err {s['error_rate'] * 100:.1f}%"
        )

    def render(self, final: bool = False) -> None:
        if not self.enabled:
            return
        sys.stderr.write(self._line() + ("\n" if final else "\x1b[K"))
        sys.stderr.flush()

    async def loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            self.render()
            try:
                await asyncio.wait_for(stop.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
        self.render(final=True)


async def _run_fixed(
    provider,
    cfg: TaskConfig,
    *,
    concurrency: int,
    total: int,
    duration_s: float,
    step: int,
    sinks: list[Aggregator],
    progress: _Progress,
    questions: list[str],
    image_b64: str | None,
    image_mime: str,
    t0: float,
    cancel: asyncio.Event,
) -> None:
    sem = asyncio.Semaphore(concurrency)

    async def attempt(idx: int) -> None:
        if cancel.is_set():
            return
        async with sem:
            if cancel.is_set():
                return
            for a in sinks:
                a.on_start()
            try:
                rec = await _run_one(
                    provider,
                    cfg,
                    idx,
                    step,
                    questions[idx % len(questions)],
                    image_b64,
                    image_mime,
                    t0,
                    cancel,
                )
            except Exception as exc:  # noqa: BLE001
                now = perf_counter()
                rec = RecordResult(
                    idx=idx,
                    step=step,
                    status="error",
                    error=f"{type(exc).__name__}: {exc}"[:1000],
                    error_class=_classify_exception(exc),
                    t_start=round(now - t0, 3),
                    t_end=round(now - t0, 3),
                )
            finally:
                for a in sinks:
                    a.on_end()
            for a in sinks:
                a.add(rec)
            progress.render()

    if duration_s > 0:
        deadline = perf_counter() + duration_s
        counter = 0

        async def worker() -> None:
            nonlocal counter
            while not cancel.is_set() and perf_counter() < deadline:
                idx = counter
                counter += 1
                await attempt(idx)

        workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
    else:
        workers = [asyncio.create_task(attempt(i)) for i in range(total)]
    await asyncio.gather(*workers, return_exceptions=True)


async def _run_open(
    provider,
    cfg: TaskConfig,
    *,
    sinks: list[Aggregator],
    progress: _Progress,
    questions: list[str],
    image_b64: str | None,
    image_mime: str,
    t0: float,
    cancel: asyncio.Event,
) -> None:
    rate = max(cfg.arrival_rate, 0.01)
    interval = 1.0 / rate
    duration_s = cfg.fixed_duration_s
    deadline = perf_counter() + duration_s if duration_s > 0 else None
    total = 0 if duration_s > 0 else cfg.total_requests
    sem = asyncio.Semaphore(max(cfg.concurrency * 8, 512))

    async def attempt(idx: int) -> None:
        async with sem:
            if cancel.is_set():
                return
            for a in sinks:
                a.on_start()
            try:
                rec = await _run_one(
                    provider,
                    cfg,
                    idx,
                    -1,
                    questions[idx % len(questions)],
                    image_b64,
                    image_mime,
                    t0,
                    cancel,
                )
            except Exception as exc:  # noqa: BLE001
                now = perf_counter()
                rec = RecordResult(
                    idx=idx,
                    step=-1,
                    status="error",
                    error=f"{type(exc).__name__}: {exc}"[:1000],
                    error_class=_classify_exception(exc),
                    t_start=round(now - t0, 3),
                    t_end=round(now - t0, 3),
                )
            finally:
                for a in sinks:
                    a.on_end()
            for a in sinks:
                a.add(rec)
            progress.render()

    counter = 0
    inflight: set[asyncio.Task] = set()
    next_t = perf_counter()
    while True:
        if cancel.is_set():
            break
        now = perf_counter()
        if deadline is not None and now >= deadline:
            break
        if total > 0 and counter >= total:
            break
        if now < next_t:
            await asyncio.sleep(next_t - now)
        if cancel.is_set():
            break
        idx = counter
        counter += 1
        inflight.add(asyncio.create_task(attempt(idx)))
        next_t += interval
        lag = perf_counter() - next_t
        if lag > 1.0:
            next_t = perf_counter()
        if len(inflight) > 600:
            for t in [t for t in inflight if t.done()]:
                inflight.discard(t)
    await asyncio.gather(*inflight, return_exceptions=True)


async def run_benchmark(
    cfg: TaskConfig,
    *,
    image_spec: str | None = None,
    quiet: bool = False,
) -> dict:
    """执行一次压测，返回结果字典（不含 API Key）。"""
    progress_enabled = not quiet and sys.stderr.isatty()
    questions = _question_pool(cfg)
    image_b64, image_mime = _resolve_image(image_spec or (cfg.image_id if cfg.with_image else None))
    t0 = perf_counter()
    agg = Aggregator(planned=_planned_for(cfg))
    progress = _Progress(agg, enabled=progress_enabled)
    stop = asyncio.Event()
    cancel = asyncio.Event()
    ptask = asyncio.create_task(progress.loop(stop)) if progress_enabled else None
    steps: list[dict] = []
    analysis: dict = {}
    status = "done"
    error = ""

    client = httpx.AsyncClient()
    try:
        provider = create_provider(cfg.protocol, cfg.base_url, cfg.api_key, cfg.model, client)
        if cfg.mode == "fixed":
            await _run_fixed(
                provider,
                cfg,
                concurrency=cfg.concurrency,
                total=cfg.total_requests,
                duration_s=cfg.fixed_duration_s,
                step=-1,
                sinks=[agg],
                progress=progress,
                questions=questions,
                image_b64=image_b64,
                image_mime=image_mime,
                t0=t0,
                cancel=cancel,
            )
        elif cfg.mode == "open":
            await _run_open(
                provider,
                cfg,
                sinks=[agg],
                progress=progress,
                questions=questions,
                image_b64=image_b64,
                image_mime=image_mime,
                t0=t0,
                cancel=cancel,
            )
        else:
            for i, level in enumerate(cfg.step_levels):
                if cancel.is_set():
                    break
                sagg = Aggregator(planned=(0 if cfg.step_duration_s > 0 else cfg.step_requests))
                await _run_fixed(
                    provider,
                    cfg,
                    concurrency=level,
                    total=cfg.step_requests,
                    duration_s=cfg.step_duration_s,
                    step=i,
                    sinks=[agg, sagg],
                    progress=progress,
                    questions=questions,
                    image_b64=image_b64,
                    image_mime=image_mime,
                    t0=t0,
                    cancel=cancel,
                )
                steps.append(step_summary(sagg.snapshot(), level))
            if steps:
                analysis = analyze_steps(
                    steps,
                    sla={
                        "ttft_p95_s": cfg.sla_ttft_p95_s,
                        "e2e_p95_s": cfg.sla_e2e_p95_s,
                        "error_rate": cfg.sla_error_rate,
                    },
                )
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"[:2000]
    finally:
        stop.set()
        if ptask is not None:
            await ptask
        await client.aclose()

    result: dict = {
        "status": status,
        "error": error,
        "config": cfg.model_dump(exclude={"api_key"}),
        "summary": agg.snapshot(),
        "steps": steps,
        "analysis": analysis,
    }
    return result


# --------------------------------------------------------------------------- #
# 结果输出
# --------------------------------------------------------------------------- #
def _c(text: str, code: str, color: bool) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if color else text


def render_result(result: dict, *, color: bool = True, lang: str = "en") -> None:
    cfg = result.get("config", {})
    s = result.get("summary", {})
    steps = result.get("steps") or []
    analysis = result.get("analysis") or {}

    print()
    print(_c(f"  {tr(lang, 'title')}", "1", color))
    print(f"  {tr(lang, 'endpoint'):<9}: {cfg.get('base_url', '')}")
    print(f"  {tr(lang, 'model'):<9}: {cfg.get('model', '')}  ({cfg.get('protocol', '')})")
    if result.get("status") != "done":
        print(_c(f"  {tr(lang, 'status'):<9}: {result.get('status')}  {result.get('error', '')}", "31", color))

    if steps:
        print()
        print(_c(f"  {tr(lang, 'per_concurrency')}", "1", color))
        print(
            f"  {tr(lang, 'h_conc'):>6}  {tr(lang, 'h_rps'):>9}  {tr(lang, 'h_out'):>10}  "
            f"{tr(lang, 'h_ttft'):>13}  {tr(lang, 'h_e2e'):>12}  {tr(lang, 'h_tpot'):>13}  "
            f"{tr(lang, 'h_err'):>8}"
        )
        for st in steps:
            print(
                f"  {st['concurrency']:>6}  {st['rps']:>9.3f}  {st['output_tps']:>10.1f}  "
                f"{st['ttft_p95']:>13.1f}  {st['e2e_p95']:>12.1f}  {st['tpot_p95']:>13.1f}  "
                f"{st['error_rate'] * 100:>8.2f}"
            )

    print()
    print(_c(f"  {tr(lang, 'overall')}", "1", color))
    print(
        f"    {tr(lang, 'r_completed'):<9}: {s.get('completed', 0):>6}     "
        f"{tr(lang, 'r_errors'):<9}: {s.get('errors', 0):>6}     "
        f"{tr(lang, 'r_elapsed'):<9}: {s.get('elapsed_s', 0):>7.2f} s"
    )

    print()
    print(f"    {tr(lang, 'latency'):<13}{tr(lang, 'avg'):>10}{'p50':>10}{'p95':>10}{'p99':>10}")
    for key in ("ttft_ms", "tpot_ms", "itl_ms", "e2e_ms"):
        stats = s.get(key) or {}
        print(
            f"    {key.split('_')[0].upper():<13}"
            f"{stats.get('avg', 0.0):>10.2f}{stats.get('p50', 0.0):>10.2f}"
            f"{stats.get('p95', 0.0):>10.2f}{stats.get('p99', 0.0):>10.2f}"
        )

    print()
    print(f"    {tr(lang, 'throughput')}")
    print(f"      {tr(lang, 'r_output'):<9}: {s.get('output_tps', 0):>8.2f} tok/s")
    print(f"      {tr(lang, 'r_input'):<9}: {s.get('input_tps', 0):>8.2f} tok/s")
    print(f"      {tr(lang, 'r_requests'):<9}: {s.get('rps', 0):>8.3f} req/s")

    print()
    rate = s.get("error_rate", 0) * 100
    breakdown = s.get("error_breakdown") or {}
    extra = ""
    if breakdown:
        pretty = "  ".join(f"{k}={v}" for k, v in breakdown.items())
        extra = f"  ({pretty})"
    rate_color = "32" if rate == 0 else ("33" if rate < 5 else "31")
    print(f"    {tr(lang, 'r_error_rate'):<9}: {_c(f'{rate:.2f}%', rate_color, color)}{extra}")

    if analysis and analysis.get("ok"):
        def _v(x):
            return "-" if x is None else x

        print()
        print(_c(f"  {tr(lang, 'analysis')}", "1", color))
        print(f"    {tr(lang, 'a_recommended'):<24}: {_v(analysis.get('recommended_concurrency'))}")
        print(
            f"    {tr(lang, 'a_saturation'):<24}: {_v((analysis.get('saturation') or {}).get('concurrency'))}     "
            f"{tr(lang, 'a_knee'):<16}: {_v((analysis.get('knee') or {}).get('concurrency'))}"
        )
        print(f"    {tr(lang, 'a_sla_max'):<24}: {_v(analysis.get('sla_max_concurrency'))}")
        print(
            f"    {tr(lang, 'a_sustainable'):<24}: {_v(analysis.get('max_sustainable_rps'))}     "
            f"{tr(lang, 'a_confidence'):<16}: {_v(analysis.get('confidence'))}"
        )
    print()


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def execute(cfg: TaskConfig, args: argparse.Namespace, *, image_spec: str | None = None) -> int:
    as_json = getattr(args, "json", False)
    quiet = getattr(args, "quiet", False)
    no_color = getattr(args, "no_color", False)
    lang = getattr(args, "lang", "en") or "en"
    sys.stderr.write(
        f"running {cfg.mode} benchmark against {cfg.base_url or DEFAULT_BASE[cfg.protocol]} "
        f"({cfg.model})...\n"
    )
    result = asyncio.run(run_benchmark(cfg, image_spec=image_spec, quiet=quiet))
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        render_result(result, color=(not no_color and sys.stdout.isatty()), lang=lang)
    fail_over = getattr(args, "fail_over", None)
    if fail_over is not None and result["summary"].get("error_rate", 0) > fail_over:
        sys.stderr.write(
            f"error rate {result['summary']['error_rate']:.4f} exceeds limit {fail_over}\n"
        )
        return 3
    return 0 if result["status"] == "done" else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.lang = resolve_lang(args.lang or os.environ.get("LMB_LANG"))
    interactive = args.interactive or (
        args.base_url is None
        and args.model is None
        and args.config is None
        and not args.json
        and sys.stdin.isatty()
    )
    try:
        if interactive:
            from .interactive import run_wizard

            return run_wizard(args)
        cfg, image_spec = _config_from_args(args)
        if not cfg.model:
            parser.error("--model is required (or run with --interactive)")
        return execute(cfg, args, image_spec=image_spec)
    except KeyboardInterrupt:
        sys.stderr.write("\ninterrupted\n")
        return 130


__all__ = ["main", "build_parser", "run_benchmark", "render_result"]


if __name__ == "__main__":
    raise SystemExit(main())
