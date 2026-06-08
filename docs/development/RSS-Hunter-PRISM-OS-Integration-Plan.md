# RSS-Hunter × PRISM-OS 深度整合方案（v2.0）

> 目标：将 RSS-Hunter 升级为「选题情报员」，具备认知信号提炼 + 表达入口识别能力
> 整合来源：topic_intelligence_agent_prd（选题情报员 PRD v1.0）
> 版本：v2.0（待开发）| 日期：2026-05-21

---

## 背景与问题

### RSS-Hunter 现状

RSS-Hunter 与 PRISM-OS 割裂：
- **触发断裂**：发现裂缝 → 推送终端，用户不会回来查看
- **消费断裂**：裂缝写入 Obsidian，但结构不对，无法被 PRISM-OS 有效召回
- **能力断裂**：只判断裂缝存在，不提炼认知信号，不识别表达入口

### 整合目标

升级为「选题情报员」——不只是发现裂缝，而是提炼认知信号 + 识别表达入口 + 关联创作者人格。

---

## 核心定位

**选题情报员** = 被动扫描多源 → 提炼认知信号 → 进入持久化队列 → PRISM-OS 按需消费

情报员负责「发现 + 提炼」，转化决策留给 PRISM-OS（保留人工确认环节）。

核心理念（来自 PRD）：
- 不给 50 个选题，给少量高价值认知刺激
- 不替代创作者思考，只激发认知反应
- 人格优先于流量，长期主题优先于热点

---

## 一、数据层

### 1.1 队列存储

```
data/
  crack_queue.json      # 当前队列（所有 status ≠ archived 的条目）
  crack_archive.json    # 归档（consumed 超过 60 天）
```

### 1.2 队列字段（v2.0 扩展）

```json
{
  "id": "uuid-v4",
  "title": "AI让程序员失业率上升30%",
  "source": "36氪",
  "source_link": "https://...",
  "crack_type": "数据裂缝",
  "consensus": "AI会创造更多就业机会",
  "reality": "AI导致程序员失业率上升30%",
  "confidence": 0.85,

  "created_at": "2026-05-21T10:00:00",
  "status": "new",
  "manual_tags": [],
  "priority_score": 0.85,
  "consumed_by": null,
  "notes": "",

  "signals": {
    "trend": "程序员职业安全感正在崩塌",
    "emotion": ["替代焦虑", "身份危机"],
    "contradiction": "AI 提高生产力，但降低普通内容价值",
    "homogenization_alert": null
  },

  "expression_angles": [
    {
      "type": "认知型创作者",
      "angle": "AI对普通程序员的影响：不是失业，是身份危机",
      "resonance": 0.9
    },
    {
      "type": "商业型创作者",
      "angle": "AI 时代的人力结构变化：程序员从执行者变为监督者",
      "resonance": 0.7
    }
  ],

  "creator_match": {
    "growth_stage": "系统型",
    "sensitive_directions": ["个体竞争力", "职业发展", "AI影响"],
    "match_score": 0.75
  }
}
```

### 1.3 新增字段说明

| 字段 | 来源 | 说明 |
|------|------|------|
| `signals` | LLM 提炼 | 趋势/情绪/矛盾/同质化预警 |
| `expression_angles` | LLM 生成 | 裂缝对应的不同表达入口 |
| `creator_match` | 数字分身 | 当前裂缝与创作者人格的匹配度 |

### 1.4 status 流转

```
[new] → 用户标记优先级 → [reviewed] → 用户选择切入 → [consumed] → 归档
    ↓                                          ↓
[用户判断无价值] → [dismissed]（直接删除，不归档）
```

### 1.5 优先级计算（v2.0）

