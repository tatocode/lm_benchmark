"""交互式命令行向导：逐步询问端点与压测配置后执行。

面向没有图形界面的用户，通过 ``llm-bench --interactive`` 或重新导向启动。
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from time import perf_counter

import httpx

from .cli import DEFAULT_BASE, render_result, run_benchmark
from .providers import ProviderError, create_provider
from .schemas import TaskConfig

_YES = {"", "y", "yes", "是", "1"}
_NO = {"n", "no", "否", "0"}


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, StopIteration):
        return default
    return raw or default


def _ask_secret(prompt: str, default: str = "") -> str:
    if default:
        return default
    try:
        return getpass.getpass(f"{prompt}: ").strip()
    except (EOFError, StopIteration):
        return ""


def _ask_int(prompt: str, default: int, minimum: int = 1) -> int:
    while True:
        raw = _ask(prompt, str(default))
        try:
            value = int(raw)
        except ValueError:
            print("  请输入整数")
            continue
        if value < minimum:
            print(f"  需 >= {minimum}")
            continue
        return value


def _ask_float(prompt: str, default: float, minimum: float = 0.0) -> float:
    while True:
        raw = _ask(prompt, str(default))
        try:
            value = float(raw)
        except ValueError:
            print("  请输入数字")
            continue
        if value < minimum:
            print(f"  需 >= {minimum}")
            continue
        return value


def _ask_yesno(prompt: str, default: bool = True) -> bool:
    while True:
        raw = _ask(f"{prompt} (y/n)", "y" if default else "n").lower()
        if raw in _YES:
            return True
        if raw in _NO:
            return False


def _ask_choice(prompt: str, choices: list[str], default: str) -> str:
    joined = "/".join(choices)
    while True:
        raw = _ask(f"{prompt} ({joined})", default).lower()
        if raw in choices:
            return raw
        print(f"  可选：{joined}")


def _list_models(cfg: TaskConfig) -> list[str]:
    async def go() -> list[str]:
        async with httpx.AsyncClient() as client:
            provider = create_provider(cfg.protocol, cfg.base_url, cfg.api_key, cfg.model, client)
            return await asyncio.wait_for(provider.list_models(), timeout=20.0)

    try:
        return asyncio.run(go())
    except Exception:  # noqa: BLE001
        return []


def _probe(cfg: TaskConfig) -> None:
    async def go() -> tuple[bool, float | None, str]:
        async with httpx.AsyncClient() as client:
            provider = create_provider(cfg.protocol, cfg.base_url, cfg.api_key, cfg.model, client)
            t0 = perf_counter()
            first = None
            text = ""
            try:
                async for chunk in provider.stream("Reply with one word: pong", 16, 30.0):
                    if first is None:
                        first = perf_counter()
                    if chunk.text:
                        text += chunk.text
                ttft = (first - t0) * 1000 if first else None
                return True, ttft, text[:60]
            except ProviderError as exc:
                return False, None, str(exc)[:200]

    ok, ttft, info = asyncio.run(go())
    if ok:
        extra = f"  TTFT {ttft:.0f}ms · {info!r}" if ttft else ""
        print(f"  ✔ 连接成功{extra}")
    else:
        print(f"  ✘ 连接失败: {info}")


def run_wizard(args: argparse.Namespace) -> int:
    print()
    print("╭───────────────────────────────────────────────╮")
    print("│  LLM Benchmark · 交互式压测                   │")
    print("╰───────────────────────────────────────────────╯")
    print("提示：直接回车使用方括号内的默认值。")
    print()

    cfg = TaskConfig()
    # 允许命令行参数作为向导默认值
    if args.protocol:
        cfg.protocol = args.protocol
    if args.base_url:
        cfg.base_url = args.base_url
    if args.api_key:
        cfg.api_key = args.api_key
    if args.model:
        cfg.model = args.model
    if args.mode:
        cfg.mode = args.mode
    if args.concurrency is not None:
        cfg.concurrency = args.concurrency
    if args.requests is not None:
        cfg.total_requests = args.requests
    if args.step_requests is not None:
        cfg.step_requests = args.step_requests
    if args.arrival_rate is not None:
        cfg.arrival_rate = args.arrival_rate
    if args.input_tokens is not None:
        cfg.input_tokens = args.input_tokens
    if args.max_output_tokens is not None:
        cfg.max_output_tokens = args.max_output_tokens
    if args.timeout is not None:
        cfg.timeout = args.timeout
    if args.levels:
        cfg.step_levels = _parse_levels(args.levels)

    protocol = _ask_choice("协议 Protocol", ["openai", "anthropic", "gemini"], cfg.protocol)
    cfg.protocol = protocol

    default_base = args.base_url or cfg.base_url or DEFAULT_BASE[protocol]
    cfg.base_url = _ask("推理地址 Base URL", default_base)

    key_default = args.api_key or ""
    cfg.api_key = _ask_secret("API Key（本地服务可留空）", key_default)

    if _ask_yesno("获取可用模型列表", default=True):
        models = _list_models(cfg)
        if models:
            print("  可用模型：")
            for i, name in enumerate(models[:30], 1):
                print(f"    {i:>2}. {name}")
            raw = _ask("选择序号或直接输入模型名", args.model or (models[0] if models else ""))
            if raw.isdigit() and 1 <= int(raw) <= min(len(models), 30):
                cfg.model = models[int(raw) - 1]
            else:
                cfg.model = raw
        else:
            print("  （未能获取，请手动输入）")
            cfg.model = _ask("模型名 Model", args.model or cfg.model)
    else:
        cfg.model = _ask("模型名 Model", args.model or cfg.model)

    if _ask_yesno("现在测试连通性", default=True):
        _probe(cfg)
        print()

    cfg.mode = _ask_choice("压测模式 Mode", ["fixed", "step", "open"], cfg.mode)
    if cfg.mode == "fixed":
        cfg.concurrency = _ask_int("并发数 concurrency", cfg.concurrency)
        cfg.total_requests = _ask_int("总请求数 requests", cfg.total_requests)
        cfg.fixed_duration_s = _ask_float("按时长（秒，0 表示按请求数）", cfg.fixed_duration_s)
    elif cfg.mode == "step":
        cfg.step_levels = _parse_levels(_ask("并发阶梯 levels", ",".join(map(str, cfg.step_levels))))
        cfg.step_requests = _ask_int("每档请求数 step-requests", cfg.step_requests)
        cfg.step_duration_s = _ask_float("每档时长（秒，0 表示按请求数）", cfg.step_duration_s)
    else:
        cfg.arrival_rate = _ask_float("到达速率 arrival-rate (req/s)", cfg.arrival_rate, minimum=0.01)
        cfg.total_requests = _ask_int("总请求数 requests", cfg.total_requests)
        cfg.fixed_duration_s = _ask_float("持续时长（秒，0 表示按请求数）", cfg.fixed_duration_s)

    print()
    cfg.input_tokens = _ask_int("输入长度 input-tokens", cfg.input_tokens)
    cfg.max_output_tokens = _ask_int("最大输出 max-output-tokens", cfg.max_output_tokens)
    cfg.timeout = _ask_float("单请求超时 timeout（秒）", cfg.timeout, minimum=1.0)

    image_spec = None
    if _ask_yesno("启用视觉测试（附图片）", default=False):
        image_spec = _ask("图片：builtin:<id> 或本地路径", "builtin:golden-gate")
        cfg.with_image = True

    print()
    print("即将运行：")
    print(f"  {cfg.protocol} · {cfg.base_url} · {cfg.model}")
    print(f"  ✘ {cfg.mode} · 输入 {cfg.input_tokens} / 输出 {cfg.max_output_tokens} tokens")
    if not _ask_yesno("开始压测", default=True):
        print("已取消。")
        return 0

    result = asyncio.run(run_benchmark(cfg, image_spec=image_spec))
    render_result(result, color=sys.stdout.isatty())
    return 0 if result["status"] == "done" else 1


def _parse_levels(text: str) -> list[int]:
    levels = []
    for part in text.split(","):
        part = part.strip()
        if part.isdigit() and int(part) >= 1:
            levels.append(int(part))
    return levels[:12] or [1, 2, 4, 8, 16]


__all__ = ["run_wizard"]
