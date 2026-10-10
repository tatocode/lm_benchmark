import json

import httpx

from llm_benchmark.providers import create_provider

OPENAI_SSE = "\n".join(
    [
        'data: {"choices":[{"delta":{"content":"Hel"}}]}',
        'data: {"choices":[{"delta":{"content":"lo"}}]}',
        'data: {"choices":[{"delta":{}}],"usage":{"prompt_tokens":10,"completion_tokens":2}}',
        "data: [DONE]",
        "",
    ]
)

ANTHROPIC_SSE = "\n".join(
    [
        'data: {"type":"message_start","message":{"usage":{"input_tokens":10}}}',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hi "}}',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"there"}}',
        'data: {"type":"message_delta","usage":{"output_tokens":3}}',
        'data: {"type":"message_stop"}',
        "",
    ]
)

GEMINI_SSE = "\n".join(
    [
        'data: {"candidates":[{"content":{"role":"model","parts":[{"text":"A"}]}}],"usageMetadata":{"promptTokenCount":8,"candidatesTokenCount":1}}',
        'data: {"candidates":[{"content":{"role":"model","parts":[{"text":"B"}]}}],"usageMetadata":{"promptTokenCount":8,"candidatesTokenCount":2}}',
        "",
    ]
)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _collect(provider) -> list:
    chunks = []
    async for chunk in provider.stream("hello", 32, 10.0):
        chunks.append(chunk)
    return chunks


async def test_openai_stream_parsing():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        body = json.loads(request.content)
        seen["stream"] = body.get("stream")
        seen["usage_flag"] = body.get("stream_options")
        return httpx.Response(200, text=OPENAI_SSE, headers={"content-type": "text/event-stream"})

    async with _client(handler) as client:
        provider = create_provider("openai", "https://api.example.com/v1", "sk-test", "m1", client)
        chunks = await _collect(provider)

    text = "".join(c.text for c in chunks if c.text)
    usage = next((c.usage for c in chunks if c.usage), None)
    assert seen["path"] == "/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["stream"] is True
    assert seen["usage_flag"] == {"include_usage": True}
    assert text == "Hello"
    assert usage and usage.completion_tokens == 2 and usage.prompt_tokens == 10


async def test_anthropic_stream_parsing():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("x-api-key")
        seen["version"] = request.headers.get("anthropic-version")
        return httpx.Response(
            200, text=ANTHROPIC_SSE, headers={"content-type": "text/event-stream"}
        )

    async with _client(handler) as client:
        provider = create_provider("anthropic", "", "sk-ant", "m2", client)
        chunks = await _collect(provider)

    text = "".join(c.text for c in chunks if c.text)
    usage = next((c.usage for c in chunks if c.usage), None)
    assert seen["path"] == "/v1/messages"
    assert seen["key"] == "sk-ant"
    assert seen["version"] == "2023-06-01"
    assert text == "Hi there"
    assert usage and usage.completion_tokens == 3 and usage.prompt_tokens == 10


async def test_gemini_stream_parsing():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["alt"] = request.url.params.get("alt")
        seen["key"] = request.url.params.get("key")
        return httpx.Response(
            200, text=GEMINI_SSE, headers={"content-type": "text/event-stream"}
        )

    async with _client(handler) as client:
        provider = create_provider("gemini", "", "g-key", "gemini-2.0-flash", client)
        chunks = await _collect(provider)

    text = "".join(c.text for c in chunks if c.text)
    usage = next((c.usage for c in chunks if c.usage), None)
    assert "streamGenerateContent" in seen["path"]
    assert seen["alt"] == "sse"
    assert seen["key"] == "g-key"
    assert text == "AB"
    assert usage and usage.completion_tokens == 2 and usage.prompt_tokens == 8


async def test_openai_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text='{"error":"rate limited"}')

    from llm_benchmark.providers import ProviderError

    async with _client(handler) as client:
        provider = create_provider("openai", "https://x/v1", "k", "m", client)
        try:
            await _collect(provider)
            raised = False
        except ProviderError as exc:
            raised = True
            assert "429" in str(exc)
    assert raised


async def test_openai_list_models():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={"data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4o"}]},
        )

    async with _client(handler) as client:
        provider = create_provider("openai", "https://api.example.com/v1", "sk-k", "", client)
        models = await provider.list_models()

    assert seen["path"] == "/v1/models"
    assert seen["auth"] == "Bearer sk-k"
    assert models == ["gpt-4o-mini", "gpt-4o"]


async def test_anthropic_list_models():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json={"data": [{"id": "claude-3-5-sonnet"}]})

    async with _client(handler) as client:
        provider = create_provider("anthropic", "https://api.anthropic.com", "sk-ant", "", client)
        models = await provider.list_models()

    assert seen["path"] == "/v1/models"
    assert seen["key"] == "sk-ant"
    assert models == ["claude-3-5-sonnet"]


async def test_gemini_list_models():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.url.params.get("key")
        return httpx.Response(
            200,
            json={"models": [{"name": "models/gemini-2.0-flash"}, {"name": "models/gemini-2.5-pro"}]},
        )

    async with _client(handler) as client:
        provider = create_provider("gemini", "https://generativelanguage.googleapis.com", "g-key", "", client)
        models = await provider.list_models()

    assert seen["path"] == "/v1beta/models"
    assert seen["key"] == "g-key"
    assert models == ["gemini-2.0-flash", "gemini-2.5-pro"]