```
priority_score = confidence × tag_multiplier × recency_factor × homogenization_penalty

tag_multiplier:
  "战略级" → ×2.0
  "关注" → ×1.5
  无标签 → ×1.0
  自由标签 → ×1.0

recency_factor:
  7天内 → ×1.0
  7-30天 → ×0.7
  30天以上 → ×0.4

homogenization_penalty:
  有同质化预警 → ×0.5
  无同质化预警 → ×1.0
```

### 1.6 队列管理规则

- 保留最近 100 条或最近 60 天（先到先清理）
- consumed 条目保留 60 天后归档
- dismissed 条目直接删除，不归档
- 归档累积为个人「认知裂缝档案」，支持趋势对比

---

## 二、信号提炼层（crack_hunter_wrapper 升级）

### 2.1 现状问题

当前 `crack_hunter_wrapper.py` 的 prompt 只判断：
- 是否有裂缝（has_crack）
- 裂缝类型（数据/逻辑/时效/视角/因果）
- consensus vs reality

**缺失能力**：
- 不提炼趋势信号
- 不识别情绪类型
- 不抽取矛盾
- 不判断同质化程度

### 2.2 升级后的信号提炼 prompt

原 prompt → 升级为 5 类信号提炼：

```python
SIGNAL_EXTRACTION_PROMPT = """你是认知裂缝猎人，负责从新闻/文章中发现认知裂缝并提炼认知信号。

**任务**：分析以下内容，输出结构化的认知信号。

**内容**：
标题：{title}
来源：{source}
摘要：{summary}

**输出 JSON**：
{{
  "has_crack": true/false,
  "crack_type": "数据裂缝/逻辑裂缝/时效裂缝/视角裂缝/因果裂缝/无",
  "consensus": "被挑战的共识/常识（如无，填'无'）",
  "reality": "与共识相悖的现实（如无，填'无'）",
  "confidence": 0.0-1.0,
  "reasoning": "判断理由（50字内）",

  "signals": {{
    "trend": "识别出的趋势变化（50字内，如无填'无'）",
    "emotion": ["焦虑", "兴奋", "替代感", "身份危机", "阶层焦虑"]，
    "contradiction": "最值得表达的矛盾（50字内，如无填'无'）",
    "homogenization_alert": "是否已同质化？全网是否在重复同类话题？（是/否/不确定）"
  }},

  "expression_angles": [
    {{
      "type": "创作者类型（技术型/认知型/商业型）",
      "angle": "适合从这个角度切入的表达入口（50字内）",
      "resonance": 0.0-1.0
    }}
  ],

  "title_suggestions": ["建议标题1", "建议标题2"]
}}
"""
```

### 2.3 升级要点

1. **trend**：从裂缝内容中提炼趋势，不是描述事件而是描述"变化方向"
2. **emotion**：识别读者情绪类型（多个），不是判断是否有情绪
3. **contradiction**：找到"最值得表达的矛盾"，不是泛泛总结
4. **homogenization_alert**：判断"这个话题是否已经同质化了"，这是新能力
5. **expression_angles**：为不同类型创作者生成表达入口，这是核心新增

---

## 三、创作者建模（数字分身扩展）

### 3.1 现状

数字分身当前只做风格学习（从修改记录学 HOOK长度/CASE深度/高频词）。

### 3.2 扩展建模维度

来自 PRD 的创作者建模 5 维度：

```python
CREATOR_MODEL = {
    "long_term_themes": [],        # 长期主题：["AI", "个体成长", "认知升级"]
    "expression_style": "",        # 表达风格：理性分析/情绪表达/结构化/故事化
    "sensitive_directions": [],    # 敏感方向：更容易对什么产生表达欲
    "worldview": "",                # 世界观结构：技术乐观/个体成长/长期主义/教育重构
    "growth_stage": "",            # 当前阶段：工具型 → 方法型 → 系统型 → 思想型
}
```

### 3.3 阶段识别逻辑

根据历史内容自动判断当前阶段：

