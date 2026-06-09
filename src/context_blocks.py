"""ContextBlock — 上下文组装的最小单元。

每个注入 prompt 的片段都包装为 ContextBlock，携带优先级、来源、token 估算等元数据，
供 ContextAssembler 按预算裁剪和排序。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BlockRole(str, Enum):
    SYSTEM = "system"
    USER = "user"


class BlockPosition(str, Enum):
    SYSTEM_BASE = "system_base"
    SYSTEM_PROFILE = "system_profile"
    SYSTEM_RULES = "system_rules"
    USER_WORLD = "user_world"
    USER_CHARACTERS = "user_characters"
    USER_PRIOR_SUMMARIES = "user_prior_summaries"
    USER_FOLLOWING_SUMMARIES = "user_following_summaries"
    USER_CHAPTER_OUTLINE = "user_chapter_outline"
    USER_UPCOMING = "user_upcoming"
    USER_NEIGHBOR_EXCERPTS = "user_neighbor_excerpts"
    USER_CROSS_REF = "user_cross_ref"
    USER_NEIGHBORHOOD = "user_neighborhood"
    USER_LOREBOOK = "user_lorebook"
    USER_VECTOR = "user_vector"
    USER_TASK = "user_task"
    USER_BOUNDARY = "user_boundary"


@dataclass
class ContextBlock:
    id: str
    content: str
    role: BlockRole
    position: BlockPosition
    priority: int = 50
    required: bool = False
    token_estimate: int = 0
    source: str = ""
    reason: str = ""

    def __post_init__(self):
        if self.token_estimate == 0 and self.content:
            self.token_estimate = estimate_tokens(self.content)


def estimate_tokens(text: str) -> int:
    """粗略 token 估算：中文约 1 字 = 1.5 token，英文约 4 字符 = 1 token。
    简化为 len(text) * 0.6 取整（偏保守）。
    """
    if not text:
        return 0
    return max(1, int(len(text) * 0.6))
