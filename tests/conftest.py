"""Shared test fixtures for novel-engine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal project directory with outline, state, and profiles."""
    project_dir = tmp_path / "test_novel"
    project_dir.mkdir()
    (project_dir / "chapters").mkdir()
    (project_dir / "state").mkdir()

    outline = {
        "meta": {
            "title": "测试小说",
            "genre": "玄幻",
            "target_words_per_chapter": 2000,
            "language": "zh-CN",
            "style_notes": ["第三人称"],
        },
        "world": {
            "setting": "一个修仙世界",
            "rules": ["灵气复苏", "境界分九层"],
        },
        "characters": [
            {"name": "林夜", "role": "protagonist", "profile": "天才少年"},
            {"name": "苏小小", "role": "heroine", "profile": "青梅竹马"},
        ],
        "chapters": [
            {"id": 1, "title": "序幕", "synopsis": "林夜觉醒金手指", "key_beats": ["觉醒", "冲突"], "pov": "林夜"},
            {"id": 2, "title": "初战", "synopsis": "第一次实战", "key_beats": ["战斗", "胜利"], "pov": "林夜"},
            {"id": 3, "title": "转折", "synopsis": "遭遇强敌", "key_beats": ["危机", "逃脱"], "pov": "林夜"},
            {"id": 1.5, "title": "番外·苏小小日记", "synopsis": "苏小小视角回忆", "key_beats": ["回忆"], "pov": "苏小小"},
        ],
    }
    (project_dir / "outline.json").write_text(
        json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    state = {
        "summaries": {
            "1": "林夜在学院觉醒了配角阅读器金手指，发现自己能看到他人的命运轨迹。",
            "2": "林夜利用金手指在比武中获胜，引起长老注意。",
        },
        "done": [1, 2],
    }
    (project_dir / "state" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    profiles = {
        "version": 1,
        "characters": {
            "林夜": {
                "static": {"identity": "穿越者", "金手指": "配角阅读器"},
                "snapshots": [
                    {"as_of_ch": 1, "境界": "炼气一层", "装备": "无"},
                    {"as_of_ch": 2, "境界": "炼气三层", "装备": "铁剑"},
                ],
            }
        },
        "foreshadowings": [
            {"id": "F001", "raised_ch": 1, "resolved_ch": None, "status": "open",
             "what": "金手指来源之谜", "importance": "high"},
        ],
        "relationships": [
            {"a": "林夜", "b": "苏小小", "kind": "青梅竹马", "since_ch": 1},
        ],
    }
    (project_dir / "state" / "profiles.json").write_text(
        json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return project_dir


@pytest.fixture
def mock_llm():
    """Patch llm.chat to return predictable responses."""
    async def fake_chat(messages, **kwargs):
        return "这是模拟生成的章节正文，大约两千字的内容。" * 50

    with patch("src.llm.chat", new=AsyncMock(side_effect=fake_chat)) as m:
        yield m
