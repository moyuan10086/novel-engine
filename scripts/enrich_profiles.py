"""扩展 profiles.json：角色快照、伏笔解消、关系演变覆盖全 380 章。

运行: python scripts/enrich_profiles.py
"""
import json
from pathlib import Path

PROFILES_PATH = Path("projects/配角阅读器/state/profiles.json")

# ============================================================
# A. 角色 Snapshots（基于 outline.json 关键剧情节点）
# ============================================================

SNAPSHOTS: dict[str, list[dict]] = {
    "林夜": [
        {"as_of_ch": 15, "状态": "得知白雾先生展示的20年前照片——少年是自己的脸", "note": "卷一末真相线开启"},
        {"as_of_ch": 25, "状态": "便利店街角目睹苏白棠遇袭并跟踪", "note": "开始主动介入剧本外事件"},
        {"as_of_ch": 42, "状态": "通读爷爷旧稿，判断22岁车祸者是剧本初代作者残影", "note": "爷爷手稿线关键节点"},
        {"as_of_ch": 50, "状态": "卷一结局——手指悬在读卡按钮上，犹豫是否读自己的完整人物卡", "note": "卷一收束"},
        {"as_of_ch": 51, "状态": "按下读卡看到自己人物卡全貌（仍不完整），发现编辑日志1247条修改", "note": "卷二开篇"},
        {"as_of_ch": 71, "状态": "发现所有被标记为'已删除'的段落全部在现实中被实现过", "note": "真相线推进"},
        {"as_of_ch": 105, "状态": "潜入方尖碑旧房间，发现墙壁后隐藏的手稿——部分写着'系统指令行'", "note": "编辑器伏笔"},
        {"as_of_ch": 123, "状态": "从柜台前走到最里层，决定回编辑部'修改'", "note": "主动出击"},
        {"as_of_ch": 140, "状态": "确认22岁车祸真相——是自己（林夜）现实中的死亡事件", "note": "核心真相之一"},
        {"as_of_ch": 160, "状态": "接受陆青鸢的话：他创造了这些人但也不再拥有她们", "note": "作者身份认知转变"},
        {"as_of_ch": 177, "状态": "发现第130章之后有一个空白的131章标题——'未完成'", "note": "结构伏笔"},
        {"as_of_ch": 193, "状态": "30个角色同时'苏醒'，笔迹归还给角色——剧本系统开始松动", "note": "系统变革"},
        {"as_of_ch": 220, "状态": "24小时倒计时开始，编辑按钮出现", "note": "卷三结局"},
        {"as_of_ch": 221, "状态": "打开编辑模式，能看到所有角色的'源代码'", "note": "卷四开篇"},
        {"as_of_ch": 240, "状态": "苏白棠说出关键的话，与ch6/ch60形成三段闭环", "note": "感情线高潮"},
        {"as_of_ch": 257, "状态": "发现自己无法使用编辑权了——系统开始反击", "note": "编辑权丧失"},
        {"as_of_ch": 280, "状态": "在陆青鸢的观察+苏白棠的后援+沈晓雾的日志支持下做出决策", "note": "团队协作"},
        {"as_of_ch": 312, "状态": "收到爷爷普通经纸遗物——内含目录权限", "note": "爷爷线收束"},
        {"as_of_ch": 318, "状态": "路过那家便利店——已经运行超过24小时了", "note": "时间意识"},
        {"as_of_ch": 336, "状态": "给出答案：我们既不是作者也不是角色，我们在此存在着", "note": "核心主题"},
        {"as_of_ch": 350, "状态": "便利店重逢苏白棠，说出'此后我不是在写你'", "note": "感情闭环"},
        {"as_of_ch": 380, "状态": "最终章——所有线收束，林夜选择留在这个世界作为'读者'而非'作者'", "note": "全书终"},
    ],
    "苏白棠": [
        {"as_of_ch": 26, "状态": "半夜发现林夜没回家，留了纸条写了一首诗给他", "note": "暗恋加深"},
        {"as_of_ch": 60, "状态": "首次主动握住林夜的手", "note": "肢体突破回扣ch6天台"},
        {"as_of_ch": 90, "状态": "与林夜达成协议：剧本之外的选择权归自己", "note": "关系定义"},
        {"as_of_ch": 124, "状态": "面对林夜说'我的预知梦停了很久了'", "note": "觉醒变化"},
        {"as_of_ch": 146, "状态": "在天台崩溃——发现预知能力本质是'作者给角色的缝隙'", "note": "身份认知危机"},
        {"as_of_ch": 165, "状态": "没有告白没有承诺，只是在便利店门口拥抱了很久", "note": "情感高潮"},
        {"as_of_ch": 225, "状态": "父母突然'改写'了行为——系统通过改写周围人来压制", "note": "被系统间接攻击"},
        {"as_of_ch": 240, "状态": "对林夜说出关键的话，形成ch6→ch60→ch240三段闭环", "note": "闭环节点"},
        {"as_of_ch": 277, "状态": "协助恢复林夜的编辑权——用她的'被书写感'作为校准锚点", "note": "功能性角色"},
        {"as_of_ch": 321, "状态": "权限分散后突然辞职去当了普通店员", "note": "主动脱离剧本"},
        {"as_of_ch": 340, "状态": "握住林夜的手说'你当初不是在写我'——回扣ch240", "note": "终极闭环"},
        {"as_of_ch": 350, "状态": "便利店门口最后对话——'我还是记得，我喜欢你'", "note": "感情收束"},
        {"as_of_ch": 380, "状态": "最终章出现在最后场景", "note": "全书终"},
    ],
    "陆青鸢": [
        {"as_of_ch": 30, "状态": "与林夜去咖啡馆楼上看爷爷旧手稿注解", "note": "调查线深入"},
        {"as_of_ch": 73, "状态": "在咖啡馆楼上发现一把钥匙——第二个预言兑现", "note": "预言线"},
        {"as_of_ch": 81, "状态": "正式来到林夜家，肢体亲密度升级", "note": "关系进展"},
        {"as_of_ch": 120, "状态": "在爷爷笔记本里发现关键记录——'创作者观察笔记'", "note": "真相线重大发现"},
        {"as_of_ch": 159, "状态": "带林夜去看家族医案——里面有一页专门写林夜的笔迹", "note": "家族线揭示"},
        {"as_of_ch": 160, "状态": "对林夜说'你创造了我但你不再拥有我，这是两件事'", "note": "核心台词"},
        {"as_of_ch": 189, "状态": "开始研究'籍本疲劳'的医学机制", "note": "转向研究者"},
        {"as_of_ch": 250, "状态": "抱住林夜说'下次见面我也不认识你了，但我记住你'", "note": "情感高潮"},
        {"as_of_ch": 281, "状态": "恢复正常，与林夜从战场中站起来", "note": "团队归位"},
        {"as_of_ch": 312, "状态": "协助破译爷爷遗纸中的医学术语部分", "note": "功能协助"},
        {"as_of_ch": 360, "状态": "之后偶尔翻看家族医案本中那一页林夜的字迹", "note": "余韵"},
        {"as_of_ch": 380, "状态": "最终章——以日记形式出现在结尾", "note": "全书终"},
    ],
    "沈晓雾": [
        {"as_of_ch": 57, "状态": "尝试停止写小说——但系统反复诱导她'继续创作'", "note": "觉醒"},
        {"as_of_ch": 80, "状态": "恐惧自己的写作能力——写出的内容正在变成现实", "note": "创作回响失控"},
        {"as_of_ch": 90, "状态": "与林夜达成精神同盟协议——只写不发表", "note": "关系升级"},
        {"as_of_ch": 149, "状态": "直面林夜：'你写过这些对吗？你就是那个作者'", "note": "指认作者"},
        {"as_of_ch": 171, "状态": "最后一个凌晨对林夜说'你不是在写我们，你现在的选择才是'", "note": "主题台词"},
        {"as_of_ch": 209, "状态": "创作能力觉醒完成——能预见20分钟后的事", "note": "能力定型"},
        {"as_of_ch": 252, "状态": "说'如果要保护他，我必须写出最后一段'", "note": "关键行动"},
        {"as_of_ch": 311, "状态": "创作能力消失——她说'终于可以正常写故事了'", "note": "能力消解"},
        {"as_of_ch": 328, "状态": "发现自己写小说时有'创造共鸣'——虚构映射现实但不再强制", "note": "能力变化"},
        {"as_of_ch": 380, "状态": "最终章——正在写一本新小说", "note": "全书终"},
    ],
    "顾笙笙": [
        {"as_of_ch": 100, "状态": "在组织和林夜之间做出最终选择——选择林夜", "note": "立场确定"},
        {"as_of_ch": 128, "状态": "全角色重置时保留了部分记忆——因为观察组的保护机制", "note": "重置幸存"},
        {"as_of_ch": 193, "状态": "参与30人苏醒事件，正式脱离观察组", "note": "身份转变"},
        {"as_of_ch": 251, "状态": "说'我们8小时后系统下一个目标就是我'", "note": "危机宣言"},
        {"as_of_ch": 298, "状态": "参与'每个人都是自己故事的作者'协作写作", "note": "主题行动"},
        {"as_of_ch": 380, "状态": "最终章——与陈砚之重建了观察组但目的变为'记录而非干预'", "note": "全书终"},
    ],
    "谢安白": [
        {"as_of_ch": 36, "状态": "首次对峙林夜——身份为江月白的盟友", "note": "登场（此处用谢安白代替江月白的卷二角色）"},
        {"as_of_ch": 103, "状态": "告诉林夜自己看到的'全校停时'现象", "note": "提供信息"},
        {"as_of_ch": 151, "状态": "再次出现在便利店——展示了一张不属于这个世界的身份证", "note": "身份谜团"},
        {"as_of_ch": 190, "状态": "在上方组织调查中发现47个籍本疲劳者数据", "note": "情报角色"},
        {"as_of_ch": 227, "状态": "发现'真实笔迹'对抗系统的方法", "note": "方法论贡献"},
        {"as_of_ch": 252, "状态": "宣布'如果保护他我必须先保护这个世界的底层'", "note": "动机明确"},
        {"as_of_ch": 310, "状态": "上方组织瓦解后成为自由人", "note": "身份解放"},
        {"as_of_ch": 344, "状态": "最后一次与林夜碰面——'我知道你不需要谢谢'", "note": "角色退场"},
    ],
}

