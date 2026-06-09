"""Prompt 构造 — 章节正文 + 章节摘要两个模板。

支持两种章节类型:
  - 普通章 (整数 id):正常按时间线推进。
  - 插入章/番外 (浮点 id 如 3.5):必须严格夹在前后章节之间,
    既不能改写已发生剧情,也不能与后续章节冲突。
    插入章会自动获得紧邻前章的末尾原文 + 紧邻后章的开头原文,
    用于精确匹配笔触、对话风格、场景细节。
"""
from __future__ import annotations

import re
from typing import Any

CHAPTER_SYSTEM = """你是一名严谨的长篇小说写作引擎。

写作要求:
1. 严格遵循给定的世界观、人物设定、章节大纲。
2. 不要重写之前已发生的剧情,但可以呼应。
3. 不要在结尾给"未完待续 / 下章预告"之类元叙述。
4. 不要在文末标注字数、备注或任何元信息。
5. 输出**纯正文**,不要任何 markdown 标题、不要章节编号(标题由系统加)。
6. 自然分段,对话用「」或""任选一种并保持一致。
7. **字数硬性要求**: 本章正文必须达到 {target_words} 字以上（允许超出但不允许不足）。不足 {target_words} 字的输出视为不合格。请充分展开场景描写、对话、内心活动，不要压缩跳过大纲中的任何节拍。
8. 风格: {style_hint}
9. **绝对禁止在正文中用章节编号引用前情**。不要写"第XX章那次……"、"想起第XX章……"、"和第XX章一样"等。角色回忆过去事件时，必须用具体的场景描写（时间、地点、动作、对话片段）来唤起读者记忆，绝不能引用章节号。章节编号是目录工具，不是叙事语言。
10. **绝对禁止在正文里出现以下任何形式的元注释**:
   - "（情感悬念：xxx）"或"（真相悬念：xxx）"等带括号的悬念标注
   - "钩子："、"情感线："、"真相线："等带冒号的章节结构标签
   - "（字数：xxx）"、"（约 xxx 字）"、"（字数控制在 xxx）"等字数标注
   - "（注：xxx）"、"（备注：xxx）"等编辑备注
   - "本章亮点："、"本章主要"等总结性元描述
   - 任何冒号开头的工程标签
   悬念必须通过故事本身的画面、动作、对话、内心独白来呈现，不要"翻译"给读者看。"""

CHAPTER_USER = """## 世界观
{world}

## 主要人物
{characters}

{prev_tail_block}## 本章大纲(第 {chapter_id} 章 — {chapter_title})
{synopsis}

关键节拍:
{beats}

视角: {pov}

{upcoming_block}## 任务
按上述要求写本章正文。直接开始,不要前言。"""


INSERT_SYSTEM = """你是一名长篇小说的"插入章"写作引擎,任务是写番外或补章。

硬约束:
1. 这一章被插入在已有章节之间。**绝对不能**改写或推翻"前情"和"后续"中已经发生的剧情。
2. 本章发生的所有事件,必须在结束时让世界状态回到能自然衔接"后续"开头的状态。
3. 不要新增会让后续剧情说不通的人物死亡、关系突变、势力变更——除非大纲明确要求。
4. **严格匹配紧邻前章末尾、后章开头的笔触、对话风格、场景细节、人物状态**。
   - 你会看到前章末尾的原文片段:这是本章开头之前一刻的真实场景,你的开头要从这里自然延展。
   - 你会看到后章开头的原文片段:这是本章结束后一刻的真实场景,你的结尾要让世界状态平滑过渡到这里。
   - 角色当时穿什么、在哪里、说话语气、情绪状态,都要以原文为准,不要凭空发明。
5. 不要在文末标注字数、备注或任何元信息;不要写"未完待续"。
6. 输出纯正文,不要 markdown 标题、不要章节编号。
7. **字数硬性要求**: 本章正文必须达到 {target_words} 字以上（允许超出但不允许不足）。不足 {target_words} 字的输出视为不合格。请充分展开场景描写、对话、内心活动，不要压缩跳过大纲中的任何节拍。
8. 风格: {style_hint}
9. **绝对禁止在正文中用章节编号引用前情**。不要写"第XX章那次……"、"想起第XX章……"、"和第XX章一样"等。角色回忆过去事件时，必须用具体的场景描写（时间、地点、动作、对话片段）来唤起读者记忆，绝不能引用章节号。
"""

