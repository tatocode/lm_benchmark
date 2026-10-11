"""Interactive command-line wizard: asks for endpoint and load-test config, then runs.

Aimed at headless users; launched via ``llm-bench --interactive`` or by running the
CLI with no arguments on a TTY. English by default, switchable to Chinese.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from time import perf_counter

import httpx

from .cli import DEFAULT_BASE, render_result, run_benchmark, tr
from .providers import ProviderError, create_provider
from .schemas import TaskConfig

_YES = {"", "y", "yes", "是", "1"}
_NO = {"n", "no", "否", "0"}
_LANG_ZH = {"zh", "cn", "zh-cn", "chinese", "中文"}
_LANG_EN = {"en", "english"}


def _color(text: str, code: str, enabled: bool) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if enabled else text


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


def _ask_int(prompt: str, default: int, lang: str, minimum: int = 1) -> int:
    while True:
        raw = _ask(prompt, str(default))
        try:
            value = int(raw)
        except ValueError:
            print(f"  {tr(lang, 'err_int')}")
            continue
        if value < minimum:
            print(f"  {tr(lang, 'err_ge', n=minimum)}")
            continue
        return value


def _ask_float(prompt: str, default: float, lang: str, minimum: float = 0.0) -> float:
    while True:
        raw = _ask(prompt, str(default))
        try:
            value = float(raw)
        except ValueError:
            print(f"  {tr(lang, 'err_num')}")
            continue
        if value < minimum:
            print(f"  {tr(lang, 'err_ge', n=minimum)}")
            continue
        return value


def _ask_yesno(prompt: str, default: bool = True) -> bool:
    while True:
        raw = _ask(f"{prompt} (y/n)", "y" if default else "n").lower()
        if raw in _YES:
            return True
        if raw in _NO:
            return False


def _ask_choice(prompt: str, choices: list[str], default: str, lang: str) -> str:
    joined = "/".join(choices)
    while True:
        raw = _ask(f"{prompt} ({joined})", default).lower()
        if raw in choices:
            return raw
        print(f"  {tr(lang, 'err_choice', opts=joined)}")


def _list_models(cfg: TaskConfig) -> list[str]:
    async def go() -> list[str]:
        async with httpx.AsyncClient() as client:
            provider = create_provider(cfg.protocol, cfg.base_url, cfg.api_key, cfg.model, client)
            return await asyncio.wait_for(provider.list_models(), timeout=20.0)

    try:
        return asyncio.run(go())
    except Exception:  # noqa: BLE001
        return []


def _probe(cfg: TaskConfig) -> tuple[bool, float | None, str]:
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
                return True, ttft, text.strip()[:60]
            except ProviderError as exc:
                return False, None, str(exc)[:200]

    return asyncio.run(go())


def run_wizard(args: argparse.Namespace) -> int:
    lang = getattr(args, "lang", "en") or "en"
    color = sys.stdout.isatty()

    print()
    raw_lang = _ask(tr(lang, "lang_prompt"), lang).strip().lower()
    if raw_lang in _LANG_ZH:
        lang = "zh"
    elif raw_lang in _LANG_EN:
        lang = "en"

    title = tr(lang, "title")
    print()
    print(f"  {title}")
    print("  " + "-" * 48)
    print(f"  {tr(lang, 'hint')}")
    print()

    cfg = TaskConfig()
    # Allow command-line arguments to seed the wizard defaults.
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

    protocol = _ask_choice("Protocol", ["openai", "anthropic", "gemini"], cfg.protocol, lang)
    cfg.protocol = protocol

    default_base = args.base_url or cfg.base_url or DEFAULT_BASE[protocol]
    cfg.base_url = _ask(tr(lang, "base_url"), default_base)

    cfg.api_key = _ask_secret(tr(lang, "api_key"), args.api_key or "")

    if _ask_yesno(tr(lang, "fetch_models"), default=True):
        models = _list_models(cfg)
        if models:
            print(f"  {tr(lang, 'models_available')}")
            for i, name in enumerate(models[:30], 1):
                print(f"    {i:>2}. {name}")
            raw = _ask(tr(lang, "choose_model"), args.model or (models[0] if models else ""))
            if raw.isdigit() and 1 <= int(raw) <= min(len(models), 30):
                cfg.model = models[int(raw) - 1]
            else:
                cfg.model = raw
        else:
            print(f"  {tr(lang, 'models_fail')}")
            cfg.model = _ask(tr(lang, "model"), args.model or cfg.model)
    else:
        cfg.model = _ask(tr(lang, "model"), args.model or cfg.model)

    if _ask_yesno(tr(lang, "test_conn"), default=True):
        ok, ttft, info = _probe(cfg)
        if ok:
            tag = _color("[OK]", "32", color)
            detail = f"  TTFT {ttft:.0f} ms" if ttft else ""
            print(f"  {tag} {tr(lang, 'conn_ok')}{detail}")
            if info:
                print(f"       {tr(lang, 'sample')}: {info!r}")
        else:
            tag = _color("[FAIL]", "31", color)
            print(f"  {tag} {tr(lang, 'conn_fail')}: {info}")

    print()
    cfg.mode = _ask_choice("Mode", ["fixed", "step", "open"], cfg.mode, lang)
    if cfg.mode == "fixed":
        cfg.concurrency = _ask_int(tr(lang, "concurrency"), cfg.concurrency, lang)
        cfg.total_requests = _ask_int(tr(lang, "requests"), cfg.total_requests, lang)
        cfg.fixed_duration_s = _ask_float(tr(lang, "duration_fixed"), cfg.fixed_duration_s, lang)
    elif cfg.mode == "step":
        cfg.step_levels = _parse_levels(_ask(tr(lang, "levels"), ",".join(map(str, cfg.step_levels))))
        cfg.step_requests = _ask_int(tr(lang, "step_requests"), cfg.step_requests, lang)
        cfg.step_duration_s = _ask_float(tr(lang, "duration_step"), cfg.step_duration_s, lang)
    else:
        cfg.arrival_rate = _ask_float(tr(lang, "arrival_rate"), cfg.arrival_rate, lang, minimum=0.01)
        cfg.total_requests = _ask_int(tr(lang, "requests"), cfg.total_requests, lang)
        cfg.fixed_duration_s = _ask_float(tr(lang, "duration_fixed"), cfg.fixed_duration_s, lang)

    print()
    cfg.input_tokens = _ask_int(tr(lang, "input_tokens"), cfg.input_tokens, lang)
    cfg.max_output_tokens = _ask_int(tr(lang, "max_output_tokens"), cfg.max_output_tokens, lang)
    cfg.timeout = _ask_float(tr(lang, "timeout"), cfg.timeout, lang, minimum=1.0)

    image_spec = None
    if _ask_yesno(tr(lang, "vision"), default=False):
        image_spec = _ask(tr(lang, "vision_image"), "builtin:golden-gate")
        cfg.with_image = True

    print()
    print(f"  {tr(lang, 'about')}:")
    print(f"    {tr(lang, 'l_protocol'):<9}: {cfg.protocol}")
    print(f"    {tr(lang, 'l_endpoint'):<9}: {cfg.base_url}")
    print(f"    {tr(lang, 'l_model'):<9}: {cfg.model}")

    if cfg.mode == "fixed":
        mode_detail = (
            f"fixed  ({tr(lang, 'l_conc')} {cfg.concurrency}, {tr(lang, 'l_req')} {cfg.total_requests})"
        )
    elif cfg.mode == "step":
        levels = ",".join(map(str, cfg.step_levels))
        mode_detail = f"step  (levels {levels}, {tr(lang, 'l_req')} {cfg.step_requests})"
    else:
        mode_detail = f"open  (arrival {cfg.arrival_rate} req/s, {tr(lang, 'l_req')} {cfg.total_requests})"
    print(f"    {tr(lang, 'l_mode'):<9}: {mode_detail}")

    print(
        f"    {tr(lang, 'l_tokens'):<9}: "
        f"{tr(lang, 'l_input')} {cfg.input_tokens} / {tr(lang, 'l_output')} {cfg.max_output_tokens}"
    )
    print(f"    {tr(lang, 'l_timeout'):<9}: {cfg.timeout:.0f} s")
    if image_spec:
        print(f"    {tr(lang, 'l_vision'):<9}: {image_spec}")
    print()

    if not _ask_yesno(tr(lang, "start"), default=True):
        print(tr(lang, "cancelled"))
        return 0

    result = asyncio.run(run_benchmark(cfg, image_spec=image_spec))
    render_result(result, color=sys.stdout.isatty(), lang=lang)
    return 0 if result["status"] == "done" else 1


def _parse_levels(text: str) -> list[int]:
    levels = []
    for part in text.split(","):
        part = part.strip()
        if part.isdigit() and int(part) >= 1:
            levels.append(int(part))
    return levels[:12] or [1, 2, 4, 8, 16]


__all__ = ["run_wizard"]
