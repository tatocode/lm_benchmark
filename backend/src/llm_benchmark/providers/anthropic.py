import json
from typing import AsyncIterator

import httpx

from .base import BaseProvider, ProviderError, StreamChunk, Usage


class AnthropicProvider(BaseProvider):
    protocol = "anthropic"

    async def stream(
        self,
        prompt: str,
        max_tokens: int,
        timeout: float,
        image_b64: str | None = None,
        image_mime: str = "image/png",
    ) -> AsyncIterator[StreamChunk]:
        base = self.base_url or "https://api.anthropic.com"
        url = f"{base}/v1/messages"

        blocks: list[dict] = [{"type": "text", "text": prompt}]
        if image_b64:
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_mime,
                        "data": image_b64,
                    },
                }
            )

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "stream": True,
            "messages": [{"role": "user", "content": blocks}],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        http_timeout = httpx.Timeout(
            connect=15.0, read=timeout, write=30.0, pool=15.0
        )
        usage: Usage | None = None
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        try:
            async with self.client.stream(
                "POST", url, json=payload, headers=headers, timeout=http_timeout
            ) as response:
                if response.status_code != 200:
                    raise ProviderError(
                        await self._read_error(response), status_code=response.status_code
                    )
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    try:
                        obj = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    etype = obj.get("type")
                    if etype == "error":
                        err = obj.get("error") or {}
                        raise ProviderError(str(err.get("message", err))[:500])
                    if etype == "message_start":
                        msg_usage = (obj.get("message") or {}).get("usage") or {}
                        prompt_tokens = msg_usage.get("input_tokens")
                    elif etype == "content_block_delta":
                        delta = obj.get("delta") or {}
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            yield StreamChunk(text=delta["text"])
                    elif etype == "message_delta":
                        u = obj.get("usage") or {}
                        if u.get("output_tokens") is not None:
                            completion_tokens = u.get("output_tokens")
        except httpx.HTTPError as exc:
            raise ProviderError(f"{type(exc).__name__}: {exc}") from exc
        if prompt_tokens is not None or completion_tokens is not None:
            usage = Usage(
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
            )
            yield StreamChunk(usage=usage)

    async def list_models(self) -> list[str]:
        base = self.base_url or "https://api.anthropic.com"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        try:
            response = await self.client.get(
                f"{base}/v1/models",
                headers=headers,
                timeout=httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=10.0),
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"{type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise ProviderError(await self._read_error(response))
        data = response.json()
        return [
            m["id"]
            for m in data.get("data", [])
            if isinstance(m, dict) and m.get("id")
        ]
