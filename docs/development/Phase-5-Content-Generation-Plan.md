# PRISM-OS Phase 5 内容生成方案

> 版本：1.0 | 日期：2026-05-20 | 状态：**规划中，待开发**

---

## 一、Phase 5 定位

**目标**：在 CCOS 大纲（Phase 4.5-4.7）基础上，实现从大纲到完整初稿的 AI 生成。

**用户场景**：个人创作者做自媒体（一个人或小团队），多平台运营（公众号 + 小红书）。

**核心原则**：
- 素材先行，生成在后（不凑合）
- 不做全篇生成，做模块级生成（保证质量可控）
- 双平台串行处理（先完成一个，再处理另一个）
- 素材入库后双平台共用
- 修改记录后台静默，不打断流程

---

## 二、整体流程

```
CCOS 大纲确认（双平台各14项）
        ↓
用户选择当前处理平台（wechat / xiaohongshu）
        ↓
平台素材缺口分析
    ↓
    缺口提示 → 全网搜索推荐 / 用户手写 → 入库 Obsidian
    ↓
    重新召回 → 素材验证通过
        ↓
分模块生成（逐模块：确认/重写/手动改）
    ↓
完整草稿输出
        ↓
切换另一平台 → 素材已备，直接生成
```

---

## 三、素材系统

### 3.1 素材召回增强（Phase 4.6 基础上的扩展）

当前 Gap Analysis 只输出"缺什么"，不区分素材类型。

Phase 5 需要按模块类型召回：

| 模块 | 素材类型 | 召回策略 |
|------|---------|---------|
| HOOK | 反直觉案例、冲突性数据 | 优先召回洞察库里的"反常识"类洞察 |
| CASE | 具体场景、人物故事、真实经历 | 优先召回原子库/案例库 |
| EXPLAIN | 分析框架、因果解释 | 优先召回原子库相关概念 |
| MODEL | 认知模型、方法论框架 | 优先召回原子库的方法类内容 |
| ACTION | 操作步骤、清单 | 优先召回方法类内容 |

### 3.2 素材缺口处理

当素材不足以支撑某个模块时：

```
缺口提示（详细说明缺什么类型的素材）
    ↓
全网搜索推荐（Tavily + DuckDuckGo/SerpAPI 多源）
    ↓
返回 3-5 篇相关文章（标题+摘要+URL）
    ↓
用户选择 1-3 篇入库
    ↓
AI 抓取选中文章 → 提取关键段落 → 生成 Obsidian frontmatter
    ↓
用户确认入库
    ↓
重新召回 → 素材验证通过
```

**备选搜索源**：
- Tavily API（主）
- DuckDuckGo API / SerpAPI（备）

**抓取工具**：
- OpenCIL / AutoCLI

### 3.3 用户手写案例

用户也可以直接写一段案例文案，AI 润色后用于生成。

**润色原则**：
- 让内容更像"文章"而非"聊天记录"
- 口语化 → 书面化
- 精简重复内容
- 前后逻辑连贯
- **不改变原意、不扩展内容、不改变第一人称视角**

**平台适配**：
- 公众号：更书面化
- 小红书：保留口语感

### 3.4 Obsidian 入库标准（严格遵循现有结构）

**Obsidian 库**：`D:\软件\obsidian笔记\内容素材库`

#### 案例类素材 → `40_知识库/原子库/`
使用 `Case_案例模板.md`：

```yaml
---
type: case
status: processed
topics: []
industries: []
platforms: []
emotions: []
quality_score: 7
credibility: 8
is_evergreen: false
content_date:
source_url:
source_type: article
atom_ids: []
created:
updated:
---

# 标题

## 核心内容（300字概括）

## 关键观点

1.
2.
3.

## 我的理解

（用户对这个内容的思考和感悟）

## 关联应用

（这个内容可以用在哪些场景）

---

## 拆解出的素材原子
> [!atom] 观点原子 / 案例原子 / 数据原子 / 金句原子 / 方法原子
```

#### 提取出的核心观点/数据 → `40_知识库/原子库/`
使用 `Atom_原子模板.md`：

