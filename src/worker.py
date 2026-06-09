"""单章 worker — 支持多项目（project_dir 代替 root）

插入章特性：自动加载紧邻的前章末尾 + 后章开头原文，提供精确上下文。
档案系统：自动注入角色当前状态、关系、未解伏笔。
上下文组装：通过 ContextAssembler 按优先级和预算裁剪。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from . import llm, profiles, prompts, state
from .context_assembler import ContextAssembler
from .context_blocks import BlockPosition, BlockRole, ContextBlock
from .token_budget import TokenBudget


def _fmt_id(cid: float | int) -> str:
    if isinstance(cid, float) and cid.is_integer():
        cid = int(cid)
    if isinstance(cid, float):
        whole = int(cid)
        frac = str(cid).split(".", 1)[1]
        return f"{whole:03d}_{frac}"
    return f"{cid:03d}"


def chapter_path(project_dir: Path, chapter: dict[str, Any]) -> Path:
    """返回项目专属的章节路径"""
    cid = chapter["id"]
    forbidden = '\\/:*?"<>|'
    safe_title = "".join(
        c for c in chapter.get("title", "untitled")
        if c not in forbidden and (c.isalnum() or c in " 　-_·")
    )
    safe_title = safe_title.strip().replace(" ", "_")[:40] or "untitled"
    return project_dir / "chapters" / f"ch{_fmt_id(cid)}_{safe_title}.md"


def _is_insert(cid: float | int) -> bool:
    return isinstance(cid, float) and not cid.is_integer()


def _strip_chapter_header(text: str) -> str:
    """去掉章节文件开头的 H1 标题"""
    lines = text.split("\n", 2)
    if lines and lines[0].startswith("# "):
        return lines[2] if len(lines) > 2 else ""
    return text


def _strip_meta_annotations(text: str) -> str:
    """去掉模型输出末尾的元注释（字数标注、备注等）。"""
    import re
    meta_paragraph = (
        r"[（(][^）)\n]*(?:"
        r"本章(?:正文)?字数|正文字数|字数统计|word count|Word count|"
        r"以下为|继续展开|扩展正文|扩展叙述|扩展描写|确保字数|"
        r"响应要求|核心节拍|严格按大纲|无任何元标注|本章正文已|"
        r"4成情感|6成冲突|情感4成|节奏4成|字数已超|"
        r"本章亮点|本章主要|备注|说明"
        r")[^）)]*[）)]"
    )
    text = re.sub(rf"\n*{meta_paragraph}\s*", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\n*(?:以下为|扩展)(?:继续)?(?:展开|正文|叙述|描写).*?(?=\n\n|$)", "\n\n", text)
    paragraphs = []
    meta_inline = re.compile(r"4成情感|6成冲突|情感4成|情感铺4成|节奏4成|本章正文已充分")
    for paragraph in text.split("\n\n"):
        stripped = paragraph.strip()
        if meta_inline.search(paragraph):
            continue
        if stripped.startswith(("（", "(")) and any(
            token in stripped
            for token in (
                "字数统计",
                "本章正文字数",
                "正文字数",
                "继续自然延伸",
                "响应要求",
                "核心节拍",
                "无任何元标注",
                "本章正文已",
            )
        ):
            continue
        paragraphs.append(paragraph)
    text = "\n\n".join(paragraphs)
    text = text.replace("情感悬念", "情感上的不安")
    text = text.replace("真相悬念", "更深的疑问")
    text = text.replace("真相线悬念", "真相线上的疑问")
    text = _strip_chapter_number_refs(text)
    text = _truncate_repetition(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.rstrip()


def _strip_chapter_number_refs(text: str) -> str:
    """去掉正文中用章节编号引用前情的写法，如"第27章梦见…"→"梦见…"。"""
    import re
    text = re.sub(r"(?:从)?第\d+章(?:时|里|中|那次|那晚|那天)?", "", text)
    return text


def _truncate_repetition(text: str, min_block_chars: int = 60, max_repeats: int = 2) -> str:
    """检测并截断重复循环的段落。保留前 max_repeats 次出现，删除之后的重复。"""
    paragraphs = text.split("\n\n")
    seen: dict[str, int] = {}
    kept: list[str] = []
    for p in paragraphs:
        key = p.strip()
        if len(key) < min_block_chars:
            kept.append(p)
            continue
        count = seen.get(key, 0) + 1
        seen[key] = count
        if count <= max_repeats:
            kept.append(p)
        else:
            break
    return "\n\n".join(kept)


def _load_neighbor_excerpts(
    project_dir: Path,
    outline: dict[str, Any],
    cid: float,
    tail_chars: int = 2500,
    head_chars: int = 2500,
) -> tuple[str | None, str | None, dict | None, dict | None]:
    """加载紧邻前章的末尾片段和紧邻后章的开头片段。

    返回: (prev_tail, next_head, prev_chapter_meta, next_chapter_meta)
    若邻章文件不存在则返回 None。
    """
    chapters = sorted(outline.get("chapters", []), key=lambda c: float(c.get("id", 0)))

    prev_ch = None
    next_ch = None
    for ch in chapters:
        ch_id = float(ch.get("id", 0))
        if ch_id < cid:
            prev_ch = ch  # 持续覆盖到最大的小于cid的章节
        elif ch_id > cid and next_ch is None:
            next_ch = ch
            break

    prev_tail = None
    next_head = None

    if prev_ch:
        p = chapter_path(project_dir, prev_ch)
        if p.exists():
            text = _strip_chapter_header(p.read_text(encoding="utf-8")).strip()
            prev_tail = text[-tail_chars:] if len(text) > tail_chars else text

    if next_ch:
        p = chapter_path(project_dir, next_ch)
        if p.exists():
            text = _strip_chapter_header(p.read_text(encoding="utf-8")).strip()
            next_head = text[:head_chars] if len(text) > head_chars else text

    return prev_tail, next_head, prev_ch, next_ch


def _build_cross_ref_context(
    project_dir: Path,
    outline: dict[str, Any],
    chapter: dict[str, Any],
) -> str | None:
    """检测大纲中引用的其他章节，收集其摘要/概要作为上下文。"""
    refs = prompts.extract_cross_refs(chapter)
    if not refs:
        return None

    st = state.load(project_dir)
    summaries = st.get("summaries", {})
    chapters_by_id = {int(float(c["id"])): c for c in outline.get("chapters", [])}

    parts = []
    for ref_id in refs:
        ref_ch = chapters_by_id.get(ref_id)
        if not ref_ch:
            continue
        title = ref_ch.get("title", "")
        summary = summaries.get(str(ref_id), "")
        synopsis = ref_ch.get("synopsis", "")
        if summary:
            parts.append(f"【{title}】{summary}")
        elif synopsis:
            parts.append(f"【{title}】{synopsis}")

    return "\n".join(parts) if parts else None


def _build_neighborhood_context(
    project_dir: Path,
    outline: dict[str, Any],
    chapter: dict[str, Any],
    window: int = 3,
) -> str | None:
    """构建±3章邻域上下文：state.json摘要 + 大纲一致性对比。

    目的：
    1. 防止上下文截断导致遗忘邻近章节细节
    2. 对比大纲(写前计划)与摘要(写后总结)，发现偏离时提醒模型
    """
    cid = int(float(chapter["id"]))
    st = state.load(project_dir)
    summaries = st.get("summaries", {})
    chapters_by_id = {int(float(c["id"])): c for c in outline.get("chapters", [])}

    neighbor_ids = [
        n for n in range(cid - window, cid + window + 1)
        if n != cid and n > 0 and n in chapters_by_id
    ]

    if not neighbor_ids:
        return None

    parts = []
    drift_warnings = []

    for nid in sorted(neighbor_ids):
        n_ch = chapters_by_id[nid]
        title = n_ch.get("title", "")
        synopsis = n_ch.get("synopsis", "")
        summary = summaries.get(str(nid), "")

        if not summary:
            continue

        rel = "前" if nid < cid else "后"
        dist = abs(nid - cid)
        parts.append(f"[{rel}{dist}章·{title}] {summary}")

        if synopsis and summary:
            syn_keys = set(synopsis.replace("，", " ").replace("。", " ").split())
            sum_keys = set(summary.replace("，", " ").replace("。", " ").split())
            overlap = syn_keys & sum_keys
            if len(syn_keys) > 3 and len(overlap) < len(syn_keys) * 0.15:
                drift_warnings.append(
                    f"⚠ ch.{nid}：大纲与实际摘要偏离较大\n"
                    f"  大纲: {synopsis[:80]}\n"
                    f"  实际: {summary[:80]}"
                )

    if not parts:
        return None

    result = "\n".join(parts)
    if drift_warnings:
        result += "\n\n### 一致性警告（以下章节实际内容与大纲有偏离，写作时注意衔接）\n"
        result += "\n".join(drift_warnings)

    return result


async def write_chapter(
    project_dir: Path,
    outline: dict[str, Any],
    chapter: dict[str, Any],
    *,
    force: bool = False,
) -> tuple[float | int, str]:
    """生成一章,返回 (chapter_id, status)"""
    cid = chapter["id"]
    out_path = chapter_path(project_dir, chapter)

    if not force and out_path.exists() and state.is_done(project_dir, cid):
        return cid, "skipped"

    priors = state.prior_summaries(project_dir, cid)
    followings = state.following_summaries(project_dir, cid) if _is_insert(cid) else None

    neighbor_excerpts = None
    if _is_insert(cid):
        prev_tail, next_head, prev_ch, next_ch = _load_neighbor_excerpts(
            project_dir, outline, float(cid)
        )
        if prev_tail or next_head:
            neighbor_excerpts = {
                "prev_tail": prev_tail,
                "next_head": next_head,
                "prev_meta": prev_ch,
                "next_meta": next_ch,
            }
    else:
        prev_tail, _, _, _ = _load_neighbor_excerpts(
            project_dir, outline, float(cid), head_chars=0
        )
        if prev_tail:
            neighbor_excerpts = {
                "prev_tail": prev_tail,
                "next_head": None,
                "prev_meta": None,
                "next_meta": None,
            }

    cross_ref_context = _build_cross_ref_context(project_dir, outline, chapter)
    neighborhood_context = _build_neighborhood_context(project_dir, outline, chapter)
    profile_context = profiles.build_context_block(project_dir, float(cid)) or None

    # Lorebook 激活
    lorebook_context = _build_lorebook_context(project_dir, outline, chapter, priors)

    msgs = prompts.build_chapter_messages(
        outline, chapter, priors, followings,
        neighbor_excerpts=neighbor_excerpts,
        profile_context=profile_context,
        cross_ref_context=cross_ref_context,
        neighborhood_context=neighborhood_context,
        lorebook_context=lorebook_context,
    )

    # 写出 context report（仅 CONTEXT_REPORT=1 时生成）
    if os.environ.get("CONTEXT_REPORT", "0") not in ("0", "false", "False", ""):
        _write_context_report(
            project_dir, cid, priors, followings,
            cross_ref_context, neighborhood_context,
            profile_context, neighbor_excerpts, msgs,
        )

    try:
        body = await llm.chat(msgs)
    except Exception as e:
        return cid, f"failed:body:{e}"

    body = body.strip()
    body = _strip_meta_annotations(body)
    if not body:
        return cid, "failed:empty-body"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if _is_insert(cid):
        header = f"# 番外 {chapter.get('title', '')} (插入于 {cid})\n\n"
    else:
        header = f"# 第{int(cid) if isinstance(cid, float) else cid}章 {chapter.get('title', '')}\n\n"

    out_path.write_text(header + body + "\n", encoding="utf-8")

    try:
        summary = await llm.chat(
            prompts.build_summary_messages(body),
            temperature=0.3,
            max_tokens=400,
        )
        summary = summary.strip()
    except Exception as e:
        summary = chapter.get("synopsis", "")[:200] + f" (摘要失败: {e})"

    state.mark_done(project_dir, cid, summary)
    return cid, "written"


def _write_context_report(
    project_dir: Path,
    cid: float | int,
    priors: list,
    followings: list | None,
    cross_ref_context: str | None,
    neighborhood_context: str | None,
    profile_context: str | None,
    neighbor_excerpts: dict | None,
    msgs: list[dict[str, str]],
) -> None:
    """输出 context_report JSON，记录本次组装详情。"""
    budget = TokenBudget()
    total_chars = sum(len(m["content"]) for m in msgs)
    est_tokens = int(total_chars * 0.6)

    report = {
        "chapter_id": cid,
        "model": budget.model,
        "token_budget": budget.available_for_context(),
        "estimated_tokens_used": est_tokens,
        "blocks": [
            {"id": "prior_summaries", "count": len(priors), "included": True},
            {"id": "following_summaries", "count": len(followings) if followings else 0, "included": followings is not None},
            {"id": "cross_ref", "included": cross_ref_context is not None},
            {"id": "neighborhood", "included": neighborhood_context is not None},
            {"id": "profile", "included": profile_context is not None},
            {"id": "neighbor_excerpts", "included": neighbor_excerpts is not None},
        ],
    }

    label = f"{int(cid):03d}" if isinstance(cid, float) and cid.is_integer() else f"{cid:g}".replace(".", "_")
    report_path = project_dir / "state" / f"context_report_ch{label}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def _build_lorebook_context(
    project_dir: Path,
    outline: dict[str, Any],
    chapter: dict[str, Any],
    priors: list[tuple[float, str]],
) -> str | None:
    """激活世界书条目，返回格式化文本或 None。"""
    try:
        from .lorebook import Lorebook
    except ImportError:
        return None

    lb = Lorebook(project_dir)
    if not lb.entries:
        return None

    scan_text = lb.build_scan_text(chapter, priors, outline)
    activated = lb.activate(scan_text, float(chapter["id"]))
    if not activated:
        return None

    return lb.to_context_string(activated)
