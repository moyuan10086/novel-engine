"""JSON 结构校验 — outline / state / profiles 的轻量验证。

无外部依赖，纯 dict 遍历。返回错误列表，空列表 = 通过。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaError:
    path: str
    message: str

    def __str__(self) -> str:
        return f"[{self.path}] {self.message}"


def validate_outline(data: Any) -> list[SchemaError]:
    errors: list[SchemaError] = []
    if not isinstance(data, dict):
        errors.append(SchemaError("", "outline 必须是 dict"))
        return errors

    if "meta" not in data:
        errors.append(SchemaError("meta", "缺少 meta 字段"))
    else:
        meta = data["meta"]
        if not isinstance(meta, dict):
            errors.append(SchemaError("meta", "meta 必须是 dict"))
        else:
            if not meta.get("title"):
                errors.append(SchemaError("meta.title", "缺少书名"))

    if "world" not in data:
        errors.append(SchemaError("world", "缺少 world 字段"))
    else:
        world = data["world"]
        if not isinstance(world, dict):
            errors.append(SchemaError("world", "world 必须是 dict"))
        elif not world.get("setting"):
            errors.append(SchemaError("world.setting", "缺少世界观描述"))

    if "characters" not in data:
        errors.append(SchemaError("characters", "缺少 characters 字段"))
    elif not isinstance(data["characters"], list):
        errors.append(SchemaError("characters", "characters 必须是 list"))
    else:
        for i, ch in enumerate(data["characters"]):
            if not isinstance(ch, dict):
                errors.append(SchemaError(f"characters[{i}]", "必须是 dict"))
            elif not ch.get("name"):
                errors.append(SchemaError(f"characters[{i}].name", "缺少角色名"))

    if "chapters" not in data:
        errors.append(SchemaError("chapters", "缺少 chapters 字段"))
    elif not isinstance(data["chapters"], list):
        errors.append(SchemaError("chapters", "chapters 必须是 list"))
    else:
        seen_ids: set[float] = set()
        for i, ch in enumerate(data["chapters"]):
            prefix = f"chapters[{i}]"
            if not isinstance(ch, dict):
                errors.append(SchemaError(prefix, "必须是 dict"))
                continue
            if "id" not in ch:
                errors.append(SchemaError(f"{prefix}.id", "缺少 id"))
            else:
                cid = float(ch["id"])
                if cid in seen_ids:
                    errors.append(SchemaError(f"{prefix}.id", f"重复 id: {ch['id']}"))
                seen_ids.add(cid)
            if not ch.get("title"):
                errors.append(SchemaError(f"{prefix}.title", "缺少标题"))
            if not ch.get("synopsis"):
                errors.append(SchemaError(f"{prefix}.synopsis", "缺少 synopsis"))

    return errors


def validate_state(data: Any) -> list[SchemaError]:
    errors: list[SchemaError] = []
    if not isinstance(data, dict):
        errors.append(SchemaError("", "state 必须是 dict"))
        return errors

    if "summaries" not in data:
        errors.append(SchemaError("summaries", "缺少 summaries 字段"))
    elif not isinstance(data["summaries"], dict):
        errors.append(SchemaError("summaries", "summaries 必须是 dict"))

    if "done" not in data:
        errors.append(SchemaError("done", "缺少 done 字段"))
    elif not isinstance(data["done"], list):
        errors.append(SchemaError("done", "done 必须是 list"))

    return errors


def validate_profiles(data: Any) -> list[SchemaError]:
    errors: list[SchemaError] = []
    if not isinstance(data, dict):
        errors.append(SchemaError("", "profiles 必须是 dict"))
        return errors

    if "characters" not in data:
        errors.append(SchemaError("characters", "缺少 characters 字段"))
    elif not isinstance(data["characters"], dict):
        errors.append(SchemaError("characters", "characters 必须是 dict"))
    else:
        for name, char in data["characters"].items():
            prefix = f"characters.{name}"
            if not isinstance(char, dict):
                errors.append(SchemaError(prefix, "必须是 dict"))
                continue
            if "static" not in char and "snapshots" not in char:
                errors.append(SchemaError(prefix, "至少需要 static 或 snapshots"))
            if "snapshots" in char:
                if not isinstance(char["snapshots"], list):
                    errors.append(SchemaError(f"{prefix}.snapshots", "必须是 list"))
                else:
                    for j, snap in enumerate(char["snapshots"]):
                        if not isinstance(snap, dict):
                            errors.append(SchemaError(f"{prefix}.snapshots[{j}]", "必须是 dict"))
                        elif "as_of_ch" not in snap:
                            errors.append(SchemaError(f"{prefix}.snapshots[{j}]", "缺少 as_of_ch"))

    if "foreshadowings" in data:
        if not isinstance(data["foreshadowings"], list):
            errors.append(SchemaError("foreshadowings", "必须是 list"))
        else:
            for i, f in enumerate(data["foreshadowings"]):
                if not isinstance(f, dict):
                    errors.append(SchemaError(f"foreshadowings[{i}]", "必须是 dict"))
                elif not f.get("id"):
                    errors.append(SchemaError(f"foreshadowings[{i}].id", "缺少 id"))

    if "relationships" in data:
        if not isinstance(data["relationships"], list):
            errors.append(SchemaError("relationships", "必须是 list"))

    return errors