INSERT_USER = """## 世界观
{world}

## 主要人物
{characters}

## 前情(本章之前发生的剧情,按时间顺序)
{prior_summaries}

## 后续(本章之后**已经写好**的剧情,按时间顺序 — 你的本章结尾必须能自然过渡到这里第一条)
{following_summaries}

{neighbor_block}## 本章定位
本章 id = {chapter_id},是一个**插入章/番外**,夹在前情最后一章和后续第一章之间。

## 本章大纲({chapter_title})
{synopsis}

关键节拍:
{beats}

视角: {pov}

## 任务
按上述硬约束写本章正文。**精确接住前章末尾的场景、人物状态、笔触**,确保结尾能让后章开头的场景自然成立。直接开始,不要前言,不要解释你如何衔接。"""


SUMMARY_SYSTEM = """你是一个章节摘要器。读章节正文,输出 100~150 字的中文摘要,
覆盖:发生了什么、谁出场、关键转折、结尾停在哪。不要评论,不要剧透下章。"""


# ============================================================
# Outline-Extract（参考蓝图提炼）—— 用于学习一本书的写法/结构,
# 输出参考文档供作者自己创作,不做章节级换皮改写。
# ============================================================

OUTLINE_EXTRACT_SYSTEM = """你是一个"小说结构与技法分析器"。任务是从一章原文中提炼可供他人**参考创作**的元素。

输出严格遵循 JSON 格式,不要任何前后文,不要 markdown 代码块包裹。字段:

{
  "skeleton": "这一章在主线上推进了什么(50-100字,只描述事件骨架,不复述对话和细节)",
  "turning_points": ["关键转折点1(简短描述类型)", "关键转折点2", ...],
  "trope_types": ["桥段类型,如:退婚、觉醒、打脸、装逼、误会、立威、收服等"],
  "pacing_notes": "节奏特点(开场/铺垫/高潮/收尾的比例与处理,30-60字)",
  "technique_notes": "写作技法亮点(如:多视角切换、悬念铺设、伏笔回收、反差对比等,30-60字)",
  "expression_patterns": ["可参考的表达模式(类型化总结,如:'用旁观者震惊衬托主角强大','在最得意时埋下危机','对话中藏机锋'等),3-5条"],
  "emotion_arc": "情绪曲线(本章主角/读者的情绪走向,20-40字)",
  "hook_style": "结尾钩子的类型(如:悬念未解、强敌登场、变身/突破、反派转视角等)"
}

严格要求:
- **不要**复制或大段引用原文。
- **只总结类型与方法**,不输出原文的角色名、地名、招式名等专有名词。
- 用泛化语言描述(例如:不写'玉天君用龙枪击败了铁臂猿',而写'主角用本命武器秒杀压境强敌');
- 输出必须是合法 JSON,字符串内不要带换行符,转义双引号用 \\"。
"""


