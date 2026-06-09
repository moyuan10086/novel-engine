---
name: novel-engine
description: "Chinese long-form novel generation engine. Use when: (1) generating chapters for a novel project, (2) managing outlines/profiles/lorebook, (3) checking generation progress, (4) quality review of generated chapters, (5) batch operations on novel projects. Trigger: /novel-engine"
---

# novel-engine — 长篇小说生成引擎 Skill

## Overview

novel-engine 是一套基于 LLM 的中文长篇小说生成框架，位于 `D:\文件\大学\大模型\实操\小说\novel-engine\`。本 skill 定义了 Claude Code 操作该引擎的标准流程。

## 工作目录

所有命令在以下目录执行：
```
cd "D:\文件\大学\大模型\实操\小说\novel-engine"
```

## 核心命令速查

### 生成章节
```bash
# 串行生成（最强一致性，推荐长篇）
python -m src.dispatcher --project "项目名" --mode strict

# 只生成指定章节
python -m src.dispatcher --only "11,12,13" --force

# 并发生成（快但一致性稍弱）
python -m src.dispatcher --mode parallel --concurrency 3

# 从断点续传（自动跳过已完成章节）
python -m src.dispatcher --project "项目名" --mode strict
```

### 检查进度
```bash
# 查看项目信息和完成进度
python -m src.cli info "项目名"

# 查看已完成章节列表
python -c "import json; s=json.load(open('projects/项目名/state/state.json')); print(f'已完成: {len(s[\"done\"])}/{len(json.load(open(\"projects/项目名/outline.json\"))[\"chapters\"])} 章')"
```

### 预览 Prompt（不调用 API）
```bash
python -m src.cli context "项目名" --chapter 12
```

### 合并出书
```bash
python -m src.merger --project "项目名"
# 输出: projects/项目名/book.md + book.txt
```

### 角色档案管理
```bash
# 添加状态快照
python -m src.profiles_cli snap add "项目名" "角色名" --at 50 --json '{"境界":"魂尊"}' --note "突破"

# 标记伏笔解决
python -m src.profiles_cli fore resolve "项目名" "F001" --at 120

# 预览某章注入的档案上下文
python -m src.profiles_cli context "项目名" --at 50
```

### 世界书
```bash
python -m src.cli lorebook list --project "项目名"
python -m src.cli lorebook test --text "测试文本" --chapter 50
```

## 工作流程

### 流程 A：批量生成章节

当用户要求生成章节时，按以下步骤执行：

1. **确认状态**：读取 `state/state.json` 确认当前进度
2. **选择模式**：
   - 长篇连续生成 → `--mode strict`（串行，每章读取前章尾部）
   - 独立章节/番外 → `--only "X,Y,Z" --mode parallel`
3. **启动生成**：使用 `run_in_background` 执行 dispatcher
4. **监控进度**：定期检查 chapters/ 目录新文件
5. **质量抽查**：生成完成后读取最后几章检查连贯性

### 流程 B：质量审查

生成后检查质量：

```bash
# 检查最新生成的章节文件大小（异常小=可能有问题）
Get-ChildItem "projects/项目名/chapters/" | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name, Length

# 读取章节检查内容
# 重点关注：开头是否衔接前章、角色状态是否正确、有无重复段落
```

**质量红线**：
- 章节 < 2KB → 可能生成中断，需 `--force` 重生成
- 出现大段重复 → `_truncate_repetition()` 应已处理，检查是否遗漏
- 角色状态倒退 → 检查 profiles.json 快照是否缺失

### 流程 C：大纲维护

生成过程中发现偏离时：

1. 读取邻域实况（state.json 摘要）确认实际走向
2. 修改后续章节的 outline.json（synopsis + key_beats）适配已写内容
3. 原则：**偏离即修正后续大纲，不重写已生成章节**

### 流程 D：档案迭代

每生成 20-30 章后执行一次：

1. 检查角色状态变化，补录 `snap add`
2. 检查伏笔是否已回收，标记 `fore resolve`
3. 检查是否有新关系建立，补录 `rel add`
4. 运行 `python -m src.profiles_cli context "项目名" --at N` 验证注入内容

## 环境配置

关键 `.env` 变量：

| 变量 | 当前推荐值 | 说明 |
|------|-----------|------|
| MODEL | grok-4-1-fast-reasoning | Thinking 模型，质量高 |
| MAX_TOKENS | 24000 | thinking 模型需要更大空间 |
| TEMPERATURE | 0.85 | 创作温度 |
| CONCURRENCY | 3 | strict 模式下实际为 1 |
| MAX_RETRIES | 4 | 失败重试 |

## 注意事项

1. **Thinking 模型**：grok-4-1-thinking/fast-reasoning 等模型会消耗 token 用于"思考"步骤，MAX_TOKENS 需设为 24000+ 才能保证输出足够长
2. **strict 模式**：每章必须等前一章完成（读取其尾部 ~2500 字），实际并发为 1
3. **断点续传**：dispatcher 自动跳过 `state.json` 中 `done` 列表里的章节
4. **后处理**：worker 自动执行三步清理 — 剥离元注释 → 清理章号引用 → 截断重复段落
5. **Windows 路径**：所有命令在 PowerShell 中执行，路径用引号包裹
6. **长时间运行**：生成 100+ 章可能需要 1-2 小时，使用 `run_in_background` 并用 Monitor 监控
