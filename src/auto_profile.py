"""自动建档 — 从 state.json 的章节摘要里反向抽取角色档案、伏笔、关系。

用法:
    python -m src.auto_profile --project "_ref_xxx"

会做的事:
  1. 读 state/state.json 的所有章节摘要
  2. 让 LLM 分批扫描摘要，识别主要角色 + 状态变化点
  3. 写入 state/profiles.json

注意：这是从摘要级元数据推断，不会把原书原文搬进任何项目的 prompt。
仅用于「分析参考样本的角色演化曲线」。
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

from . import llm, profiles  # noqa: E402

PROJECTS_DIR = ROOT / "projects"


SCAN_SYSTEM = """你是一个"小说档案抽取器"。给你一段连续章节的摘要，请抽出本批次出现的角色信息和关键事件。

输出严格 JSON，不要 markdown 包裹：

{
  "characters": [
    {"name": "角色名", "first_seen_ch": 章号, "static": {"identity": "...", "性格": "..."}}
  ],
  "snapshots": [
    {"name": "角色名", "as_of_ch": 章号, "deltas": {"境界":"...","伴侣":"...","状态":"..."}, "note": "事件简述"}
  ],
  "foreshadowings": [
    {"raised_ch": 章号, "what": "伏笔内容", "importance": "low|medium|high"}
  ],
  "relationships": [
    {"a": "角色A", "b": "角色B", "kind": "关系类型", "since_ch": 章号}
  ]
}

