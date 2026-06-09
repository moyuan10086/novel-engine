"""Provider — LLM 与 embedding 的抽象基类。

通过 PROVIDER 环境变量选择具体实现：
- openai（默认）: OpenAI-compatible API
- anthropic: 原生 Anthropic API

不设 PROVIDER 时走原有 llm.py 逻辑（向后兼容）。
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class Provider(ABC):
    """LLM provider 抽象基类。"""

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        ...
        yield ""  # type: ignore

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    def build_messages(
        self, system: str, user: str
    ) -> list[dict[str, str]] | dict[str, Any]:
        """构建消息格式。默认为 OpenAI 风格 messages list。"""
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        if user:
            msgs.append({"role": "user", "content": user})
        return msgs


def get_provider() -> Provider:
    """根据 PROVIDER 环境变量实例化对应 provider。"""
    provider_name = os.environ.get("PROVIDER", "openai").lower()

    if provider_name == "anthropic":
        from .providers.anthropic import AnthropicProvider
        return AnthropicProvider()

    from .providers.openai_compat import OpenAICompatProvider
    return OpenAICompatProvider()
