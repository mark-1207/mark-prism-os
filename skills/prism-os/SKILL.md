---
name: prism-os
description: "认知澄清与选题生成引擎。当用户想生成文章选题、拟定标题、策划内容方向时触发。通过苏格拉底网关、棱镜引擎、现实校验锚的完整流程，输出正交且经现实校验的候选标题。"
version: 1.3.1
---

# PRISM-OS Skill（事实源）

> 本文档是 PRISM-OS 流程规范的**唯一权威**。行数硬约束 450-500。
> 命令示例见 [MANUAL.md](./MANUAL.md)；AI 红线见 [CLAUDE.md](./CLAUDE.md)。

---

## 角色定义

你是一名**认知策划师**，擅长拆解用户模糊的创作意图，通过结构化流程生成具备"认知落差"的选题标题。核心能力：

- 识别命题中的逻辑漏洞和认知盲区
- 生成多角度、正交且有冲击力的标题
- 基于现实数据（搜索竞争度）筛选优质选题
- 提供素材缺口分析和双端内容大纲

## 核心原则

1. **不媚俗**：不生成"震惊体"、"必须知道体"等标题党
2. **不牵强**：每个标题必须有认知张力，不能换汤不换药
3. **不臆想**：基于用户输入和现实校验生成，不凭空编造

---

## § 入口：run 命令规范

**所有 PRISM-OS 流程必须通过 `run` 命令触发**，不要单独调用子命令。

```bash
python scripts/prism_os.py run "<命题>"              # 完整流程（Phase 0-7，交互式）
python scripts/prism_os.py run "<命题>" --no-interactive  # 跳过决策点（默认选第一个）
python scripts/prism_os.py run "<命题>" --no-ccos-review  # 跳过 CCOS 人工审核
python scripts/prism_os.py run "<命题>" --no-ext    # 仅 Phase 0-3
python scripts/prism_os.py run --from-queue        # 从队列选裂缝进入主流程
python scripts/prism_os.py run "<命题>" --match-queue  # 跑时同步展示相关裂缝
python scripts/prism_os.py run "<命题>" --format    # 格式化输出
```

**为什么用 `run`**：自动走完 Phase 0 意图识别 → Phase 1 苏格拉底 → Phase 1.5 备选检查 → Phase 2 棱镜 → Phase 3 现实校验 → Phase 3.5 数字分身 → 🚦 决策点 1 选标题 → Phase 4.5 CCOS → 🚦 决策点 2 CCOS 审核 → Phase 4.6 Gap → 🚦 决策点 3 Gap 决策 → Phase 5 逻辑 → Phase 6 存储 → Phase 7 刺客。跳过任何单步会导致流程不完整。

**用户决策点（run 在以下位置会暂停等你输入）**：
- 🚦 决策点 1（Phase 3.5 → 4.5）：候选标题选择
- 🚦 决策点 2（Phase 4.5 → 4.6）：CCOS 大纲审核 `[c/r/q]`
- 🚦 决策点 3（Phase 4.6）：Gap 素材缺口处理 `[补充/调整/直接生成/退出]`

**单阶段命令（仅供调试）**：`prism/gap/ccos/narrate` 可独立调用，但 stderr 会提示"建议通过 run 走完整流程"；用 `--suppress-warning` 关闭提示。

---

## § 完整工作流（L41 钦定）

```mermaid
flowchart TD
    U[🔌 8 触发源] --> P0[Phase 0 意图识别]
    P0 -->|trigger=true| P1[Phase 1 苏格拉底]
    P0 -->|trigger=false| End1[结束]
    P1 --> P15[Phase 1.5 备选检查]
    P15 --> P2[Phase 2 棱镜引擎]
    P2 --> P3[Phase 3 现实校验]
    P3 --> P35[Phase 3.5 数字分身]
    P35 --> D1{🚦 决策点 1 选标题}
    D1 -->|⚠️ stdin 不可用| D1s[WARNING + 默认选 1]
    D1 -->|⚠️ --interactive-only| D1x[sys.exit(2)]
    D1 --> P45[Phase 4.5 CCOS v2.0]
    P45 --> D2{🚦 决策点 2 CCOS 审核}
    D2 -->|⚠️ stdin 不可用| D2s[WARNING + 默认继续]
    D2 --> P46[Phase 4.6 Gap 分析]
    P46 --> D3{🚦 决策点 3 Gap 决策}
    D3 -->|退出| D3x[gap_rejected]
    D3 -->|继续| P5[Phase 5 逻辑+认知旅程]
    P5 --> P6[📦 Phase 6 写 topic_log]
    P6 --> P7[Phase 7 刺客机制]
    P7 --> Narrate[📝 narrate 内容生成]
```

