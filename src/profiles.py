"""角色档案 + 伏笔追踪系统 — 解决长篇小说前后状态不一致问题。

存储: projects/<name>/state/profiles.json

核心数据:
  - characters: 每个角色有 static (永不变) + snapshots (稀疏时间快照)
  - foreshadowings: 伏笔表（id / raised_ch / resolved_ch / status / what）
  - relationships: 关系网（CP / 师徒 / 家族）

读取 API:
  - effective_state_at(name, chapter_id): 合并所有 ≤ ch 的快照,得到角色在该章的有效状态
  - active_foreshadowings_at(chapter_id): 该章存在的所有未解伏笔
  - active_relationships_at(chapter_id): 该章已建立的所有关系

写入 API:
  - add_character(name, static_profile)
  - add_snapshot(name, as_of_ch, deltas)  # 增量, 只写变化的字段
  - add_foreshadowing(raised_ch, what, ...)
  - resolve_foreshadowing(fid, resolved_ch)
  - add_relationship(a, b, kind, since_ch)
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_FILE = "profiles.json"


def _path(project_dir: Path) -> Path:
    return project_dir / "state" / _FILE


def _empty() -> dict[str, Any]:
    return {
        "version": 1,
        "characters": {},
        "foreshadowings": [],
        "relationships": [],
    }


def load(project_dir: Path) -> dict[str, Any]:
    p = _path(project_dir)
    if not p.exists():
        return _empty()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return _empty()


def save(project_dir: Path, data: dict[str, Any]) -> None:
    p = _path(project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ==================== 角色档案 ====================

def add_character(project_dir: Path, name: str, static_profile: dict[str, Any]) -> None:
    """添加或更新角色的静态档案。"""
    with _LOCK:
        data = load(project_dir)
        if name not in data["characters"]:
            data["characters"][name] = {"static": static_profile, "snapshots": []}
        else:
            data["characters"][name]["static"].update(static_profile)
        save(project_dir, data)


def add_snapshot(
    project_dir: Path,
    name: str,
    as_of_ch: float,
    deltas: dict[str, Any],
    note: str = "",
) -> None:
    """记录角色在某章后的状态变化。deltas 只写**变化的字段**。"""
    with _LOCK:
        data = load(project_dir)
        if name not in data["characters"]:
            data["characters"][name] = {"static": {}, "snapshots": []}
        snap = {"as_of_ch": float(as_of_ch), **deltas}
        if note:
            snap["note"] = note
        data["characters"][name]["snapshots"].append(snap)
        data["characters"][name]["snapshots"].sort(key=lambda s: float(s["as_of_ch"]))
        save(project_dir, data)


def effective_state_at(
    project_dir: Path, name: str, chapter_id: float
) -> dict[str, Any] | None:
    """合并所有 as_of_ch <= chapter_id 的快照，返回该章的有效状态。"""
    data = load(project_dir)
    if name not in data["characters"]:
        return None
    char = data["characters"][name]
    state: dict[str, Any] = {**char.get("static", {})}
    for snap in char.get("snapshots", []):
        if float(snap["as_of_ch"]) <= float(chapter_id):
            for k, v in snap.items():
                if k in ("as_of_ch", "note"):
                    continue
                state[k] = v
    return state


def all_effective_states_at(
    project_dir: Path, chapter_id: float
) -> dict[str, dict[str, Any]]:
    """返回所有角色在该章的有效状态。"""
    data = load(project_dir)
    out = {}
    for name in data.get("characters", {}):
        out[name] = effective_state_at(project_dir, name, chapter_id) or {}
    return out


# ==================== 伏笔 ====================

def add_foreshadowing(
    project_dir: Path,
    fid: str,
    raised_ch: float,
    what: str,
    importance: str = "medium",
) -> None:
    with _LOCK:
        data = load(project_dir)
        for f in data["foreshadowings"]:
            if f["id"] == fid:
                f.update({"raised_ch": float(raised_ch), "what": what,
                          "importance": importance})
                save(project_dir, data)
                return
        data["foreshadowings"].append({
            "id": fid,
            "raised_ch": float(raised_ch),
            "resolved_ch": None,
            "status": "open",
            "what": what,
            "importance": importance,
        })
        save(project_dir, data)


def resolve_foreshadowing(
    project_dir: Path, fid: str, resolved_ch: float, status: str = "resolved"
) -> bool:
    with _LOCK:
        data = load(project_dir)
        for f in data["foreshadowings"]:
            if f["id"] == fid:
                f["resolved_ch"] = float(resolved_ch)
                f["status"] = status
                save(project_dir, data)
                return True
        return False


def active_foreshadowings_at(
    project_dir: Path, chapter_id: float
) -> list[dict[str, Any]]:
    """该章节当前应该考虑的未解伏笔（已raised但未resolved或resolved>本章）。"""
    data = load(project_dir)
    out = []
    cid = float(chapter_id)
    for f in data.get("foreshadowings", []):
        if float(f["raised_ch"]) > cid:
            continue  # 还没埋
        if f.get("resolved_ch") is not None and float(f["resolved_ch"]) < cid:
            continue  # 已经解了
        if f.get("status") == "abandoned":
            continue
        out.append(f)
    return out


# ==================== 关系网 ====================

def add_relationship(
    project_dir: Path, a: str, b: str, kind: str, since_ch: float, note: str = ""
) -> None:
    with _LOCK:
        data = load(project_dir)
        rel = {"a": a, "b": b, "kind": kind, "since_ch": float(since_ch)}
        if note:
            rel["note"] = note
        data["relationships"].append(rel)
        save(project_dir, data)


def active_relationships_at(
    project_dir: Path, chapter_id: float
) -> list[dict[str, Any]]:
    data = load(project_dir)
    cid = float(chapter_id)
    return [r for r in data.get("relationships", []) if float(r["since_ch"]) <= cid]


# ==================== Prompt 注入 ====================

def _format_state_card(name: str, state: dict[str, Any]) -> str:
    """把一个角色的有效状态格式化为 prompt 可读的卡片。

    注意：包含「结局前不揭」的字段会被过滤掉，不注入 prompt。
    """
    if not state:
        return f"### {name}\n(无档案)"
    lines = [f"### {name}"]
    # 优先展示常用字段
    priority = [
        "identity", "身份", "武魂", "金手指",
        "level", "境界", "魂环", "魂骨", "装备",
        "伴侣", "关系", "贞操", "孕况",
        "成就", "技能", "心境", "目标",
        "appearance", "外貌", "personality", "性格",
    ]
    seen = set()
    for k in priority:
        if k in state:
            v = state[k]
            # 过滤隐藏信息
            if isinstance(v, str) and "结局前不揭" in v:
                continue
            if isinstance(v, list):
                v = ", ".join(str(x) for x in v) if v else "(无)"
            lines.append(f"- {k}: {v}")
            seen.add(k)
    # 其他字段
    for k, v in state.items():
        if k in seen:
            continue
        # 过滤隐藏字段名和隐藏内容
        if k in ("隐藏身份", "隐藏", "隐藏设定", "隐藏伏笔"):
            continue
        if isinstance(v, str) and "结局前不揭" in v:
            continue
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v) if v else "(无)"
        lines.append(f"- {k}: {v}")
    return "\n".join(lines)


def build_context_block(project_dir: Path, chapter_id: float) -> str:
    """生成完整的"角色当前状态 + 关系 + 伏笔"上下文块，用于 prompt 注入。"""
    parts = []

    # 角色状态
    states = all_effective_states_at(project_dir, chapter_id)
    if states:
        parts.append("## 角色档案（截至本章）")
        for name, st in states.items():
            parts.append(_format_state_card(name, st))
        parts.append("")

    # 关系网
    rels = active_relationships_at(project_dir, chapter_id)
    if rels:
        parts.append("## 关系网（截至本章）")
        for r in rels:
            since = r["since_ch"]
            since_disp = int(since) if isinstance(since, float) and since.is_integer() else since
            line = f"- {r['a']} ←→ {r['b']} : {r['kind']} (从第{since_disp}章起)"
            if r.get("note"):
                line += f"  // {r['note']}"
            parts.append(line)
        parts.append("")

    # 未解伏笔
    fores = active_foreshadowings_at(project_dir, chapter_id)
    if fores:
        parts.append("## 当前未解伏笔（请避免遗忘，本章可顺势处理或继续保留）")
        for f in fores:
            raised = f["raised_ch"]
            raised_disp = int(raised) if isinstance(raised, float) and raised.is_integer() else raised
            imp = f.get("importance", "medium")
            line = f"- [{f['id']}|{imp}] (第{raised_disp}章埋) {f['what']}"
            parts.append(line)
        parts.append("")

    if not parts:
        return ""
    return "\n".join(parts)