BLUEPRINT_SYNTHESIS_SYSTEM = """你是一个"小说创作蓝图整合器"。给定多章的结构提炼数据,你需要汇总成一份给作者参考的创作蓝图,帮助 TA 学习这本书的写法与节奏,然后自己用全新的人物、世界观、风格重新创作。

输出 markdown 文档,包含以下章节:

## 整体结构与节奏
- 全书分几个大段(开篇/转折/高潮/收尾),每段大约多少章
- 节奏特点(每多少章一个小高潮,每多少章一个大转折)

## 主线骨架(类型化,无具体名字)
- 用泛化语言列出主线推进的关键节点

## 经典桥段清单
- 出现频率最高的桥段类型(退婚/打脸/觉醒/装逼/收服/误会等)
- 每类桥段的常见处理手法

## 可借鉴的写作技法
- 节奏控制
- 悬念铺设与伏笔
- 视角切换
- 情绪反差

## 可参考的表达模式
- 类型化总结(不复制原文),例如:
  - "在群体震惊中烘托主角"
  - "用反派嘲讽前置铺垫之后打脸"
  - "招式名 + 视觉奇观 + 旁观者反应"三段式战斗描写
  - 等等

## 创作建议
- 如果作者要写一本类似定位的新书,应该如何重新设计世界观、人物、金手指,使其原创化
- 哪些桥段值得保留参考,哪些需要规避(避免与源作雷同)

严格要求:
- 不要复制原文。
- 不要使用源作的角色名、地名、武功名等专有名词。
- 全部用泛化与类型化语言。
- 给作者实操建议,帮 TA 自己创作,不要替 TA 换皮重写。
"""


REWRITE_SYSTEM = """[已废弃 — 改用 outline-extract 模式]
请使用 build_outline_extract_messages 函数,从原章提炼参考蓝图,而不是做章节级换皮改写。
"""

REWRITE_USER = "[已废弃]"


def _format_characters(chars: list[dict[str, Any]]) -> str:
    lines = []
    for c in chars:
        lines.append(f"- {c['name']} ({c.get('role','')}): {c.get('profile','')}")
    return "\n".join(lines)


def _format_beats(beats: list[str]) -> str:
    return "\n".join(f"- {b}" for b in beats) if beats else "(无)"


def _fmt_summaries(items: list[tuple[float, str]], empty_text: str) -> str:
    if not items:
        return empty_text
    lines = []
    for i, s in items:
        if isinstance(i, float) and i.is_integer():
            i = int(i)
        lines.append(f"[ch.{i}] {s}")
    return "\n".join(lines)


def _format_upcoming_block(outline: dict, current_id: float, lookahead: int = 5) -> str:
    """构造后续 N 章的大纲预览，让模型知道'后面要做什么，不要提前做'。"""
    chapters = sorted(outline.get("chapters", []), key=lambda c: float(c.get("id", 0)))
    upcoming = [c for c in chapters if float(c.get("id", 0)) > float(current_id)][:lookahead]
    if not upcoming:
        return ""
    lines = [
        "## 后续章节预览（这些内容留给后面的章节，本章不要提前触发或暗示）",
        "",
    ]
    for c in upcoming:
        cid = c.get("id", "?")
        if isinstance(cid, float) and cid.is_integer():
            cid = int(cid)
        title = c.get("title", "")
        synopsis = c.get("synopsis", "")[:120]
        lines.append(f"- [ch.{cid}] {title}：{synopsis}...")
    lines.append("")
    lines.append("**重要**：上述后续章节的内容严禁在本章提前出现或暗示。特别是标记为「结局前不揭」的隐藏真相，在对应章节到来之前，任何角色（包括系统消息、NPC对话、内心独白）都不能透露。")
    lines.append("")
    return "\n".join(lines) + "\n"


_CROSS_REF_RE = re.compile(r"(?:ch|CH)(\d+)|第(\d+)章")


def extract_cross_refs(chapter: dict[str, Any]) -> list[int]:
    """从 synopsis 和 key_beats 中提取被引用的章节号。"""
    text = chapter.get("synopsis", "")
    for b in chapter.get("key_beats", []):
        text += " " + b
    refs = set()
    for m in _CROSS_REF_RE.finditer(text):
        num = m.group(1) or m.group(2)
        refs.add(int(num))
    own_id = int(float(chapter.get("id", 0)))
    refs.discard(own_id)
    return sorted(refs)


