"""DeepSeek API 客户端封装（httpx 直连，避免 Windows 上 AsyncOpenAI 挂起）。

支持：
- JSON 输出（response_format）
- 流式输出（SSE）
- 重试机制（指数退避，最多 3 次）
"""
import asyncio
import json
import logging
from typing import AsyncGenerator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class DeepSeekClient:
    def __init__(self):
        self.api_key = settings.deepseek_api_key or "DEMO_KEY"
        self.base_url = settings.deepseek_base_url.rstrip("/")
        self.model = settings.deepseek_model
        self.timeout = float(settings.llm_timeout_seconds)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _chat_completion(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            resp = await http.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code == 429:
                raise httpx.HTTPStatusError(
                    "rate limited",
                    request=resp.request,
                    response=resp,
                )
            resp.raise_for_status()
            return resp.json()

    async def chat_json(
        self,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict:
        """单次调用，强制返回 JSON 对象。"""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens or settings.llm_max_tokens,
            "temperature": temperature if temperature is not None else settings.llm_temperature,
        }
        content = "{}"
        for attempt in range(3):
            try:
                data = await self._chat_completion(payload)
                content = data["choices"][0]["message"]["content"] or "{}"
                return json.loads(content)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < 2:
                    wait = 2 ** attempt
                    logger.warning(f"Rate limited, retry in {wait}s")
                    await asyncio.sleep(wait)
                    continue
                logger.error(f"API error attempt {attempt}: {e}")
                if attempt == 2:
                    raise
                await asyncio.sleep(1)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode failed: {e}, content={content[:200]}")
                if attempt == 2:
                    raise
        return {}

    async def chat_messages_json(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict:
        """多轮 messages，强制 JSON 对象输出（Agent 规划用）。"""
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens or settings.llm_max_tokens,
            "temperature": temperature if temperature is not None else settings.llm_temperature,
        }
        content = "{}"
        for attempt in range(3):
            try:
                data = await self._chat_completion(payload)
                content = data["choices"][0]["message"]["content"] or "{}"
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode failed: {e}, content={content[:200]}")
                if attempt == 2:
                    raise
        return {}

    async def chat_text(
        self,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """单次调用，返回文本。"""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens or settings.llm_max_tokens,
            "temperature": temperature if temperature is not None else settings.llm_temperature,
        }
        data = await self._chat_completion(payload)
        return data["choices"][0]["message"]["content"] or ""

    async def chat_stream(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式输出，按 token 逐块返回（用于聊天 SSE）。"""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or settings.llm_max_tokens,
            "temperature": temperature if temperature is not None else settings.llm_temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            async with http.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}).get("content")
                    if delta:
                        yield delta


client = DeepSeekClient()
