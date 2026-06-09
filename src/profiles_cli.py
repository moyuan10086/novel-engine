"""Profiles CLI — 管理角色档案、伏笔、关系。

子命令:
    char add <project> <name> --json '<静态档案JSON>'
    char list <project> [--at <章>]
    char show <project> <name> [--at <章>]

    snap add <project> <name> --at <章> --json '<增量JSON>' [--note "..."]
    snap list <project> <name>

    fore add <project> <id> --at <章> --what "..." [--imp medium]
    fore resolve <project> <id> --at <章>
    fore list <project> [--at <章>]

    rel add <project> <a> <b> --kind <kind> --since <章> [--note "..."]
    rel list <project> [--at <章>]

    context <project> --at <章>      # 预览注入到 prompt 的上下文块
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from . import profiles

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).parent.parent
PROJECTS_DIR = ROOT / "projects"


def _project(name: str) -> Path:
    p = PROJECTS_DIR / name
    if not p.exists():
        print(f"[错误] 项目不存在: {name}")
        sys.exit(1)
    return p


def _parse_json(s: str) -> dict:
    try:
        return json.loads(s)
    except Exception as e:
        print(f"[错误] JSON 解析失败: {e}")
        sys.exit(1)


def cmd_char_add(args):
    p = _project(args.project)
    static = _parse_json(args.json)
    profiles.add_character(p, args.name, static)
    print(f"[OK] 已添加角色: {args.name}")


def cmd_char_list(args):
    p = _project(args.project)
    data = profiles.load(p)
    chars = data.get("characters", {})
    if not chars:
        print("(无角色)")
        return
    print(f"角色总数: {len(chars)}")
    for name in sorted(chars.keys()):
        c = chars[name]
        n_snap = len(c.get("snapshots", []))
        print(f"  - {name}  (静态字段: {len(c.get('static', {}))}, 快照: {n_snap})")


def cmd_char_show(args):
    p = _project(args.project)
    if args.at is None:
        data = profiles.load(p)
        char = data.get("characters", {}).get(args.name)
        if not char:
            print(f"(未找到 {args.name})")
            return
        print(f"=== {args.name} ===")
        print("\n[静态档案]")
        for k, v in char.get("static", {}).items():
            print(f"  {k}: {v}")
        snaps = char.get("snapshots", [])
        if snaps:
            print(f"\n[快照 {len(snaps)} 个]")
            for s in snaps:
                ch = s.get("as_of_ch")
                deltas = {k: v for k, v in s.items() if k not in ("as_of_ch", "note")}
                line = f"  @ch{ch}: {json.dumps(deltas, ensure_ascii=False)}"
                if s.get("note"):
                    line += f"  // {s['note']}"
                print(line)
    else:
        st = profiles.effective_state_at(p, args.name, args.at)
        if st is None:
            print(f"(未找到 {args.name})")
            return
        print(f"=== {args.name} 在第{args.at}章的有效状态 ===")
        for k, v in st.items():
            print(f"  {k}: {v}")


def cmd_snap_add(args):
    p = _project(args.project)
    deltas = _parse_json(args.json)
    profiles.add_snapshot(p, args.name, args.at, deltas, note=args.note or "")
    print(f"[OK] {args.name} @第{args.at}章 已记录变化")


def cmd_snap_list(args):
    p = _project(args.project)
    data = profiles.load(p)
    char = data.get("characters", {}).get(args.name)
    if not char:
        print(f"(未找到 {args.name})")
        return
    snaps = char.get("snapshots", [])
    if not snaps:
        print("(无快照)")
        return
    for s in snaps:
        ch = s.get("as_of_ch")
        deltas = {k: v for k, v in s.items() if k not in ("as_of_ch", "note")}
        line = f"@ch{ch}: {json.dumps(deltas, ensure_ascii=False)}"
        if s.get("note"):
            line += f"  // {s['note']}"
        print(line)


def cmd_fore_add(args):
    p = _project(args.project)
    profiles.add_foreshadowing(p, args.id, args.at, args.what, args.imp)
    print(f"[OK] 伏笔 {args.id} 已埋于第{args.at}章")


def cmd_fore_resolve(args):
    p = _project(args.project)
    ok = profiles.resolve_foreshadowing(p, args.id, args.at, args.status)
    if ok:
        print(f"[OK] 伏笔 {args.id} @第{args.at}章 已 {args.status}")
    else:
        print(f"[错误] 找不到伏笔 {args.id}")


def cmd_fore_list(args):
    p = _project(args.project)
    if args.at is not None:
        items = profiles.active_foreshadowings_at(p, args.at)
        print(f"在第{args.at}章活跃的伏笔:")
    else:
        items = profiles.load(p).get("foreshadowings", [])
        print(f"全部伏笔:")
    if not items:
        print("(无)")
        return
    for f in items:
        raised = f["raised_ch"]
        rs = f.get("resolved_ch")
        line = f"  [{f['id']}|{f.get('importance','medium')}] " \
               f"raised@{raised}, status={f.get('status','open')}"
        if rs is not None:
            line += f", resolved@{rs}"
        line += f"\n      => {f['what']}"
        print(line)


def cmd_rel_add(args):
    p = _project(args.project)
    profiles.add_relationship(p, args.a, args.b, args.kind, args.since, args.note or "")
    print(f"[OK] 关系已建立: {args.a} <-> {args.b} ({args.kind}) 自第{args.since}章")


def cmd_rel_list(args):
    p = _project(args.project)
    if args.at is not None:
        items = profiles.active_relationships_at(p, args.at)
        print(f"截至第{args.at}章的关系:")
    else:
        items = profiles.load(p).get("relationships", [])
        print(f"所有关系:")
    if not items:
        print("(无)")
        return
    for r in items:
        line = f"  {r['a']} <-> {r['b']} : {r['kind']} (自第{r['since_ch']}章起)"
        if r.get("note"):
            line += f"  // {r['note']}"
        print(line)


def cmd_context(args):
    p = _project(args.project)
    block = profiles.build_context_block(p, args.at)
    if not block:
        print("(无档案/关系/伏笔)")
        return
    print(block)


def main():
    parser = argparse.ArgumentParser(description="profiles CLI - 角色档案/伏笔/关系")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # char
    p_char = sub.add_parser("char", help="角色管理")
    char_sub = p_char.add_subparsers(dest="action", required=True)
    a = char_sub.add_parser("add"); a.add_argument("project"); a.add_argument("name"); a.add_argument("--json", required=True); a.set_defaults(func=cmd_char_add)
    a = char_sub.add_parser("list"); a.add_argument("project"); a.set_defaults(func=cmd_char_list)
    a = char_sub.add_parser("show"); a.add_argument("project"); a.add_argument("name"); a.add_argument("--at", type=float); a.set_defaults(func=cmd_char_show)

    # snap
    p_snap = sub.add_parser("snap", help="状态快照")
    snap_sub = p_snap.add_subparsers(dest="action", required=True)
    a = snap_sub.add_parser("add"); a.add_argument("project"); a.add_argument("name"); a.add_argument("--at", type=float, required=True); a.add_argument("--json", required=True); a.add_argument("--note", default=""); a.set_defaults(func=cmd_snap_add)
    a = snap_sub.add_parser("list"); a.add_argument("project"); a.add_argument("name"); a.set_defaults(func=cmd_snap_list)

    # fore
    p_fore = sub.add_parser("fore", help="伏笔")
    fore_sub = p_fore.add_subparsers(dest="action", required=True)
    a = fore_sub.add_parser("add"); a.add_argument("project"); a.add_argument("id"); a.add_argument("--at", type=float, required=True); a.add_argument("--what", required=True); a.add_argument("--imp", default="medium", choices=["low","medium","high"]); a.set_defaults(func=cmd_fore_add)
    a = fore_sub.add_parser("resolve"); a.add_argument("project"); a.add_argument("id"); a.add_argument("--at", type=float, required=True); a.add_argument("--status", default="resolved", choices=["resolved","abandoned"]); a.set_defaults(func=cmd_fore_resolve)
    a = fore_sub.add_parser("list"); a.add_argument("project"); a.add_argument("--at", type=float); a.set_defaults(func=cmd_fore_list)

    # rel
    p_rel = sub.add_parser("rel", help="关系")
    rel_sub = p_rel.add_subparsers(dest="action", required=True)
    a = rel_sub.add_parser("add"); a.add_argument("project"); a.add_argument("a"); a.add_argument("b"); a.add_argument("--kind", required=True); a.add_argument("--since", type=float, required=True); a.add_argument("--note", default=""); a.set_defaults(func=cmd_rel_add)
    a = rel_sub.add_parser("list"); a.add_argument("project"); a.add_argument("--at", type=float); a.set_defaults(func=cmd_rel_list)

    # context
    a = sub.add_parser("context", help="预览注入到prompt的档案上下文")
    a.add_argument("project"); a.add_argument("--at", type=float, required=True); a.set_defaults(func=cmd_context)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
