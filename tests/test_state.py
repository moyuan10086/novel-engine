"""Tests for src/state.py — 状态持久化。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import state


class TestLoad:
    def test_empty_project(self, tmp_path: Path):
        project = tmp_path / "empty"
        project.mkdir()
        result = state.load(project)
        assert result == {"summaries": {}, "done": []}

    def test_existing_state(self, tmp_project: Path):
        result = state.load(tmp_project)
        assert "1" in result["summaries"]
        assert 1 in result["done"]


class TestMarkDone:
    def test_mark_new_chapter(self, tmp_project: Path):
        state.mark_done(tmp_project, 3, "第三章摘要")
        st = state.load(tmp_project)
        assert st["summaries"]["3"] == "第三章摘要"
        assert 3 in st["done"]

    def test_mark_float_chapter(self, tmp_project: Path):
        state.mark_done(tmp_project, 1.5, "番外摘要")
        st = state.load(tmp_project)
        assert st["summaries"]["1.5"] == "番外摘要"
        assert 1.5 in st["done"]

    def test_idempotent(self, tmp_project: Path):
        state.mark_done(tmp_project, 1, "重写摘要")
        st = state.load(tmp_project)
        assert st["summaries"]["1"] == "重写摘要"
        assert st["done"].count(1) == 1


class TestPriorSummaries:
    def test_returns_earlier_chapters(self, tmp_project: Path):
        priors = state.prior_summaries(tmp_project, 3)
        assert len(priors) == 2
        assert priors[0][0] == 1.0
        assert priors[1][0] == 2.0

    def test_empty_for_first_chapter(self, tmp_project: Path):
        priors = state.prior_summaries(tmp_project, 1)
        assert priors == []

    def test_insert_chapter_priors(self, tmp_project: Path):
        priors = state.prior_summaries(tmp_project, 1.5)
        assert len(priors) == 1
        assert priors[0][0] == 1.0


class TestFollowingSummaries:
    def test_returns_later_chapters(self, tmp_project: Path):
        followings = state.following_summaries(tmp_project, 1)
        assert len(followings) == 1
        assert followings[0][0] == 2.0

    def test_empty_for_last(self, tmp_project: Path):
        followings = state.following_summaries(tmp_project, 3)
        assert followings == []


class TestIsDone:
    def test_done_chapter(self, tmp_project: Path):
        assert state.is_done(tmp_project, 1) is True

    def test_not_done(self, tmp_project: Path):
        assert state.is_done(tmp_project, 3) is False