# ============================================================
# B. 伏笔解消（F001-F015 → resolved_ch + status: closed）
# ============================================================

FORESHADOWING_RESOLUTIONS: dict[str, dict] = {
    "F001": {"resolved_ch": 380, "status": "closed"},
    "F002": {"resolved_ch": 340, "status": "closed"},
    "F003": {"resolved_ch": 120, "status": "closed"},
    "F004": {"resolved_ch": 140, "status": "closed"},
    "F005": {"resolved_ch": 193, "status": "closed"},
    "F006": {"resolved_ch": 277, "status": "closed"},
    "F007": {"resolved_ch": 160, "status": "closed"},
    "F008": {"resolved_ch": 140, "status": "closed"},
    "F009": {"resolved_ch": 312, "status": "closed"},
    "F010": {"resolved_ch": 177, "status": "closed"},
    "F011": {"resolved_ch": 312, "status": "closed"},
    "F012": {"resolved_ch": 310, "status": "closed"},
    "F013": {"resolved_ch": 311, "status": "closed"},
    "F014": {"resolved_ch": 350, "status": "closed"},
    "F015": {"resolved_ch": 336, "status": "closed"},
}

# ============================================================
# C. 关系演变 — 新增 + 演变条目
# ============================================================

NEW_RELATIONSHIPS: list[dict] = [
    {"a": "林夜", "b": "苏白棠", "kind": "恋人(确认)", "since_ch": 165, "note": "便利店门口无言拥抱确认关系"},
    {"a": "林夜", "b": "苏白棠", "kind": "并肩作战", "since_ch": 277, "note": "苏白棠用被书写感校准林夜的编辑权"},
    {"a": "林夜", "b": "陆青鸢", "kind": "调查搭档→精神同盟", "since_ch": 120, "note": "发现创作者观察笔记后关系质变"},
    {"a": "林夜", "b": "陆青鸢", "kind": "彼此独立的同行者", "since_ch": 160, "note": "你创造了我但不再拥有我"},
    {"a": "林夜", "b": "沈晓雾", "kind": "精神同盟", "since_ch": 90, "note": "达成只写不发表协议"},
    {"a": "林夜", "b": "沈晓雾", "kind": "创作信任者", "since_ch": 252, "note": "沈晓雾主动写出最后一段保护林夜"},
    {"a": "林夜", "b": "顾笙笙", "kind": "被选择的同盟", "since_ch": 100, "note": "顾笙笙在组织和林夜之间选择后者"},
    {"a": "林夜", "b": "谢安白", "kind": "情报提供者→战友", "since_ch": 190, "note": "从单向信息变为双向协作"},
    {"a": "林夜", "b": "作者(剧本系统)", "kind": "对抗", "since_ch": 221, "note": "开启编辑模式后系统开始反击"},
    {"a": "林夜", "b": "作者(剧本系统)", "kind": "超越", "since_ch": 336, "note": "既不是作者也不是角色"},
    {"a": "苏白棠", "b": "陆青鸢", "kind": "默契共存", "since_ch": 165, "note": "两人都接受各自与林夜的关系形态"},
    {"a": "顾笙笙", "b": "陈砚之", "kind": "重建搭档", "since_ch": 380, "note": "重建观察组目的变为记录而非干预"},
    {"a": "沈晓雾", "b": "谢安白", "kind": "情报交换", "since_ch": 209, "note": "创作预见能力与组织情报互补"},
    {"a": "林夜", "b": "白雾先生", "kind": "揭示者→被超越者", "since_ch": 312, "note": "爷爷遗纸揭示白雾先生本质"},
]