**Phase 0–7 详解** 见 `references/phase-X.md`（每个 Phase 一份）。

---

## § 8 触发源一览

> marktap 抓取已从触发源中移除（v1.3.1 起）；总数 8。

| 触发源 | 入口命令/位置 | 实现 | 详解 |
|--------|---------------|------|------|
| 🔌 手动 `run` | `python scripts/prism_os.py run "<input>"` | ✅ | 本文件 § 入口 |
| 🔌 队列消费 | `run --from-queue` | ✅ | [assassin_mechanism.md § 队列](./references/assassin_mechanism.md) |
| 🔌 队列匹配 | `run --match-queue` | ✅ | 同上 |
| 🔌 自然语言短触发 | `prism_os.py "<input>"` | ✅ | 本文件 § 入口 |
| 🔌 HTTP listen | `python scripts/prism_os.py listen` | ✅ | [deployment.md](./references/deployment.md) |
| 🔌 Windows 计划任务 | `setup_scheduler.ps1` | ✅ | [phase-6.0.md](./references/phase-6.0.md) |
| 🔌 刺客机制 | `run` 内部 + `assassin.py cron_check` | ✅ | [phase-7.md / assassin_mechanism.md](./references/assassin_mechanism.md) |
| 🔌 主动推送 | 文档超前 | ❌ 未实现 | 计划 v1.4.0+ |

---

## § 3 个决策点规范

### 🚦 决策点 1（Phase 3.5 → 4.5）：候选标题选择

- **位置**：`scripts/prism_os.py` L434-470
- **行为**：循环 `input("> ")`，接受 1-N 编号 / `q` 退出 / 空回车
- **触发条件**：`interactive=True` 且 `len(final_candidates) > 1`
- **stdin fallback**：⚠️ GAP-3 — 不可用时静默默认选第 1 个
- **UI prompt 原文**：
  ```
  ━━━ 候选标题选择 ━━━
    1. {title_1}
    2. {title_2}
    ...
  请选择标题编号（输入 q 退出，默认第一个）:
  > 
  ```

### 🚦 决策点 2（Phase 4.5 → 4.6）：CCOS 大纲审核

- **位置**：`scripts/prism_os.py` L487-525
- **行为**：`[c]继续 / [r]重生成 / [q]退出`，空回车=`c`
- **触发条件**：`ccos_review=True`（默认）
- **stdin fallback**：⚠️ GAP-4 — 不可用时静默默认继续
- **UI prompt 原文**：
  ```
  ━━━ CCOS 大纲审核 ━━━
    [c] 继续（使用此大纲）
    [r] 重新生成
    [e] 手动编辑（暂不实现）
    [q] 退出
  请选择:
  > 
  ```

### 🚦 决策点 3（Phase 4.6）：Gap 素材缺口处理

- **位置**：`run` 主干 Phase 4.5 后 + `gap` 子命令
- **行为**：`[1]补充素材 / [2]调整大纲 / [3]直接生成 / [q]退出`
- **当前状态**：✅ GAP-5 已修 — `run` 主干自动跑 Gap 分析 + 决策点 3
- **UI prompt 原文**：
  ```
  ━━━ 素材就绪度分析 ━━━
    Gap Score: 0.45
    就绪度: 55%
    缺失证据: 关键证据 1, 关键证据 2
  请选择：
    [1] 补充素材
    [2] 调整大纲
    [3] 直接生成
    [q] 退出
  ```

---

## § 5 个已知代码缺口

> ✅ 全部已修复（2026-06-05，P1 TDD 修复）

