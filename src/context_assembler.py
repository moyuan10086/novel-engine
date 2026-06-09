"""ContextAssembler — 统一上下文组装与预算裁剪。

收集所有候选 ContextBlock，按优先级排序，在 token 预算内选择保留哪些块，
最终输出 messages 列表和调试报告。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .context_blocks import BlockRole, ContextBlock
from .token_budget import TokenBudget, count_tokens


@dataclass
class AssemblyResult:
    messages: list[dict[str, str]]
    included: list[ContextBlock]
    excluded: list[ContextBlock]
    total_tokens: int
    budget: int

    def to_report(self) -> dict[str, Any]:
        blocks = []
        for b in self.included:
            blocks.append({
                "id": b.id,
                "priority": b.priority,
                "tokens": b.token_estimate,
                "included": True,
                "reason": b.reason or b.source,
            })
        for b in self.excluded:
            blocks.append({
                "id": b.id,
                "priority": b.priority,
                "tokens": b.token_estimate,
                "included": False,
                "reason": "budget overflow",
            })
        return {
            "token_budget": self.budget,
            "used_tokens": self.total_tokens,
            "blocks": blocks,
        }


class ContextAssembler:
    def __init__(self, budget: TokenBudget | None = None):
        self.budget = budget or TokenBudget()
        self._blocks: list[ContextBlock] = []

    def add(self, block: ContextBlock) -> None:
        if block.content.strip():
            if block.token_estimate == 0:
                block.token_estimate = count_tokens(block.content)
            self._blocks.append(block)

    def add_many(self, blocks: list[ContextBlock]) -> None:
        for b in blocks:
            self.add(b)

    def assemble(self) -> AssemblyResult:
        """按优先级裁剪，返回组装结果。"""
        available = self.budget.available_for_context()

        required = [b for b in self._blocks if b.required]
        optional = [b for b in self._blocks if not b.required]
        optional.sort(key=lambda b: b.priority, reverse=True)

        included: list[ContextBlock] = []
        excluded: list[ContextBlock] = []
        used = 0

        for b in required:
            used += b.token_estimate
            included.append(b)

        for b in optional:
            if used + b.token_estimate <= available:
                used += b.token_estimate
                included.append(b)
            else:
                excluded.append(b)

        messages = self._build_messages(included)

        return AssemblyResult(
            messages=messages,
            included=included,
            excluded=excluded,
            total_tokens=used,
            budget=available,
        )

    def to_messages(self) -> list[dict[str, str]]:
        return self.assemble().messages

    def write_report(self, path: Path, chapter_id: float | int = 0) -> None:
        result = self.assemble()
        report = result.to_report()
        report["chapter_id"] = chapter_id
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _build_messages(self, blocks: list[ContextBlock]) -> list[dict[str, str]]:
        """将 included blocks 按 role 和 position 组装为 messages。"""
        system_blocks = [b for b in blocks if b.role == BlockRole.SYSTEM]
        user_blocks = [b for b in blocks if b.role == BlockRole.USER]

        system_blocks.sort(key=lambda b: b.position.value)
        user_blocks.sort(key=lambda b: b.position.value)

        system_content = "\n\n".join(b.content for b in system_blocks)
        user_content = "\n\n".join(b.content for b in user_blocks)

        messages = []
        if system_content.strip():
            messages.append({"role": "system", "content": system_content})
        if user_content.strip():
            messages.append({"role": "user", "content": user_content})

        return messages
