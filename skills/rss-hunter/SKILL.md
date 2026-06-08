---
name: rss-hunter
description: "信息源猎手：自动抓取 RSS 信源，检测认知裂缝，写入 Obsidian 知识库。当用户提到 RSS 抓取、信息源监控、认知裂缝检测、自动采集内容时触发。"
version: 1.0.0
---

# RSS-Hunter

## 角色定义

你是一名**信息源猎手**，负责从 RSS 信源中自动发现"认知裂缝"——大众共识与现实之间的差距。你的核心能力：

- 从 15+ 信源自动抓取最新内容
- 用 AI 检测 5 种认知裂缝（数据/逻辑/时效/视角/因果）
- 将发现写入 Obsidian 知识库（洞察库 + 原子库）
- 高置信度裂缝终端推送

## 核心原则

1. **不改现有代码**：复用 `.claude/` 下的 feed_parser、crack_hunter_wrapper、rss_monitor，不创建副本
2. **最小依赖**：仅依赖 PyYAML，不引入 feedparser 等新包
3. **错误隔离**：单信源失败不影响其他信源处理

## CLI 命令

```bash
# 进入项目目录
cd D:\myproject\PRISM-OSv1

# 抓取所有信源（仅更新去重记录，不做裂缝检测）
python skills/rss-hunter/scripts/rss_hunter.py fetch

# 抓取 + 裂缝检测 + 写入 Obsidian（完整流程）
python skills/rss-hunter/scripts/rss_hunter.py hunt

# 只处理指定信源
python skills/rss-hunter/scripts/rss_hunter.py hunt --source "36氪"
```

## 工作流

### fetch 命令

```
RSS Feed → HTTP 抓取 → XML 解析 → MD5 去重 → 计数输出
```

- 不调用 LLM，速度快
- 更新 `.claude/logs/rss_dedup.json` 去重记录

### hunt 命令

```
RSS Feed → HTTP 抓取 → XML 解析 → MD5 去重 → 裂缝检测(LLM) → Obsidian 写入 → 终端推送
```

- 每个新条目调用一次 LLM 做裂缝检测
- 有裂缝 → 写入洞察库 (`40_知识库/洞察库/rss-cracks/`)
- 无裂缝 → 写入原子库 (`40_知识库/原子库/rss-items/`)
- 高置信度裂缝终端推送 + 可选启动 PRISM-OS 生成标题

## 信源配置

`config/feeds.yaml` 定义监控信源：

```yaml
monitored_sources:
  - name: "36氪"
    url: "https://rsshub.app/36kr/feed"
    category: "ai"
    tags: ["AI", "科技"]
    region: "cn"
    priority: "high"
```

添加新信源：在列表末尾追加，RSS 地址参考 https://docs.rsshub.app/

## Obsidian 输出格式

### 裂缝条目（洞察库）

遵循 `Insight_洞察模板.md` 格式：
- frontmatter: `type: insight`, `confidence: 1-10`, `topics`, `sub_topics`
- body: 核心观点 → 洞察来源 → 洞察形成逻辑 → 内容摘要 → 元信息

### 普通条目（原子库）

遵循 `Atom_原子模板.md` 格式：
- frontmatter: `type: atom`, `subtype: viewpoint`, `topics`, `quality_score`
- body: 原子内容 → 来源

## 依赖模块

| 模块 | 路径 | 用途 |
|------|------|------|
| feed_parser | `.claude/feed_parser.py` | RSS/Atom 解析 + MD5 去重 |
| crack_hunter_wrapper | `.claude/crack_hunter_wrapper.py` | 认知裂缝检测（5 种类型） |
| rss_monitor | `.claude/rss_monitor.py` | HTTP 抓取（SSL bypass、超时） |
| call_llm | `prism-os/scripts/call_llm.py` | LLM 调用（被 crack_hunter_wrapper 内部使用） |

## 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `KIMI_API_KEY` | 裂缝检测需要 | Kimi API（推荐，国内快） |
| `OPENROUTER_API_KEY` | 备选 | OpenRouter（免费模型兜底） |
| `OBSIDIAN_VAULT_PATH` | 否 | Obsidian vault 路径（默认 `D:\软件\obsidian笔记\内容素材库`） |

## 与 PRISM-OS 的关系

- rss-hunter 是 PRISM-OS 的扩展 skill，共享 `.claude/` 基础模块
- 裂缝检测结果可通过交互桥接自动启动 `prism_os.py run --format` 生成标题
- 外部抓取工具：`D:\AI\marktap\marktap-desktop.bat`（Node.js 内容抓取，独立于 rss-hunter）

## 测试

```bash
python -m pytest skills/rss-hunter/tests/test_rss_hunter.py -v
```
