from dataclasses import dataclass
from typing import AsyncIterator

import httpx


class ProviderError(Exception):
    def __init__(self, message: str = "", status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class Usage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass
class StreamChunk:
    text: str = ""
    usage: Usage | None = None


class BaseProvider:
    protocol: str = ""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        client: httpx.AsyncClient,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = client

    async def stream(
        self,
        prompt: str,
        max_tokens: int,
        timeout: float,
        image_b64: str | None = None,
        image_mime: str = "image/png",
    ) -> AsyncIterator[StreamChunk]:
        raise NotImplementedError

    async def list_models(self) -> list[str]:
        raise NotImplementedError

    async def _read_error(self, response: httpx.Response) -> str:
        try:
            body = (await response.aread()).decode(errors="replace")[:500]
        except Exception:
            body = ""
        return f"HTTP {response.status_code}: {body}"


def create_provider(
    protocol: str,
    base_url: str,
    api_key: str,
    model: str,
    client: httpx.AsyncClient,
) -> BaseProvider:
    from ..config import resolve_endpoint

    base_url = resolve_endpoint(base_url)
    from .anthropic import AnthropicProvider
    from .gemini import GeminiProvider
    from .openai import OpenAIProvider

    providers: dict[str, type[BaseProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
    }
    cls = providers.get(protocol)
    if cls is None:
        raise ProviderError(f"unsupported protocol: {protocol}")
    return cls(base_url, api_key, model, client)
