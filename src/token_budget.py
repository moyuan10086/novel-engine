"""TokenBudget — token 估算与预算管理。

优先使用 tiktoken（可选依赖），回退到字符近似。
内置常见模型的上下文窗口限制。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

MODEL_CONTEXT_LIMITS: dict[str, int] = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 16_385,
    "claude-3-opus": 200_000,
    "claude-3-sonnet": 200_000,
    "claude-3-haiku": 200_000,
    "claude-3.5-sonnet": 200_000,
    "deepseek-chat": 64_000,
    "deepseek-coder": 128_000,
    "qwen-plus": 128_000,
    "qwen-max": 32_000,
}

DEFAULT_CONTEXT_LIMIT = 32_000

_tiktoken_enc = None


def _get_tiktoken():
    global _tiktoken_enc
    if _tiktoken_enc is not None:
        return _tiktoken_enc
    try:
        import tiktoken
        _tiktoken_enc = tiktoken.encoding_for_model("gpt-4o")
    except (ImportError, Exception):
        _tiktoken_enc = False
    return _tiktoken_enc


def count_tokens(text: str) -> int:
    """精确 token 计数（tiktoken 可用时），否则用字符近似。"""
    enc = _get_tiktoken()
    if enc and enc is not False:
        return len(enc.encode(text))
    return max(1, int(len(text) * 0.6))


@dataclass
class TokenBudget:
    model: str = ""
    max_output_tokens: int = 0
    _context_limit: int = 0

    def __post_init__(self):
        if not self.model:
            self.model = os.environ.get("MODEL", "gpt-4o-mini")
        if not self.max_output_tokens:
            self.max_output_tokens = int(os.environ.get("MAX_TOKENS", "8000"))
        if not self._context_limit:
            self._context_limit = self._resolve_limit()

    def _resolve_limit(self) -> int:
        model_lower = self.model.lower()
        for key, limit in MODEL_CONTEXT_LIMITS.items():
            if key in model_lower:
                return limit
        return DEFAULT_CONTEXT_LIMIT

    @property
    def context_limit(self) -> int:
        return self._context_limit

    def available_for_context(self) -> int:
        """可用于上下文内容的 token 数（总限制 - 输出预留 - 安全余量）。"""
        safety_margin = 500
        return max(0, self._context_limit - self.max_output_tokens - safety_margin)

    def fits(self, token_count: int, already_used: int) -> bool:
        """判断新增 token_count 是否超预算。"""
        return already_used + token_count <= self.available_for_context()
