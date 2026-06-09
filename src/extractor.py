"""Outline-Extract — 从原书提炼参考蓝图（结构 / 技法 / 桥段 / 表达模式）。

用法:
    python -m src.extractor --src "原书.txt" --output "参考蓝图.md"
    python -m src.extractor --src "原书.txt" --output "参考蓝图.md" --sample 30
    python -m src.extractor --src "原书.txt" --output "参考蓝图.md" --concurrency 5

设计原则:
- 不复制、不换皮、不重写。
- 仅提炼"类型化"的结构与写法，作为作者自己创作时的参考。
- 输出参考蓝图 markdown，作者读完后基于此自由发挥。
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
load_dotenv(ROOT / ".env")

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

from . import llm, prompts  # noqa: E402

DEFAULT_PATTERN = r"^第[一二三四五六七八九十百千万零〇\d]+[章回]"


def split_chapters(text: str, pattern: str) -> list[tuple[str, str]]:
    """切章：返回 [(title_line, body), ...]"""
    lines = text.splitlines()
    rx = re.compile(pattern)
    indices = [i for i, ln in enumerate(lines) if rx.match(ln.strip())]
    if not indices:
        return []
    chapters = []
    for k, start in enumerate(indices):
        end = indices[k + 1] if k + 1 < len(indices) else len(lines)
        title = lines[start].strip()
        body = "\n".join(lines[start + 1:end]).strip()
        if body:
            chapters.append((title, body))
    return chapters


def _parse_json_lenient(text: str) -> dict | None:
    """容忍 LLM 输出周围的杂物（markdown 代码块等）。"""
    text = text.strip()
    # 去除 markdown code fence
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    # 找到第一个 { 和最后一个 }
    s = text.find("{")
    e = text.rfind("}")
    if s == -1 or e == -1:
        return None
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return None


async def extract_one(idx: int, title: str, body: str, sem: asyncio.Semaphore) -> dict:
    """对单章做 outline-extract。返回结构化数据。"""
    # 限制 body 长度，避免超长 prompt
    body_for_extract = body[:8000]
    msgs = prompts.build_outline_extract_messages(body_for_extract)

    async with sem:
        try:
            resp = await llm.chat(msgs, temperature=0.4, max_tokens=900)
        except Exception as e:
            return {
                "chapter_idx": idx,
                "title": title,
                "error": f"LLM 调用失败: {e}",
            }

    parsed = _parse_json_lenient(resp)
    if parsed is None:
        return {
            "chapter_idx": idx,
            "title": title,
            "error": "JSON 解析失败",
            "raw": resp[:300],
        }

    parsed["chapter_idx"] = idx
    parsed["title"] = title
    return parsed


def _build_summary_for_synthesis(extracts: list[dict]) -> str:
    """将多章提炼结果格式化为给 synthesis prompt 用的文本。"""
    lines = []
    for ex in extracts:
        if "error" in ex:
            continue
        idx = ex.get("chapter_idx", "?")
        skel = ex.get("skeleton", "")
        tps = ex.get("turning_points", [])
        tropes = ex.get("trope_types", [])
        pacing = ex.get("pacing_notes", "")
        tech = ex.get("technique_notes", "")
        exprs = ex.get("expression_patterns", [])
        emo = ex.get("emotion_arc", "")
        hook = ex.get("hook_style", "")

        lines.append(f"### 第{idx}章")
        lines.append(f"- 骨架: {skel}")
        if tps:
            lines.append(f"- 转折点: {', '.join(tps)}")
        if tropes:
            lines.append(f"- 桥段类型: {', '.join(tropes)}")
        if pacing:
            lines.append(f"- 节奏: {pacing}")
        if tech:
            lines.append(f"- 技法: {tech}")
        if exprs:
            lines.append(f"- 表达模式: {'; '.join(exprs)}")
        if emo:
            lines.append(f"- 情绪曲线: {emo}")
        if hook:
            lines.append(f"- 钩子类型: {hook}")
        lines.append("")
    return "\n".join(lines)


async def synthesize_blueprint(extracts: list[dict]) -> str:
    """把所有章节的提炼结果汇总成最终蓝图文档。"""
    summary_text = _build_summary_for_synthesis(extracts)
    if len(summary_text) > 60000:
        summary_text = summary_text[:60000] + "\n\n[此处省略后续章节,数据已超长]"

    msgs = prompts.build_blueprint_synthesis_messages(summary_text)
    resp = await llm.chat(msgs, temperature=0.5, max_tokens=4000)
    return resp.strip()


async def run_extract(
    src: Path,
    output: Path,
    pattern: str,
    sample: int | None,
    concurrency: int,
    raw_output: Path | None,
) -> int:
    text = src.read_text(encoding="utf-8", errors="replace")
    chunks = split_chapters(text, pattern)
    if not chunks:
        print(f"[WARN] 没匹配到章节标题(pattern={pattern!r})")
        return 1

    total = len(chunks)
    print(f"[INFO] 切出 {total} 章")

    if sample and sample < total:
        # 均匀采样：开头/中段/结尾各取一些，避免只看前 N 章
        step = max(1, total // sample)
        selected = [(i, chunks[i]) for i in range(0, total, step)][:sample]
        print(f"[INFO] 均匀采样 {len(selected)} 章 (step={step})")
    else:
        selected = list(enumerate(chunks))

    sem = asyncio.Semaphore(concurrency)

    print(f"[INFO] 提炼中 (并发 {concurrency}) ...")
    tasks = [extract_one(idx + 1, title, body, sem) for idx, (title, body) in selected]
    extracts = await asyncio.gather(*tasks)

    ok = sum(1 for ex in extracts if "error" not in ex)
    fail = len(extracts) - ok
    print(f"[INFO] 提炼完成: 成功 {ok} 章, 失败 {fail} 章")

    # 保存原始 JSON（便于复跑/调试）
    if raw_output:
        raw_output.parent.mkdir(parents=True, exist_ok=True)
        raw_output.write_text(
            json.dumps(extracts, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"[OK] 原始提炼数据 -> {raw_output}")

    # 汇总成蓝图
    print("[INFO] 整合成参考创作蓝图 ...")
    blueprint = await synthesize_blueprint(extracts)

    # 加上头部说明
    header = f"""# 创作参考蓝图