抽取原则:
- 只抽**主要角色**（戏份多次出现），不要抽路人。
- snapshots 只在状态明显变化时记录（境界突破、关系突破、第一次、怀孕、死亡等）。
- 不要复制原文句子，用泛化语言描述。
- 如果某项没有明显事件可抽，对应数组返回 []。
"""


def _parse_json_lenient(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    s = text.find("{")
    e = text.rfind("}")
    if s == -1 or e == -1:
        return None
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return None


async def scan_batch(batch_summaries: list[tuple[float, str]], sem: asyncio.Semaphore) -> dict:
    """扫描一批摘要，抽出角色/状态/伏笔/关系。"""
    chunk_text = "\n\n".join(
        f"[第{int(c) if isinstance(c, float) and c.is_integer() else c}章] {s}"
        for c, s in batch_summaries
    )

    msgs = [
        {"role": "system", "content": SCAN_SYSTEM},
        {"role": "user", "content": f"以下是连续 {len(batch_summaries)} 章的摘要，请抽取档案数据：\n\n{chunk_text}"},
    ]

    async with sem:
        try:
            resp = await llm.chat(msgs, temperature=0.3, max_tokens=2000)
        except Exception as e:
            return {"error": str(e)}

    parsed = _parse_json_lenient(resp)
    return parsed or {"error": "JSON parse failed", "raw": resp[:300]}


async def auto_profile(project_dir: Path, batch_size: int, concurrency: int) -> int:
    state_path = project_dir / "state" / "state.json"
    if not state_path.exists():
        print(f"[错误] 未找到 state.json: {state_path}")
        return 1

    data = json.loads(state_path.read_text(encoding="utf-8"))
    summaries = data.get("summaries", {})
    if not summaries:
        print("[错误] 摘要为空")
        return 1

    items = sorted(
        ((float(k), v) for k, v in summaries.items()),
        key=lambda x: x[0]
    )

    # 分批
    batches = []
    for i in range(0, len(items), batch_size):
        batches.append(items[i:i + batch_size])

    print(f"[INFO] 共 {len(items)} 章，分 {len(batches)} 批，每批 {batch_size} 章")
    print(f"[INFO] 并发上限 {concurrency}")

    sem = asyncio.Semaphore(concurrency)
    print("[INFO] 扫描中 ...")

    tasks = [scan_batch(b, sem) for b in batches]
    results = await asyncio.gather(*tasks)

    ok_batches = [r for r in results if "error" not in r]
    err_batches = [r for r in results if "error" in r]
    print(f"[INFO] 成功 {len(ok_batches)} 批，失败 {len(err_batches)} 批")

    # 合并结果
    all_chars: dict[str, dict] = {}  # name -> {static, first_seen_ch}
    all_snaps: list[dict] = []
    all_fores: list[dict] = []
    all_rels: list[tuple[str, str, str, float]] = []

    for r in ok_batches:
        for c in r.get("characters", []) or []:
            name = c.get("name")
            if not name:
                continue
            if name not in all_chars:
                all_chars[name] = {
                    "static": c.get("static", {}),
                    "first_seen_ch": c.get("first_seen_ch", 0),
                }
            else:
                # 合并静态字段（后到的不覆盖已有的）
                for k, v in (c.get("static") or {}).items():
                    if k not in all_chars[name]["static"]:
                        all_chars[name]["static"][k] = v

        for s in r.get("snapshots", []) or []:
            if s.get("name"):
                all_snaps.append(s)

        for f in r.get("foreshadowings", []) or []:
            if f.get("what"):
                all_fores.append(f)

        for rel in r.get("relationships", []) or []:
            if rel.get("a") and rel.get("b"):
                all_rels.append((rel["a"], rel["b"], rel.get("kind", ""),
                                  float(rel.get("since_ch", 0))))

    print(f"[INFO] 提取到: {len(all_chars)} 个角色, {len(all_snaps)} 个快照, "
          f"{len(all_fores)} 个伏笔, {len(all_rels)} 个关系")

    # 写入 profiles.json（清空原档案）
    new_data = {
        "version": 1,
        "characters": {},
        "foreshadowings": [],
        "relationships": [],
    }

    for name, info in all_chars.items():
        new_data["characters"][name] = {
            "static": info["static"],
            "snapshots": [],
        }

    # 注入快照（按 as_of_ch 排序）
    for s in sorted(all_snaps, key=lambda x: float(x.get("as_of_ch", 0))):
        name = s["name"]
        if name not in new_data["characters"]:
            # 自动补一个空角色
            new_data["characters"][name] = {"static": {}, "snapshots": []}
        snap = {"as_of_ch": float(s["as_of_ch"]), **(s.get("deltas") or {})}
        if s.get("note"):
            snap["note"] = s["note"]
        new_data["characters"][name]["snapshots"].append(snap)

    # 伏笔（自动编号）
    for i, f in enumerate(all_fores, 1):
        new_data["foreshadowings"].append({
            "id": f"AUTO_{i:03d}",
            "raised_ch": float(f.get("raised_ch", 0)),
            "resolved_ch": None,
            "status": "open",
            "what": f["what"],
            "importance": f.get("importance", "medium"),
        })

    # 关系去重
    seen_rels = set()
    for a, b, kind, since in sorted(all_rels, key=lambda x: x[3]):
        key = tuple(sorted([a, b])) + (kind,)
        if key in seen_rels:
            continue
        seen_rels.add(key)
        new_data["relationships"].append({
            "a": a, "b": b, "kind": kind, "since_ch": since,
        })

    out = project_dir / "state" / "profiles.json"
    out.write_text(
        json.dumps(new_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"[OK] profiles.json -> {out}")
    print(f"     {len(new_data['characters'])} 个角色")
    print(f"     {sum(len(c['snapshots']) for c in new_data['characters'].values())} 个快照")
    print(f"     {len(new_data['foreshadowings'])} 个伏笔")
    print(f"     {len(new_data['relationships'])} 个关系")
    return 0


def main():
    ap = argparse.ArgumentParser(description="从 state.json 摘要自动建档")
    ap.add_argument("--project", required=True, help="项目名")
    ap.add_argument("--batch-size", type=int, default=20,
                    help="每批喂给 LLM 多少章摘要（默认 20）")
    ap.add_argument("--concurrency", type=int,
                    default=int(os.environ.get("CONCURRENCY", "5")))
    args = ap.parse_args()

    project_dir = PROJECTS_DIR / args.project
    if not project_dir.exists():
        print(f"[错误] 项目不存在: {args.project}")
        sys.exit(1)

    rc = asyncio.run(auto_profile(project_dir, args.batch_size, args.concurrency))
    sys.exit(rc)


if __name__ == "__main__":
    main()
