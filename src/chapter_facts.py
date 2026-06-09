"""ChapterFacts — 结构化章节事实提取 + 分层记忆管理。

生成章节后，通过额外 LLM 调用提取结构化事实（事件、角色、地点、状态变化等），
存入 state.json 的 chapter_facts 和 long_memory 字段。

通过环境变量 EXTRACT_FACTS=1 控制是否启用。
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import llm, state


@dataclass
class ChapterFacts:
    chapter_id: float
    events: list[str] = field(default_factory=list)
    characters_present: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    time_markers: list[str] = field(default_factory=list)
    state_changes: list[dict[str, str]] = field(default_factory=list)
    foreshadowing_movements: list[dict[str, str]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("chapter_id")
        return d

    @classmethod
    def from_dict(cls, chapter_id: float, d: dict[str, Any]) -> "ChapterFacts":
        return cls(
            chapter_id=chapter_id,
            events=d.get("events", []),
            characters_present=d.get("characters_present", []),
            locations=d.get("locations", []),
            time_markers=d.get("time_markers", []),
            state_changes=d.get("state_changes", []),
            foreshadowing_movements=d.get("foreshadowing_movements", []),
            open_questions=d.get("open_questions", []),
        )


EXTRACT_PROMPT = """\
你是一个小说分析助手。从下面的章节正文中提取结构化事实，输出严格 JSON。

要求提取:
- events: 本章发生的关键事件（3-8条）
- characters_present: 本章出场的角色名
- locations: 本章涉及的地点
- time_markers: 时间线索（如"三天后"、"黄昏"）
- state_changes: 角色状态变化 [{character, field, from, to}]
- foreshadowing_movements: 伏笔动态 [{id或描述, action: raised/advanced/resolved}]
- open_questions: 本章留下的悬念

输出格式（纯 JSON，无其他文字）:
```json
{
  "events": [...],
  "characters_present": [...],
  "locations": [...],
  "time_markers": [...],
  "state_changes": [...],
  "foreshadowing_movements": [...],
  "open_questions": [...]
}
```"""


def is_enabled() -> bool:
    return os.environ.get("EXTRACT_FACTS", "").strip() in ("1", "true", "yes")


async def extract_chapter_facts(text: str, chapter_id: float) -> ChapterFacts:
    """调用 LLM 从章节正文中提取结构化事实。"""
    msgs = [
        {"role": "system", "content": EXTRACT_PROMPT},
        {"role": "user", "content": text[:12000]},
    ]
    try:
        raw = await llm.chat(msgs, temperature=0.2, max_tokens=1500)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
        data = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return ChapterFacts(chapter_id=chapter_id)

    return ChapterFacts.from_dict(chapter_id, data)


def save_chapter_facts(project_dir: Path, facts: ChapterFacts) -> None:
    """将提取的事实写入 state.json 的 chapter_facts 字段。"""
    st = state.load(project_dir)
    if "chapter_facts" not in st:
        st["chapter_facts"] = {}
    key = str(int(facts.chapter_id) if isinstance(facts.chapter_id, float) and facts.chapter_id.is_integer() else facts.chapter_id)
    st["chapter_facts"][key] = facts.to_dict()
    state.save(project_dir, st)


def load_chapter_facts(project_dir: Path, chapter_id: float) -> ChapterFacts | None:
    """从 state.json 读取指定章节的事实。"""
    st = state.load(project_dir)
    facts_store = st.get("chapter_facts", {})
    key = str(int(chapter_id) if isinstance(chapter_id, float) and chapter_id.is_integer() else chapter_id)
    if key not in facts_store:
        return None
    return ChapterFacts.from_dict(chapter_id, facts_store[key])


async def update_long_memory(project_dir: Path, new_facts: ChapterFacts) -> None:
    """根据新提取的事实更新长期记忆。"""
    st = state.load(project_dir)
    if "long_memory" not in st:
        st["long_memory"] = {
            "plot_so_far": "",
            "open_threads": [],
            "do_not_reveal": [],
        }

    lm = st["long_memory"]

    for q in new_facts.open_questions:
        if q not in lm["open_threads"]:
            lm["open_threads"].append(q)

    for fm in new_facts.foreshadowing_movements:
        action = fm.get("action", "")
        desc = fm.get("id", fm.get("描述", ""))
        if action == "resolved" and desc:
            lm["open_threads"] = [t for t in lm["open_threads"] if desc not in t]

    if len(lm["open_threads"]) > 30:
        lm["open_threads"] = lm["open_threads"][-30:]

    state.save(project_dir, st)


def get_long_memory(project_dir: Path) -> dict[str, Any]:
    """获取长期记忆。"""
    st = state.load(project_dir)
    return st.get("long_memory", {})
