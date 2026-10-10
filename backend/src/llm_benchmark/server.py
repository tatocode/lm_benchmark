import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import update

from .api import router
from .config import STATIC_DIR
from .db import SessionLocal, dispose_db, init_db
from .models import TaskRow

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)


async def _mark_interrupted() -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(TaskRow)
            .where(TaskRow.status.in_(["pending", "running"]))
            .values(
                status="interrupted",
                error="service restarted while running",
                finished_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _mark_interrupted()
    yield
    await dispose_db()


app = FastAPI(title="LLM Benchmark", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


def _mount_static(application: FastAPI) -> None:
    if not (STATIC_DIR / "index.html").exists():
        return
    assets_dir = STATIC_DIR / "_next"
    if assets_dir.exists():
        application.mount(
            "/_next", StaticFiles(directory=str(assets_dir)), name="next_assets"
        )

    @application.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        root = STATIC_DIR.resolve()
        candidates: list[Path] = []
        if full_path:
            candidates.append(root / full_path)
            candidates.append(root / full_path / "index.html")
        candidates.append(root / "index.html")
        for cand in candidates:
            try:
                resolved = cand.resolve()
                resolved.relative_to(root)
            except ValueError:
                continue
            if resolved.is_file():
                return FileResponse(resolved)
        return FileResponse(root / "index.html")


_mount_static(app)