| 阶段 | 特征 | 系统提示 |
|------|------|---------|
| 工具型 | 多工具教程、Prompt 技巧 | "你正在从'工具型表达'进入'方法型表达'" |
| 方法型 | 工作流、效率方法、系统搭建 | "你正在从'方法型表达'进入'系统型表达'" |
| 系统型 | 方法论沉淀、行业洞察 | "你正在从'系统型表达'进入'思想型表达'" |
| 思想型 | 社会观察、价值观输出 | "你已进入'思想型表达'阶段" |

### 3.4 与队列的关联

crack_queue 中的 `creator_match` 字段：
- `growth_stage`：当前裂缝适合哪个阶段的创作者
- `sensitive_directions`：裂缝触发了哪些敏感方向
- `match_score`：综合评分（0-1）

---

## 四、RSS-Hunter 输出改造

### 4.1 输出变化

**现状**：发现裂缝 → 写入 Obsidian → 推送终端

**改造后**：

```
# 新输出格式（简洁汇总，不再逐条推送）
[RSS-Hunter] 完成：新增 2 条认知裂缝，队列当前共 12 条
  - [数据裂缝] AI让程序员失业率上升30%
    信号：替代焦虑 / 教育崩塌前兆
    表达入口：认知型→身份危机视角 商业型→人力结构视角
  - [视角裂缝] 程序员不需要学算法了？
    信号：技术教育正在被重新定义
    表达入口：技术型→重新定义学习路径 认知型→教育公平视角
```

### 4.2 队列管理命令

```bash
# 查看队列（展示信号和表达入口）
python prism_os.py queue --list

# 标记/打标裂缝
python prism_os.py queue --tag <id> <自由标签>
python prism_os.py queue --tag <id> "战略级"

# 调整优先级
python prism_os.py queue --priority <id> --up

# 标记为已读/待处理
python prism_os.py queue --status <id> reviewed

# 清除无用条目
python prism_os.py queue --dismiss <id>
```

---

## 五、PRISM-OS 接入层

### 5.1 入口一：显式浏览选择 `--from-queue`

```
python prism_os.py run --from-queue
```

行为：
1. 列出队列中 `status=new` 或 `status=reviewed` 的裂缝
2. 按 `priority_score` 排序，最多展示 20 条
3. 每条展示：标题、裂缝类型、signals 摘要、expression_angles
4. 用户数字多选（1,3,5 空格分隔），可选多条
5. 选中裂缝合并 `consensus/reality/signals/expression_angles` → 作为输入进入主流程
6. 选中裂缝 `status → consumed`

### 5.2 入口二：结合队列匹配 `--match-queue`

```
python prism_os.py run "AI程序员发展" --match-queue
```

行为：
1. 正常走意图识别流程
2. 同时在队列中搜索与输入语义相关的裂缝（标题关键词匹配）
3. 如果找到 → 在输出中展示所有相关裂缝及其 signals/expression_angles
4. 最匹配那条标注「AI 推荐」（基于 creator_match.match_score）
5. 用户确认后 → 用裂缝的 signals + expression_angles 增强原始输入

### 5.3 入口三：正常输入时被动提示

```
python prism_os.py run "AI程序员发展"
```

行为：
- 不阻断流程
- 在输出开头简短提示：`[队列中有 2 条相关裂缝（信号：替代焦虑），使用 --match-queue 查看详情]`
- 让用户知道队列有货，但不强制处理

### 5.4 接入命令汇总

```bash
# 原有方式：用户主动输入
python prism_os.py run "AI时代程序员生存指南"

# 新增：从队列选择（展示信号和表达入口）
python prism_os.py run --from-queue

# 新增：输入时匹配队列
python prism_os.py run "AI程序员发展" --match-queue

# 队列管理
python prism_os.py queue --list
python prism_os.py queue --tag <id> <自由标签>
python prism_os.py queue --dismiss <id>
```

---

## 六、实施计划

### Phase A：crack_queue 数据结构 + RSS-Hunter 改造

