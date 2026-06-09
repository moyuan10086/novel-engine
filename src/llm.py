"""LLM client — OpenAI 兼容协议,带指数退避重试。

只暴露 chat() 一个函数。所有 worker 共用。
默认走流式(--stream)以减少长响应被代理切断的概率。
"""
from __future__ import annotations

import json as _json
import os
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

API_KEY = os.environ.get("OPENAI_API_KEY", "")
API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
MODEL = os.environ.get("MODEL", "gpt-4o-mini")
GROUP = os.environ.get("GROUP", "")  # 部分代理要求(如 aabao 的 "Grok官逆")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "8000"))
TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.85"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "4"))
USE_STREAM = os.environ.get("USE_STREAM", "0") not in ("0", "false", "False", "")


class TransientError(Exception):
    pass


def _is_retryable_status(status: int) -> bool:
    return status == 429 or 500 <= status < 600


async def _chat_nonstream(payload: dict[str, Any], headers: dict[str, str]) -> str:
    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=15.0)) as cli:
        r = await cli.post(f"{API_BASE}/chat/completions", json=payload, headers=headers)
        if _is_retryable_status(r.status_code):
            raise TransientError(f"{r.status_code}: {r.text[:200]}")
        if r.status_code >= 400:
            raise RuntimeError(f"API {r.status_code}: {r.text[:500]}")
        data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"响应格式异常: {data}") from e


async def _chat_stream(payload: dict[str, Any], headers: dict[str, str]) -> str:
    payload = {**payload, "stream": True}
    chunks: list[str] = []
    timeout = httpx.Timeout(300.0, connect=15.0, read=60.0)
    async with httpx.AsyncClient(timeout=timeout) as cli:
        async with cli.stream(
            "POST", f"{API_BASE}/chat/completions", json=payload, headers=headers,
        ) as r:
            if _is_retryable_status(r.status_code):
                body = (await r.aread()).decode("utf-8", "replace")[:200]
                raise TransientError(f"{r.status_code}: {body}")
            if r.status_code >= 400:
                body = (await r.aread()).decode("utf-8", "replace")[:500]
                raise RuntimeError(f"API {r.status_code}: {body}")
            async for line in r.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = _json.loads(data)
                except _json.JSONDecodeError:
                    continue
                try:
                    delta = obj["choices"][0]["delta"].get("content")
                except (KeyError, IndexError):
                    continue
                if delta:
                    chunks.append(delta)
    if not chunks:
        raise TransientError("stream 返回空")
    return "".join(chunks)


@retry(
    reraise=True,
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((TransientError, httpx.TransportError, httpx.ReadTimeout)),
)
async def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    stream: bool | None = None,
) -> str:
    """非流式默认调用,返回完整 assistant 文本。

    stream=True / 环境变量 USE_STREAM=1(默认): 走流式,响应稳定性更好。
    """
    if not API_KEY:
        raise RuntimeError("OPENAI_API_KEY 未设置,检查 .env")

    payload: dict[str, Any] = {
        "model": model or MODEL,
        "messages": messages,
        "temperature": TEMPERATURE if temperature is None else temperature,
        "max_tokens": MAX_TOKENS if max_tokens is None else max_tokens,
    }
    if GROUP:
        payload["group"] = GROUP
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    use_stream = USE_STREAM if stream is None else stream
    if use_stream:
        return await _chat_stream(payload, headers)
    return await _chat_nonstream(payload, headers)

