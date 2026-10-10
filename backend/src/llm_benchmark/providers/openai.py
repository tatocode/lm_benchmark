import json
from typing import AsyncIterator

import httpx

from .base import BaseProvider, ProviderError, StreamChunk, Usage


class OpenAIProvider(BaseProvider):
    protocol = "openai"

    async def stream(
        self,
        prompt: str,
        max_tokens: int,
        timeout: float,
        image_b64: str | None = None,
        image_mime: str = "image/png",
    ) -> AsyncIterator[StreamChunk]:
        base = self.base_url or "https://api.openai.com/v1"
        url = f"{base}/chat/completions"

        content: list[dict] = [{"type": "text", "text": prompt}]
        if image_b64:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image_mime};base64,{image_b64}"},
                }
            )

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        http_timeout = httpx.Timeout(
            connect=15.0, read=timeout, write=30.0, pool=15.0
        )
        usage: Usage | None = None
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
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("usage"):
                        u = obj["usage"]
                        usage = Usage(
                            prompt_tokens=u.get("prompt_tokens"),
                            completion_tokens=u.get("completion_tokens"),
                        )
                    if obj.get("error"):
                        raise ProviderError(str(obj["error"])[:500])
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    text = delta.get("content")
                    if text:
                        yield StreamChunk(text=text)
        except httpx.HTTPError as exc:
            raise ProviderError(f"{type(exc).__name__}: {exc}") from exc
        if usage:
            yield StreamChunk(usage=usage)

    async def list_models(self) -> list[str]:
        base = self.base_url or "https://api.openai.com/v1"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            response = await self.client.get(
                f"{base}/models",
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
