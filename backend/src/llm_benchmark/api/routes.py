import asyncio
import base64
import json
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, desc, select

from ..bench.engine import TERMINAL_STATUSES, manager
from ..bench.metrics import aggregate_records
from ..bench.workload import (
    SAMPLE_QUESTIONS,
    VISION_QUESTIONS,
    get_builtin_image,
    list_builtin_images,
)
from ..crypto import encrypt
from ..db import SessionLocal
from ..models import ImageRow, PresetRow, RecordRow, TaskRow
from ..providers import ProviderError, create_provider
from ..schemas import (
    ImageIn,
    ImageOut,
    ModelListResult,
    PresetIn,
    PresetOut,
    ProbeRequest,
    ProbeResult,
    RecordOut,
    TaskConfig,
    TaskCreate,
    TaskDetail,
    TaskSummary,
)

router = APIRouter(prefix="/api")


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _record_to_dict(r: RecordRow) -> dict:
    return {
        "idx": r.idx,
        "step": r.step,
        "status": r.status,
        "ttft_ms": r.ttft_ms,
        "e2e_ms": r.e2e_ms,
        "tpot_ms": r.tpot_ms,
        "output_tokens": r.output_tokens,
        "input_tokens": r.input_tokens,
        "tok_per_s": r.tok_per_s,
        "itl_p50_ms": r.itl_p50_ms,
        "error_class": r.error_class,
        "error": r.error,
        "t_start": r.t_start,
        "t_end": r.t_end,
    }


def _row_to_summary(row: TaskRow) -> TaskSummary:
    cfg = TaskConfig.model_validate_json(row.config_json)
    return TaskSummary(
        id=row.id,
        name=row.name,
        protocol=row.protocol,
        base_url=row.base_url,
        model=row.model,
        status=row.status,
        error=row.error or "",
        created_at=_iso(row.created_at) or "",
        started_at=_iso(row.started_at),
        finished_at=_iso(row.finished_at),
        config=cfg.model_copy(update={"api_key": ""}),
        summary=json.loads(row.summary_json or "{}"),
        steps=json.loads(row.steps_json or "[]"),
        analysis=json.loads(row.analysis_json or "{}"),
    )


@router.post("/tasks", response_model=TaskSummary)
async def create_task(body: TaskCreate) -> TaskSummary:
    cfg = body.config
    if not cfg.model:
        raise HTTPException(400, "model is required")
    if cfg.mode == "step" and not cfg.step_levels:
        raise HTTPException(400, "step_levels is required for step mode")

    stored = cfg.model_dump()
    stored["api_key"] = ""
    row = TaskRow(
        name=body.name or f"{cfg.model} · {cfg.protocol}",
        protocol=cfg.protocol,
        base_url=cfg.base_url,
        model=cfg.model,
        api_key_enc=encrypt(cfg.api_key),
        config_json=json.dumps(stored, ensure_ascii=False),
        status="pending",
    )
    async with SessionLocal() as session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
    await manager.start(row.id)
    async with SessionLocal() as session:
        fresh = await session.get(TaskRow, row.id)
    assert fresh is not None
    return _row_to_summary(fresh)


@router.get("/tasks", response_model=list[TaskSummary])
async def list_tasks(limit: int = 100, offset: int = 0) -> list[TaskSummary]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(TaskRow)
            .order_by(desc(TaskRow.created_at))
            .limit(min(limit, 500))
            .offset(max(offset, 0))
        )
        rows = result.scalars().all()
    return [_row_to_summary(r) for r in rows]