# ============================================================
# 主逻辑
# ============================================================

def enrich():
    data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    characters = data["characters"]  # dict keyed by name
    foreshadowings = data["foreshadowings"]
    relationships = data["relationships"]

    # --- A. 添加角色 snapshots ---
    snap_added = 0
    for char_name, new_snaps in SNAPSHOTS.items():
        if char_name not in characters:
            characters[char_name] = {"static": {}, "snapshots": []}
            print(f"  新建角色条目: {char_name}")

        existing_chs = {s.get("as_of_ch") for s in characters[char_name].get("snapshots", [])}
        if "snapshots" not in characters[char_name]:
            characters[char_name]["snapshots"] = []

        for snap in new_snaps:
            if snap["as_of_ch"] not in existing_chs:
                characters[char_name]["snapshots"].append(snap)
                snap_added += 1

        characters[char_name]["snapshots"].sort(key=lambda s: s.get("as_of_ch", 0))

    print(f"角色快照: 新增 {snap_added} 条")

    # --- B. 更新伏笔解消 ---
    foreshadow_updated = 0
    for f in foreshadowings:
        fid = f.get("id", "")
        if fid in FORESHADOWING_RESOLUTIONS:
            res = FORESHADOWING_RESOLUTIONS[fid]
            if f.get("status") != "closed":
                f["resolved_ch"] = res["resolved_ch"]
                f["status"] = res["status"]
                foreshadow_updated += 1

    print(f"伏笔解消: 更新 {foreshadow_updated}/{len(FORESHADOWING_RESOLUTIONS)} 条")

    # --- C. 添加关系演变 ---
    existing_rels = {
        (r["a"], r["b"], r.get("since_ch", 0))
        for r in relationships
    }
    rel_added = 0
    for rel in NEW_RELATIONSHIPS:
        key = (rel["a"], rel["b"], rel.get("since_ch", 0))
        if key not in existing_rels:
            relationships.append(rel)
            existing_rels.add(key)
            rel_added += 1

    print(f"关系条目: 新增 {rel_added} 条 (总计 {len(relationships)})")

    # --- 写回 ---
    PROFILES_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n已写入: {PROFILES_PATH}")

    # --- 统计 ---
    print("\n=== 最终统计 ===")
    for name in ["林夜", "苏白棠", "陆青鸢", "沈晓雾", "顾笙笙", "谢安白"]:
        if name in characters:
            n = len(characters[name].get("snapshots", []))
            print(f"  {name}: {n} snapshots")
    closed = sum(1 for f in foreshadowings if f.get("status") == "closed")
    print(f"  伏笔: {closed}/{len(foreshadowings)} closed")
    print(f"  关系: {len(relationships)} 条")


if __name__ == "__main__":
    enrich()
