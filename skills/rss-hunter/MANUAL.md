# RSS-Hunter 使用手册

> 信息源猎手：自动抓取 RSS，发现认知裂缝，写入 Obsidian 知识库

---

## 这是什么？

RSS-Hunter 是一个自动化工具，帮你做三件事：

1. **抓取**：从 15 个信息源（知乎、36氪、Hacker News 等）自动获取最新文章
2. **检测**：用 AI 分析每篇文章，寻找"认知裂缝"——大众认知和现实之间的差距
3. **记录**：把发现的内容自动写入你的 Obsidian 笔记库

### 什么是"认知裂缝"？

简单说，就是"大家都这么认为，但事实并非如此"的情况。

举个例子：
- **共识**：AI 会创造更多就业机会
- **现实**：最新数据显示 AI 导致程序员失业率上升 30%
- **裂缝类型**：数据裂缝（新数据推翻旧认知）

发现这种裂缝 = 发现一个好的写作选题。

---

## 前置条件

开始之前，确保你有：

| 条件 | 说明 |
|------|------|
| Python 3.10+ | 运行 `python --version` 检查 |
| PyYAML | 运行 `pip install pyyaml` 安装 |
| Obsidian | 已安装，且有笔记库 |
| PRISM-OS 项目 | 已克隆到本地 |
| LLM API Key | Kimi / OpenRouter 任选一个（裂缝检测需要） |

### 检查 Python

```bash
python --version
# 应该显示 Python 3.10.x 或更高
```

### 安装 PyYAML

```bash
pip install pyyaml
```

### 检查 LLM API Key

```bash
# Kimi（推荐，国内快）
echo %KIMI_API_KEY%

# 或者 OpenRouter（免费模型兜底）
echo %OPENROUTER_API_KEY%
```

如果都没有，需要先设置一个。推荐用 Kimi：

1. 去 https://platform.moonshot.cn 注册
2. 创建 API Key
3. 设置环境变量：`set KIMI_API_KEY=你的key`

---

## 目录结构

```
skills/rss-hunter/
├── config/
│   └── feeds.yaml          # 信源配置（你要监控哪些网站）
├── scripts/
│   ├── rss_hunter.py       # 主程序
│   └── obsidian_writer.py  # Obsidian 写入模块
├── data/
│   └── .gitignore
└── tests/
    └── test_rss_hunter.py  # 测试文件
```

---

## 第一步：配置信源

打开 `config/feeds.yaml`，你会看到 15 个已配置好的信源：

```yaml
monitored_sources:
  - name: "知乎热榜"
    url: "https://rsshub.app/zhihu/hot"
    category: "social"
    tags: ["热点", "中文"]
    region: "cn"
    priority: "high"

  - name: "Hacker News"
    url: "https://rsshub.app/hacker-news/best"
    category: "ai"
    tags: ["AI", "英文"]
    region: "intl"
    priority: "high"
  # ... 还有 13 个
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | 信源名称，用于显示和 `--source` 过滤 |
| `url` | 是 | RSS 地址（大多数用 rsshub.app 代理） |
| `category` | 否 | 分类，如 ai / tech / social / business / news |
| `tags` | 否 | 标签列表，写入 Obsidian frontmatter |
| `region` | 否 | cn（国内）/ intl（国际） |
| `priority` | 否 | high / medium / low（目前仅作标记） |
| `check_interval` | 否 | 预留字段，MVP 不使用 |

### 添加新信源

在 `monitored_sources` 列表末尾加一个：

```yaml
  - name: "我的信源"
    url: "https://rsshub.app/xxx/rss"  # RSS 地址
    category: "ai"
    tags: ["AI", "中文"]
    region: "cn"
    priority: "medium"
