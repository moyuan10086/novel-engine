"""Anthropic provider — 原生 Claude API（system 放顶层参数）。

需要安装可选依赖: pip install novel-engine[anthropic]
"""
from __future__ import annotations

import os
from typing import Any, AsyncIterator

from ..provider import Provider


class AnthropicProvider(Provider):
    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("API_KEY", "")
        self.model = os.environ.get("MODEL", "claude-sonnet-4-6-20250514")
        self.max_tokens = int(os.environ.get("MAX_TOKENS", "8000"))
        self.temperature = float(os.environ.get("TEMPERATURE", "0.85"))
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise RuntimeError("anthropic 未安装。pip install novel-engine[anthropic]")
        return self._client

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        client = self._get_client()
        model = model or self.model
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens or self.max_tokens

        system_text, user_messages = self._split_system(messages)

        resp = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_text,
            messages=user_messages,
        )
        return resp.content[0].text

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        model = model or self.model
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens or self.max_tokens

        system_text, user_messages = self._split_system(messages)

        async with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_text,
            messages=user_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def count_tokens(self, text: str) -> int:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            return client.count_tokens(text)
        except (ImportError, Exception):
            return max(1, int(len(text) * 0.6))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(
            "Anthropic 暂不提供 embedding API。"
            "请使用 OpenAI-compatible provider 或本地模型进行 embedding。"
        )

    def build_messages(
        self, system: str, user: str
    ) -> list[dict[str, str]] | dict[str, Any]:
        return {
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }

    @staticmethod
    def _split_system(
        messages: list[dict[str, str]],
    ) -> tuple[str, list[dict[str, str]]]:
        """将 OpenAI 格式的 messages 拆分为 system + 非 system 消息。"""
        system_parts = []
        other = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                other.append(msg)
        return "\n\n".join(system_parts), other
