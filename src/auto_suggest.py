"""auto_suggest — 自动建议档案更新。

对比 ChapterFacts.state_changes 与现有 profiles，
输出建议列表（需确认模式，不自动写入）。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import profiles
from .chapter_facts import ChapterFacts, load_chapter_facts


@dataclass
class ProfileSuggestion:
    character: str
    field: str
    current_value: str
    suggested_value: str
    source_chapter: float
    reason: str

    def __str__(self) -> str:
        return (
            f"[{self.character}] {self.field}: "
            f"'{self.current_value}' → '{self.suggested_value}' "
            f"(来源: 第{self.source_chapter:g}章, {self.reason})"
        )


def suggest_updates(
    project_dir: Path, chapter_id: float
) -> list[ProfileSuggestion]:
    """根据章节事实的 state_changes，生成档案更新建议。"""
    facts = load_chapter_facts(project_dir, chapter_id)
    if not facts or not facts.state_changes:
        return []

    suggestions: list[ProfileSuggestion] = []

    for change in facts.state_changes:
        char_name = change.get("character", "")
        field_name = change.get("field", "")
        new_value = change.get("to", "")
        old_value = change.get("from", "")

        if not char_name or not field_name:
            continue

        current_state = profiles.effective_state_at(project_dir, char_name, chapter_id)
        current_value = ""
        if current_state:
            current_value = str(current_state.get(field_name, ""))

        if current_value == new_value:
            continue

        suggestions.append(ProfileSuggestion(
            character=char_name,
            field=field_name,
            current_value=current_value or old_value,
            suggested_value=new_value,
            source_chapter=chapter_id,
            reason=f"state_change extracted from chapter",
        ))

    return suggestions


def apply_suggestion(project_dir: Path, suggestion: ProfileSuggestion) -> None:
    """将建议应用为 snapshot。"""
    profiles.add_snapshot(
        project_dir,
        suggestion.character,
        suggestion.source_chapter,
        {suggestion.field: suggestion.suggested_value},
        note=f"auto-suggested from ch{suggestion.source_chapter:g}",
    )
