"""Tests for src/profiles.py — 角色档案、伏笔、关系。"""
from __future__ import annotations

import pytest

from src import profiles


class TestEffectiveStateAt:
    def test_merge_snapshots(self, tmp_project):
        state = profiles.effective_state_at(tmp_project, "林夜", 2)
        assert state["境界"] == "炼气三层"
        assert state["装备"] == "铁剑"
        assert state["identity"] == "穿越者"

    def test_earlier_chapter(self, tmp_project):
        state = profiles.effective_state_at(tmp_project, "林夜", 1)
        assert state["境界"] == "炼气一层"
        assert state["装备"] == "无"

    def test_unknown_character(self, tmp_project):
        assert profiles.effective_state_at(tmp_project, "不存在", 1) is None


class TestActiveForeshadowings:
    def test_open_foreshadowing(self, tmp_project):
        fores = profiles.active_foreshadowings_at(tmp_project, 2)
        assert len(fores) == 1
        assert fores[0]["id"] == "F001"

    def test_before_raised(self, tmp_project):
        fores = profiles.active_foreshadowings_at(tmp_project, 0.5)
        assert fores == []

    def test_after_resolved(self, tmp_project):
        profiles.resolve_foreshadowing(tmp_project, "F001", 3)
        fores = profiles.active_foreshadowings_at(tmp_project, 5)
        assert fores == []


class TestActiveRelationships:
    def test_active(self, tmp_project):
        rels = profiles.active_relationships_at(tmp_project, 2)
        assert len(rels) == 1
        assert rels[0]["kind"] == "青梅竹马"

    def test_before_since(self, tmp_project):
        rels = profiles.active_relationships_at(tmp_project, 0.5)
        assert rels == []


class TestBuildContextBlock:
    def test_includes_all_sections(self, tmp_project):
        ctx = profiles.build_context_block(tmp_project, 2)
        assert "角色档案" in ctx
        assert "林夜" in ctx
        assert "关系网" in ctx
        assert "未解伏笔" in ctx

    def test_empty_project(self, tmp_path):
        project = tmp_path / "empty"
        project.mkdir()
        (project / "state").mkdir()
        ctx = profiles.build_context_block(project, 1)
        assert ctx == ""


class TestAddCharacter:
    def test_add_new(self, tmp_project):
        profiles.add_character(tmp_project, "新角色", {"identity": "路人"})
        state = profiles.effective_state_at(tmp_project, "新角色", 1)
        assert state["identity"] == "路人"

    def test_update_static(self, tmp_project):
        profiles.add_character(tmp_project, "林夜", {"新字段": "新值"})
        state = profiles.effective_state_at(tmp_project, "林夜", 1)
        assert state["新字段"] == "新值"
        assert state["identity"] == "穿越者"


class TestAddSnapshot:
    def test_add_snapshot(self, tmp_project):
        profiles.add_snapshot(tmp_project, "林夜", 5, {"境界": "筑基"}, note="突破")
        state = profiles.effective_state_at(tmp_project, "林夜", 5)
        assert state["境界"] == "筑基"

    def test_snapshot_ordering(self, tmp_project):
        profiles.add_snapshot(tmp_project, "林夜", 10, {"境界": "金丹"})
        profiles.add_snapshot(tmp_project, "林夜", 5, {"境界": "筑基"})
        state = profiles.effective_state_at(tmp_project, "林夜", 7)
        assert state["境界"] == "筑基"
