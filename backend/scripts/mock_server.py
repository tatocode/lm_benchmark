"""OpenAI / Anthropic / Gemini 兼容的流式 mock 服务，供本地联调与测试使用。
启动: uv run python scripts/mock_server.py [--port 8765] [--ttft 0.05] [--tpot 0.01] [--tokens 20]
"""

import argparse
import asyncio
import json
import random
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

app = FastAPI()

TTFT = 0.05
TPOT = 0.01
TOKENS = 20
ERROR_RATE = 0.0


@app.post("/mock/config")
async def mock_config(request: Request) -> dict:
    global TTFT, TPOT, TOKENS, ERROR_RATE
    body = await request.json()
    if "ttft" in body:
        TTFT = float(body["ttft"])
    if "tpot" in body:
        TPOT = float(body["tpot"])
    if "tokens" in body:
        TOKENS = int(body["tokens"])
    if "error_rate" in body:
        ERROR_RATE = float(body["error_rate"])
    return {"ttft": TTFT, "tpot": TPOT, "tokens": TOKENS, "error_rate": ERROR_RATE}


def _maybe_inject_error() -> Response | None:
    if ERROR_RATE > 0 and random.random() < ERROR_RATE:
        return JSONResponse(
            status_code=503,
            content={"error": {"message": "mock injected failure"}},
        )
    return None


async def _text_chunks() -> AsyncIterator[str]:
    await asyncio.sleep(TTFT)
    for i in range(TOKENS):
        yield f"tok{i} "
        await asyncio.sleep(TPOT)


@app.post("/v1/chat/completions")
async def openai_chat(request: Request) -> Response:
    await request.json()
    injected = _maybe_inject_error()
    if injected is not None:
        return injected

    async def gen() -> AsyncIterator[str]:
        parts = []
        async for piece in _text_chunks():
            parts.append(piece)
            yield f"data: {json.dumps({'choices': [{'delta': {'content': piece}}]})}\n\n"
        usage = {
            "prompt_tokens": 16,
            "completion_tokens": len(parts),
            "total_tokens": 16 + len(parts),
        }
        yield f"data: {json.dumps({'choices': [{'delta': {}}], 'usage': usage})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/v1/messages")
async def anthropic_messages(request: Request) -> Response:
    await request.json()
    injected = _maybe_inject_error()
    if injected is not None:
        return injected

    async def gen() -> AsyncIterator[str]:
        yield f"data: {json.dumps({'type': 'message_start', 'message': {'usage': {'input_tokens': 16}}})}\n\n"
        n = 0
        async for piece in _text_chunks():
            n += 1
            yield f"data: {json.dumps({'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': piece}})}\n\n"
        yield f"data: {json.dumps({'type': 'message_delta', 'usage': {'output_tokens': n}})}\n\n"
        yield f"data: {json.dumps({'type': 'message_stop'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/v1beta/models/{model_path:path}")
async def gemini_stream(model_path: str, request: Request) -> Response:
    await request.json()
    injected = _maybe_inject_error()
    if injected is not None:
        return injected

    async def gen() -> AsyncIterator[str]:
        n = 0
        async for piece in _text_chunks():
            n += 1
            payload = {
                "candidates": [
                    {"content": {"role": "model", "parts": [{"text": piece}]}}
                ],
                "usageMetadata": {
                    "promptTokenCount": 16,
                    "candidatesTokenCount": n,
                },
            }
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/v1/models")
async def models_list(request: Request) -> dict:
    if request.headers.get("x-api-key"):
        return {"data": [{"id": "mock-claude"}]}
    return {"data": [{"id": "mock-gpt"}, {"id": "mock-gpt-mini"}]}


@app.get("/v1beta/models")
async def gemini_models(request: Request) -> dict:
    return {"models": [{"name": "models/mock-gemini"}]}


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--ttft", type=float, default=0.05)
    parser.add_argument("--tpot", type=float, default=0.01)
    parser.add_argument("--tokens", type=int, default=20)
    parser.add_argument("--error-rate", type=float, default=0.0)
    args = parser.parse_args()

    global TTFT, TPOT, TOKENS, ERROR_RATE
    TTFT, TPOT, TOKENS = args.ttft, args.tpot, args.tokens
    ERROR_RATE = args.error_rate

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
