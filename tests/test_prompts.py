"""Tests for src/prompts.py — 覆盖普通章/插入章/档案注入/交叉引用/邻域。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.prompts import (
    _format_neighbor_block,
    _format_neighborhood_block,
    _format_cross_ref_block,
    _format_upcoming_block,
    build_chapter_messages,
    extract_cross_refs,
)


@pytest.fixture
def outline():
    return {
        "meta": {
            "title": "测试",
            "target_words_per_chapter": 2000,
            "style_notes": ["简洁"],
        },
        "world": {"setting": "修仙世界", "rules": ["灵气复苏"]},
        "characters": [
            {"name": "林夜", "role": "protagonist", "profile": "天才"},
        ],
        "chapters": [
            {"id": 1, "title": "序幕", "synopsis": "开场", "key_beats": ["觉醒"], "pov": "林夜"},
            {"id": 2, "title": "初战", "synopsis": "战斗 参见ch1伏笔", "key_beats": ["打斗"], "pov": "林夜"},
            {"id": 3, "title": "转折", "synopsis": "危机", "key_beats": ["逃脱"], "pov": "林夜"},
            {"id": 1.5, "title": "番外", "synopsis": "回忆", "key_beats": ["回忆"], "pov": "苏小小"},
        ],
    }


class TestExtractCrossRefs:
    def test_detects_ch_pattern(self):
        chapter = {"id": 5, "synopsis": "回顾ch3的事件", "key_beats": ["呼应ch1"]}
        refs = extract_cross_refs(chapter)
        assert refs == [1, 3]

    def test_detects_chinese_pattern(self):
        chapter = {"id": 10, "synopsis": "想起第7章的约定", "key_beats": []}
        refs = extract_cross_refs(chapter)
        assert refs == [7]

    def test_excludes_self(self):
        chapter = {"id": 5, "synopsis": "本章ch5内容", "key_beats": []}
        refs = extract_cross_refs(chapter)
        assert refs == []

    def test_no_refs(self):
        chapter = {"id": 1, "synopsis": "普通开场", "key_beats": ["觉醒"]}
        refs = extract_cross_refs(chapter)
        assert refs == []


class TestFormatNeighborBlock:
    def test_none_input(self):
        assert _format_neighbor_block(None) == ""

    def test_empty_dict(self):
        assert _format_neighbor_block({}) == ""

    def test_with_prev_tail(self):
        excerpts = {
            "prev_tail": "前章末尾文字",
            "prev_meta": {"id": 3, "title": "转折"},
            "next_head": None,
            "next_meta": None,
        }
        result = _format_neighbor_block(excerpts)
        assert "紧邻前章原文末尾" in result
        assert "ch.3 转折" in result
        assert "前章末尾文字" in result

    def test_with_both(self):
        excerpts = {
            "prev_tail": "前章末尾",
            "prev_meta": {"id": 1, "title": "序幕"},
            "next_head": "后章开头",
            "next_meta": {"id": 2, "title": "初战"},
        }
        result = _format_neighbor_block(excerpts)
        assert "紧邻前章原文末尾" in result
        assert "紧邻后章原文开头" in result

    def test_float_id_display(self):
        excerpts = {
            "prev_tail": "文字",
            "prev_meta": {"id": 3.0, "title": "三章"},
            "next_head": None,
            "next_meta": None,
        }
        result = _format_neighbor_block(excerpts)
        assert "ch.3" in result


class TestFormatNeighborhoodBlock:
    def test_none_input(self):
        assert _format_neighborhood_block(None) == ""

    def test_empty_string(self):
        assert _format_neighborhood_block("") == ""

    def test_with_content(self):
        result = _format_neighborhood_block("前1章摘要内容")
        assert "邻近章节实况" in result
        assert "前1章摘要内容" in result
        assert "优先级高于大纲" in result


class TestFormatCrossRefBlock:
    def test_empty(self):
        assert _format_cross_ref_block("") == ""
        assert _format_cross_ref_block(None) == ""

    def test_with_content(self):
        result = _format_cross_ref_block("[第3章] 发生了战斗")
        assert "本章需要呼应的往事" in result
        assert "[第3章]" in result


class TestBuildChapterMessages:
    def test_normal_chapter(self, outline):
        chapter = outline["chapters"][0]  # id=1
        priors = []
        msgs = build_chapter_messages(outline, chapter, priors)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert "世界观" in msgs[1]["content"]
        assert "林夜" in msgs[1]["content"]

    def test_insert_chapter(self, outline):
        chapter = outline["chapters"][3]  # id=1.5
        priors = [(1, "第一章摘要")]
        followings = [(2, "第二章摘要")]
        msgs = build_chapter_messages(outline, chapter, priors, followings)
        assert "插入章" in msgs[0]["content"]
        assert "前情" in msgs[1]["content"]
        assert "后续" in msgs[1]["content"]

    def test_profile_injection(self, outline):
        chapter = outline["chapters"][0]
        profile_ctx = "## 角色档案\n### 林夜\n- 境界: 炼气一层"
        msgs = build_chapter_messages(outline, chapter, [], profile_context=profile_ctx)
        assert "角色档案" in msgs[0]["content"]
        assert "写作硬规则" in msgs[0]["content"]

    def test_cross_ref_injection(self, outline):
        chapter = outline["chapters"][1]  # id=2, has ch1 ref
        msgs = build_chapter_messages(
            outline, chapter, [(1, "第一章摘要")],
            cross_ref_context="[第1章] 林夜觉醒"
        )
        assert "本章需要呼应的往事" in msgs[1]["content"]

    def test_neighborhood_injection(self, outline):
        chapter = outline["chapters"][1]
        msgs = build_chapter_messages(
            outline, chapter, [(1, "摘要")],
            neighborhood_context="[前1章] 林夜觉醒"
        )
        assert "邻近章节实况" in msgs[1]["content"]

    def test_boundary_note(self, outline):
        chapter = {**outline["chapters"][0], "boundary_note": "不要写到战斗结束"}
        msgs = build_chapter_messages(outline, chapter, [])
        assert "硬性章节边界" in msgs[1]["content"]
        assert "不要写到战斗结束" in msgs[1]["content"]