def _format_cross_ref_block(cross_ref_context: str) -> str:
    """包装交叉引用上下文为 prompt 块。"""
    if not cross_ref_context:
        return ""
    return (
        "## 本章需要呼应的往事（系统已为你检索，直接用场景描写呼应即可）\n\n"
        + cross_ref_context
        + "\n\n**写作要求**：呼应上述事件时，用具体的时间、地点、动作、对话片段唤起读者记忆。"
        "禁止在正文中写「第X章」或任何章节编号。\n\n"
    )


def _format_neighborhood_block(neighborhood_context: str | None) -> str:
    """包装±3章邻域上下文为 prompt 块。"""
    if not neighborhood_context:
        return ""
    return (
        "## 邻近章节实况（±3章已写内容摘要——以此为准，防止遗忘细节）\n\n"
        + neighborhood_context
        + "\n\n"
        "**注意**: 上方摘要是已完成章节的实际内容总结，优先级高于大纲。"
        "若与大纲有出入，以摘要为准保持连贯。\n\n"
    )


def _format_neighbor_block(neighbor_excerpts: dict | None) -> str:
    """格式化前后章原文片段块。"""
    if not neighbor_excerpts:
        return ""
    parts = []

    prev_tail = neighbor_excerpts.get("prev_tail")
    prev_meta = neighbor_excerpts.get("prev_meta")
    if prev_tail and prev_meta:
        prev_id = prev_meta.get("id", "?")
        prev_title = prev_meta.get("title", "")
        if isinstance(prev_id, float) and prev_id.is_integer():
            prev_id = int(prev_id)
        parts.append(
            f"## 紧邻前章原文末尾(ch.{prev_id} {prev_title} — 你的开头从这里无缝延展)\n\n"
            f"```\n{prev_tail}\n```\n"
        )

    next_head = neighbor_excerpts.get("next_head")
    next_meta = neighbor_excerpts.get("next_meta")
    if next_head and next_meta:
        next_id = next_meta.get("id", "?")
        next_title = next_meta.get("title", "")
        if isinstance(next_id, float) and next_id.is_integer():
            next_id = int(next_id)
        parts.append(
            f"## 紧邻后章原文开头(ch.{next_id} {next_title} — 你的结尾必须让此场景自然成立)\n\n"
            f"```\n{next_head}\n```\n"
        )

    if not parts:
        return ""
    return "\n".join(parts) + "\n"