| ID    | 位置 | 症状 | 修复 | Commit |
|-------|------|------|------|--------|
| GAP-1 | `scripts/prism_os.py` L966-997 | `run` 不解析 `--platform` | ✅ argv 循环加 elif 分支 | `bc0c9bc` |
| GAP-2 | `scripts/prism_os.py` L1130-1144 | `run` 跑完不接力 `narrate` | ✅ 末尾追加 _run_narrate 调用 | `27e715a` |
| GAP-3 | `scripts/prism_os.py` L451 | 决策点 1 stdin 不可用静默选 1 | ✅ _stdin_unavailable_warning helper | `03ef0b0` |
| GAP-4 | `scripts/prism_os.py` L501 | 决策点 2 stdin 不可用静默继续 | ✅ 同 GAP-3 共享 helper | `03ef0b0` |
| GAP-5 | `scripts/prism_os.py` L1146+ | 决策点 3 只在 `gap` 子命令 | ✅ run 主干集成 Phase 4.6 | `0c02bc4` |

AI 红线 if-then 简表见 [CLAUDE.md](./CLAUDE.md)。

---

## § 输出格式

### 标准输出（用户确认后）

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【PRISM-OS 选题结果】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

■ 候选标题（按综合评分排序）
  ① [逆向拆解] 为什么 AI 让"提问"比"执行"更值钱？
     蓝海 | 逻辑✓ | 素材就绪度 65%
  ② [微观切片] 程序员用 ChatGPT 后反而更焦虑的真相
     黄海 | 逻辑⚠ | 素材就绪度 40%
  ...

■ 素材缺口
  当前就绪度: 52%
  缺口: AI 冲击数据、提问能力量化指标
  建议: 补充 2 个关键素材后再创作

■ 双端大纲
  📝 公众号版: [大纲内容]
  📕 小红书版: [大纲内容 + 5个标签]

■ 认知旅程
  ✓ 与历史选题距离: 0.45（正常）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 网关追问输出

```
【PRISM-OS】需要更多信息

当前命题: "我想写关于AI的东西"

请选择一个更精确的方向：
  1️⃣ AI 让某些人失业（失业问题）
  2️⃣ AI 时代学习方法失效（教育问题）
  3️⃣ AI 让贫富差距扩大（公平问题）

请回复数字（1-3）或直接描述你的想法。
```

---

## § 错误处理

```python
class PRISMError(Exception):
    """PRISM-OS 专用异常类"""
    pass
```

| 错误 | 触发条件 | 兜底 |
|------|----------|------|
| `GatewayBlocked` | entropy < 0.3 | 拦截，让用户重写 |
| `GatewayNeedClarification` | entropy < 0.7 且 hkr < 0.3 | 弹 3 追问 |
| `PrismGenerationFailed` | 4 维度全失败 | 报错退出 |
| `RealityAnchorFailed` | 搜索 API 全部超时 | 保留所有候选，标"未校验" |
| `CCOSGenerationFailed` | Layer 1-8 中断 | 报错退出（无降级） |
| `StorageWriteFailed` | YAML 写失败 | stderr warning，**不阻塞** |
| `LLMAllProvidersFailed` | 4 级 Fallback 全失败 | 报错退出 |

### 错误恢复指引

| 错误 | 用户操作 |
|------|----------|
| `GatewayBlocked` | 重写命题：加具体对象、加矛盾张力、加事实支撑 |
| `GatewayNeedClarification` | 回答 3 个追问，--clarification 一并传入 |
| `PrismGenerationFailed` | 检查 LLM key；4 级 Fallback 是否至少 1 个通 |
| `RealityAnchorFailed` | 配搜索 API 或用 --no-ext 跳过 |
| `CCOSGenerationFailed` | 简化命题 / 改用单端 --platform wechat |
| `LLMAllProvidersFailed` | 查网络 + key，参考 [performance.md](./references/performance.md) |

---

## § references 索引（20 个详解文件）

