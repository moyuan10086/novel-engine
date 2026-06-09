# -*- coding: utf-8 -*-
"""质量检查与自动修复 — 检测偏短章节并自动重跑。

用法:
    python -m src.quality_check --project "配角阅读器"
    python -m src.quality_check --project "配角阅读器" --min-words 2500 --max-retries 3
    python -m src.quality_check --project "配角阅读器" --check-only  # 只检查不重跑

功能:
  1. 扫描所有已生成章节，统计字数
  2. 找出低于阈值的偏短章节
  3. 自动重跑偏短章节（可设最大重试次数）
  4. 检测元注释泄露、破墙引用等质量问题
  5. 重跑后重新合并 book.md
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "projects"
load_dotenv(ROOT / ".env")

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


def get_project_path(project_name: str | None = None) -> Path:
    if not project_name:
        default_file = ROOT / ".default_project"
        if default_file.exists():
            project_name = default_file.read_text(encoding="utf-8").strip()
        else:
            print("[错误] 请通过 --project 指定项目名")
            sys.exit(1)
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        print(f"[错误] 项目不存在: {project_name}")
        sys.exit(1)
    return project_dir


def scan_chapters(project_dir: Path) -> list[dict]:
    """扫描所有章节，返回 [{id, filename, body_len, issues}]"""
    chapters_dir = project_dir / "chapters"
    if not chapters_dir.exists():
        return []

    results = []
    for f in sorted(chapters_dir.glob("ch*.md")):
        text = f.read_text(encoding="utf-8")
        lines = text.split("\n", 2)
        body = lines[2] if len(lines) > 2 else text

        # 提取章节号
        m = re.search(r"ch(\d+)", f.name)
        cid = int(m.group(1)) if m else 0

        # 检测质量问题
        issues = []

        # 元注释
        for pat in [r"（情感悬念", r"（真相悬念", r"（字数[：:]", r"（注[：:]"]:
            if re.search(pat, body):
                issues.append("元注释泄露")
                break

        # 破墙（排除标题行）
        if re.search(r"第[一二三四五六七八九十0-9]+章", body):
            # 排除角色口语化回忆（如"第一次"不算）
            matches = re.findall(r"第[一二三四五六七八九十0-9]+章", body)
            real_breaks = [m for m in matches if "第一章" not in m or "里" in body[body.find(m)-5:body.find(m)]]
            if real_breaks:
                issues.append("破墙引用")

        # 隐藏信息泄露
        for phrase in ["好好演，作者", "你是作者", "原作者", "现实中已死"]:
            if phrase in body and cid <= 35:
                issues.append(f"隐藏信息泄露:{phrase}")
                break

        results.append({
            "id": cid,
            "filename": f.name,
            "path": f,
            "body_len": len(body),
            "issues": issues,
        })

    return results


def print_report(results: list[dict], min_words: int) -> list[int]:
    """打印质量报告，返回需要重跑的章节 ID 列表"""
    total_words = sum(r["body_len"] for r in results)
    short = [r for r in results if r["body_len"] < min_words]
    has_issues = [r for r in results if r["issues"]]

    print(f"=== 质量检查报告 ===")
    print(f"总章数: {len(results)}")
    print(f"总字数: {total_words:,} 字")
    print(f"平均每章: {total_words // len(results) if results else 0} 字")
    print(f"目标字数: >= {min_words} 字/章")
    print()

    if short:
        print(f"偏短章节 (<{min_words}字): {len(short)} 章")
        for r in short:
            print(f"  ch{r['id']:03d}: {r['body_len']:5d} 字  {r['filename'][:40]}")
        print()

    if has_issues:
        print(f"质量问题: {len(has_issues)} 章")
        for r in has_issues:
            print(f"  ch{r['id']:03d}: {', '.join(r['issues'])}")
        print()

    # 需要重跑的：偏短 + 有质量问题
    rerun_ids = set()
    for r in short:
        rerun_ids.add(r["id"])
    for r in has_issues:
        rerun_ids.add(r["id"])

    if not rerun_ids:
        print("[OK] 所有章节质量达标")
    else:
        print(f"需要重跑: {len(rerun_ids)} 章")
        print(f"章节号: {sorted(rerun_ids)}")

    return sorted(rerun_ids)


async def rerun_chapters(project_dir: Path, chapter_ids: list[int], concurrency: int) -> int:
    """重跑指定章节"""
    from . import worker

    outline_path = project_dir / "outline.json"
    outline = json.loads(outline_path.read_text(encoding="utf-8"))

    chapters_to_run = [
        c for c in outline.get("chapters", [])
        if int(float(c.get("id", 0))) in chapter_ids
    ]

    if not chapters_to_run:
        print("[WARN] 没有找到对应的大纲章节")
        return 0

    sem = asyncio.Semaphore(concurrency)
    failures = 0

    async def run_one(ch):
        nonlocal failures
        async with sem:
            cid, status = await worker.write_chapter(project_dir, outline, ch, force=True)
            label = f"ch{int(cid):03d}" if isinstance(cid, (int, float)) else f"ch{cid}"
            if status == "written":
                print(f"  {label} -> OK")
            else:
                print(f"  {label} -> {status}")
                failures += 1

    print(f"[INFO] 重跑 {len(chapters_to_run)} 章 (并发 {concurrency}) ...")
    await asyncio.gather(*(run_one(ch) for ch in chapters_to_run))
    return failures


def main():
    ap = argparse.ArgumentParser(description="质量检查与自动修复")
    ap.add_argument("--project", type=str, help="项目名称")
    ap.add_argument("--min-words", type=int, default=2500,
                    help="最低字数阈值（默认 2500）")
    ap.add_argument("--max-retries", type=int, default=2,
                    help="最大重试轮数（默认 2）")
    ap.add_argument("--concurrency", type=int,
                    default=int(os.environ.get("CONCURRENCY", "5")))
    ap.add_argument("--check-only", action="store_true",
                    help="只检查不重跑")
    ap.add_argument("--merge", action="store_true", default=True,
                    help="修复后自动合并 book.md（默认开启）")
    args = ap.parse_args()

    project_dir = get_project_path(args.project)

    for attempt in range(1, args.max_retries + 1):
        print(f"\n{'='*50}")
        print(f"第 {attempt} 轮检查")
        print(f"{'='*50}\n")

        results = scan_chapters(project_dir)
        if not results:
            print("[错误] 没有找到章节文件")
            sys.exit(1)

        rerun_ids = print_report(results, args.min_words)

        if not rerun_ids:
            break

        if args.check_only:
            print("\n[INFO] --check-only 模式，不自动重跑")
            break

        print(f"\n[INFO] 开始第 {attempt} 轮自动重跑...")
        failures = asyncio.run(rerun_chapters(project_dir, rerun_ids, args.concurrency))

        if failures:
            print(f"[WARN] 本轮有 {failures} 章生成失败")

    # 最终报告
    print(f"\n{'='*50}")
    print("最终检查")
    print(f"{'='*50}\n")
    results = scan_chapters(project_dir)
    final_rerun = print_report(results, args.min_words)

    if final_rerun:
        print(f"\n[WARN] 仍有 {len(final_rerun)} 章未达标（可能需要调整大纲或增加 max-retries）")
    else:
        print("\n[OK] 全部章节质量达标!")

    # 合并
    if args.merge and not args.check_only:
        print("\n[INFO] 合并 book.md ...")
        from . import merger
        merger.merge(project_dir)


if __name__ == "__main__":
    main()
