"""持久化状态 — 支持多项目（传入 project_dir 而非 root）"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


def _state_path(project_dir: Path) -> Path:
    return project_dir / "state" / "state.json"


def _key(cid: float | int) -> str:
    if isinstance(cid, float) and cid.is_integer():
        cid = int(cid)
    return str(cid)


def load(project_dir: Path) -> dict[str, Any]:
    p = _state_path(project_dir)
    if not p.exists():
        return {"summaries": {}, "done": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"summaries": {}, "done": []}


def save(project_dir: Path, state: dict[str, Any]) -> None:
    p = _state_path(project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Windows 下并发 + tmp 重命名容易 PermissionError；改为直接写。
    # 调用方已通过 _LOCK 保证串行化。
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_done(project_dir: Path, chapter_id: float | int, summary: str) -> None:
    """线程/协程安全地登记完成"""
    with _LOCK:
        st = load(project_dir)
        st["summaries"][_key(chapter_id)] = summary
        existing = {float(x) for x in st.get("done", [])}
        if float(chapter_id) not in existing:
            st["done"].append(chapter_id)
            st["done"].sort(key=float)
        save(project_dir, st)


def prior_summaries(project_dir: Path, before_id: float | int) -> list[tuple[float, str]]:
    """返回 chapter_id < before_id 的所有摘要"""
    st = load(project_dir)
    out = []
    for k, v in st.get("summaries", {}).items():
        i = float(k)
        if i < float(before_id):
            out.append((i, v))
    out.sort(key=lambda x: x[0])
    return out


def following_summaries(project_dir: Path, after_id: float | int) -> list[tuple[float, str]]:
    """返回 chapter_id > after_id 的所有摘要（用于插入章）"""
    st = load(project_dir)
    out = []
    for k, v in st.get("summaries", {}).items():
        i = float(k)
        if i > float(after_id):
            out.append((i, v))
    out.sort(key=lambda x: x[0])
    return out


def is_done(project_dir: Path, chapter_id: float | int) -> bool:
    st = load(project_dir)
    return float(chapter_id) in {float(x) for x in st.get("done", [])}
