"""LLM 客户端：配置缺失与重试行为。"""
import httpx
import pytest

import app.services.llm_client as llm
from app.services.llm_client import DeepSeekClient, LLMNotConfiguredError, LLMUpstreamError


def _ok_response(content: str = "ok") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "deepseek-chat",
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        },
    )


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """重试等待不应拖慢测试。"""
    monkeypatch.setattr(llm, "_backoff", lambda attempt: 0)


@pytest.mark.asyncio
async def test_missing_key_raises_clear_error():
    client = DeepSeekClient(api_key="")
    assert client.configured is False
    with pytest.raises(LLMNotConfiguredError, match="DEEPSEEK_API_KEY"):
        await client.chat_text("system", "user")


@pytest.mark.asyncio
async def test_retries_on_503_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"error": "busy"})
        return _ok_response("retried")

    client = DeepSeekClient(api_key="test-key", max_retries=3)
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        assert await client.chat_text("s", "u") == "retried"
    finally:
        await client.aclose()
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_401_maps_to_friendly_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid key"})

    client = DeepSeekClient(api_key="bad-key", max_retries=2)
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMUpstreamError, match="鉴权失败"):
            await client.chat_text("s", "u")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_chat_json_rejects_invalid_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response("not-json")

    client = DeepSeekClient(api_key="test-key", max_retries=2)
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMUpstreamError, match="JSON"):
            await client.chat_json("s", "u")
    finally:
        await client.aclose()