```yaml
---
type: atom
subtype: method  # viewpoint/case/data/quote/method
status: active
topics: []
applicable_topics: []
source_note: ""  # 必填：来源原文文件名
quality_score: 8
usage_count: 0
confidence: 8
created: [DATE]
updated: [DATE]
---
```

#### 发现的认知裂缝 → `40_知识库/洞察库/`
使用 `Insight_洞察模板.md`（现有逻辑不变）。

---

## 四、模块生成设计

### 4.1 分模块生成 vs 全篇生成

**选择：分模块生成**

| 维度 | 全篇生成 | 分模块生成 |
|------|----------|------------|
| 质量可控性 | 低（5000字会漂移） | 高（每段独立生成） |
| 用户参与感 | 低 | 高（逐段确认） |
| 修改追踪粒度 | 粗 | 细 |
| 中断/恢复 | 难 | 易 |
| 生成失败影响 | 大 | 小（只废一段） |

### 4.2 平台模块配置

| 模块 | 公众号 | 小红书 | 说明 |
|------|--------|--------|------|
| HOOK | ✅ 必有 | ✅ 必有 | 公众号是开篇，小红书是封面 |
| CASE | ✅ 必有 | ✅ 必有 | 公众号是论据，小红书是故事即观点 |
| EXPLAIN | ✅ 必有 | ❌ 可选 | 公众号需要分析解读 |
| MODEL | ✅ 建议有 | ❌ 可选 | 公众号需要框架感 |
| COUNTER | ✅ 建议有 | ❌ 可选 | 制造记忆点 |
| ACTION | ✅ 建议有 | ✅ 必有 | 给行动路径 |
| BOUNDARY | ✅ 建议有 | ❌ 可选 | 提升高级感 |

### 4.3 各模块 prompt 差异

#### HOOK

| 维度 | 公众号 | 小红书 |
|------|--------|--------|
| 角色 | 思想产品式的开篇 | 种草安利式的封面 |
| 长度 | 20-30字 | 20字以内，可带emoji |
| 功能 | 制造认知停顿，让人重新思考 | 制造情绪共鸣，让人想点进去 |
| 写法 | 反直觉断言/数据冲击/强冲突场景 | 身份标签/情绪词/悬念/"这说的就是我" |
| 禁止 | 正确的废话、温和观点 | 平铺直叙、无刺激点 |

#### CASE

| 维度 | 公众号 | 小红书 |
|------|--------|--------|
| 功能 | 论据，服务论点 | 主角，故事即观点 |
| 深度 | 深度叙事，500字以上 | 短平快场景，200-300字 |
| 结构 | 起承转合，决策/心理变化 | 情绪弧线，高潮前置 |
| 视角 | 第三或第一均可 | 第一人称亲历感 |
| 关键 | 细节够真，有时间感 | 情绪共鸣强，能让读者代入 |

#### MODEL

| 维度 | 公众号 | 小红书 |
|------|--------|--------|
| 功能 | 框架感，要有命名 | 不强求命名，更随意 |
| 结构 | 完整框架，3层以上 | 一个核心观点够用 |
| 关键 | 让人能记住模型名字 | 避免说教，让读者自己悟 |

### 4.4 前序模块上下文传递

每个模块生成时传入前序模块摘要，避免重复和断裂：

```python
def _build_module_context(previous_modules: List[Dict]) -> str:
    """构建前序模块摘要，供下一模块使用"""
    if not previous_modules:
        return ""
    summaries = []
    for m in previous_modules[-2:]:  # 只传最近2个模块
        summaries.append(f"{m['模块']}：{m['draft'][:50]}...")
    return "前序模块摘要：" + " | ".join(summaries)
```

### 4.5 逐模块交互流程

```
[模块1 HOOK] 生成 → 显示草稿 + 素材来源
        ↓
用户操作：✓确认 / 🔄重写 / ✏️手动修改
        ↓
[模块2 CASE] 生成（携带HOOK的认知状态）
        ↓
... 重复直到所有模块
        ↓
[预览完整初稿] 可导出/复制/继续编辑
```