> **来源**: `{src.name}`
> **提炼章节数**: {len(extracts)} / {total}
> **使用说明**: 这是一份**参考创作蓝图**。它提炼了原书的结构、节奏、桥段类型与写作技法，但**不包含原书的角色名、地名、招式名等专有内容**。请基于这份蓝图，结合你自己的世界观与人物设定，重新创作属于你的小说。
>
> **重要**: 不要将原书内容直接搬运或换皮。这份文档是用于学习写法、参考节奏的工具，不是用于洗稿。

---

"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(header + blueprint + "\n", encoding="utf-8")
    print(f"[OK] 参考蓝图 -> {output}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Outline-Extract: 从原书提炼参考创作蓝图")
    ap.add_argument("--src", required=True, help="原书 .txt 路径")
    ap.add_argument("--output", required=True, help="输出蓝图 .md 路径")
    ap.add_argument("--pattern", default=DEFAULT_PATTERN, help="章节标题正则")
    ap.add_argument("--sample", type=int, default=30,
                    help="均匀采样多少章(默认30,设0或大于总章数=全部)")
    ap.add_argument("--concurrency", type=int,
                    default=int(os.environ.get("CONCURRENCY", "3")))
    ap.add_argument("--raw-output", default="",
                    help="可选:把每章原始提炼JSON保存到这里")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.exists():
        print(f"[错误] 找不到文件: {src}")
        sys.exit(2)

    sample = None if args.sample <= 0 else args.sample
    raw = Path(args.raw_output) if args.raw_output else None

    rc = asyncio.run(run_extract(
        src=src,
        output=Path(args.output),
        pattern=args.pattern,
        sample=sample,
        concurrency=args.concurrency,
        raw_output=raw,
    ))
    sys.exit(rc)


if __name__ == "__main__":
    main()