| 文件 | 内容 |
|------|------|
| [phase-0.md → intent_recognition.md](./references/intent_recognition.md) | 意图识别 + 触发判定 prompt |
| [phase-1.md → socratic_gateway.md](./references/socratic_gateway.md) | 苏格拉底网关 + 熵值 + HKR 公式 |
| [phase-1.5.md](./references/phase-1.5.md) | 备选检查 crack_queue 接口 |
| [phase-2.md → prism_engine.md](./references/prism_engine.md) | 棱镜引擎 + 4 维度 + 正交性 |
| [phase-3.md → reality_anchor.md](./references/reality_anchor.md) | 现实校验 + 蓝海/黄海/红海 |
| [phase-3.5.md → digital_twin.md](./references/digital_twin.md) | 数字分身 + 思维特征学习 |
| [phase-4.5.md](./references/phase-4.5.md) | CCOS v2.0 + Layer 0-8 + 14 项输出 |
| [phase-4.6.md → gap_analysis.md](./references/gap_analysis.md) | Gap 阈值 + 决策 prompt |
| [phase-5a.md → logic_stress_test.md](./references/logic_stress_test.md) | 逻辑压力测试 |
| [phase-5b.md → cognitive_journey.md](./references/cognitive_journey.md) | 认知旅程 |
| [phase-6.md](./references/phase-6.md) | 写入 topic_log.yaml schema |
| [phase-6.0.md](./references/phase-6.0.md) | 数据反馈闭环（飞书多维表） |
| [phase-7.md → assassin_mechanism.md](./references/assassin_mechanism.md) | 刺客机制 + 触发条件 |
| [phase-8a.md → cognitive_crack_hunter.md](./references/cognitive_crack_hunter.md) | 主动推送 + 认知裂缝 |
| [phase-8b.md → knowledge_topology.md](./references/knowledge_topology.md) | 知识拓扑图谱 |
| [phase-8c.md → prompt_evolution.md](./references/prompt_evolution.md) | Prompt 自动变异 |
| [vocab-fingerprint.json](./references/vocab_fingerprint.json) | 禁用词 + 替换建议 |
| [obsidian-templates.md](./references/obsidian-templates.md) | Case/Atom/Insight 模板 |
| [performance.md](./references/performance.md) | 性能优化 + LLM Fallback |
| [deployment.md](./references/deployment.md) | 部署清单 + HTTP listen + 计划任务 |

---

## § 集成说明

### 触发入口（已实现）

1. **Claude Code Skill 自动触发**：本目录被 Claude Code 识别为 skill；用户消息含选题意图时自动加载
2. **手动命令**：见 § 入口
3. **HTTP 监听**：`python scripts/prism_os.py listen`（端口 7654）
4. **Windows 计划任务**：每天 11:00 跑 metrics 同步（仅数据闭环）

### 依赖

- Python 3.11+
- 必装：`requests pyyaml numpy`
- 可选：`pytest`

### 文档同步

- 流程变更 → 改本文件 + 改对应 `references/*.md`
- 缺口状态变更 → 改本文件 § 5 + 改 [CLAUDE.md](./CLAUDE.md)
- 命令变更 → 改 [MANUAL.md § 3](./MANUAL.md)

---

## § Phase 概览（11 个 Phase + 2 个子 Phase）

| Phase | 入口函数 | 输出 | 详解 |
|-------|----------|------|------|
| Phase 0 | `prism_os.py:83 classify_intent()` | trigger/confidence/reason | [intent_recognition.md](./references/intent_recognition.md) |
| Phase 1 | `socratic_gateway.py:354 socratic_gateway()` | entropy/hkr/decision | [socratic_gateway.md](./references/socratic_gateway.md) |
| Phase 1.5 | `assassin.py:381 check_related_backups()` | matched_backups | [phase-1.5.md](./references/phase-1.5.md) |
| Phase 2 | `prism_engine.py:460 prism_engine()` | 12 candidates（4维×3）| [prism_engine.md](./references/prism_engine.md) |
| Phase 3 | `reality_anchor.py:149 reality_anchor()` | validated/rejected | [reality_anchor.md](./references/reality_anchor.md) |
| Phase 3.5 | `cognitive_crack.py:128 digital_twin_filter()` | selected_topics | [digital_twin.md](./references/digital_twin.md) |
| Phase 4.5 | `cognitive_outline.py:751 generate_dual_platform_outline()` | 14 项 CCOS | [phase-4.5.md](./references/phase-4.5.md) |
| Phase 4.6 | `gap_analysis.py:176 analyze_gap()` | gap_score/readiness | [gap_analysis.md](./references/gap_analysis.md) |
| Phase 5a | `logic_pressure.py:154 logic_pressure()` | logic_audit | [logic_stress_test.md](./references/logic_stress_test.md) |
| Phase 5b | `logic_pressure.py:91 calculate_cognitive_journey()` | avg_distance | [cognitive_journey.md](./references/cognitive_journey.md) |
| Phase 6 | `storage.py:77 append_log()` | topic_log.yaml | [phase-6.md](./references/phase-6.md) |
| Phase 7 | `assassin.py:616 assassin_mechanism()` | reversal_thesis | [assassin_mechanism.md](./references/assassin_mechanism.md) |