**重写策略（Phase 5.0）**：
- 不提供"重写方向"选项，让 LLM 重新生成
- 连续重写 2-3 次仍不满意，提示"建议手动修改"

---

## 五、修改记录系统（后台静默）

用户手动修改草稿时，记录：

```python
{
    "module": "HOOK",
    "original": "...",
    "modified": "...",
    "user_id": "digital_twin_id",
    "timestamp": "2026-05-20T10:30:00",
    "platform": "wechat",
    "topic": "AI让内容创作更容易"
}
```

**Phase 5.0 不做**：
- 修改原因分析（信号不够）
- 风格匹配评分（Phase 5.5）
- 主动弹出框要求用户解释

---

## 六、技术实现路径

### Phase 5.0 ✅（已实现）

**已做**：
- 分模块生成（公众号为主，小红书后续）
- 素材按类型召回（Obsidian 增强）
- 素材缺口 → 全网搜索推荐 → 入库流程
- 用户手写案例 → AI 润色
- 逐模块确认交互
- 后台修改记录

### Phase 5.5 ✅（已实现）

- 小红书版本支持
- 风格匹配度评分
- 修改习惯分析
- 文章抓取 → Obsidian 入库 → 自动召回全流程
- 交互界面（逐模块确认/重写/手动改）

### Phase 5.6 ✅（2026-05-25，commit 084ab0d+78be94a）

- Issue 1: 微信抓取三级降级（autocli → wechat-article-extractor skill → markitdown-web）
- Issue 2: 搜索结果传入生成模块（imported 素材追加到 materials）
- Issue 3: E2E 测试（test_e2e.py 7/7 通过）
- Issue 4: LLM 每 provider 指数退避重试（1s → 2s，max_retries=2）
- Issue 5: interactive workflow 润色接入（[p]润色后编辑）
- Issue 6: archive 命令暴露（--search / --trends / --list）
- Issue 7: 抓取重试机制（超时 3 次退避 1s→2s→4s，403/451 不重试）

### Phase 6.0（已完成，v1.3.0）

- **完整方案**：`docs/development/Phase-6-Data-Feedback-Loop-Plan.md`
- **核心**：飞书多维表格手动录入 5 个数字 → 后台自动同步 → 反哺生成策略
- **MVP 范围**：模板优选（B：按平台 × 叙事策略 / 模块组合统计真实互动率）
- **状态**：✅ 已完成，合并到 main（commit 98a0be4 + merge 9131abf）

### Phase 6.1（已完成，v1.3.1）

- **完整方案**：`docs/development/Phase-6.1-Calibration-Integration-Plan.md`
- **核心**：把 Phase 6.0 生成的 calibration.yaml 真正接入 narrate 步骤
- **新增**：`compute_calibration_boost()` + `evaluate_narrative_strategy(calibration=, platform=)`
- **状态**：✅ 已完成，合并到 main

### Phase 6.2（待启动，30+ 篇后）

- HKR 校准：用真实数据反推 H/K/R 哪个维度真预测互动率
- 样本量阈值：≥30 篇 + 距上次校准 >7 天

---

## 七、待讨论/优化事项

1. **Obsidian obsidian_writer.py 扩展**：新增 `write_case_material()` 等函数（增强功能，非阻塞）
2. **搜索推荐结果去重+排序**：Tavily 返回结果的相关性过滤（可优化）
3. **用户选择文章后的抓取方案**：OpenCIL/AutoCLI 的具体调用方式（Phase 5.6 已部分实现）
4. **模块 prompt 的完整实现**：每个模块的详细 prompt template（已基线实现）

---

## 八、参考文档

- `docs/development/Phase-4.7-LLM-Optimization-Plan.md` — Phase 4.7 优化方案（已完成）
- `docs/development/Phase-5-Content-Generation-Plan.md` — Phase 5 完整方案（Phase 5.0~5.6 已完成）
- `D:\软件\obsidian笔记\内容素材库\99_系统\Template\` — Obsidian 模板标准
- `skills/rss-hunter/scripts/obsidian_writer.py` — 现有 Obsidian 写入模块