@router.get("/tasks/{task_id}", response_model=TaskDetail)
async def get_task(task_id: str) -> TaskDetail:
    async with SessionLocal() as session:
        row = await session.get(TaskRow, task_id)
        if row is None:
            raise HTTPException(404, "task not found")
        result = await session.execute(
            select(RecordRow).where(RecordRow.task_id == task_id).order_by(RecordRow.idx)
        )
        db_records = result.scalars().all()

    rt = manager.get(task_id)
    if rt is not None and len(rt.records) >= len(db_records):
        records = [RecordOut(**r.as_dict()) for r in rt.records]
        steps = rt.steps
        summary = rt.final_snapshot or rt.aggregator.snapshot()
        analysis = rt.analysis or json.loads(row.analysis_json or "{}")
        status = rt.status
        error = rt.error
    else:
        records = [RecordOut(**_record_to_dict(r)) for r in db_records]
        steps = json.loads(row.steps_json or "[]")
        summary = json.loads(row.summary_json or "{}")
        analysis = json.loads(row.analysis_json or "{}")
        status = row.status
        error = row.error

    base = _row_to_summary(row)
    return TaskDetail(
        **base.model_dump(exclude={"summary", "steps", "status", "error", "analysis"}),
        status=status,
        error=error,
        summary=summary,
        steps=steps,
        analysis=analysis,
        records=records,
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> dict:
    if manager.get(task_id) is None:
        async with SessionLocal() as session:
            row = await session.get(TaskRow, task_id)
            if row is None:
                raise HTTPException(404, "task not found")
            if row.status not in TERMINAL_STATUSES:
                row.status = "cancelled"
                row.finished_at = datetime.now(timezone.utc)
                await session.commit()
        return {"ok": True}
    return {"ok": manager.cancel(task_id)}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str) -> dict:
    rt = manager.get(task_id)
    if rt is not None and not rt.finished:
        raise HTTPException(409, "task is running, cancel it first")
    async with SessionLocal() as session:
        row = await session.get(TaskRow, task_id)
        if row is None:
            raise HTTPException(404, "task not found")
        await session.execute(delete(RecordRow).where(RecordRow.task_id == task_id))
        await session.delete(row)
        await session.commit()
    return {"ok": True}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/tasks/{task_id}/events")