```

### 找 RSS 地址

大部分网站没有直接提供 RSS，用 [RSSHub](https://rsshub.app) 代理：

| 网站 | RSS 地址 |
|------|----------|
| 知乎热榜 | `https://rsshub.app/zhihu/hot` |
| 微博热搜 | `https://rsshub.app/weibo/hot/search` |
| 36氪 | `https://rsshub.app/36kr/feed` |
| Hacker News | `https://rsshub.app/hacker-news/best` |
| TechCrunch | `https://rsshub.app/techcrunch/rss` |

更多路由见：https://docs.rsshub.app/

---

## 第二步：配置 Obsidian 路径

RSS-Hunter 需要知道你的 Obsidian 笔记库在哪里。

### 方法一：环境变量（推荐）

```bash
set OBSIDIAN_VAULT_PATH=D:\软件\obsidian笔记\内容素材库
```

### 方法二：使用默认路径

默认路径是 `D:\软件\obsidian笔记\内容素材库`。如果你的笔记库在这个位置，不用改任何东西。

### 输出目录

RSS-Hunter 会自动创建以下目录：

```
你的笔记库/
└── 40_知识库/
    ├── 洞察库/
    │   └── rss-cracks/       # 有认知裂缝的文章
    └── 原子库/
        └── rss-items/        # 普通文章
```

---

## 第三步：运行

### 命令一览

```bash
# 进入项目目录
cd D:\myproject\PRISM-OSv1

# 1. 抓取所有信源（只更新去重记录，不做裂缝检测）
python skills/rss-hunter/scripts/rss_hunter.py fetch

# 2. 抓取 + 裂缝检测 + 写入 Obsidian（完整流程）
python skills/rss-hunter/scripts/rss_hunter.py hunt

# 3. 只处理指定信源
python skills/rss-hunter/scripts/rss_hunter.py hunt --source "36氪"
```

### fetch vs hunt 的区别

| 命令 | 做什么 | 用时 | LLM 调用 |
|------|--------|------|----------|
| `fetch` | 抓取 RSS + 去重记录 | 快（几秒） | 无 |
| `hunt` | fetch + 裂缝检测 + 写入 Obsidian | 慢（每条目需 LLM） | 每条新文章 1 次 |

### 运行示例

```bash
> python skills/rss-hunter/scripts/rss_hunter.py hunt --source "36氪"

[检查] 36氪...
[写入] 普通 → 2026-05-14-新框架发布性能提升50%.md
[写入] 裂缝 → 2026-05-14-AI导致程序员失业率上升30%.md
========================================
【PRISM-OS 认知裂缝发现】
========================================

共识：AI 会创造更多就业机会
现实：AI 导致程序员失业率上升 30%

裂缝类型：数据裂缝 | 置信度：85%
来源：36氪
原文：AI 导致程序员失业率上升 30%

建议选题方向：
  1. 为什么 AI 创造就业的数据是错的？
  2. 程序员失业潮：被忽视的真相

========================================

========================================
[完成] 裂缝: 1, 普通: 5, 错误: 0
========================================
```

---

## 第四步：查看结果

### 在 Obsidian 中查看

打开 Obsidian，导航到：

- **有裂缝的文章**：`40_知识库/洞察库/rss-cracks/`
- **普通文章**：`40_知识库/原子库/rss-items/`

每篇文章都是一个 Markdown 文件，带有 YAML frontmatter：

```markdown
---
source: 36氪
category: ai
tags: [AI, 科技, 中文]
date: 2026-05-14
url: https://...
crack_type: 数据裂缝
confidence: 0.85
---

# AI 导致程序员失业率上升 30%

最新调研报告显示...

## 认知裂缝
- 共识：AI 会创造更多就业机会
- 现实：AI 导致程序员失业率上升 30%
- 裂缝类型：数据裂缝
- 置信度：85%
```

### 去重机制

RSS-Hunter 会记住已处理过的文章（通过 MD5 指纹）。重复运行 `hunt` 不会重复处理同一篇文章。

---

## 常见问题

### Q: 运行报错 "ModuleNotFoundError: No module named 'yaml'"

