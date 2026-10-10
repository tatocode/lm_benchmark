# ---------- Stage 1: build frontend ----------
# node:20-alpine / uv 运行时镜像均为多架构（linux/amd64 + arm64/v8），
# 可在 Windows / macOS（含 Apple Silicon）/ Linux 上直接构建与运行。
FROM node:20-alpine AS fe
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: runtime ----------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY backend/pyproject.toml backend/README.md ./
COPY backend/src ./src
COPY backend/uv.lock ./uv.lock
RUN uv sync --frozen --no-dev

COPY --from=fe /build/frontend/out ./static

ENV LMB_HOST=0.0.0.0 \
    LMB_PORT=8000 \
    LMB_DATA_DIR=/data \
    LMB_STATIC_DIR=/app/static \
    LMB_IN_DOCKER=1

EXPOSE 8000
VOLUME ["/data"]
CMD ["uv", "run", "llm-benchmark"]