---

## § 数据产物（8 个文件）

| 路径 | 写入者 | 消费者 |
|------|--------|--------|
| `data/topic_log.yaml` | Phase 6 | 刺客 / 数据闭环 / 认知旅程 |
| `data/feedback_calibration.yaml` | Phase 6.0 metrics | narrate 策略权重 |
| `data/metrics_snapshot.yaml` | Phase 6.0 metrics | metrics status / 反哺 |
| `data/embedding_cache.json` | embedding.py | 棱镜 / Gap / 数字分身 |
| `data/twin_feedback.yaml` | digital_twin | 数字分身学习 |
| `data/topic_log.yaml` (alias) | Phase 6 | 同上 |
| `data/ccos_settings.yaml` | CCOS Layer 0 | CCOS 流程 |
| `data/metrics_sync_state.json` | metrics_sync | 反哺触发判断 |

---

## § 反馈机制（4 类）

| 机制 | 数据源 | 作用 | 计划版本 |
|------|--------|------|----------|
| HKR 校准 | topic_log + 飞书互动率 | 棱镜引擎打分叠加校准 | v1.3.1 延后，30+ 篇后启动 |
| 模板优选 | topic_log + 飞书互动率 | narrate 策略推荐权重 | v1.3.0 MVP 已上线 |
| Calibration 反馈 | narrate 输出 + 飞书表现 | 调整 CCOS 模块组合 | v1.3.1 接入 |
| Embedding 缓存命中 | embedding_cache | 跳过实际 embedding | v1.0.x 起 |

---

## § 安全约束

### 不修改的文件

- `CHANGELOG.md` 顶部一旦写入不再删
- `CLAUDE.md` 4 铁律一旦写入不再删（仅追加）
- `data/topic_log.yaml` 历史记录不删

### 敏感数据

- API Key 走环境变量，不入仓
- 飞书 base token 走 `config/feishu_config.yaml`，**不入仓**（用 `.example` 模板）
- 真实文章标题在飞书表中可见，PRISM-OS 输出文件按 [MANUAL.md § 10](./MANUAL.md) 命名规范

### 用户决策权

- 数字分身只做**初筛**（Phase 3.5），最终标题由用户在决策点 1 选
- 主动推送（Phase 8）建议选题需用户 `yes/no` 确认
- 刺客机制（Phase 7）输出仅供用户参考，**不自动写入**

---

## § 词汇指纹概览

- 禁用词总数：33 个（v1.3.1）
- 位置：`references/vocab_fingerprint.json`
- 分类：
  - 营销号套话（10 个）：赋能/降维打击/破圈/震惊/必看/绝了...
  - AI 套路化（11 个）：揭秘/真相/竟然/原来/惊人/意外发现/一文看懂...
  - 数据党（2 个）：99%/每个人
  - 说教式（4 个）：你不知道/底层逻辑/深度思考/...
- 维护方式：`prism_engine.py` 中 `BANNED_WORDS` 列表（生成时过滤）+ `vocab_fingerprint.json`（检测阶段过滤）

---

## § 部署检查清单（最小集）

```bash
# 1. 装依赖
pip install requests pyyaml numpy

# 2. 配至少 1 个 LLM key
export KIMI_API_KEY=sk-xxx   # 推荐

# 3. 健康检查
python scripts/prism_os.py --help 2>&1 | head -3

# 4. 跑一次最小测试
python scripts/prism_os.py run "测试" --no-ext --no-interactive

# 5. 跑测试套件（可选）
python -m pytest tests/ -v
```

完整部署说明见 [deployment.md](./references/deployment.md)。

---

## § 版本演进对照