def build_chapter_messages(
    outline: dict[str, Any],
    chapter: dict[str, Any],
    prior_summaries: list[tuple[float, str]],
    following_summaries: list[tuple[float, str]] | None = None,
    neighbor_excerpts: dict | None = None,
    profile_context: str | None = None,
    cross_ref_context: str | None = None,
    neighborhood_context: str | None = None,
    lorebook_context: str | None = None,
) -> list[dict[str, str]]:
    meta = outline["meta"]
    world = outline["world"]
    style_hint = " / ".join(meta.get("style_notes", [])) or "克制、画面感强"
    world_block = world["setting"] + "\n规则:\n" + "\n".join(f"- {r}" for r in world.get("rules", []))

    # 角色档案 + 伏笔 + 关系（如果有）
    profile_block = ""
    if profile_context:
        profile_block = (
            "\n\n# 严格遵守:角色档案、关系网与伏笔(本章发生时刻的真实状态)\n\n"
            + profile_context
            + "\n\n**写作硬规则**: 严格按上述档案写作。\n"
            "- 不要让角色突破到档案中尚未达到的境界,不要让伴侣关系或贞操状态倒退,\n"
            "- 不要遗忘已埋的伏笔,可以在合适时机自然推进或保留它们。\n"
            "- 装备、技能、招式名必须与档案一致,不要凭空发明替代名。\n"
        )

    cid = chapter["id"]
    is_insert = isinstance(cid, float) and not cid.is_integer()

    if is_insert:
        sys_prompt = INSERT_SYSTEM.format(
            target_words=meta.get("target_words_per_chapter", 3000),
            style_hint=style_hint,
        ) + profile_block
        user_prompt = INSERT_USER.format(
            world=world_block,
            characters=_format_characters(outline["characters"]),
            prior_summaries=_fmt_summaries(prior_summaries, "(无前情)"),
            following_summaries=_fmt_summaries(
                following_summaries or [],
                "(无后续 — 这是当前最末章,按普通续写处理即可)",
            ),
            neighbor_block=_format_neighbor_block(neighbor_excerpts),
            chapter_id=cid,
            chapter_title=chapter["title"],
            synopsis=chapter["synopsis"],
            beats=_format_beats(chapter.get("key_beats", [])),
            pov=chapter.get("pov", "(未指定)"),
        )
    else:
        sys_prompt = CHAPTER_SYSTEM.format(
            target_words=meta.get("target_words_per_chapter", 3000),
            style_hint=style_hint,
        ) + profile_block
        upcoming_block = _format_upcoming_block(outline, float(cid), lookahead=5)
        # 普通章：前章末尾原文衔接
        prev_tail_block = ""
        if neighbor_excerpts and neighbor_excerpts.get("prev_tail"):
            prev_tail_block = (
                "## 前章末尾原文（你的开头需从这里自然衔接，保持语气、场景、情绪连贯）\n\n"
                f"```\n{neighbor_excerpts['prev_tail']}\n```\n\n"
            )
        user_prompt = CHAPTER_USER.format(
            world=world_block,
            characters=_format_characters(outline["characters"]),
            chapter_id=int(cid) if isinstance(cid, float) else cid,
            chapter_title=chapter["title"],
            synopsis=chapter["synopsis"],
            beats=_format_beats(chapter.get("key_beats", [])),
            pov=chapter.get("pov", "(未指定)"),
            upcoming_block=upcoming_block,
            prev_tail_block=prev_tail_block,
        )

    # 交叉引用章节回顾
    cross_ref_block = _format_cross_ref_block(cross_ref_context)
    if cross_ref_block:
        user_prompt += "\n" + cross_ref_block

    # ±3章邻域实况（已写摘要 + 一致性检查）
    neighborhood_block = _format_neighborhood_block(neighborhood_context)
    if neighborhood_block:
        user_prompt += "\n" + neighborhood_block

    # 世界书激活条目
    if lorebook_context:
        user_prompt += "\n\n" + lorebook_context

    # 章节硬性边界约束（如果 outline 提供了 boundary_note）
    boundary_note = chapter.get("boundary_note")
    if boundary_note:
        user_prompt += (
            f"\n\n## 【硬性章节边界】\n{boundary_note}\n"
            f"严格遵守上述边界——超出边界的内容留给下一章，不要塞进本章。"
        )

    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_summary_messages(chapter_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SUMMARY_SYSTEM},
        {"role": "user", "content": chapter_text},
    ]


def build_outline_extract_messages(chapter_text: str) -> list[dict[str, str]]:
    """从一章原文提炼结构/技法/桥段/表达模式（参考用，不复述原文）。"""
    return [
        {"role": "system", "content": OUTLINE_EXTRACT_SYSTEM},
        {"role": "user", "content": f"以下是某一章原文，请按 JSON 格式提炼参考要素：\n\n{chapter_text}"},
    ]


def build_blueprint_synthesis_messages(extracts_summary: str) -> list[dict[str, str]]:
    """汇总多章提炼数据，生成完整参考蓝图。"""
    return [
        {"role": "system", "content": BLUEPRINT_SYNTHESIS_SYSTEM},
        {"role": "user", "content": f"以下是多章的结构化提炼数据，请汇总成创作参考蓝图：\n\n{extracts_summary}"},
    ]

