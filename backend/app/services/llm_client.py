"""DeepSeek API 客户端封装（httpx 直连，避免 Windows 上 AsyncOpenAI 挂起）。

支持：
- JSON 输出（response_format）
- 流式输出（SSE）
- 重试机制（指数退避 + 抖动，覆盖 429 / 5xx / 超时）
- 连接复用（进程内共享 AsyncClient）
- 未配置 Key 时抛出 ``LLMNotConfiguredError``，由 API 层转成可读提示
"""
import asyncio
import json
import logging
import random
from typing import AsyncGenerator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 可重试的上游状态码：限流与瞬时故障
_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
_RETRYABLE_EXC = (httpx.TimeoutException, httpx.TransportError)


class LLMNotConfiguredError(RuntimeError):
    """未配置 DEEPSEEK_API_KEY（配置问题，不是上游故障）。"""


class LLMUpstreamError(RuntimeError):
    """LLM 上游返回不可恢复的错误状态。"""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def _backoff(attempt: int) -> float:
    """指数退避 + 抖动，避免多请求同时重试打爆上游。"""
    return min(2**attempt, 8) + random.uniform(0, 0.25)


class DeepSeekClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_retries: int = 3,
    ) -> None:
        # 注意：不再用占位 Key 兜底，否则配置缺失会伪装成 401 上游错误
        self.api_key = (api_key if api_key is not None else settings.deepseek_api_key or "").strip()
        self.base_url = (base_url or settings.deepseek_base_url).rstrip("/")
        self.model = model or settings.deepseek_model
        self.timeout = float(timeout or settings.llm_timeout_seconds)
        self.max_retries = max(1, max_retries)
        self._http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------ 基础
    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _ensure_configured(self) -> None:
        if not self.configured:
            raise LLMNotConfiguredError(
                "未配置 DEEPSEEK_API_KEY，AI 功能不可用。请在 backend/.env 填入 Key 后重启后端。"
            )

    def _http_client(self) -> httpx.AsyncClient:
        """进程内共享连接池；跨请求复用 TCP/TLS。"""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._http

    async def aclose(self) -> None:
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
        self._http = None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _log_usage(self, data: dict) -> None:
        usage = data.get("usage") or {}
        if not usage:
            return
        logger.info(
            "LLM usage model=%s prompt_tokens=%s completion_tokens=%s",
            data.get("model", self.model),
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
        )

    async def _chat_completion(self, payload: dict) -> dict:
        """单次调用 + 重试；返回完整响应 JSON。"""
        self._ensure_configured()
        url = f"{self.base_url}/chat/completions"
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                resp = await self._http_client().post(url, headers=self._headers(), json=payload)
            except _RETRYABLE_EXC as exc:
                last_error = exc
                if attempt == self.max_retries - 1:
                    break
                wait = _backoff(attempt)
                logger.warning("LLM transport error (%s), retry in %.2fs", exc.__class__.__name__, wait)
                await asyncio.sleep(wait)
                continue

            if resp.status_code in _RETRYABLE_STATUS and attempt < self.max_retries - 1:
                wait = _backoff(attempt)
                logger.warning("LLM %s, retry in %.2fs", resp.status_code, wait)
                await asyncio.sleep(wait)
                continue

            if resp.status_code >= 400:
                detail = resp.text[:300]
                if resp.status_code in (401, 403):
                    raise LLMUpstreamError(
                        resp.status_code,
                        "DeepSeek 鉴权失败：请检查 backend/.env 中的 DEEPSEEK_API_KEY 是否有效。",
                    )
                raise LLMUpstreamError(resp.status_code, f"LLM 上游错误 {resp.status_code}: {detail}")

            data = resp.json()
            self._log_usage(data)
            return data

        raise LLMUpstreamError(
            0,
            f"LLM 请求失败（重试 {self.max_retries} 次）：{last_error}",
        )

    def _base_payload(
        self,
        messages: list[dict],
        *,
        max_tokens: int | None,
        temperature: float | None,
        json_mode: bool = False,
    ) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens if max_tokens is not None else settings.llm_max_tokens,
            "temperature": temperature if temperature is not None else settings.llm_temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    # ------------------------------------------------------------------ 公开方法
    async def chat_json(
        self,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict:
        """单次调用，强制返回 JSON 对象。"""
        payload = self._base_payload(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=True,
        )
        content = "{}"
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            data = await self._chat_completion(payload)
            content = data["choices"][0]["message"]["content"] or "{}"
            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                last_error = exc
                logger.error("JSON decode failed (attempt %d): %s, content=%s", attempt + 1, exc, content[:200])
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(_backoff(attempt))
        raise LLMUpstreamError(0, f"模型未返回合法 JSON：{last_error}")

    async def chat_messages_json(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict:
        """多轮 messages，强制 JSON 对象输出（Agent 规划用）。"""
        payload = self._base_payload(
            messages, max_tokens=max_tokens, temperature=temperature, json_mode=True
        )
        content = "{}"
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            data = await self._chat_completion(payload)
            content = data["choices"][0]["message"]["content"] or "{}"
            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                last_error = exc
                logger.error("JSON decode failed (attempt %d): %s, content=%s", attempt + 1, exc, content[:200])
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(_backoff(attempt))
        raise LLMUpstreamError(0, f"模型未返回合法 JSON：{last_error}")

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        tool_choice: str = "auto",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict:
        """带函数调用的单轮请求，返回完整 assistant message（可能含 tool_calls）。

        调用方负责执行 tool_calls、把结果作为 role=tool 消息追加后再次调用，
        形成 tool-calling 循环。
        """
        payload = self._base_payload(messages, max_tokens=max_tokens, temperature=temperature)
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice
        data = await self._chat_completion(payload)
        return data["choices"][0]["message"]

    async def chat_text(
        self,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """单次调用，返回文本。"""
        payload = self._base_payload(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        data = await self._chat_completion(payload)
        return data["choices"][0]["message"]["content"] or ""

    async def chat_stream(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式输出，按 token 逐块返回（用于聊天 SSE）。"""
        self._ensure_configured()
        payload = self._base_payload(messages, max_tokens=max_tokens, temperature=temperature)
        payload["stream"] = True

        async with self._http_client().stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
        ) as resp:
            if resp.status_code >= 400:
                body = (await resp.aread()).decode("utf-8", "ignore")[:300]
                if resp.status_code in (401, 403):
                    raise LLMUpstreamError(
                        resp.status_code,
                        "DeepSeek 鉴权失败：请检查 backend/.env 中的 DEEPSEEK_API_KEY 是否有效。",
                    )
                raise LLMUpstreamError(resp.status_code, f"LLM 上游错误 {resp.status_code}: {body}")

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
