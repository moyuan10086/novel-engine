"""启动前健康检查 — 在 dispatcher.run() 前验证项目配置完整性。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import schemas


def check(project_dir: Path, outline: dict[str, Any] | None = None) -> list[str]:
    """返回错误消息列表，空列表表示通过。"""
    issues: list[str] = []

    # 1. outline.json 存在且可解析
    outline_path = project_dir / "outline.json"
    if not outline_path.exists():
        issues.append(f"outline.json 不存在: {outline_path}")
    elif outline is None:
        import json
        try:
            outline = json.loads(outline_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            issues.append(f"outline.json 解析失败: {e}")

    # 2. outline schema 校验
    if outline is not None:
        schema_errors = schemas.validate_outline(outline)
        for err in schema_errors:
            issues.append(f"outline schema: {err}")

    # 3. API_KEY 已设置
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("API_KEY", "")
    if not api_key:
        issues.append("未设置 OPENAI_API_KEY 或 API_KEY 环境变量")

    # 4. chapters 目录可写
    chapters_dir = project_dir / "chapters"
    if not chapters_dir.exists():
        try:
            chapters_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            issues.append(f"无法创建 chapters 目录: {e}")

    # 5. state 目录可写
    state_dir = project_dir / "state"
    if not state_dir.exists():
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            issues.append(f"无法创建 state 目录: {e}")

    # 6. profiles.json 校验（如果存在）
    profiles_path = project_dir / "state" / "profiles.json"
    if profiles_path.exists():
        import json
        try:
            profiles_data = json.loads(profiles_path.read_text(encoding="utf-8"))
            profile_errors = schemas.validate_profiles(profiles_data)
            for err in profile_errors:
                issues.append(f"profiles schema: {err}")
        except (json.JSONDecodeError, OSError) as e:
            issues.append(f"profiles.json 解析失败: {e}")

    return issues
