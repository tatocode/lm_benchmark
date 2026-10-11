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
    p.add_argument("--interactive", "-i", action="store_true", help="进入交互式向导")
    p.add_argument("--config", help="从 TaskConfig JSON 文件读取配置作为基准")

    p.add_argument("--protocol", choices=["openai", "anthropic", "gemini"], default=None)
    p.add_argument("--base-url", dest="base_url", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--api-key", dest="api_key", default=None, help="也可用环境变量 LMB_API_KEY")

    p.add_argument("--mode", choices=["fixed", "step", "open"], default=None)
    p.add_argument("--concurrency", type=int, default=None, help="fixed/open 模式的并发数")
    p.add_argument("--requests", type=int, default=None, help="总请求数（fixed / open）")
    p.add_argument("--levels", default=None, help="阶梯并发，逗号分隔，如 1,2,4,8,16")
    p.add_argument("--step-requests", dest="step_requests", type=int, default=None, help="每档请求数")
    p.add_argument("--arrival-rate", dest="arrival_rate", type=float, default=None, help="open 模式到达速率 req/s")
    p.add_argument(
        "--duration",
        type=float,
        default=None,
        help="按时长压测（秒）。fixed/open 用 fixed_duration，step 用 step_duration；0 表示按请求数",
    )
    p.add_argument("--input-tokens", dest="input_tokens", type=int, default=None)
    p.add_argument("--max-output-tokens", dest="max_output_tokens", type=int, default=None, help="即 max_tokens")
    p.add_argument("--timeout", type=float, default=None, help="单请求超时（秒）")
    p.add_argument("--image", default=None, help="视觉测试图片：builtin:<id> 或本地文件路径")
    p.add_argument("--questions", default=None, help="自定义问题，多个用 | 分隔")

    p.add_argument("--json", action="store_true", help="以 JSON 输出结果到 stdout")
    p.add_argument("--quiet", action="store_true", help="不显示实时进度")
    p.add_argument("--no-color", dest="no_color", action="store_true", help="禁用彩色输出")
    p.add_argument(
        "--fail-over",
        dest="fail_over",
        type=float,
        default=None,
        help="错误率超过该阈值时以退出码 3 结束（便于 CI）",
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
            f"{s['rps']:.1f} rps  {s['output_tps']:.0f} tok/s  "
            f"TTFT p95 {s['ttft_ms']['p95']:.0f}ms  err {s['error_rate'] * 100:.1f}%"
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


def _stats_line(label: str, stats: dict, unit: str = "ms") -> str:
    return (
        f"  {label:<6} avg {stats['avg']:>9.2f}  p50 {stats['p50']:>9.2f}  "
        f"p95 {stats['p95']:>9.2f}  p99 {stats['p99']:>9.2f}  {unit}"
    )


def render_result(result: dict, *, color: bool = True) -> None:
    cfg = result.get("config", {})
    s = result.get("summary", {})
    steps = result.get("steps") or []
    analysis = result.get("analysis") or {}

    print()
    print(_c("── LLM Benchmark ────────────────────────────────", "1", color))
    print(f"  endpoint : {cfg.get('base_url', '')}")
    print(f"  model    : {cfg.get('model', '')}  ({cfg.get('protocol', '')})")
    if result.get("status") != "done":
        print(_c(f"  status   : {result.get('status')}  {result.get('error', '')}", "31", color))

    if steps:
        print()
        print(_c("  per-concurrency", "1", color))
        header = (
            f"  {'conc':>5}  {'rps':>8}  {'out t/s':>9}  "
            f"{'TTFT p95':>9}  {'E2E p95':>9}  {'TPOT p95':>9}  {'err%':>6}"
        )
        print(header)
        for st in steps:
            print(
                f"  {st['concurrency']:>5}  {st['rps']:>8.3f}  {st['output_tps']:>9.1f}  "
                f"{st['ttft_p95']:>9.1f}  {st['e2e_p95']:>9.1f}  {st['tpot_p95']:>9.1f}  "
                f"{st['error_rate'] * 100:>6.2f}"
            )

    print()
    print(_c("  overall metrics", "1", color))
    print(f"  completed {s.get('completed', 0)}   errors {s.get('errors', 0)}   "
          f"elapsed {s.get('elapsed_s', 0)}s")
    print(_stats_line("TTFT", s.get("ttft_ms", {})))
    print(_stats_line("TPOT", s.get("tpot_ms", {})))
    print(_stats_line("ITL", s.get("itl_ms", {})))
    print(_stats_line("E2E", s.get("e2e_ms", {})))
    print(f"  output   {s.get('output_tps', 0):.1f} tok/s   "
          f"input {s.get('input_tps', 0):.1f} tok/s   RPS {s.get('rps', 0):.3f}")
    print(f"  error rate {s.get('error_rate', 0) * 100:.2f}%   "
          f"{s.get('error_breakdown', {}) or ''}")

    if analysis and analysis.get("ok"):
        print()
        print(_c("  analysis", "1", color))
        rec = analysis.get("recommended_concurrency")
        sat = (analysis.get("saturation") or {}).get("concurrency")
        knee = (analysis.get("knee") or {}).get("concurrency")
        print(f"  recommended concurrency : {rec}")
        print(f"  saturation              : {sat}   knee: {knee}   "
              f"SLA max: {analysis.get('sla_max_concurrency')}")
        print(f"  max sustainable rps     : {analysis.get('max_sustainable_rps')}   "
              f"confidence: {analysis.get('confidence')}")
    print()


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def execute(cfg: TaskConfig, args: argparse.Namespace, *, image_spec: str | None = None) -> int:
    as_json = getattr(args, "json", False)
    quiet = getattr(args, "quiet", False)
    no_color = getattr(args, "no_color", False)
    sys.stderr.write(
        f"running {cfg.mode} benchmark against {cfg.base_url or DEFAULT_BASE[cfg.protocol]} "
        f"({cfg.model})...\n"
    )
    result = asyncio.run(run_benchmark(cfg, image_spec=image_spec, quiet=quiet))
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        render_result(result, color=(not no_color and sys.stdout.isatty()))
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
