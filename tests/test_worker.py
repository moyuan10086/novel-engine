"""Tests for src/worker.py — 单章生成全流程（mock LLM）。"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src import state, worker


@pytest.fixture
def outline(tmp_project: Path) -> dict:
    return json.loads((tmp_project / "outline.json").read_text(encoding="utf-8"))


class TestChapterPath:
    def test_normal_chapter(self, tmp_project, outline):
        ch = outline["chapters"][0]  # id=1
        p = worker.chapter_path(tmp_project, ch)
        assert "ch001_" in str(p)
        assert p.suffix == ".md"

    def test_insert_chapter(self, tmp_project, outline):
        ch = outline["chapters"][3]  # id=1.5
        p = worker.chapter_path(tmp_project, ch)
        assert "ch001_5_" in str(p)


class TestWriteChapter:
    @pytest.mark.asyncio
    async def test_normal_generation(self, tmp_project, outline, mock_llm):
        ch = outline["chapters"][2]  # id=3, not done
        cid, status = await worker.write_chapter(tmp_project, outline, ch, force=True)
        assert cid == 3
        assert status == "written"
        assert state.is_done(tmp_project, 3)
        out_path = worker.chapter_path(tmp_project, ch)
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert content.startswith("# 第3章")

    @pytest.mark.asyncio
    async def test_skip_existing(self, tmp_project, outline, mock_llm):
        ch = outline["chapters"][0]  # id=1, already done
        # Create the chapter file
        out_path = worker.chapter_path(tmp_project, ch)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("# 已存在", encoding="utf-8")

        cid, status = await worker.write_chapter(tmp_project, outline, ch, force=False)
        assert status == "skipped"
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_overwrite(self, tmp_project, outline, mock_llm):
        ch = outline["chapters"][0]  # id=1, already done
        out_path = worker.chapter_path(tmp_project, ch)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("# 旧内容", encoding="utf-8")

        cid, status = await worker.write_chapter(tmp_project, outline, ch, force=True)
        assert status == "written"
        content = out_path.read_text(encoding="utf-8")
        assert "旧内容" not in content

    @pytest.mark.asyncio
    async def test_insert_chapter_generation(self, tmp_project, outline, mock_llm):
        # Write ch1 and ch2 files for neighbor excerpts
        ch1 = outline["chapters"][0]
        ch2 = outline["chapters"][1]
        p1 = worker.chapter_path(tmp_project, ch1)
        p2 = worker.chapter_path(tmp_project, ch2)
        p1.parent.mkdir(parents=True, exist_ok=True)
        p1.write_text("# 第1章 序幕\n\n第一章末尾内容", encoding="utf-8")
        p2.write_text("# 第2章 初战\n\n第二章开头内容", encoding="utf-8")

        ch_insert = outline["chapters"][3]  # id=1.5
        cid, status = await worker.write_chapter(tmp_project, outline, ch_insert, force=True)
        assert cid == 1.5
        assert status == "written"
        out_path = worker.chapter_path(tmp_project, ch_insert)
        content = out_path.read_text(encoding="utf-8")
        assert "番外" in content

    @pytest.mark.asyncio
    async def test_llm_failure(self, tmp_project, outline):
        ch = outline["chapters"][2]
        with patch("src.llm.chat", new=AsyncMock(side_effect=RuntimeError("API error"))):
            cid, status = await worker.write_chapter(tmp_project, outline, ch, force=True)
        assert status.startswith("failed")
        assert not state.is_done(tmp_project, 3)


class TestBuildCrossRefContext:
    def test_detects_refs(self, tmp_project, outline):
        ch = outline["chapters"][1]  # synopsis has "参见ch1"
        # Modify synopsis to have a cross-ref
        ch["synopsis"] = "战斗 参见ch1伏笔"
        ctx = worker._build_cross_ref_context(tmp_project, outline, ch)
        assert ctx is not None
        assert "觉醒了配角阅读器金手指" in ctx

    def test_no_refs(self, tmp_project, outline):
        ch = outline["chapters"][0]  # no refs
        ctx = worker._build_cross_ref_context(tmp_project, outline, ch)
        assert ctx is None


class TestBuildNeighborhoodContext:
    def test_with_neighbors(self, tmp_project, outline):
        ch = outline["chapters"][1]  # id=2
        ctx = worker._build_neighborhood_context(tmp_project, outline, ch)
        assert ctx is not None
        assert "前1章" in ctx
        assert "觉醒了配角阅读器金手指" in ctx

    def test_first_chapter_no_prior(self, tmp_project, outline):
        ch = outline["chapters"][0]  # id=1
        ctx = worker._build_neighborhood_context(tmp_project, outline, ch)
        # Should still have ch2 as neighbor
        assert ctx is not None
