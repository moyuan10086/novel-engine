"""合并器 — 支持多项目（--project）"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from . import worker

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "projects"


def get_project_path(project_name: str | None = None) -> Path:
    """获取项目路径（与 dispatcher 保持一致）"""
    if not project_name:
        default_file = ROOT / ".default_project"
        if default_file.exists():
            project_name = default_file.read_text(encoding="utf-8").strip()
        else:
            project_name = "反派模拟器"

    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        print(f"[错误] 项目不存在: {project_name}")
        print(f"可用项目: {[p.name for p in PROJECTS_DIR.iterdir() if p.is_dir()]}")
        sys.exit(1)
    return project_dir


def _fmt_id(cid: float | int) -> str:
    if isinstance(cid, float) and not cid.is_integer():
        return f"{cid:g}"
    return str(int(cid))


def _is_insert(cid: float | int) -> bool:
    return isinstance(cid, float) and not cid.is_integer()


def _md_to_txt(md: str) -> str:
    out = md
    out = re.sub(r"^#{1,6}\s*", "", out, flags=re.MULTILINE)
    out = out.replace("`", "")
    out = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"\1", out)
    out = re.sub(r"__([^_]+)__", r"\1", out)
    out = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", out)
    out = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"\1", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def _clean_reader_text(text: str) -> str:
    """Apply final reader-facing cleanup to merged chapter body."""
    text = worker._strip_meta_annotations(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def merge(project_dir: Path) -> None:
    outline_path = project_dir / "outline.json"
    if not outline_path.exists():
        print(f"❌ 未找到 outline.json: {outline_path}")
        return

    outline = json.loads(outline_path.read_text(encoding="utf-8"))
    chapters = sorted(outline.get("chapters", []), key=lambda c: float(c.get("id", 0)))
    title = outline["meta"].get("title", "Untitled")

    md_parts: list[str] = [f"# {title}\n", "## 目录\n"]
    txt_parts: list[str] = [title, "", "目  录", ""]

    existing_chapters = [ch for ch in chapters if worker.chapter_path(project_dir, ch).exists()]
    skipped_chapters = [ch.get("id", 0) for ch in chapters if not worker.chapter_path(project_dir, ch).exists()]

    for ch in existing_chapters:
        cid = ch.get("id", 0)
        label = "番外" if _is_insert(cid) else f"第{_fmt_id(cid)}章"
        md_parts.append(f"- {label} {ch.get('title', '')}")
        txt_parts.append(f"  {label} {ch.get('title', '')}")
    md_parts.append("\n---\n")
    txt_parts.append("")
    txt_parts.append("=" * 40)
    txt_parts.append("")

    missing: list = []
    for ch in existing_chapters:
        path = worker.chapter_path(project_dir, ch)
        cid = ch.get("id", 0)
        label = "番外" if _is_insert(cid) else f"第{_fmt_id(cid)}章"
        title = ch.get("title", "")

        raw = path.read_text(encoding="utf-8").rstrip()
        lines = raw.split("\n", 2)
        body = lines[2] if len(lines) > 2 else raw

        clean_body = _clean_reader_text(body)
        md_parts.append(f"\n# {label} {title}\n\n{clean_body}\n")
        txt_parts.append("")
        txt_parts.append(f"{label} {title}")
        txt_parts.append("")
        txt_parts.append(_md_to_txt(clean_body).strip())
        txt_parts.append("")

    out_md = project_dir / "book.md"
    out_txt = project_dir / "book.txt"

    out_md.write_text("\n".join(md_parts), encoding="utf-8")
    out_txt.write_text("\n".join(txt_parts).rstrip() + "\n", encoding="utf-8")

    print(f"[OK] 项目 [{project_dir.name}] 合并完成")
    print(f"   -> {out_md}")
    print(f"   -> {out_txt}")
    if skipped_chapters:
        print(f"[WARN] 已跳过缺失章节: {skipped_chapters}")


def main() -> None:
    ap = argparse.ArgumentParser(description="novel-engine 多项目合并器")
    ap.add_argument("--project", type=str, help="项目名称 (默认使用 .default_project)")
    args = ap.parse_args()

    project_dir = get_project_path(args.project)
    merge(project_dir)


if __name__ == "__main__":
    main()
