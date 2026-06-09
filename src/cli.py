#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""novel-engine CLI - 多小说项目管理工具

命令:
  python -m src.cli create <name> [--genre <type>]   创建新小说项目
  python -m src.cli list                              列出所有项目
  python -m src.cli default <name>                    设置默认项目
  python -m src.cli info [<name>]                     查看项目信息
  python -m src.cli context [<name>] --chapter N     预览章节完整 prompt 组成
"""

import argparse
import io
import json
import sys
from pathlib import Path

# 修复 Windows 控制台 gbk 编码问题
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).parent.parent
PROJECTS_DIR = ROOT / "projects"
DEFAULT_FILE = ROOT / ".default_project"


def _default_outline_template(name: str, genre: str) -> dict:
    """生成中性、通用的小说大纲模板（不含任何具体题材偏向内容）"""
    return {
        "meta": {
            "title": name,
            "genre": genre,
            "target_words_per_chapter": 3000,
            "language": "zh-CN",
            "style_notes": [
                "第三人称紧贴主角",
                "多用具体细节，少用抽象形容词",
                "对话推动情节，场景留白",
                "每章末尾留一个钩子"
            ]
        },
        "world": {
            "setting": "在这里填写世界观（200-500字）：时空背景、势力分布、能量体系、地理环境等。",
            "rules": [
                "规则一：（核心设定）",
                "规则二：（关键限制或机制）",
                "规则三：（特殊体系）"
            ]
        },
        "characters": [
            {
                "name": "主角",
                "role": "protagonist",
                "profile": "性格、背景、动机、外貌（100-200字）"
            },
            {
                "name": "配角A",
                "role": "mentor",
                "profile": "关键NPC，对剧情有重要推动作用"
            }
        ],
        "chapters": [
            {
                "id": 1,
                "title": "第一章 序幕",
                "synopsis": "本章100-200字概要：发生什么、出场谁、推进什么冲突、结尾停在哪",
                "key_beats": ["开场场景", "引入冲突", "主角动机暴露", "钩子"],
                "pov": "主角"
            }
        ]
    }


def create_project(name: str, genre: str = "通用") -> None:
    """创建新小说项目"""
    project_dir = PROJECTS_DIR / name
    if project_dir.exists():
        print(f"[警告] 项目已存在: {project_dir}")
        return

    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "chapters").mkdir(exist_ok=True)
    (project_dir / "state").mkdir(exist_ok=True)

    outline = _default_outline_template(name, genre)
    (project_dir / "outline.json").write_text(
        json.dumps(outline, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # 同时初始化空的 state.json
    (project_dir / "state" / "state.json").write_text(
        json.dumps({"summaries": {}, "done": []}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"[OK] 项目创建成功: {project_dir}")
    print(f"     -> 编辑 outline.json 填写世界观和章节大纲")
    print(f"     -> 设为默认: python -m src.cli default \"{name}\"")
    print(f"     -> 生成章节: python -m src.dispatcher --project \"{name}\" --only 1")


def list_projects() -> None:
    """列出所有项目"""
    if not PROJECTS_DIR.exists() or not any(PROJECTS_DIR.iterdir()):
        print("还没有任何项目。使用 `python -m src.cli create <name>` 创建第一个。")
        return

    default_project = None
    if DEFAULT_FILE.exists():
        default_project = DEFAULT_FILE.read_text(encoding="utf-8").strip()

    # 忽略下划线开头的目录（如 _blueprints 等工具目录）
    projects = sorted(
        p for p in PROJECTS_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("_") and not p.name.startswith(".")
    )

    print("=" * 50)
    print(f"已创建的项目（共 {len(projects)} 个）：")
    print("=" * 50)
    for p in projects:
        marker = " [默认]" if p.name == default_project else ""
        # 统计章节数
        chapters_dir = p / "chapters"
        ch_count = len(list(chapters_dir.glob("ch*.md"))) if chapters_dir.exists() else 0

        # 读取标题
        outline_path = p / "outline.json"
        title = ""
        genre = ""
        if outline_path.exists():
            try:
                data = json.loads(outline_path.read_text(encoding="utf-8"))
                title = data.get("meta", {}).get("title", "")
                genre = data.get("meta", {}).get("genre", "")
            except Exception:
                pass

        print(f"  - {p.name}{marker}")
        if title and title != p.name:
            print(f"      标题: {title}")
        if genre:
            print(f"      类型: {genre}")
        print(f"      已生成章节: {ch_count}")
    print("=" * 50)


def set_default(project_name: str) -> None:
    """设置默认项目"""
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        print(f"[错误] 项目不存在: {project_name}")
        print(f"       使用 `python -m src.cli list` 查看可用项目")
        sys.exit(1)

    DEFAULT_FILE.write_text(project_name, encoding="utf-8")
    print(f"[OK] 默认项目已设置为: {project_name}")
    print(f"     -> 后续命令可省略 --project 参数")


def show_info(project_name: str = None) -> None:
    """查看项目详细信息"""
    if not project_name:
        if DEFAULT_FILE.exists():
            project_name = DEFAULT_FILE.read_text(encoding="utf-8").strip()
        else:
            print("[错误] 请指定项目名 或 先设置默认项目")
            sys.exit(1)

    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        print(f"[错误] 项目不存在: {project_name}")
        sys.exit(1)

    outline_path = project_dir / "outline.json"
    if not outline_path.exists():
        print(f"[错误] 未找到 outline.json")
        return

    data = json.loads(outline_path.read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    chapters = data.get("chapters", [])

    print(f"\n项目: {project_name}")
    print(f"路径: {project_dir}")
    print(f"标题: {meta.get('title', '')}")
    print(f"类型: {meta.get('genre', '')}")
    print(f"目标字数/章: {meta.get('target_words_per_chapter', 'N/A')}")
    print(f"\n章节大纲（共 {len(chapters)} 章）：")

    state_path = project_dir / "state" / "state.json"
    done_set = set()
    if state_path.exists():
        try:
            state_data = json.loads(state_path.read_text(encoding="utf-8"))
            done_set = {float(x) for x in state_data.get("done", [])}
        except Exception:
            pass

    for ch in sorted(chapters, key=lambda c: float(c.get("id", 0))):
        cid = ch.get("id", 0)
        status = "[已完成]" if float(cid) in done_set else "[待生成]"
        print(f"  {status} ch{cid}: {ch.get('title', '')}")
    print()


def show_context(project_name: str | None, chapter_id: float) -> None:
    """预览某章的完整 prompt 组成（不调用 API）。"""
    if not project_name:
        if DEFAULT_FILE.exists():
            project_name = DEFAULT_FILE.read_text(encoding="utf-8").strip()
        else:
            print("[错误] 请指定项目名 或 先设置默认项目")
            sys.exit(1)

    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        print(f"[错误] 项目不存在: {project_name}")
        sys.exit(1)

    outline_path = project_dir / "outline.json"
    if not outline_path.exists():
        print("[错误] 未找到 outline.json")
        sys.exit(1)

    from . import profiles, prompts, state as state_mod
    from .worker import _build_cross_ref_context, _build_neighborhood_context, _is_insert, _load_neighbor_excerpts

    outline = json.loads(outline_path.read_text(encoding="utf-8"))
    chapters = outline.get("chapters", [])
    chapter = None
    for ch in chapters:
        if float(ch.get("id", 0)) == chapter_id:
            chapter = ch
            break

    if chapter is None:
        print(f"[错误] 找不到章节 id={chapter_id}")
        sys.exit(1)

    cid = chapter["id"]
    priors = state_mod.prior_summaries(project_dir, cid)
    followings = state_mod.following_summaries(project_dir, cid) if _is_insert(cid) else None

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

    cross_ref_context = _build_cross_ref_context(project_dir, outline, chapter)
    neighborhood_context = _build_neighborhood_context(project_dir, outline, chapter)
    profile_context = profiles.build_context_block(project_dir, float(cid)) or None

    msgs = prompts.build_chapter_messages(
        outline, chapter, priors, followings,
        neighbor_excerpts=neighbor_excerpts,
        profile_context=profile_context,
        cross_ref_context=cross_ref_context,
        neighborhood_context=neighborhood_context,
    )

    # 输出详细报告
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  Context Preview: {project_name} / 第{cid}章 {chapter.get('title', '')}")
    print(f"{sep}\n")

    # 统计各部分
    print("## 组成块统计")
    print(f"  - 前情摘要: {len(priors)} 条")
    if followings is not None:
        print(f"  - 后续摘要: {len(followings)} 条")
    print(f"  - 交叉引用: {'有' if cross_ref_context else '无'}")
    print(f"  - 邻域实况: {'有' if neighborhood_context else '无'}")
    print(f"  - 角色档案: {'有' if profile_context else '无'}")
    print(f"  - 邻章原文: {'有' if neighbor_excerpts else '无（非插入章或邻章文件不存在）'}")
    print()

    for i, msg in enumerate(msgs):
        role = msg["role"].upper()
        content = msg["content"]
        chars = len(content)
        est_tokens = chars // 2
        print(f"## Message [{i}] role={role}  (~{est_tokens} tokens, {chars} chars)")
        print("-" * 60)
        # 只打印前 2000 字符，避免屏幕爆炸
        if len(content) > 2000:
            print(content[:2000])
            print(f"\n  ... (截断，共 {chars} 字符)")
        else:
            print(content)
        print()

    total_chars = sum(len(m["content"]) for m in msgs)
    print(f"{sep}")
    print(f"  总字符数: {total_chars}  |  估算 tokens: ~{total_chars // 2}")
    print(f"{sep}\n")


def _resolve_project(name: str | None) -> Path:
    """解析项目路径，支持 --project 或默认项目。"""
    if not name:
        if DEFAULT_FILE.exists():
            name = DEFAULT_FILE.read_text(encoding="utf-8").strip()
        else:
            print("[错误] 请指定项目名 或 先设置默认项目")
            sys.exit(1)
    project_dir = PROJECTS_DIR / name
    if not project_dir.exists():
        print(f"[错误] 项目不存在: {name}")
        sys.exit(1)
    return project_dir


def _handle_lorebook(args) -> None:
    """处理 lorebook 子命令。"""
    from .lorebook import LoreEntry, Lorebook

    project_dir = _resolve_project(getattr(args, "project", None))
    lb = Lorebook(project_dir)

    if args.lorebook_cmd == "list":
        if not lb.entries:
            print("世界书为空。使用 `lorebook add` 添加条目。")
            return
        print(f"世界书条目（共 {len(lb.entries)} 条）：")
        for e in lb.entries:
            status = "启用" if e.enabled else "禁用"
            keys = ", ".join(e.primary_keys[:3])
            print(f"  [{e.id}] {e.title} (pri={e.priority}, {status}) keys: {keys}")

    elif args.lorebook_cmd == "add":
        entry = LoreEntry(
            id=args.id,
            title=args.title,
            type=args.type,
            primary_keys=[k.strip() for k in args.keys.split(",") if k.strip()],
            secondary_keys=[k.strip() for k in args.secondary_keys.split(",") if k.strip()],
            content=args.content,
            priority=args.priority,
            recursive=args.recursive,
        )
        lb.add(entry)
        print(f"[OK] 条目已添加/更新: {args.id}")

    elif args.lorebook_cmd == "remove":
        if lb.remove(args.id):
            print(f"[OK] 条目已删除: {args.id}")
        else:
            print(f"[错误] 条目不存在: {args.id}")

    elif args.lorebook_cmd == "test":
        activated = lb.activate(args.text, args.chapter)
        if not activated:
            print("无条目被激活。")
        else:
            print(f"激活了 {len(activated)} 个条目：")
            for e in activated:
                print(f"  [{e.id}] {e.title} (pri={e.priority})")
                print(f"    内容预览: {e.content[:100]}...")

    else:
        print("用法: python -m src.cli lorebook [list|add|remove|test]")


def _handle_vector(args) -> None:
    """处理 vector 子命令。"""
    from .vector_store import VectorStore

    project_dir = _resolve_project(getattr(args, "project", None))
    vs = VectorStore(project_dir)

    if not vs.available:
        print("[错误] chromadb 未安装。运行: pip install novel-engine[vector]")
        return

    if args.vector_cmd == "status":
        info = vs.status()
        print(f"向量库状态 ({project_dir.name}):")
        for k, v in info.items():
            if k == "available":
                continue
            print(f"  {k}: {v} 条文档")

    elif args.vector_cmd == "index" or args.vector_cmd == "rebuild":
        outline_path = project_dir / "outline.json"
        if not outline_path.exists():
            print("[错误] outline.json 不存在")
            return
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
        print("正在重建向量索引...")
        stats = vs.rebuild(project_dir, outline)
        print(f"[OK] 索引完成:")
        for k, v in stats.items():
            print(f"  {k}: {v} 条")

    elif args.vector_cmd == "query":
        results = vs.query(args.text, n_results=args.n)
        if not results:
            print("无匹配结果。")
        else:
            print(f"检索到 {len(results)} 条结果：")
            for i, chunk in enumerate(results, 1):
                print(f"\n  [{i}] score={chunk.score:.3f} | {chunk.source_type}/{chunk.source_id}")
                preview = chunk.content[:150].replace("\n", " ")
                print(f"      {preview}...")

    else:
        print("用法: python -m src.cli vector [index|query|rebuild|status]")


def main():
    parser = argparse.ArgumentParser(
        description="novel-engine 多小说管理 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    create_p = subparsers.add_parser("create", help="创建新小说项目")
    create_p.add_argument("name", help="项目名称")
    create_p.add_argument("--genre", default="通用", help="小说类型（如：玄幻、都市、科幻）")

    subparsers.add_parser("list", help="列出所有项目")

    default_p = subparsers.add_parser("default", help="设置默认项目")
    default_p.add_argument("name", help="项目名称")

    info_p = subparsers.add_parser("info", help="查看项目详情")
    info_p.add_argument("name", nargs="?", default=None, help="项目名称（可选，默认查看默认项目）")

    context_p = subparsers.add_parser("context", help="预览章节完整 prompt 组成（不调用 API）")
    context_p.add_argument("name", nargs="?", default=None, help="项目名称（可选）")
    context_p.add_argument("--chapter", type=float, required=True, help="章节 ID（支持小数如 1.5）")

    lorebook_p = subparsers.add_parser("lorebook", help="世界书管理")
    lorebook_sub = lorebook_p.add_subparsers(dest="lorebook_cmd")
    lb_list = lorebook_sub.add_parser("list", help="列出所有条目")
    lb_list.add_argument("--project", default=None)
    lb_add = lorebook_sub.add_parser("add", help="添加条目")
    lb_add.add_argument("--project", default=None)
    lb_add.add_argument("--id", required=True)
    lb_add.add_argument("--title", required=True)
    lb_add.add_argument("--keys", required=True, help="主关键词,逗号分隔")
    lb_add.add_argument("--secondary-keys", default="", help="副关键词,逗号分隔")
    lb_add.add_argument("--content", required=True)
    lb_add.add_argument("--type", default="general")
    lb_add.add_argument("--priority", type=int, default=50)
    lb_add.add_argument("--recursive", action="store_true")
    lb_remove = lorebook_sub.add_parser("remove", help="删除条目")
    lb_remove.add_argument("--project", default=None)
    lb_remove.add_argument("--id", required=True)
    lb_test = lorebook_sub.add_parser("test", help="测试激活")
    lb_test.add_argument("--project", default=None)
    lb_test.add_argument("--text", required=True, help="测试文本")
    lb_test.add_argument("--chapter", type=float, default=1)

    vector_p = subparsers.add_parser("vector", help="向量检索管理")
    vector_sub = vector_p.add_subparsers(dest="vector_cmd")
    v_index = vector_sub.add_parser("index", help="索引项目内容")
    v_index.add_argument("--project", default=None)
    v_query = vector_sub.add_parser("query", help="语义检索")
    v_query.add_argument("--project", default=None)
    v_query.add_argument("--text", required=True)
    v_query.add_argument("--n", type=int, default=5)
    v_rebuild = vector_sub.add_parser("rebuild", help="重建索引")
    v_rebuild.add_argument("--project", default=None)
    v_status = vector_sub.add_parser("status", help="查看索引状态")
    v_status.add_argument("--project", default=None)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "create":
        create_project(args.name, args.genre)
    elif args.command == "list":
        list_projects()
    elif args.command == "default":
        set_default(args.name)
    elif args.command == "info":
        show_info(args.name)
    elif args.command == "context":
        show_context(args.name, args.chapter)
    elif args.command == "lorebook":
        _handle_lorebook(args)
    elif args.command == "vector":
        _handle_vector(args)


if __name__ == "__main__":
    main()
