import json
from typing import AsyncIterator
from urllib.parse import quote

import httpx

from .base import BaseProvider, ProviderError, StreamChunk, Usage


class GeminiProvider(BaseProvider):
    protocol = "gemini"

    async def stream(
        self,
        prompt: str,
        max_tokens: int,
        timeout: float,
        image_b64: str | None = None,
        image_mime: str = "image/png",
    ) -> AsyncIterator[StreamChunk]:
        base = self.base_url or "https://generativelanguage.googleapis.com"
        model_part = quote(self.model, safe="")
        url = f"{base}/v1beta/models/{model_part}:streamGenerateContent"
        params = {"alt": "sse"}
        if self.api_key:
            params["key"] = self.api_key

        parts: list[dict] = [{"text": prompt}]
        if image_b64:
            parts.append(
                {"inline_data": {"mime_type": image_mime, "data": image_b64}}
            )

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        headers = {"Content-Type": "application/json"}

        http_timeout = httpx.Timeout(
            connect=15.0, read=timeout, write=30.0, pool=15.0
        )
        usage: Usage | None = None
        try:
            async with self.client.stream(
                "POST",
                url,
                params=params,
                json=payload,
                headers=headers,
                timeout=http_timeout,
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
                    if obj.get("error"):
                        raise ProviderError(str(obj["error"])[:500])
                    meta = obj.get("usageMetadata") or {}
                    if meta.get("candidatesTokenCount") is not None:
                        usage = Usage(
                            prompt_tokens=meta.get("promptTokenCount"),
                            completion_tokens=meta.get("candidatesTokenCount"),
                        )
                    cands = obj.get("candidates") or []
                    if not cands:
                        continue
                    for part in (cands[0].get("content") or {}).get("parts") or []:
                        text = part.get("text")
                        if text and not part.get("thought"):
                            yield StreamChunk(text=text)
        except httpx.HTTPError as exc:
            raise ProviderError(f"{type(exc).__name__}: {exc}") from exc
        if usage:
            yield StreamChunk(usage=usage)

    async def list_models(self) -> list[str]:
        base = self.base_url or "https://generativelanguage.googleapis.com"
        params: dict[str, str] = {}
        if self.api_key:
            params["key"] = self.api_key
        try:
            response = await self.client.get(
                f"{base}/v1beta/models",
                params=params,
                timeout=httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=10.0),
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"{type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise ProviderError(await self._read_error(response))
        data = response.json()
        return [
            str(m.get("name", "")).removeprefix("models/")
            for m in data.get("models", [])
            if m.get("name")
        ]