async def task_events(task_id: str) -> StreamingResponse:
    async with SessionLocal() as session:
        row = await session.get(TaskRow, task_id)
        if row is None:
            raise HTTPException(404, "task not found")

    async def gen():
        q, rt = manager.subscribe(task_id)
        try:
            if rt is None:
                async with SessionLocal() as session:
                    result = await session.execute(
                        select(RecordRow)
                        .where(RecordRow.task_id == task_id)
                        .order_by(RecordRow.idx)
                    )
                    db_records = result.scalars().all()
                records = [_record_to_dict(r) for r in db_records]
                cfg_total = json.loads(row.summary_json or "{}").get("planned") or len(
                    records
                )
                agg = aggregate_records(records, planned=int(cfg_total))
                analysis = json.loads(row.analysis_json or "{}")
                yield _sse({"type": "records", "data": records})
                yield _sse({"type": "steps", "data": json.loads(row.steps_json or "[]")})
                if analysis:
                    yield _sse({"type": "analysis", "data": analysis})
                yield _sse(
                    {
                        "type": "snapshot",
                        "data": {
                            **(json.loads(row.summary_json or "{}") or agg.snapshot()),
                            "current_step": None,
                        },
                    }
                )
                yield _sse({"type": "status", "data": {"status": row.status, "error": row.error}})
                return

            yield _sse({"type": "records", "data": [r.as_dict() for r in rt.records]})
            yield _sse({"type": "steps", "data": rt.steps})
            if rt.analysis:
                yield _sse({"type": "analysis", "data": rt.analysis})
            yield _sse(rt.snapshot_event())
            yield _sse({"type": "status", "data": {"status": rt.status, "error": rt.error}})
            if rt.finished:
                return
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield _sse(event)
                if event.get("type") == "status" and event.get("data", {}).get(
                    "status"
                ) in TERMINAL_STATUSES:
                    break
        finally:
            manager.unsubscribe(task_id, q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/presets", response_model=list[PresetOut])
async def list_presets() -> list[PresetOut]:
    async with SessionLocal() as session:
        rows = (await session.execute(select(PresetRow).order_by(PresetRow.name))).scalars().all()
    return [
        PresetOut(
            id=r.id,
            name=r.name,
            config=TaskConfig.model_validate_json(r.config_json),
        )
        for r in rows
    ]


@router.post("/presets", response_model=PresetOut)
async def save_preset(body: PresetIn) -> PresetOut:
    dump = body.config.model_dump()
    dump["api_key"] = ""
    cfg_json = json.dumps(dump, ensure_ascii=False)
    async with SessionLocal() as session:
        existing = (
            await session.execute(select(PresetRow).where(PresetRow.name == body.name))
        ).scalar_one_or_none()
        if existing:
            existing.config_json = cfg_json
            preset_id = existing.id
        else:
            row = PresetRow(name=body.name, config_json=cfg_json)
            session.add(row)
            await session.flush()
            preset_id = row.id
        await session.commit()
    return PresetOut(id=preset_id, name=body.name, config=TaskConfig.model_validate_json(cfg_json))


@router.delete("/presets/{preset_id}")
async def delete_preset(preset_id: str) -> dict:
    async with SessionLocal() as session:
        result = await session.execute(delete(PresetRow).where(PresetRow.id == preset_id))
        if result.rowcount == 0:
            raise HTTPException(404, "preset not found")
        await session.commit()
    return {"ok": True}


@router.post("/probe", response_model=ProbeResult)
async def probe(body: ProbeRequest) -> ProbeResult:
    from time import perf_counter

    if not body.model:
        return ProbeResult(ok=False, error="model is required")
    ttft_ms = None
    total_ms = None
    text = ""
    try:
        async with httpx.AsyncClient() as client:
            provider = create_provider(
                body.protocol, body.base_url, body.api_key, body.model, client
            )
            t0 = perf_counter()
            first = None
            async for chunk in provider.stream(
                "Reply with a single word: pong", max_tokens=16, timeout=30.0
            ):
                if first is None:
                    first = perf_counter()
                if chunk.text:
                    text += chunk.text
            t1 = perf_counter()
            ttft_ms = round((first - t0) * 1000, 2) if first else None
            total_ms = round((t1 - t0) * 1000, 2)
        return ProbeResult(ok=True, ttft_ms=ttft_ms, latency_ms=total_ms, text=text[:200])
    except ProviderError as exc:
        return ProbeResult(ok=False, error=str(exc)[:500])
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(ok=False, error=f"{type(exc).__name__}: {exc}"[:500])


@router.post("/models", response_model=ModelListResult)
async def list_models(body: ProbeRequest) -> ModelListResult:
    try:
        async with httpx.AsyncClient() as client:
            provider = create_provider(
                body.protocol, body.base_url, body.api_key, body.model or "", client
            )
            models = await asyncio.wait_for(provider.list_models(), timeout=20.0)
        return ModelListResult(ok=True, models=list(dict.fromkeys(models)))
    except ProviderError as exc:
        return ModelListResult(ok=False, error=str(exc)[:500])
    except Exception as exc:  # noqa: BLE001
        return ModelListResult(ok=False, error=f"{type(exc).__name__}: {exc}"[:500])


@router.get("/samples")
async def samples() -> dict:
    return {"text": SAMPLE_QUESTIONS, "vision": VISION_QUESTIONS}


def _image_out(row: ImageRow) -> ImageOut:
    return ImageOut(
        id=row.id,
        name=row.name or "上传图片",
        source=row.source or "upload",
        mime=row.mime or "image/jpeg",
        url=f"/api/images/{row.id}/raw",
        credit="",
        size=len(row.data or b""),
    )


@router.get("/images", response_model=list[ImageOut])
async def list_images() -> list[ImageOut]:
    out = [ImageOut(**m) for m in list_builtin_images()]
    async with SessionLocal() as session:
        result = await session.execute(
            select(ImageRow).order_by(desc(ImageRow.created_at))
        )
        rows = result.scalars().all()
    out.extend(_image_out(r) for r in rows)
    return out


@router.get("/images/{image_id}/raw")
async def get_image_raw(image_id: str) -> Response:
    if image_id.startswith("builtin:"):
        got = get_builtin_image(image_id)
        if got is None:
            raise HTTPException(404, "image not found")
        data, mime = got
    else:
        async with SessionLocal() as session:
            row = await session.get(ImageRow, image_id)
        if row is None:
            raise HTTPException(404, "image not found")
        data, mime = row.data, row.mime or "image/jpeg"
    return Response(
        content=data,
        media_type=mime,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/images", response_model=ImageOut)
async def upload_image(body: ImageIn) -> ImageOut:
    try:
        raw = base64.b64decode(body.data_base64, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, "invalid base64 image data") from exc
    if not raw:
        raise HTTPException(400, "empty image data")
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(413, "image too large (max 8 MB)")
    mime = (body.mime or "image/jpeg").strip().lower()
    if not mime.startswith("image/"):
        raise HTTPException(400, "only image uploads are allowed")
    row = ImageRow(
        name=(body.name or "上传图片")[:200], mime=mime, data=raw, source="upload"
    )
    async with SessionLocal() as session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return _image_out(row)


@router.delete("/images/{image_id}")
async def delete_image(image_id: str) -> dict:
    if image_id.startswith("builtin:"):
        raise HTTPException(400, "builtin images cannot be deleted")
    async with SessionLocal() as session:
        result = await session.execute(
            delete(ImageRow).where(ImageRow.id == image_id)
        )
        if result.rowcount == 0:
            raise HTTPException(404, "image not found")
        await session.commit()
    return {"ok": True}


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}