**目标**：队列可正常积累，RSS-Hunter 输出改造

**工作内容**：
1. 重构 `crack_queue.json` 数据结构（新增 signals、expression_angles、creator_match 字段）
2. 升级 `crack_hunter_wrapper.py` 的 prompt（5 类信号提炼）
3. 改造 RSS-Hunter 输出：从写 Obsidian 改为写 crack_queue
4. 实现 `queue` 子命令（--list/--tag/--dismiss）

**验收标准**：
- `python rss_hunter.py hunt` 不再写入 Obsidian，改为写入 crack_queue
- `python prism_os.py queue --list` 可正确展示队列内容

---

### Phase B：PRISM-OS `--from-queue` 入口

**目标**：可从队列选择进入主流程

**工作内容**：
1. 实现 `run --from-queue` 命令
2. 队列浏览 UI：展示裂缝 + signals + expression_angles
3. 多选合并逻辑：收集选中裂缝的 consensus/reality/signals/expression_angles，注入主流程
4. 选中裂缝 status → consumed

**验收标准**：
- `python prism_os.py run --from-queue` 可正确展示队列、选择并进入主流程

---

### Phase C：`--match-queue` + 被动提示

**目标**：正常输入时可选触发队列匹配

**工作内容**：
1. 实现 `run --match-queue` 命令
2. 关键词匹配逻辑：在 crack_queue 中搜索标题包含输入关键词的条目
3. 输出增强：signals + expression_angles 作为 context 注入 prompt
4. 正常输入时的被动提示（不阻断）

**验收标准**：
- `python prism_os.py run "AI程序员" --match-queue` 可匹配并展示队列中的相关裂缝

---

### Phase D：数字分身扩展 + 归档功能

**目标**：创作者建模 + 趋势感知基础

**工作内容**：
1. 扩展数字分身：加入 growth_stage / sensitive_directions / worldview 建模
2. 实现 crack_queue 的 creator_match 字段计算
3. 实现 crack_archive.json 归档逻辑
4. 趋势感知基础：归档查询接口（当前裂缝 vs 历史归档）

**验收标准**：
- `python prism_os.py run --from-queue` 展示的裂缝包含 creator_match 信息

---

## 七、Obsidian 历史条目处理

### 当前状态

RSS-Hunter 历史已写入 Obsidian 的条目：
- `洞察库/rss-cracks/` — 有裂缝的新闻条目
- `原子库/rss-items/` — 普通新闻条目

### 处理方案

**RSS-Hunter 不再写入 Obsidian**；历史已写入的条目：
- 保留在原位置，scan_vault 继续正常召回
- 不再主动依赖，不再作为情报来源
- 可选：一次性迁移到 crack_queue（但需要逐条重新分析，成本高）

---

## 八、技术债与风险

### 技术债

1. **crack_hunter_wrapper.py 重写**：prompt 升级后需要重新测试验证输出格式
2. **数字分身模型扩展**：需要新的训练数据或手动标注
3. **队列 schema 变更**：v2.0 字段结构与 v1.0 不兼容，需要迁移脚本

### 风险

1. **信号提炼质量不稳定**：LLM 生成 signals 的质量需要持续校准
2. **expression_angles 过度发散**：LLM 可能生成过多角度，需要限制数量（最多 3 个）
3. **homogenization_alert 误判**：同质化判断主观性强，需要人工标记校准

---

## 九、废弃 / 降级功能

| 功能 | 处理 | 原因 |
|------|------|------|
| RSS-Hunter 写 Obsidian | 废弃 | 裂缝进入 crack_queue，Obsidian 不再承载情报 |
| RSS-Hunter 终端推送 | 降级为每日汇总 | 不做信息轰炸，低频高价值刺激 |
| Obsidian rss-cracks/ 目录 | 保留不处理 | 历史遗留，不再主动依赖 |

---

**最后更新**：2026-05-21