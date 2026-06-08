# 文档 6：Sprint Plan - 开发执行计划


## 一、开发路线图（Roadmap）

PRISM-OS 采用敏捷开发模式，分 4 个 Sprint 迭代交付：

| Sprint | 版本 | 核心功能 | 交付时间 | 验收标准 |
| --- | --- | --- | --- | --- |
| **Sprint 1** | V1 | 苏格拉底网关 + 棱镜引擎 + 现实校验 | 2 周 | 能生成 4 个正交标题并校验新颖度 |
| **Sprint 2** | V1.5 | 素材缺口分析 + 双端大纲生成 | 1 周 | 能输出 Gap Report 和两套大纲 |
| **Sprint 3** | V2 & V3 | 逻辑压力测试 + 刺客机制 + Prompt 自进化 | 2 周 | 能自动检测谬误并定期发起自我否定 |
| **Sprint 4** | V4 | 全域感知（RSS 监控 + 认知裂缝捕捉） | 1 周 | 能主动推送选题预警 |

---

## 二、Sprint 1：V1 核心闭环（2 周）

### 目标

实现“意图澄清 → 四维生成 → 现实校验”的完整流程。

### 任务拆解

#### Week 1：基础架构 + 苏格拉底网关

**Day 1-2：项目初始化**

- [ ]  创建 Python 项目骨架（使用 Poetry 管理依赖）

- [ ]  搭建目录结构：

  ```plaintext
  prism-os/
  ├── src/
  │   ├── core/          # 核心逻辑层
  │   ├── adapters/      # 适配器层
  │   ├── prompts/       # Prompt 库
  │   └── utils/         # 工具函数
  ├── tests/             # 单元测试
  ├── data/              # 数据存储
  ├── config/            # 配置文件
  └── pyproject.toml
  ```

- [ ]  配置开发环境（Python 3.11+, pre-commit hooks）

**Day 3-4：实现存储适配器**

- [ ]  实现 `LocalFileStorage` 类

- [ ]  创建默认配置文件 `user_config.yaml`

- [ ]  实现日志写入功能（JSONL 格式）

- [ ]  编写单元测试

**Day 5-7：实现苏格拉底网关**

- [ ]  实现 `AnthropicRouter` 类（LLM 调用封装）

- [ ]  编写“意图熵值计算” Prompt

- [ ]  实现 `SocraticGateway` 类：

  - `calculate_entropy(user_input)` 方法

  - `gate_decision(entropy)` 方法

- [ ]  编写单元测试（使用 Mock LLM）

- [ ]  集成测试：输入模糊命题，验证是否正确拦截

#### Week 2：棱镜引擎 + 现实校验

**Day 8-10：实现棱镜引擎**

- [ ]  编写“四维标题生成” Prompt

- [ ]  实现 `PrismEngine` 类：

  - `generate_candidates(thesis, config)` 方法

  - `check_orthogonality(titles)` 方法（使用 Embedding）

- [ ]  集成 Sentence Transformers 或 OpenAI Embeddings

- [ ]  编写单元测试

**Day 11-12：实现现实校验锚**

- [ ]  实现 `SerperAdapter` 类

- [ ]  编写“新颖度评估” Prompt

- [ ]  实现 `RealityAnchor` 类：

  - `validate_novelty(title, keywords)` 方法

- [ ]  编写单元测试

**Day 13-14：集成与端到端测试**

- [ ]  实现 `PRISMOrchestrator` 类（编排所有模块）

- [ ]  实现 CLI 入口（使用 Click 或 Typer）

- [ ]  端到端测试：

  - 输入：“AI 时代最大的不公平：它把‘会提问’的人变成超人，把‘会执行’的人变成垃圾”

  - 预期输出：4 个正交标题 + 新颖度评分

