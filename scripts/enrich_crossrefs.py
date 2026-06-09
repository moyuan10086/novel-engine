"""批量为 outline.json 章节添加交叉引用标记。

运行: python scripts/enrich_crossrefs.py
"""
import json
import re
from pathlib import Path

OUTLINE_PATH = Path("projects/配角阅读器/outline.json")

# 已有引用检测正则
CROSS_REF_RE = re.compile(r"(?:ch|CH)(\d+)|第(\d+)章")

# ============================================================
# 规则 1: 手动确认的高价值回扣（目标章 → 应引用的章列表 + 原因）
# ============================================================
MANUAL_REFS: dict[int, list[tuple[int, str]]] = {
    60: [(6, "苏白棠主动握手回扣天台同盟")],
    80: [(57, "沈晓雾恐惧写作回扣籍本觉醒")],
    100: [(9, "顾笙笙的选择回扣灰色摊牌")],
    120: [(12, "陆青鸢发现笔记回扣同床"), (14, "回扣识破之吻")],
    140: [(15, "22岁车祸真相回扣白雾先生照片")],
    170: [(135, "爷爷对话回扣爷爷手稿")],
    177: [(130, "第131章标题回扣卷一大结局")],
    192: [(128, "全角色重置通知回扣首次重置")],
    220: [(51, "24h倒计时回扣编辑日志"), (131, "回扣图书馆发现")],
    240: [(6, "苏白棠的话形成三段闭环"), (60, "回扣ch60握手")],
    257: [(221, "编辑权失效回扣灰色编辑器首次开启")],
    277: [(165, "编辑权恢复回扣拥抱"), (225, "回扣系统适应性改写")],
    280: [(51, "林夜决策回扣编辑日志")],
    310: [(190, "组织溃败回扣籍本疲劳研究"), (192, "回扣全角色重置")],
    312: [(33, "爷爷遗纸回扣星河伏笔"), (42, "回扣爷爷手稿判断")],
    318: [(1, "林夜回家回扣开篇便利店")],
    330: [(42, "爷爷设备回扣手稿发现"), (137, "回扣时间线准继承")],
    336: [(1, "林夜答案回扣开篇身份"), (160, "回扣陆青鸢的领悟")],
    340: [(240, "苏白棠闭环显式回扣")],
    342: [(131, "回访图书馆回扣卷三开篇")],
    344: [(36, "谢安白感慨回扣首次对峙")],
    350: [(1, "便利店重逢回扣开篇"), (50, "回扣卷一结局")],
    360: [(33, "爷爷手稿翻阅回扣星河"), (312, "回扣遗纸发现")],
    370: [(1, "倒数章回扣开篇"), (321, "回扣卷五权限分散")],
    373: [(1, "偶遇小说回扣开篇便利店")],
    380: [(1, "最终章回扣开篇"), (6, "回扣天台同盟"), (50, "回扣卷一结局")],
}

# ============================================================
# 规则 2: 关键词 → 应引用的首次出现章
# ============================================================
KEYWORD_REFS: list[tuple[str, list[int], str]] = [
    # (关键词正则, 引用章列表, 简述)
    (r"笔记本|爷爷手稿|爷爷的手稿|祖父手稿", [33, 42], "爷爷手稿线"),
    (r"编辑权|编辑模式|编辑器", [221], "编辑器系统"),
    (r"籍本疲劳|疲劳者|疲倦者联盟", [189], "籍本疲劳研究"),
    (r"图书馆|方尖碑图书馆", [106], "图书馆发现"),
    (r"全角色重置|全员重置|记忆重置", [128], "首次全角色重置"),
    (r"便利店.*空班|空班店", [1], "开篇空班店"),
    (r"天台同盟|天台.*秘密", [6], "天台同盟"),
    (r"编辑日志|1247", [51], "编辑日志"),
    (r"剧本观察组|观察组", [7], "观察组首现"),
    (r"时间线.*继承|准继承", [137], "时间线准继承"),
    (r"创作回响|写作预言", [57], "沈晓雾创作回响"),
    (r"星河.*笔名|爷爷.*笔名", [33], "星河伏笔"),
    (r"上方组织|组织.*溃败|组织.*瓦解", [65, 190], "组织线"),
]

