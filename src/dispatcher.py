"""调度器 — 支持多项目（--project）"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "projects"

# 支持 --project 参数
def get_project_path(project_name: str | None = None) -> Path:
    if not project_name:
        # 读取默认项目
        default_file = ROOT / ".default_project"
        if default_file.exists():
            project_name = default_file.read_text(encoding="utf-8").strip()
        else:
            project_name = "反派模拟器"  # 默认项目

    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        print(f"[错误] 项目不存在: {project_name}")
        print(f"可用项目: {[p.name for p in PROJECTS_DIR.iterdir() if p.is_dir()]}")
        sys.exit(1)

    return project_dir


def main() -> None:
    ap = argparse.ArgumentParser(description="novel-engine 多小说并发章节生成器")
    ap.add_argument("--project", type=str, help="指定项目名称 (默认: 反派模拟器 或 .default_project)")
    ap.add_argument("--mode", choices=["strict", "window", "parallel"], default="window")
    ap.add_argument("--window", type=int, default=1, help="window 模式下串行预热的章节数")
    ap.add_argument("--concurrency", type=int,
                    default=int(os.environ.get("CONCURRENCY", "3")))
    ap.add_argument("--only", type=str, default="",
                    help="只跑指定 id,逗号分隔,支持小数(如 1,3.5,5)")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的章节")
    args = ap.parse_args()

    project_dir = get_project_path(args.project)
    outline_path = project_dir / "outline.json"
    load_dotenv(ROOT / ".env")   # 加载引擎配置

    from . import worker

    async def run() -> int:
        if not outline_path.exists():
            print(f"[错误] 未找到 outline.json: {outline_path}")
            return 1

        outline = json.loads(outline_path.read_text(encoding="utf-8"))
        chapters = outline.get("chapters", [])

        if args.only:
            only_set = {float(x.strip()) for x in args.only.split(",") if x.strip()}
            chapters = [c for c in chapters if float(c.get("id", 0)) in only_set]

        chapters.sort(key=lambda c: float(c.get("id", 0)))

        if not chapters:
            print("没有要写的章节。")
            return 0

        sem = asyncio.Semaphore(args.concurrency)

        async def guarded(ch: dict[str, Any]):
            async with sem:
                cid, status = await worker.write_chapter(
                    project_dir, outline, ch, force=args.force
                )
                label = f"{cid:g}" if isinstance(cid, float) else f"{cid:03d}"
                print(f"  ch{label} -> {status}", flush=True)
                return cid, status

        failures = 0

        if args.mode == "strict":
            for ch in chapters:
                _, status = await guarded(ch)
                if status.startswith("failed"):
                    failures += 1
        elif args.mode == "window":
            head = chapters[:args.window]
            tail = chapters[args.window:]
            print(f"[串行预热] {len(head)} 章 ...")
            for ch in head:
                _, status = await guarded(ch)
                if status.startswith("failed"):
                    failures += 1
            if tail:
                print(f"[并发] 剩余 {len(tail)} 章,并发上限 {args.concurrency} ...")
                results = await asyncio.gather(
                    *(guarded(ch) for ch in tail), return_exceptions=True
                )
                for r in results:
                    if isinstance(r, Exception) or (isinstance(r, tuple) and r[1].startswith("failed")):
                        failures += 1
        else:  # parallel
            results = await asyncio.gather(
                *(guarded(ch) for ch in chapters), return_exceptions=True
            )
            for r in results:
                if isinstance(r, Exception) or (isinstance(r, tuple) and r[1].startswith("failed")):
                    failures += 1

        print(f"\n项目 [{project_dir.name}] 完成: 总章节 {len(chapters)}, 失败 {failures}。")
        return failures

    failures = asyncio.run(run())
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