- [ ]  编写 [README.md](http://README.md) 和使用文档

### 验收标准

- [ ]  能正确拦截模糊输入（熵值 < 1.5）

- [ ]  能生成 4 个语义相似度 < 0.75 的标题

- [ ]  能调用搜索 API 并返回新颖度评分

- [ ]  所有数据写入 `topic_log.jsonl`

---

## 三、Sprint 2：V1.5 执行下沉（1 周）

### 目标

增强素材分析能力，支持双端内容生成。

### 任务拆解

**Day 1-3：实现知识网关**

- [ ]  实现 `LocalMarkdownGateway` 类（使用 ChromaDB）

- [ ]  索引本地 Markdown 文件夹

- [ ]  实现 `fetch_context(query)` 方法

- [ ]  编写单元测试

**Day 4-5：实现素材缺口分析**

- [ ]  编写“素材缺口分析” Prompt

- [ ]  实现 `GapAnalyzer` 类：

  - `analyze_gap(thesis, context)` 方法

- [ ]  集成到主流程中

- [ ]  编写单元测试

**Day 6-7：实现双端大纲生成**

- [ ]  编写“双端大纲生成” Prompt

- [ ]  实现 `OutlineGenerator` 类：

  - `generate_wechat_outline(title)` 方法

  - `generate_xiaohongshu_outline(title)` 方法

- [ ]  集成到主流程中

- [ ]  端到端测试

### 验收标准

- [ ]  能从本地文件夹检索相关素材

- [ ]  能输出 Gap Report（缺口分数 + 缺失证据列表）

- [ ]  能生成公众号和小红书两套大纲

---

## 四、Sprint 3：V2 & V3 战略逻辑（2 周）

### 目标

实现逻辑审计和自我进化能力。

### 任务拆解

#### Week 1：逻辑压力测试

**Day 1-3：实现逻辑审计器**

- [ ]  编写“逻辑压力测试” Prompt

- [ ]  实现 `LogicAuditor` 类：

  - `stress_test(title)` 方法

- [ ]  集成到主流程中

- [ ]  编写单元测试

**Day 4-5：实现认知旅程规划**

- [ ]  实现 `calculate_cognitive_distance(current, history)` 方法

- [ ]  集成到主流程中（在生成前检查）

- [ ]  编写单元测试

#### Week 2：刺客机制 + Prompt 自进化

**Day 6-8：实现刺客机制**

- [ ]  编写“自我否定” Prompt

- [ ]  实现 `AssassinTask` 类：

  - `scan_historical_topics(days=90)` 方法

  - `generate_reversal(topic)` 方法

- [ ]  实现定时任务调度（使用 APScheduler）

- [ ]  编写单元测试

**Day 9-10：实现 Prompt 自进化**

- [ ]  实现 `PromptEvolver` 类：

  - `analyze_edit_patterns(logs)` 方法

  - `update_system_prompt(patterns)` 方法

- [ ]  集成到主流程中（每 10 次选题后自动执行）

- [ ]  编写单元测试

### 验收标准

- [ ]  能检测出标题中的逻辑谬误（循环论证、幸存者偏差等）

- [ ]  能自动扫描 3 个月前的爆款并生成反转选题

- [ ]  能根据用户改词记录自动修改 Prompt

---

## 五、Sprint 4：V4 全域感知（1 周）

### 目标

实现主动选题推送能力。

### 任务拆解

**Day 1-3：实现 RSS 监控**

- [ ]  实现 `RSSMonitor` 类：

  - `fetch_feeds(sources)` 方法

  - `detect_cognitive_gap(articles, fingerprints)` 方法

- [ ]  集成外部信息源（如 Hacker News, 36Kr）

- [ ]  编写单元测试

**Day 4-5：实现认知裂缝捕捉**

- [ ]  实现 `CognitiveCrackDetector` 类：

  - `compare_consensus_vs_reality(topic)` 方法

- [ ]  实现推送机制（邮件或 Webhook）

- [ ]  编写单元测试

**Day 6-7：集成与优化**

- [ ]  端到端测试

- [ ]  性能优化（缓存、批量处理）

- [ ]  编写最终文档

### 验收标准

- [ ]  能监控至少 5 个外部信息源

- [ ]  能主动发现“社会共识与现实的裂缝”

- [ ]  能推送选题预警（每天最多 3 条）

---

## 六、技术栈与工具

| 类别 | 技术选型 | 用途 |
| --- | --- | --- |
| **语言** | Python 3.11+ | 主开发语言 |
| **依赖管理** | Poetry | 包管理 |
| **LLM SDK** | Anthropic Python SDK | 调用 Claude |
| **向量数据库** | ChromaDB | 本地向量检索 |
| **搜索 API** | Serper | 现实校验 |
| **存储** | SQLite / JSONL | 数据持久化 |
| **配置管理** | YAML + Pydantic | 类型安全的配置 |
| **日志** | structlog | 结构化日志 |
| **测试** | pytest + hypothesis | 单元测试 + 属性测试 |
| **任务调度** | APScheduler | 定时任务 |
| **CLI** | Typer | 命令行接口 |

---

## 七、开发规范

### 代码风格

- 使用 Black 格式化代码

- 使用 Ruff 进行 Lint 检查

- 使用 mypy 进行类型检查

### Git 工作流

- 主分支：`main`（稳定版本）

- 开发分支：`develop`（集成分支）

- 功能分支：`feature/xxx`（新功能）

- 修复分支：`fix/xxx`（Bug 修复）

### Commit 规范

```plaintext
feat: 添加苏格拉底网关模块
fix: 修复熵值计算错误
docs: 更新 README
test: 添加棱镜引擎单元测试
refactor: 重构适配器层
```

---

## 八、风险与应对

| 风险 | 影响 | 应对策略 |
| --- | --- | --- |
| **LLM API 不稳定** | 高 | 实现重试机制 + 降级策略（切换模型） |
| **向量检索性能差** | 中 | 使用缓存 + 限制检索范围 |
| **Prompt 效果不佳** | 高 | 快速迭代 + A/B 测试 |
| **成本超预算** | 中 | 成本编排 + 使用低成本模型 |

---

## 九、下一步

参考 **文档 7：QA & Validation - 验收与质量控制**，了解如何验证系统是否符合预期。