```bash
pip install pyyaml
```

### Q: 运行报错 "HTTP Error 403: Forbidden"

rsshub.app 服务可能暂时不可用。解决方案：

1. 等一会儿再试
2. 换一个 rsshub 镜像（修改 feeds.yaml 中的 url）
3. 自建 rsshub：https://docs.rsshub.app/deploy/

### Q: 运行报错 "KIMI_API_KEY not set"

裂缝检测需要 LLM API。设置环境变量：

```bash
set KIMI_API_KEY=你的key
```

或者用 OpenRouter（免费模型）：

```bash
set OPENROUTER_API_KEY=你的key
```

### Q: Obsidian 中没看到文件

检查：
1. `OBSIDIAN_VAULT_PATH` 环境变量是否正确
2. Obsidian 是否刷新了文件列表（按 Ctrl+R）
3. 查看终端输出是否有 `[写入]` 日志

### Q: 想添加新的信息源

编辑 `config/feeds.yaml`，在 `monitored_sources` 列表末尾添加新条目。参考上面的"添加新信源"章节。

### Q: 想跳过某些信源

在 `config/feeds.yaml` 中删除或注释掉不需要的条目：

```yaml
  # - name: "不需要的信源"
  #   url: "..."
```

### Q: 裂缝检测太慢

每个新文章都需要调用一次 LLM，这是正常的。如果想先看看有哪些新文章，用 `fetch` 命令：

```bash
python skills/rss-hunter/scripts/rss_hunter.py fetch
```

### Q: Windows 终端显示乱码

这是 Windows GBK 编码问题，不影响实际功能。文件内容是正确的 UTF-8 编码。

---

## 进阶用法

### 自动定时运行

Windows 任务计划程序：

```bat
@echo off
cd /d D:\myproject\PRISM-OSv1
python skills/rss-hunter/scripts/rss_hunter.py hunt >> logs\rss-hunter.log 2>&1
```

设置每天运行一次（比如早上 9 点）。

### 自建 RSSHub

如果 rsshub.app 不稳定，可以自己部署：

```bash
# Docker 部署
docker run -d --name rsshub -p 1200:1200 diygod/rsshub
```

然后把 feeds.yaml 中的 `https://rsshub.app` 改成 `http://localhost:1200`。

### 查看去重记录

去重数据存在 `.claude/logs/rss_dedup.json`，可以查看已处理过的文章指纹：

```bash
type .claude\logs\rss_dedup.json
```

---

## 技术细节（选读）

### 数据流

```
RSS Feed (XML)
    ↓
parse_xml() 解析
    ↓
extract_items() 提取条目
    ↓
is_duplicate() 去重检查（MD5 指纹）
    ↓
analyze_content() 裂缝检测（LLM）
    ↓
write_crack() / write_item() 写入 Obsidian
```

### 复用的模块

| 模块 | 来源 | 用途 |
|------|------|------|
| feed_parser.py | `.claude/` | RSS/Atom 解析 + MD5 去重 |
| crack_hunter_wrapper.py | `.claude/` | 认知裂缝检测（5 种类型） |
| rss_monitor.py | `.claude/` | HTTP 抓取（SSL bypass、超时） |
| call_llm.py | `prism-os/scripts/` | LLM 调用（3 层 fallback） |

### 裂缝类型

| 类型 | 说明 | 例子 |
|------|------|------|
| 数据裂缝 | 新数据推翻旧共识 | "AI 创造就业" vs 实际失业数据 |
| 逻辑裂缝 | 前提假设被质疑 | "学历越高收入越高" 被反例推翻 |
| 时效裂缝 | 情况已变，旧结论过时 | "远程办公效率低" 已被证明错误 |
| 视角裂缝 | 换个角度看同一个问题 | 管理者 vs 员工对"996"的不同看法 |
| 因果裂缝 | 表面因果被揭示为虚假 | "成功因为早起" 实际是相关非因果 |
