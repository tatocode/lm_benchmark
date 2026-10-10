from typing import Literal

from pydantic import BaseModel, Field

Protocol = Literal["openai", "anthropic", "gemini"]
Mode = Literal["fixed", "step", "open"]


class TaskConfig(BaseModel):
    protocol: Protocol = "openai"
    base_url: str = ""
    api_key: str = ""
    model: str = ""

    mode: Mode = "fixed"
    concurrency: int = Field(default=4, ge=1, le=512)
    total_requests: int = Field(default=20, ge=1, le=10000)
    step_levels: list[int] = Field(default=[1, 2, 4, 8, 16], min_length=1, max_length=12)
    step_requests: int = Field(default=10, ge=1, le=10000)

    arrival_rate: float = Field(default=1.0, ge=0.01, le=10000.0)
    fixed_duration_s: float = Field(default=0.0, ge=0.0, le=86400.0)
    step_duration_s: float = Field(default=0.0, ge=0.0, le=86400.0)
    auto_stop: bool = True

    sla_ttft_p95_s: float = Field(default=2.0, ge=0.1, le=3600.0)
    sla_e2e_p95_s: float = Field(default=15.0, ge=0.1, le=3600.0)
    sla_error_rate: float = Field(default=0.005, ge=0.0, le=1.0)

    input_tokens: int = Field(default=256, ge=1, le=200000)
    max_output_tokens: int = Field(default=256, ge=1, le=32000)
    timeout: float = Field(default=120.0, ge=1.0, le=3600.0)
    with_image: bool = False
    image_id: str = Field(default="", max_length=64)
    questions: list[str] = Field(default_factory=list, max_length=500)


class TaskCreate(BaseModel):
    name: str = ""
    config: TaskConfig


class TaskSummary(BaseModel):
    id: str
    name: str
    protocol: str
    base_url: str
    model: str
    status: str
    error: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    config: TaskConfig
    summary: dict
    steps: list[dict]
    analysis: dict = {}


class RecordOut(BaseModel):
    idx: int
    step: int
    status: str
    ttft_ms: float | None
    e2e_ms: float | None
    tpot_ms: float | None
    output_tokens: int
    input_tokens: int = 0
    tok_per_s: float | None
    itl_p50_ms: float | None = None
    error_class: str = "ok"
    error: str
    t_start: float
    t_end: float


class TaskDetail(TaskSummary):
    records: list[RecordOut] = []


class PresetIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    config: TaskConfig


class PresetOut(BaseModel):
    id: str
    name: str
    config: TaskConfig


class ProbeRequest(BaseModel):
    protocol: Protocol = "openai"
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class ProbeResult(BaseModel):
    ok: bool
    ttft_ms: float | None = None
    latency_ms: float | None = None
    error: str = ""
    text: str = ""


class ModelListResult(BaseModel):
    ok: bool
    models: list[str] = []
    error: str = ""


class ImageIn(BaseModel):
    name: str = Field(default="", max_length=200)
    mime: str = Field(default="image/jpeg", max_length=60)
    data_base64: str = Field(min_length=1)


class ImageOut(BaseModel):
    id: str
    name: str
    source: str
    mime: str
    url: str
    credit: str = ""
    size: int = 0
