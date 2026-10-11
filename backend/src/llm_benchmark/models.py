import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), default="")
    protocol: Mapped[str] = mapped_column(String(20))
    base_url: Mapped[str] = mapped_column(String(500))
    model: Mapped[str] = mapped_column(String(200))
    api_key_enc: Mapped[str] = mapped_column(Text, default="")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    summary_json: Mapped[str] = mapped_column(Text, default="{}")
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    analysis_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    records: Mapped[list["RecordRow"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="selectin"
    )


class RecordRow(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    idx: Mapped[int] = mapped_column(Integer)
    step: Mapped[int] = mapped_column(Integer, default=-1)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    ttft_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    e2e_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    tpot_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    tok_per_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    itl_p50_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_class: Mapped[str] = mapped_column(String(20), default="ok")
    error: Mapped[str] = mapped_column(Text, default="")
    t_start: Mapped[float] = mapped_column(Float, default=0.0)
    t_end: Mapped[float] = mapped_column(Float, default=0.0)

    task: Mapped[TaskRow] = relationship(back_populates="records")


class PresetRow(Base):
    __tablename__ = "presets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ImageRow(Base):
    """用户上传的视觉测试图片（内置图片以文件形式随程序分发）。"""

    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), default="")
    mime: Mapped[str] = mapped_column(String(60), default="image/jpeg")
    data: Mapped[bytes] = mapped_column(LargeBinary)
    source: Mapped[str] = mapped_column(String(20), default="upload")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