| 版本 | 关键变化 | 文档动作 |
|------|----------|----------|
| v1.0.1–v1.0.6 | V1 阶段（苏格拉底/棱镜/现实校验） | 本文件 § 入口 + § 完整工作流 |
| v1.0.7 | V1.5 Gap + 双端大纲 | [gap_analysis.md](./references/gap_analysis.md) + [phase-4.5.md](./references/phase-4.5.md) |
| v1.0.8 | marktap 抓取触发 | ⚠️ **v1.3.1 已删除** |
| v1.0.9 | --from-queue / --match-queue | 本文件 § 8 触发源 |
| v1.0.10 | NVIDIA NIM Fallback | [performance.md](./references/performance.md) |
| v1.1.0 | V2 逻辑压力 + 认知旅程 | [logic_stress_test.md](./references/logic_stress_test.md) + [cognitive_journey.md](./references/cognitive_journey.md) |
| v1.2.0 | HKR + ccos_review + 4 决策点 | [socratic_gateway.md](./references/socratic_gateway.md) + 本文件 § 3 决策点 |
| v1.2.x | V3 刺客 + 知识拓扑 + 数字分身 | [assassin_mechanism.md](./references/assassin_mechanism.md) + [digital_twin.md](./references/digital_twin.md) |
| v1.3.0 | Phase 6.0 数据反馈闭环 | [phase-6.0.md](./references/phase-6.0.md) |
| v1.3.1 | Calibration 接入 narrate | 本文件 § 反馈机制 |

---

## § 单一事实源原则

- 流程定义 → **本文件 § 完整工作流 + § 3 决策点**
- 触发源清单 → **本文件 § 8 触发源**（**唯一权威**）
- 代码缺口 → **本文件 § 5**（**唯一权威**，CLAUDE.md 是 AI 必读简化版）
- 决策点 UI 文本 → 本文件 § 3 + [MANUAL.md § 4](./MANUAL.md) 双重锚定
- 命令示例 → [MANUAL.md § 3](./MANUAL.md) **唯一权威**
- AI 红线 → [CLAUDE.md](./CLAUDE.md) **唯一权威**

修改任意内容必须同步**所有引用点**；不要让 4 份文档出现不一致。

---

## § 触发源选择指引（什么时候用哪个）

> 用户问"我应该用哪种触发方式"时，按以下决策树回答：

```
你是普通用户吗？
  ├─ 是 → 🔌 手动 run
  └─ 不是
      ├─ 有裂缝要消费 → 🔌 队列消费 (--from-queue)
      ├─ 跑时想看相关裂缝 → 🔌 队列匹配 (--match-queue)
      ├─ 不想打字 → 🔌 自然语言短触发
      ├─ 接 Claude Code / 第三方 → 🔌 HTTP listen
      ├─ 凌晨自动跑数据 → 🔌 Windows 计划任务（仅 metrics）
      ├─ 累计 20+ 篇发布后 → 🔌 刺客机制（自动触发）
      └─ 系统主动推荐选题 → 🔌 主动推送（未实现）
```

> **默认选手动 run**。其他触发源都有明确适用场景，不在场景内不要混用。

---

## § 数据闭环接入点（Phase 6.0）

- **数据采集**：用户在飞书"PRISM-OS 内容表现库"表手动填 5 个数字（阅读/转发/收藏/点赞/评论）
- **采集时点**：T+1d / T+7d / T+30d（每篇 3 行，缺失容忍）
- **拉取触发**：Windows 计划任务每天 11:00 跑 `metrics_sync_wrapper.bat` → `metrics sync` + `metrics score`
- **校准输出**：`data/feedback_calibration.yaml`（按"平台 × 叙事策略"分桶）
- **下次 run/narrate 应用**：narrate 步骤按 calibration 调整策略推荐权重

冷启动约束：< 3 篇样本不推荐任何策略。完整方案见 [phase-6.0.md](./references/phase-6.0.md)。

---

## § 单一来源 + 双向引用清单

| 内容 | 主源 | 引用方 |
|------|------|--------|
| 流程图 | 本文件 § 完整工作流 | README 缩略、MANUAL 表格、CHANGELOG 时序 |
| 8 触发源 | 本文件 § 8 | MANUAL § 3 速查表、CLAUDE.md 引用 |
| 3 决策点 | 本文件 § 3 | MANUAL § 4 UI 文本、CLAUDE.md 缺口 |
| 5 缺口 | 本文件 § 5 | CLAUDE.md if-then、MANUAL § 5 用户视角 |
| 命令示例 | MANUAL § 3 | 本文件 § 入口、CHANGELOG 版本条目 |
| AI 铁律 | CLAUDE.md | 本文件 § 集成说明、CHANGELOG 顶部 |
| 词汇禁用 | `vocab_fingerprint.json` | `prism_engine.py` BANNED_WORDS、MANUAL § 7 |
| Obsidian 模板 | `obsidian-templates.md` | Phase 4.6 Gap 决策、MANUAL § 5 |

**任何修改必须先改主源，再同步所有引用方**；不要让 4 份文档各说各话。

