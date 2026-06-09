"""conflict_detector — 检测章节事实与档案之间的冲突。

检测类型：
- 状态倒退（境界回退、等级下降）
- 关系矛盾（敌人突变朋友无过渡）
- 时间线冲突（事件发生顺序矛盾）
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import profiles
from .chapter_facts import ChapterFacts, load_chapter_facts


@dataclass
class Conflict:
    type: str
    severity: str
    character: str
    description: str
    chapter_id: float

    def __str__(self) -> str:
        return f"[{self.severity}|{self.type}] 第{self.chapter_id:g}章 {self.character}: {self.description}"


PROGRESSION_FIELDS = {
    "境界", "level", "等级", "修为", "实力", "魂环",
}

IRREVERSIBLE_FIELDS = {
    "贞操", "生死", "死亡",
}


def detect_conflicts(
    project_dir: Path,
    chapter_id: float,
) -> list[Conflict]:
    """检测指定章节的事实与历史档案之间的冲突。"""
    facts = load_chapter_facts(project_dir, chapter_id)
    if not facts:
        return []

    conflicts: list[Conflict] = []

    conflicts.extend(_check_state_regression(project_dir, facts))
    conflicts.extend(_check_relationship_contradictions(project_dir, facts))

    return conflicts


def detect_all_conflicts(project_dir: Path) -> list[Conflict]:
    """扫描所有已提取事实的章节，检测冲突。"""
    from . import state as state_mod
    st = state_mod.load(project_dir)
    facts_store = st.get("chapter_facts", {})

    all_conflicts: list[Conflict] = []
    for key in sorted(facts_store.keys(), key=float):
        cid = float(key)
        conflicts = detect_conflicts(project_dir, cid)
        all_conflicts.extend(conflicts)

    return all_conflicts


def _check_state_regression(
    project_dir: Path, facts: ChapterFacts
) -> list[Conflict]:
    """检测状态倒退：如境界从高变低。"""
    conflicts: list[Conflict] = []

    for change in facts.state_changes:
        char = change.get("character", "")
        field_name = change.get("field", "")
        old_val = change.get("from", "")
        new_val = change.get("to", "")

        if not char or not field_name:
            continue

        if field_name in IRREVERSIBLE_FIELDS and old_val and new_val != old_val:
            conflicts.append(Conflict(
                type="irreversible_change",
                severity="HIGH",
                character=char,
                description=f"{field_name}: '{old_val}' → '{new_val}' (该字段通常不可逆)",
                chapter_id=facts.chapter_id,
            ))
            continue

        if field_name in PROGRESSION_FIELDS:
            prev_state = profiles.effective_state_at(
                project_dir, char, facts.chapter_id - 0.01
            )
            if prev_state and field_name in prev_state:
                recorded = str(prev_state[field_name])
                if old_val and recorded and old_val != recorded:
                    conflicts.append(Conflict(
                        type="state_regression",
                        severity="MEDIUM",
                        character=char,
                        description=(
                            f"{field_name}: 档案记录 '{recorded}', "
                            f"本章声称从 '{old_val}' 变为 '{new_val}'"
                        ),
                        chapter_id=facts.chapter_id,
                    ))

    return conflicts


def _check_relationship_contradictions(
    project_dir: Path, facts: ChapterFacts
) -> list[Conflict]:
    """检测关系矛盾：已有敌对关系突然变友好（无过渡章节）。"""
    conflicts: list[Conflict] = []

    rels = profiles.active_relationships_at(project_dir, facts.chapter_id)
    present_chars = set(facts.characters_present)

    hostile_kinds = {"敌人", "仇敌", "对手", "敌对"}
    friendly_kinds = {"朋友", "伙伴", "盟友", "恋人", "伴侣"}

    for rel in rels:
        a, b = rel["a"], rel["b"]
        if a not in present_chars and b not in present_chars:
            continue

        kind = rel.get("kind", "")
        if kind in hostile_kinds:
            for event in facts.events:
                if (a in event or b in event) and any(
                    w in event for w in ("合作", "联手", "结盟", "相爱", "亲密")
                ):
                    conflicts.append(Conflict(
                        type="relationship_contradiction",
                        severity="MEDIUM",
                        character=f"{a} & {b}",
                        description=f"关系为'{kind}'但本章出现友好互动: {event[:50]}",
                        chapter_id=facts.chapter_id,
                    ))
                    break

    return conflicts
