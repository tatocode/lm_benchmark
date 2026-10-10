from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import DB_URL

engine = create_async_engine(DB_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


_ADD_COLUMNS: dict[str, list[str]] = {
    "tasks": [
        "analysis_json TEXT DEFAULT '{}'",
    ],
    "records": [
        "input_tokens INTEGER DEFAULT 0",
        "error_class VARCHAR(20) DEFAULT 'ok'",
        "itl_p50_ms FLOAT",
    ],
}


async def _migrate_missing_columns(conn) -> None:
    from sqlalchemy import inspect as sa_inspect

    def _sync(sync_conn) -> None:
        inspector = sa_inspect(sync_conn)
        for table, statements in _ADD_COLUMNS.items():
            try:
                cols = {c["name"] for c in inspector.get_columns(table)}
            except Exception:
                continue
            for stmt in statements:
                col_name = stmt.split(" ", 1)[0]
                if col_name not in cols:
                    sync_conn.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {stmt}"
                    )

    await conn.run_sync(_sync)


async def init_db() -> None:
    from . import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # SQLite 的 DDL 执行后会被隐式提交，这里单独 connect 执行，无需显式 commit
    async with engine.connect() as conn:
        await _migrate_missing_columns(conn)


async def dispose_db() -> None:
    await engine.dispose()
