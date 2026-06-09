"""Lorebook / World Info — 关键词动态激活的世界书系统。

项目目录下的 lorebook.json 存储世界书条目。
写章时扫描本章标题、synopsis、key_beats、出场角色、近章摘要，
匹配条目的 primary_keys / secondary_keys 后激活注入上下文。
支持 1 层递归激活。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LoreEntry:
    id: str
    title: str
    type: str = "general"
    primary_keys: list[str] = field(default_factory=list)
    secondary_keys: list[str] = field(default_factory=list)
    logic: str = "AND_ANY"
    content: str = ""
    priority: int = 50
    position: str = "before_chapter_outline"
    active_chapter_range: tuple[float, float] = (1, 9999)
    max_tokens: int = 500
    recursive: bool = False
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "primary_keys": self.primary_keys,
            "secondary_keys": self.secondary_keys,
            "logic": self.logic,
            "content": self.content,
            "priority": self.priority,
            "position": self.position,
            "active_chapter_range": list(self.active_chapter_range),
            "max_tokens": self.max_tokens,
            "recursive": self.recursive,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LoreEntry":
        chapter_range = d.get("active_chapter_range", [1, 9999])
        return cls(
            id=d["id"],
            title=d.get("title", d["id"]),
            type=d.get("type", "general"),
            primary_keys=d.get("primary_keys", d.get("keys", [])),
            secondary_keys=d.get("secondary_keys", []),
            logic=d.get("logic", "AND_ANY"),
            content=d.get("content", ""),
            priority=d.get("priority", 50),
            position=d.get("position", "before_chapter_outline"),
            active_chapter_range=(float(chapter_range[0]), float(chapter_range[1])),
            max_tokens=d.get("max_tokens", 500),
            recursive=d.get("recursive", False),
            enabled=d.get("enabled", True),
        )


class Lorebook:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self._path = project_dir / "lorebook.json"
        self.entries: list[LoreEntry] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self.entries = []
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self.entries = [LoreEntry.from_dict(e) for e in data.get("entries", [])]
        except (json.JSONDecodeError, OSError):
            self.entries = []

    def save(self) -> None:
        data = {"entries": [e.to_dict() for e in self.entries]}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add(self, entry: LoreEntry) -> None:
        for i, e in enumerate(self.entries):
            if e.id == entry.id:
                self.entries[i] = entry
                self.save()
                return
        self.entries.append(entry)
        self.save()

    def remove(self, entry_id: str) -> bool:
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.id != entry_id]
        if len(self.entries) < before:
            self.save()
            return True
        return False

    def get(self, entry_id: str) -> LoreEntry | None:
        for e in self.entries:
            if e.id == entry_id:
                return e
        return None

    def activate(
        self,
        scan_text: str,
        chapter_id: float,
        max_recursion: int = 1,
    ) -> list[LoreEntry]:
        """扫描文本，返回被激活的条目列表（含递归）。"""
        activated: list[LoreEntry] = []
        activated_ids: set[str] = set()

        self._activate_round(scan_text, chapter_id, activated, activated_ids)

        if max_recursion > 0:
            recursive_entries = [e for e in activated if e.recursive]
            if recursive_entries:
                recursive_text = "\n".join(e.content for e in recursive_entries)
                self._activate_round(
                    recursive_text, chapter_id, activated, activated_ids
                )

        activated.sort(key=lambda e: e.priority, reverse=True)
        return activated

    def _activate_round(
        self,
        text: str,
        chapter_id: float,
        activated: list[LoreEntry],
        activated_ids: set[str],
    ) -> None:
        text_lower = text.lower()
        for entry in self.entries:
            if entry.id in activated_ids:
                continue
            if not entry.enabled:
                continue
            if not (entry.active_chapter_range[0] <= chapter_id <= entry.active_chapter_range[1]):
                continue
            if self._matches(entry, text_lower):
                activated.append(entry)
                activated_ids.add(entry.id)

    def _matches(self, entry: LoreEntry, text_lower: str) -> bool:
        """检查条目的关键词是否在文本中被触发。"""
        if not entry.primary_keys:
            return False

        primary_hit = any(k.lower() in text_lower for k in entry.primary_keys)
        if not primary_hit:
            return False

        if entry.logic == "AND_ANY" and entry.secondary_keys:
            return any(k.lower() in text_lower for k in entry.secondary_keys)

        return True

    def build_scan_text(
        self,
        chapter: dict[str, Any],
        priors: list[tuple[float, str]],
        outline: dict[str, Any],
    ) -> str:
        """构建用于关键词扫描的组合文本。"""
        parts = [
            chapter.get("title", ""),
            chapter.get("synopsis", ""),
            " ".join(chapter.get("key_beats", [])),
            chapter.get("pov", ""),
        ]
        for _, summary in priors[-3:]:
            parts.append(summary)

        return "\n".join(parts)

    def to_context_string(self, activated: list[LoreEntry]) -> str:
        """将激活的条目格式化为 prompt 注入文本。"""
        if not activated:
            return ""
        parts = ["## 世界书（本章激活的设定条目）\n"]
        for entry in activated:
            content = entry.content
            if len(content) > entry.max_tokens * 2:
                content = content[:entry.max_tokens * 2] + "..."
            parts.append(f"### [{entry.type}] {entry.title}\n{content}\n")
        return "\n".join(parts)
