import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from time import perf_counter

import httpx
from sqlalchemy import update

from ..config import SNAPSHOT_INTERVAL
from ..crypto import decrypt
from ..db import SessionLocal
from ..models import ImageRow, RecordRow, TaskRow
from ..providers import ProviderError, create_provider
from ..schemas import TaskConfig
from .analysis import analyze_steps, check_auto_stop
from .metrics import Aggregator, RecordResult, percentile, step_summary
from .workload import (
    DEFAULT_IMAGE_ID,
    SAMPLE_QUESTIONS,
    VISION_QUESTIONS,
    compose_prompt,
    count_tokens,
    get_builtin_image,
)

log = logging.getLogger("llmbench.engine")

TERMINAL_STATUSES = {"done", "failed", "cancelled", "interrupted"}


class RequestAborted(Exception):
    pass


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


class TaskRuntime:
    def __init__(self, task_id: str, planned: int) -> None:
        self.task_id = task_id
        self.planned = planned
        self.cancel = asyncio.Event()
        self.subscribers: set[asyncio.Queue] = set()
        self.records: list[RecordResult] = []
        self.status = "running"
        self.error = ""
        self.steps: list[dict] = []
        self.current_step: dict | None = None
        self.aggregator = Aggregator(planned=planned)
        self.final_snapshot: dict | None = None
        self.analysis: dict = {}
        self.stop_reason: str = ""
        self.questions: list[str] = []
        self.image_mime: str = "image/jpeg"
        self.t0 = perf_counter()
        self._pending: list[RecordResult] = []
        self._last_flush = 0.0

    @property
    def finished(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def snapshot_event(self) -> dict:
        data = (
            self.final_snapshot
            if self.final_snapshot is not None
            else self.aggregator.snapshot()
        )
        payload = dict(data)
        if self.current_step is not None:
            payload["current_step"] = {
                "index": self.current_step["index"],
                "concurrency": self.current_step["concurrency"],
                "snapshot": self.current_step["agg"].snapshot(),
            }
        else:
            payload["current_step"] = None
        return {"type": "snapshot", "data": payload}


class TaskManager:
    def __init__(self) -> None:
        self.runtimes: dict[str, TaskRuntime] = {}
        self._bg_tasks: dict[str, asyncio.Task] = {}

    def get(self, task_id: str) -> TaskRuntime | None:
        return self.runtimes.get(task_id)

    def planned_for(self, cfg: TaskConfig) -> int:
        if cfg.mode == "fixed":
            if cfg.fixed_duration_s > 0:
                return 0
            return cfg.total_requests
        if cfg.mode == "open":
            if cfg.fixed_duration_s > 0:
                return 0
            return cfg.total_requests
        if cfg.step_duration_s > 0:
            return 0
        return len(cfg.step_levels) * cfg.step_requests

    async def start(self, task_id: str) -> None:
        async with SessionLocal() as session:
            row = await session.get(TaskRow, task_id)
        if row is None:
            raise ValueError(f"task {task_id} not found")
        cfg = TaskConfig.model_validate_json(row.config_json)
        rt = TaskRuntime(task_id, self.planned_for(cfg))
        self.runtimes[task_id] = rt
        bg = asyncio.create_task(self._run(task_id, rt))
        self._bg_tasks[task_id] = bg
        bg.add_done_callback(lambda _t: self._bg_tasks.pop(task_id, None))

    def cancel(self, task_id: str) -> bool:
        rt = self.runtimes.get(task_id)
        if rt is None or rt.finished:
            return False
        rt.cancel.set()
        return True

    def subscribe(self, task_id: str) -> tuple[asyncio.Queue, TaskRuntime | None]:
        rt = self.runtimes.get(task_id)
        q: asyncio.Queue = asyncio.Queue(maxsize=20000)
        if rt is not None:
            rt.subscribers.add(q)
        return q, rt

    def unsubscribe(self, task_id: str, q: asyncio.Queue) -> None:
        rt = self.runtimes.get(task_id)
        if rt is not None:
            rt.subscribers.discard(q)

    @staticmethod
    def _question_pool(cfg: TaskConfig) -> list[str]:
        custom = [q.strip() for q in cfg.questions if q and q.strip()]
        if custom:
            return custom
        return VISION_QUESTIONS if cfg.with_image else SAMPLE_QUESTIONS

    @staticmethod
    async def _resolve_image(cfg: TaskConfig) -> tuple[str | None, str]:
        if not cfg.with_image:
            return None, "image/jpeg"
        image_id = cfg.image_id or DEFAULT_IMAGE_ID
        data: tuple[bytes, str] | None = None
        if image_id.startswith("builtin:"):
            data = get_builtin_image(image_id)
        else:
            async with SessionLocal() as session:
                row = await session.get(ImageRow, image_id)
            if row is not None:
                data = (row.data, row.mime or "image/jpeg")
        if data is None:
            data = get_builtin_image(DEFAULT_IMAGE_ID)
        if data is None:
            return None, "image/jpeg"
        raw, mime = data
        return base64.b64encode(raw).decode(), mime

    @staticmethod
    def _publish(rt: TaskRuntime, event: dict) -> None:
        for q in list(rt.subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def _run(self, task_id: str, rt: TaskRuntime) -> None:
        async with SessionLocal() as session:
            row = await session.get(TaskRow, task_id)
            if row is None:
                rt.status = "failed"
                rt.error = "task row not found"
                return
            cfg = TaskConfig.model_validate_json(row.config_json)
            api_key = decrypt(row.api_key_enc)
            row.status = "running"
            row.started_at = datetime.now(timezone.utc)
            await session.commit()

        self._publish(rt, {"type": "status", "data": {"status": "running"}})

        client = httpx.AsyncClient()
        snapshot_task: asyncio.Task | None = None
        try:
            provider = create_provider(
                cfg.protocol, cfg.base_url, api_key, cfg.model, client
            )
            rt.questions = self._question_pool(cfg)
            image_b64, image_mime = await self._resolve_image(cfg)
            rt.image_mime = image_mime
            snapshot_task = asyncio.create_task(self._snapshot_loop(rt))

            if cfg.mode == "fixed":
                await self._run_fixed(
                    rt,
                    provider,
                    cfg,
                    client,
                    concurrency=cfg.concurrency,
                    total=cfg.total_requests,
                    duration_s=cfg.fixed_duration_s,
                    step=-1,
                    image_b64=image_b64,
                )
            elif cfg.mode == "open":
                await self._run_open(
                    rt,
                    provider,
                    cfg,
                    client,
                    image_b64=image_b64,
                )
            else:
                step_duration = cfg.step_duration_s
                step_planned = 0 if step_duration > 0 else cfg.step_requests
                sat_streak = 0
                for i, level in enumerate(cfg.step_levels):
                    if rt.cancel.is_set():
                        break
                    step_agg = Aggregator(planned=step_planned)
                    rt.current_step = {
                        "index": i,
                        "concurrency": level,
                        "agg": step_agg,
                    }
                    self._publish(
                        rt,
                        {
                            "type": "step_start",
                            "data": {"index": i, "concurrency": level},
                        },
                    )
                    await self._run_fixed(
                        rt,
                        provider,
                        cfg,
                        client,
                        concurrency=level,
                        total=cfg.step_requests,
                        duration_s=step_duration,
                        step=i,
                        image_b64=image_b64,
                        step_agg=step_agg,
                    )
                    summary = step_summary(step_agg.snapshot(), level)
                    rt.steps.append(summary)
                    self._publish(rt, {"type": "steps", "data": rt.steps})
                    rt.current_step = None
                    if rt.cancel.is_set():
                        break
                    stop_reason = ""
                    if cfg.auto_stop and not rt.stop_reason:
                        prev = rt.steps[-2] if len(rt.steps) >= 2 else None
                        stop_reason, sat_streak = check_auto_stop(
                            summary, prev, sat_streak, cfg.sla_error_rate
                        )
                    if stop_reason:
                        rt.stop_reason = stop_reason
                        self._publish(
                            rt,
                            {
                                "type": "auto_stop",
                                "data": {"reason": stop_reason},
                            },
                        )
                        break
                    await asyncio.sleep(0.5)

            status = "cancelled" if rt.cancel.is_set() else "done"
        except Exception as exc:  # noqa: BLE001
            log.exception("task %s failed", task_id)
            status = "failed"
            rt.error = f"{type(exc).__name__}: {exc}"[:2000]
        finally:
            if snapshot_task is not None:
                snapshot_task.cancel()
                try:
                    await snapshot_task
                except asyncio.CancelledError:
                    pass
            await self._flush(rt, force=True)
            await client.aclose()
            rt.final_snapshot = rt.aggregator.snapshot()
            rt.status = status
            rt.current_step = None
            if cfg.mode == "step" and rt.steps:
                rt.analysis = analyze_steps(
                    rt.steps,
                    sla={
                        "ttft_p95_s": cfg.sla_ttft_p95_s,
                        "e2e_p95_s": cfg.sla_e2e_p95_s,
                        "error_rate": cfg.sla_error_rate,
                    },
                    stop_reason=rt.stop_reason,
                )
            async with SessionLocal() as session:
                await session.execute(
                    update(TaskRow)
                    .where(TaskRow.id == task_id)
                    .values(
                        status=status,
                        error=rt.error,
                        summary_json=json.dumps(rt.final_snapshot),
                        steps_json=json.dumps(rt.steps, ensure_ascii=False),
                        analysis_json=json.dumps(rt.analysis, ensure_ascii=False),
                        finished_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()
            self._publish(rt, rt.snapshot_event())
            if rt.analysis:
                self._publish(rt, {"type": "analysis", "data": rt.analysis})
            self._publish(
                rt,
                {"type": "status", "data": {"status": status, "error": rt.error}},
            )

    async def _snapshot_loop(self, rt: TaskRuntime) -> None:
        while True:
            await asyncio.sleep(SNAPSHOT_INTERVAL)
            await self._flush(rt)
            self._publish(rt, rt.snapshot_event())

    async def _attempt(
        self,
        rt: TaskRuntime,
        provider,
        cfg: TaskConfig,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        idx: int,
        step: int,
        image_b64: str | None,
        step_agg: Aggregator | None = None,
    ) -> None:
        if rt.cancel.is_set():
            return
        async with sem:
            if rt.cancel.is_set():
                return
            rt.aggregator.on_start()
            if step_agg is not None:
                step_agg.on_start()
            try:
                rec = await self._run_one(rt, provider, cfg, client, idx, step, image_b64)
            except Exception as exc:  # noqa: BLE001
                now = perf_counter()
                rec = RecordResult(
                    idx=idx,
                    step=step,
                    status="error",
                    error=f"{type(exc).__name__}: {exc}"[:1000],
                    error_class=_classify_exception(exc),
                    t_start=round(now - rt.t0, 3),
                    t_end=round(now - rt.t0, 3),
                )
            finally:
                rt.aggregator.on_end()
                if step_agg is not None:
                    step_agg.on_end()
            rt.aggregator.add(rec)
            if step_agg is not None:
                step_agg.add(rec)
            rt.records.append(rec)
            rt._pending.append(rec)
            self._publish(rt, {"type": "record", "data": rec.as_dict()})
            await self._flush(rt)

    async def _run_fixed(
        self,
        rt: TaskRuntime,
        provider,
        cfg: TaskConfig,
        client: httpx.AsyncClient,
        *,
        concurrency: int,
        total: int,
        duration_s: float,
        step: int,
        image_b64: str | None,
        step_agg: Aggregator | None = None,
    ) -> None:
        sem = asyncio.Semaphore(concurrency)

        if duration_s > 0:
            deadline = perf_counter() + duration_s
            counter = 0

            async def worker() -> None:
                nonlocal counter
                while not rt.cancel.is_set() and perf_counter() < deadline:
                    idx = counter
                    counter += 1
                    await self._attempt(
                        rt, provider, cfg, client, sem, idx, step, image_b64, step_agg
                    )

            workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
        else:
            workers = [
                asyncio.create_task(
                    self._attempt(
                        rt, provider, cfg, client, sem, i, step, image_b64, step_agg
                    )
                )
                for i in range(total)
            ]
        await asyncio.gather(*workers, return_exceptions=True)

    async def _run_open(
        self,
        rt: TaskRuntime,
        provider,
        cfg: TaskConfig,
        client: httpx.AsyncClient,
        *,
        image_b64: str | None,
        step: int = -1,
        step_agg: Aggregator | None = None,
    ) -> None:
        """Open-loop：按固定到达速率注入请求，不等待前序请求完成。"""
        rate = max(cfg.arrival_rate, 0.01)
        interval = 1.0 / rate
        duration_s = cfg.fixed_duration_s
        deadline = perf_counter() + duration_s if duration_s > 0 else None
        total = 0 if duration_s > 0 else cfg.total_requests
        # open-loop 下信号量仅作极端保护，不参与节奏控制
        sem = asyncio.Semaphore(max(cfg.concurrency * 8, 512))

        counter = 0
        inflight: set[asyncio.Task] = set()
        next_t = perf_counter()

        while True:
            if rt.cancel.is_set():
                break
            now = perf_counter()
            if deadline is not None and now >= deadline:
                break
            if total > 0 and counter >= total:
                break
            if now < next_t:
                await asyncio.sleep(next_t - now)
            if rt.cancel.is_set():
                break
            idx = counter
            counter += 1
            inflight.add(
                asyncio.create_task(
                    self._attempt(
                        rt, provider, cfg, client, sem, idx, step, image_b64, step_agg
                    )
                )
            )
            next_t += interval
            lag = perf_counter() - next_t
            if lag > 1.0:
                next_t = perf_counter()
            if len(inflight) > 600:
                done = [t for t in inflight if t.done()]
                for t in done:
                    inflight.discard(t)
        await asyncio.gather(*inflight, return_exceptions=True)

    async def _run_one(
        self,
        rt: TaskRuntime,
        provider,
        cfg: TaskConfig,
        client: httpx.AsyncClient,
        idx: int,
        step: int,
        image_b64: str | None,
    ) -> RecordResult:
        questions = rt.questions or SAMPLE_QUESTIONS
        question = questions[idx % len(questions)]
        prompt = compose_prompt(cfg.input_tokens, question, idx)
        t0 = perf_counter()
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
                prompt,
                cfg.max_output_tokens,
                cfg.timeout,
                image_b64,
                rt.image_mime,
            ):
                if rt.cancel.is_set():
                    raise RequestAborted
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
        except RequestAborted:
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

        t1 = perf_counter()
        text = "".join(parts)
        output_tokens = 0
        if usage is not None and usage.completion_tokens:
            output_tokens = int(usage.completion_tokens)
        elif text:
            output_tokens = count_tokens(text)

        input_tokens = 0
        if usage is not None and usage.prompt_tokens:
            input_tokens = int(usage.prompt_tokens)
        else:
            input_tokens = count_tokens(prompt)

        itls_ms = [
            round((token_times[i] - token_times[i - 1]) * 1000, 3)
            for i in range(1, len(token_times))
        ]
        itl_p50_ms = (
            round(percentile(sorted(itls_ms), 50), 3) if itls_ms else None
        )

        ttft_ms = round((ttft - t0) * 1000, 2) if ttft else None
        e2e_ms = round((t1 - t0) * 1000, 2)
        tpot_ms = None
        tok_per_s = None
        if status == "ok" and ttft is not None and output_tokens >= 2:
            gen_span = t1 - ttft
            if gen_span > 0:
                tpot_ms = round(gen_span / (output_tokens - 1) * 1000, 3)
                tok_per_s = round((output_tokens - 1) / gen_span, 2)

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
            itl_p50_ms=itl_p50_ms,
            error_class=error_class,
            error=error,
            t_start=round(t0 - rt.t0, 3),
            t_end=round(t1 - rt.t0, 3),
            itls=itls_ms,
        )

    async def _flush(self, rt: TaskRuntime, force: bool = False) -> None:
        now = perf_counter()
        if not rt._pending:
            return
        if not force and len(rt._pending) < 30 and now - rt._last_flush < 1.0:
            return
        batch, rt._pending = rt._pending, []
        rt._last_flush = now
        try:
            async with SessionLocal() as session:
                session.add_all(
                    [
                        RecordRow(
                            task_id=rt.task_id,
                            idx=r.idx,
                            step=r.step,
                            status=r.status,
                            ttft_ms=r.ttft_ms,
                            e2e_ms=r.e2e_ms,
                            tpot_ms=r.tpot_ms,
                            output_tokens=r.output_tokens,
                            input_tokens=r.input_tokens,
                            tok_per_s=r.tok_per_s,
                            itl_p50_ms=r.itl_p50_ms,
                            error_class=r.error_class,
                            error=r.error,
                            t_start=r.t_start,
                            t_end=r.t_end,
                        )
                        for r in batch
                    ]
                )
                await session.commit()
        except Exception:  # noqa: BLE001
            log.exception("failed to flush records for task %s", rt.task_id)
            rt._pending = batch + rt._pending


manager = TaskManager()