# ============================================================
# 规则 3: 卷间呼应 — 每卷高潮/结局章引用对应卷开篇设定章
# ============================================================
VOLUME_ECHOES: dict[int, list[tuple[int, str]]] = {
    # 卷二高潮
    128: [(51, "卷二高潮回扣编辑日志")],
    129: [(51, "卷二收束回扣编辑日志")],
    130: [(51, "卷二结局回扣编辑日志"), (1, "回扣开篇")],
    # 卷三高潮
    219: [(131, "卷三高潮回扣图书馆")],
    220: [(131, "卷三结局回扣图书馆"), (51, "回扣编辑日志")],
    # 卷四高潮
    310: [(221, "卷四高潮回扣灰色编辑器")],
    311: [(221, "卷四回扣编辑器"), (131, "回扣图书馆")],
    312: [(221, "卷四收束回扣编辑器")],
    319: [(1, "卷四结局回扣开篇")],
    320: [(1, "卷四末回扣开篇"), (50, "回扣卷一结局")],
    # 卷五闭环
    321: [(1, "卷五开篇回扣开篇")],
    379: [(1, "倒数第二章回扣开篇"), (321, "回扣卷五开篇")],
    380: [(321, "最终章回扣卷五开篇")],
}


def _existing_refs(chapter: dict) -> set[int]:
    """提取章节中已有的交叉引用。"""
    text = chapter.get("synopsis", "")
    for b in chapter.get("key_beats", []):
        text += " " + b
    refs = set()
    for m in CROSS_REF_RE.finditer(text):
        num = m.group(1) or m.group(2)
        refs.add(int(num))
    return refs


def enrich():
    data = json.loads(OUTLINE_PATH.read_text(encoding="utf-8"))
    chapters = data["chapters"]
    chapters_by_id = {int(float(c["id"])): c for c in chapters}

    added_count = 0
    chapters_touched = set()

    for ch in chapters:
        cid = int(float(ch["id"]))
        existing = _existing_refs(ch)
        new_beats: list[str] = []

        # 规则 1: 手动高价值回扣
        if cid in MANUAL_REFS:
            for ref_id, reason in MANUAL_REFS[cid]:
                if ref_id not in existing and ref_id != cid:
                    new_beats.append(f"呼应ch{ref_id}：{reason}")
                    existing.add(ref_id)

        # 规则 3: 卷间呼应
        if cid in VOLUME_ECHOES:
            for ref_id, reason in VOLUME_ECHOES[cid]:
                if ref_id not in existing and ref_id != cid:
                    new_beats.append(f"呼应ch{ref_id}：{reason}")
                    existing.add(ref_id)

        # 规则 2: 关键词匹配
        all_text = ch.get("synopsis", "") + " " + " ".join(ch.get("key_beats", []))
        for pattern, ref_ids, desc in KEYWORD_REFS:
            if re.search(pattern, all_text):
                for ref_id in ref_ids:
                    if ref_id not in existing and ref_id != cid and ref_id < cid:
                        new_beats.append(f"呼应ch{ref_id}：{desc}")
                        existing.add(ref_id)

        if new_beats:
            if "key_beats" not in ch:
                ch["key_beats"] = []
            ch["key_beats"].extend(new_beats)
            added_count += len(new_beats)
            chapters_touched.add(cid)

    OUTLINE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 统计
    print(f"新增交叉引用: {added_count} 条，涉及 {len(chapters_touched)} 章")
    # 按卷统计
    vol_ranges = [(1, 50), (51, 130), (131, 220), (221, 320), (321, 380)]
    vol_names = ["卷一", "卷二", "卷三", "卷四", "卷五"]
    for name, (lo, hi) in zip(vol_names, vol_ranges):
        count = sum(1 for c in chapters_touched if lo <= c <= hi)
        print(f"  {name} (ch{lo}-{hi}): {count} 章被修改")

    # 验证总引用数
    total_with_refs = sum(1 for c in chapters if _existing_refs(c))
    print(f"\n总计有交叉引用的章节: {total_with_refs}/380")


if __name__ == "__main__":
    enrich()
