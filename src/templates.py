"""Templates — YAML 模板加载与合并。

从 prompts/ 目录加载 base + genre + style 模板，合并为最终 prompt 配置。
需要可选依赖: pip install novel-engine[templates]

层级: base.yaml → genres/<genre>.yaml → styles/<style>.yaml
后层覆盖前层同名 key，list 类型做追加。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        raise RuntimeError("pyyaml 未安装。pip install novel-engine[templates]")
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并。list 追加，dict 递归，标量覆盖。"""
    result = base.copy()
    for key, val in override.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = _deep_merge(result[key], val)
            elif isinstance(result[key], list) and isinstance(val, list):
                result[key] = result[key] + val
            else:
                result[key] = val
        else:
            result[key] = val
    return result


def load_template(
    genre: str | None = None,
    style: str | None = None,
    prompts_dir: Path | None = None,
) -> dict[str, Any]:
    """加载并合并模板。返回最终配置 dict。

    Args:
        genre: 题材名（对应 genres/<genre>.yaml）
        style: 风格名（对应 styles/<style>.yaml）
        prompts_dir: 模板目录，默认为项目根目录下的 prompts/
    """
    root = prompts_dir or PROMPTS_DIR

    result = _load_yaml(root / "base.yaml")

    if genre:
        genre_data = _load_yaml(root / "genres" / f"{genre}.yaml")
        if genre_data:
            result = _deep_merge(result, genre_data)

    if style:
        style_data = _load_yaml(root / "styles" / f"{style}.yaml")
        if style_data:
            result = _deep_merge(result, style_data)

    return result


def get_system_prompt(template: dict[str, Any], is_insert: bool = False) -> str:
    """从模板配置中提取最终 system prompt。"""
    parts = []

    base_key = "system_insert" if is_insert else "system_base"
    if base_key in template:
        parts.append(template[base_key].strip())

    if "writing_rules" in template:
        rules = template["writing_rules"]
        if isinstance(rules, list):
            rules_text = "\n".join(f"- {r}" for r in rules)
            parts.append(f"写作规则：\n{rules_text}")

    if "output_format" in template:
        parts.append(template["output_format"].strip())

    if "system_addon" in template:
        parts.append(template["system_addon"].strip())

    if "vocabulary_hints" in template:
        hints = template["vocabulary_hints"]
        hint_parts = []
        if "avoid" in hints:
            hint_parts.append("避免使用：" + "、".join(hints["avoid"]))
        if "prefer" in hints:
            hint_parts.append("推荐使用：" + "、".join(hints["prefer"]))
        if hint_parts:
            parts.append("\n".join(hint_parts))

    return "\n\n".join(parts)


def get_boundary_note(template: dict[str, Any]) -> str:
    """获取插入章边界提示。"""
    return template.get("boundary_note", "").strip()


def list_available(prompts_dir: Path | None = None) -> dict[str, list[str]]:
    """列出可用的 genre 和 style 模板。"""
    root = prompts_dir or PROMPTS_DIR
    result: dict[str, list[str]] = {"genres": [], "styles": []}

    genres_dir = root / "genres"
    if genres_dir.exists():
        result["genres"] = sorted(
            p.stem for p in genres_dir.glob("*.yaml")
        )

    styles_dir = root / "styles"
    if styles_dir.exists():
        result["styles"] = sorted(
            p.stem for p in styles_dir.glob("*.yaml")
        )

    return result
