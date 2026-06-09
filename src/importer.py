"""导入已有长篇小说 — 切章 + 抽摘要 + 写入 state/outline。

已适配多项目架构（--project 参数）。

用法:
    python -m src.importer --project "斗罗黄金龙" --src novel.txt
    python -m src.importer --project "斗罗黄金龙" --src novel.txt --skip-summary
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "projects"
load_dotenv(ROOT / ".env")

from . import llm, prompts, state, worker  # noqa: E402

DEFAULT_PATTERN = r"^第[一二三四五六七八九十百千万零〇\d]+[章回]"


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
        # 自动创建
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "chapters").mkdir(exist_ok=True)
        (project_dir / "state").mkdir(exist_ok=True)
        (project_dir / "state" / "state.json").write_text(
            json.dumps({"summaries": {}, "done": []}, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[OK] 自动创建项目: {project_dir}")

    return project_dir


def split_chapters(text: str, pattern: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    rx = re.compile(pattern)
    indices: list[int] = []
    for i, ln in enumerate(lines):
        if rx.match(ln.strip()):
            indices.append(i)

    if not indices:
        return []

    chapters: list[tuple[str, str]] = []
    for k, start in enumerate(indices):
        end = indices[k + 1] if k + 1 < len(indices) else len(lines)
        title = lines[start].strip()
        body = "\n".join(lines[start + 1 : end]).strip()
        if body:
            chapters.append((title, body))
    return chapters


def parse_title(title_line: str) -> tuple[str, str]:
    m = re.match(r"^第([一二三四五六七八九十百千万零〇\d]+)[章回]\s*[:：]?\s*(.*)$", title_line)
    if not m:
        return title_line, ""
    num_str, name = m.group(1), m.group(2).strip()
    return num_str, name


_CN_NUM = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
           "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_to_int(s: str) -> int | None:
    if s.isdigit():
        return int(s)
    total = 0
    section = 0
    current = 0
    for ch in s:
        if ch in _CN_NUM:
            current = _CN_NUM[ch]
        elif ch == "十":
            section += (current or 1) * 10
            current = 0
        elif ch == "百":
            section += (current or 1) * 100
            current = 0
        elif ch == "千":
            section += (current or 1) * 1000
            current = 0
        elif ch == "万":
            total += (section + current) * 10000
            section = 0
            current = 0
        else:
            return None
    return total + section + current


async def summarize(body: str) -> str:
    msgs = prompts.build_summary_messages(body[:6000])
    try:
        return (await llm.chat(msgs, temperature=0.3, max_tokens=400)).strip()
    except Exception as e:
        return f"(摘要失败: {e})"


async def import_novel(
    project_dir: Path,
    src: Path,
    pattern: str,
    concurrency: int,
    skip_summary: bool,
    base_id: int,
) -> int:
    text = src.read_text(encoding="utf-8", errors="replace")
    chunks = split_chapters(text, pattern)
    if not chunks:
        print(f"[WARN] 没匹配到章节标题(pattern={pattern!r})。")
        return 1
    print(f"切出 {len(chunks)} 章。")

    parsed: list[tuple[int, str, str]] = []
    for i, (title_line, body) in enumerate(chunks):
        num_str, name = parse_title(title_line)
        n = None
        if num_str.isdigit():
            n = int(num_str)
        else:
            n = cn_to_int(num_str)
        if n is None:
            n = base_id + i
        else:
            n = base_id + n - 1 if base_id > 1 else n
        parsed.append((n, name or f"导入章{n}", body))

    seen = set()
    final: list[tuple[int, str, str]] = []
    for n, name, body in parsed:
        while n in seen:
            n += 1
        seen.add(n)
        final.append((n, name, body))
    final.sort(key=lambda x: x[0])

    sem = asyncio.Semaphore(concurrency)

    async def handle(n: int, name: str, body: str) -> tuple[int, str, str]:
        chapter_dict = {"id": n, "title": name}
        out_path = worker.chapter_path(project_dir, chapter_dict)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        header = f"# 第{n}章 {name}\n\n"
        out_path.write_text(header + body.strip() + "\n", encoding="utf-8")
        if skip_summary:
            summary = body.strip()[:200]
        else:
            async with sem:
                summary = await summarize(body)
        state.mark_done(project_dir, n, summary)
        return n, name, "ok"

    print(f"处理中(并发上限 {concurrency}) ...")
    results = await asyncio.gather(*(handle(n, name, body) for n, name, body in final))
    for n, name, status in results:
        print(f"  ch{n:03d} {name[:20]:<20} -> {status}")

    # 写 outline.json
    outline_path = project_dir / "outline.json"
    if outline_path.exists():
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
    else:
        outline = {
            "meta": {
                "title": src.stem,
                "genre": "同人续写",
                "target_words_per_chapter": 3000,
                "language": "zh-CN",
                "style_notes": [],
            },
            "world": {"setting": "(从导入的小说中提取,请补充)", "rules": []},
            "characters": [],
            "chapters": [],
        }

    existing_ids = {float(c["id"]) for c in outline.get("chapters", [])}
    added = 0
    for n, name, _ in final:
        if float(n) in existing_ids:
            continue
        outline["chapters"].append({
            "id": n,
            "title": name,
            "synopsis": "(已从原文导入)",
            "key_beats": [],
            "pov": "",
            "imported": True,
        })
        added += 1
    outline["chapters"].sort(key=lambda c: float(c["id"]))
    outline_path.write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] 导入完成: 共 {len(final)} 章, outline 新增 {added} 章")
    print(f"项目路径: {project_dir}")
    print(f"续写方式: 在 outline.json 中追加新章节, 然后:")
    print(f"  python -m src.dispatcher --project \"{project_dir.name}\" --only <新章节id>")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="导入已有小说到项目中")
    ap.add_argument("--project", type=str, help="项目名称(不存在则自动创建)")
    ap.add_argument("--src", required=True, help="源 .txt 文件路径")
    ap.add_argument("--pattern", default=DEFAULT_PATTERN, help="章节标题正则")
    ap.add_argument("--concurrency", type=int,
                    default=int(os.environ.get("CONCURRENCY", "3")))
    ap.add_argument("--skip-summary", action="store_true",
                    help="跳过LLM摘要(用每章前200字代替,速度快)")
    ap.add_argument("--base-id", type=int, default=1)
    args = ap.parse_args()

    src = Path(args.src)
    if not src.exists():
        print(f"[错误] 找不到文件: {src}", file=sys.stderr)
        sys.exit(2)

    project_dir = get_project_path(args.project)

    rc = asyncio.run(import_novel(
        project_dir, src, args.pattern, args.concurrency, args.skip_summary, args.base_id
    ))
    sys.exit(rc)


if __name__ == "__main__":
    main()
