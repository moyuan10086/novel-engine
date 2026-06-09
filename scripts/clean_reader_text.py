#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Clean a merged novel text into a reader-facing draft.

This is intentionally conservative: it removes obvious generation/meta
artifacts and missing-chapter placeholders, but does not rewrite plot prose.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


META_LINE_RE = re.compile(
    r"^\s*[（(][^）)\n]*(?:"
    r"本章(?:正文)?字数|正文字数|字数统计|word count|"
    r"以下为|继续展开|扩展正文|扩展叙述|扩展描写|确保字数|"
    r"响应要求|核心节拍|严格按大纲|无任何元标注|本章正文已|"
    r"4成情感|6成冲突|情感4成|节奏4成|字数已超|"
    r"本章亮点|本章主要|备注|说明"
    r")[^）)]*[）)]\s*$",
    re.IGNORECASE,
)


def _chapter_no_from_toc(line: str) -> int | None:
    m = re.match(r"^\s+第(\d+)章\b", line)
    if not m:
        return None
    return int(m.group(1))


def _strip_missing_body(text: str) -> tuple[str, int]:
    """Remove body blocks like '第153章 ...\n\n(章节文件缺失)' to EOF."""
    marker = re.search(r"\n第\d+章[^\n]*\n\s*\n\(章节文件缺失\)", text)
    if not marker:
        return text, 0
    removed = text[marker.start():]
    count = removed.count("(章节文件缺失)")
    return text[: marker.start()].rstrip() + "\n", count


def clean_text(text: str, max_chapter: int | None = None) -> tuple[str, dict[str, int]]:
    text, missing_count = _strip_missing_body(text)

    removed_meta = 0
    removed_toc = 0
    kept_lines: list[str] = []

    for line in text.splitlines():
        ch_no = _chapter_no_from_toc(line)
        if max_chapter is not None and ch_no is not None and ch_no > max_chapter:
            removed_toc += 1
            continue

        stripped = line.strip()
        if META_LINE_RE.match(line):
            removed_meta += 1
            continue

        if (
            stripped.startswith(("（", "("))
            and any(
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
            )
        ):
            removed_meta += 1
            continue

        # Remove standalone expansion directives that escaped parentheses.
        if re.match(r"^\s*(?:以下为|扩展)(?:继续)?(?:展开|正文|叙述|描写)", line):
            removed_meta += 1
            continue

        if re.search(r"4成情感|6成冲突|情感4成|情感铺4成|节奏4成|本章正文已充分", line):
            removed_meta += 1
            continue

        line = line.replace("情感悬念", "情感上的不安")
        line = line.replace("真相线悬念", "真相线上的疑问")
        line = line.replace("真相悬念", "更深的疑问")
        kept_lines.append(line.rstrip())

    cleaned = "\n".join(kept_lines)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned).rstrip() + "\n"
    stats = {
        "missing_blocks_removed": missing_count,
        "toc_lines_removed": removed_toc,
        "meta_lines_removed": removed_meta,
    }
    return cleaned, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean merged novel text for readers.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-chapter", type=int)
    args = parser.parse_args()

    src = args.path
    dst = args.output or src
    text = src.read_text(encoding="utf-8")
    cleaned, stats = clean_text(text, args.max_chapter)
    dst.write_text(cleaned, encoding="utf-8")
    print(f"[OK] cleaned -> {dst}")
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
