# PRISM-OS Phase 6 数据反馈闭环方案

> 版本：1.0 | 日期：2026-06-03 | 状态：**规划中，待开发（Phase 6.0 MVP：模板优选 B）**
>
> 关联：v1.3.0 | 与 v1.2.0 兼容，purely additive

---

## 一、Phase 6 定位

**目标**：把"生成→发布"补成完整飞轮，让 PRISM-OS 从「生成工具」进化成「数据驱动的创作者操作系统」。

**核心痛点**：
- **盲目发布**：生成后发布，不知道哪篇真火
- **凭感觉调优**：调提示词/选题规则靠经验，没有数据反馈
- **刺客机制空转**：assassin 依赖 ≥20 篇历史爆款数据，目前没有真实数据来源

**核心原则**：
- **录入极简**：用户只填 5 个数字（阅读/转发/收藏/点赞/评论）
- **自动化驱动**：PRISM-OS 定期读飞书表，自动反哺生成机制，无 CLI 参与
- **B 优先 A 延后**：先做"模板优选"（快反馈），再做"HKR 校准"（慢反馈但更深）
- **缺失容忍**：3 个时间点不要求都填，能填多少算多少

---

## 二、整体架构

```
                  [用户发布文章到公众号/小红书]
                              ↓
                  [用户每天在飞书表里填 5 个数字]
                              ↓
              ┌───────────────────────────────┐
              │  飞书多维表格                  │
              │  PRISM-OS 内容表现库           │
              │  （20 列 / 5 公式 / 3 视图）   │
              └───────────────────────────────┘
                              ↓
              ┌───────────────────────────────┐
              │  PRISM-OS 后台进程             │
              │  （Windows 计划任务 / cron）    │
              │  - 每天凌晨 3 点增量拉取        │
              │  - 解析 T+1/7/30d 三个时间点    │
              │  - 计算派生指标                  │
              │  - 更新本地反哺配置              │
              └───────────────────────────────┘
                              ↓
              ┌───────────────────────────────┐
              │  本地反哺配置                  │
              │  data/feedback_calibration.yaml│
              │  - 叙事策略表现排序             │
              │  - CCOS 模块组合得分            │
              │  - HKR 校准系数（6.1+）         │
              └───────────────────────────────┘
                              ↓
              [下次 run/narrate 调用时自动应用]
```

---

## 三、数据字段（飞书多维表格）

### 3.1 表名

**内容表现**（位于用户飞书 base `QVz9byNH0auzRis9KeDcUoe3nZf` 中）

**飞书 URL**：https://my.feishu.cn/base/QVz9byNH0auzRis9KeDcUoe3nZf?table=tbliXecencoSdnaB&view=vewhWxYEie

### 3.2 字段设计（20 列）

| # | 字段名 | 类型 | 来源 | 必填 | 说明 |
|---|--------|------|------|------|------|
| 1 | 文章ID | 文本 | PRISM-OS 自动 | ✅ | 主键，格式 `标题_YYYYMMDD` |
| 2 | 标题 | 文本 | PRISM-OS 自动 | ✅ | 从草稿文件读 |
| 3 | 平台 | 单选 | PRISM-OS 自动 | ✅ | wechat / xiaohongshu |
| 4 | 发布时间 | 日期 | PRISM-OS 自动 | ✅ | 从草稿 mtime |
| 5 | 原始命题 | 文本 | PRISM-OS 自动 | ❌ | gateway 输入 |
| 6 | 叙事策略 | 文本 | PRISM-OS 自动 | ❌ | 观点碰撞型 / 数据驱动型等 |
| 7 | 字数 | 数字 | PRISM-OS 自动 | ❌ | 最终草稿字数 |
| 8 | 预测HKR | 数字 | PRISM-OS 自动 | ❌ | prism 阶段打分（0-1） |
| 9 | 预测质量分 | 数字 | PRISM-OS 自动 | ❌ | quality_check 输出（0-100） |
| 10 | CCOS模块 | 多选 | PRISM-OS 自动 | ❌ | HOOK/CASE/MODEL/COUNTER... |
| 11 | 时间点 | 单选 | PRISM-OS 自动 | ✅ | t_plus_1d / t_plus_7d / t_plus_30d |
| 12 | 阅读量 | 数字 | 用户填 | ✅（自动行可空） | 累计阅读次数 |
| 13 | 转发量 | 数字 | 用户填 | ❌ | 累计转发次数 |
| 14 | 收藏量 | 数字 | 用户填 | ❌ | 累计收藏次数 |
| 15 | 点赞量 | 数字 | 用户填 | ❌ | 累计点赞次数 |
| 16 | 评论数 | 数字 | 用户填 | ❌ | 累计评论条数 |
| 17 | 互动率 | 公式 | 飞书计算 | — | (点赞+评论+收藏+转发)/阅读 |
| 18 | 点赞率 | 公式 | 飞书计算 | — | 点赞/阅读 |
| 19 | 收藏率 | 公式 | 飞书计算 | — | 收藏/阅读 |
| 20 | 转发率 | 公式 | 飞书计算 | — | 转发/阅读 |
| 21 | 评论率 | 公式 | 飞书计算 | — | 评论/阅读 |

**核心约定**：
- 同一篇文章在 T+1d/7d/30d 各产生 **1 行**（共 3 行/篇）
- 缺失时间点保留该行，5 个数字字段留空（不删除，便于后续补填）
- 派生指标 17-21 在飞书端用公式自动计算，PRISM-OS 不重复算

### 3.3 视图设计（3 个）

| 视图 | 类型 | 分组/排序 | 用途 |
|------|------|----------|------|
| 默认表格 | 表格 | 按发布时间倒序 | 录入 + 浏览 |
| 看板 | 看板 | 按平台分组 | 平台对比 |
| 表现排名 | 表格 | 按互动率降序 | 找爆款规律 |

---

## 四、自动化反哺机制

### 4.1 流程（无 CLI 参与）

```
[每天凌晨 3:00] Windows 计划任务触发
        ↓
metrics_sync.py 执行：
    1. 读取飞书表新增/更新行（自上次同步以来）
    2. 校验字段格式（5 个数字字段非负）
    3. 写入本地 metrics_snapshot.yaml
        ↓
template_scorer.py 执行：
    1. 加载 metrics_snapshot.yaml
    2. 按（平台 × 叙事策略）分组，计算平均互动率
    3. 按（平台 × CCOS 模块组合）分组，计算平均互动率
    4. 写入 feedback_calibration.yaml
        ↓
calibration_engine.py 执行（Phase 6.1+）：
    1. 加载历史 N 篇真实表现数据
    2. 计算 H/K/R 与互动率的相关性
    3. 调整 HKR 权重系数
    4. 写入 hkr_weights.yaml
```

### 4.2 调度方式

**Windows 计划任务**（推荐，最简单）：

```powershell
# 一次性配置（用户跑一次即可）
schtasks /create /tn "PRISM-OS Metrics Sync" /tr "python D:\myproject\PRISM-OSv1\skills\prism-os\scripts\metrics_sync.py" /sc daily /st 03:00
```

**备选**（技术用户）：
- `cron`（Linux/macOS）
- Windows 服务（Python `pywin32` + `win32com`）
- APScheduler（嵌入 Python 进程）

**MVP 选 Windows 计划任务**：零依赖、可视化、易调试。

### 4.3 增量同步逻辑

```python
# metrics_sync.py 核心逻辑（伪代码）
last_sync = load_last_sync_time()  # 从 metrics_sync_state.json 读
new_rows = fetch_feishu_rows(modified_after=last_sync)

for row in new_rows:
    if validate_row(row):  # 文章ID/平台/时间点 格式正确
        save_to_snapshot(row)
    else:
        log_invalid_row(row)

update_last_sync_time(now())
```

**幂等性保证**：每行用「文章ID + 时间点」作为唯一键，重复同步不会产生重复行。

---

## 五、反哺机制 B：模板优选（Phase 6.0 MVP）

### 5.1 核心问题

**问题**：在历史数据中，哪种「叙事策略 × 平台」组合的真实表现最好？

**示例**：
- 公众号 + 数据驱动型 → 平均互动率 8.2%（历史 12 篇均值）
- 公众号 + 观点碰撞型 → 平均互动率 5.1%
- 公众号 + 人物线索型 → 平均互动率 3.8%

→ 结论：下次公众号生成时，PRISM-OS 优先推荐「数据驱动型」

### 5.2 统计模型

**输入**：
- 平台（wechat / xiaohongshu）
- 叙事策略（观点碰撞型/数据驱动型/悬念解密型/人物线索型/时间线型）
- CCOS 模块组合（HOOK, CASE, EXPLAIN, MODEL, COUNTER, EVIDENCE, ACTION, BOUNDARY 的子集）
- 真实互动率（从飞书读）

**计算**：
```python
# 按平台 × 策略分组
strategy_perf = group_by(platform, strategy).agg(
    avg_engagement=mean(engagement_rate),
    sample_size=count(),
    confidence=ci_95(engagement_rate)  # 95% 置信区间
)

# 按平台 × 模块组合分组
module_perf = group_by(platform, frozenset(ccos_modules)).agg(
    avg_engagement=mean(engagement_rate),
    sample_size=count()
)
```

**最小样本量**：≥3 篇才开始推荐（避免被单篇异常值带偏）

**冷启动**（<3 篇）：不推荐任何策略，按默认权重出牌

### 5.3 应用方式

在 `narrate` / `generate` 阶段：

```python
# 之前
strategy = select_strategy_default(thesis, ccos_outline)

# 之后
calibration = load_calibration(platform)
strategy = select_strategy_with_calibration(
    thesis, ccos_outline, calibration
)
# 内部逻辑：calibration 中高分策略权重 +0.3
```

**渐进式调整**：单条数据的影响小（避免被噪音带偏），10+ 篇后才显著影响推荐

### 5.4 输出示例

`data/feedback_calibration.yaml`：

```yaml
last_updated: 2026-07-01T03:00:15
sample_size: 17

by_platform_strategy:
  wechat:
    数据驱动型:
      avg_engagement: 0.082
      sample_size: 5
      confidence_low: 0.061
      confidence_high: 0.103
    观点碰撞型:
      avg_engagement: 0.051
      sample_size: 4
      confidence_low: 0.034
      confidence_high: 0.068
    人物线索型:
      avg_engagement: 0.038
      sample_size: 3
      confidence_low: 0.020
      confidence_high: 0.056
  xiaohongshu:
    悬念解密型:
      avg_engagement: 0.124
      sample_size: 3
      confidence_low: 0.087
      confidence_high: 0.161

by_platform_module_combo:
  wechat:
    "HOOK,CASE,MODEL,ACTION":
      avg_engagement: 0.078
      sample_size: 4
    "HOOK,CASE,EXPLAIN,COUNTER,EVIDENCE":
      avg_engagement: 0.064
      sample_size: 3
```

---

## 六、反哺机制 A：HKR 校准（Phase 6.1，30+ 篇后）

**目标**：用真实数据反推 H/K/R 哪个维度真的预测互动率

**计算**：
```python
# 对历史 N 篇文章
for article in history:
    pred_h = article['predicted_hkr']['h']
    pred_k = article['predicted_hkr']['k']
    pred_r = article['predicted_hkr']['r']
    actual_engagement = article['engagement_rate']

# 计算每个维度与互动率的相关性
corr_h = pearson_corr(pred_h_list, actual_engagement_list)
corr_k = pearson_corr(pred_k_list, actual_engagement_list)
corr_r = pearson_corr(pred_r_list, actual_engagement_list)

# 调整 HKR 权重（基于相关性比例）
new_h_weight = corr_h / (corr_h + corr_k + corr_r)
new_k_weight = corr_k / (corr_h + corr_k + corr_r)
new_r_weight = corr_r / (corr_h + corr_k + corr_r)
```

**应用**：棱镜引擎打分时，H/K/R 用新权重合成 hkr_avg

**触发条件**：
- 样本量 ≥30 篇
- 距上次校准 >7 天
- 至少有一个维度的相关性 >0.3

---

## 七、技术实现路径

### 7.1 文件结构

```
skills/prism-os/
├── config/
│   ├── feishu_config.yaml           # 飞书 app_id/app_secret/bitable token
│   └── feishu_config.yaml.example
├── data/
│   ├── metrics_snapshot.yaml         # 飞书表本地副本（带时间戳）
│   ├── metrics_sync_state.json       # 增量同步状态
│   ├── feedback_calibration.yaml     # 反哺配置（实时更新）
│   └── hkr_weights.yaml              # HKR 校准系数（6.1+）
├── scripts/
│   ├── feishu_bitable.py             # 飞书多维表格 API 封装
│   ├── metrics_sync.py               # 增量同步主程序
│   ├── template_scorer.py            # B 模板优选统计
│   ├── calibration_engine.py         # A HKR 校准引擎（6.1+）
│   └── tests/
│       ├── test_feishu_bitable.py
│       ├── test_metrics_sync.py
│       ├── test_template_scorer.py
│       └── test_calibration_engine.py
└── prism_os.py                       # CLI 集成 metrics 命令
```

### 7.2 飞书 Open API 关键调用

| 操作 | API 端点 | 方法 |
|------|---------|------|
| 鉴权 | `/open-apis/auth/v3/tenant_access_token/internal` | POST |
| 列出多维表格 | `/open-apis/bitable/v1/apps` | GET |
| 列出记录（增量） | `/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records` | GET |
| 创建记录 | `/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records` | POST |
| 更新记录 | `/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}` | PUT |
| 创建多维表格 | `/open-apis/bitable/v1/apps` | POST |

**飞书凭证获取流程**（一次性配置）：
1. 登录飞书开放平台 https://open.feishu.cn/
2. 创建企业自建应用，获取 `app_id` + `app_secret`
3. 添加权限 `bitable:app:readonly` / `bitable:app` / `bitable:record:readonly` / `bitable:record`
4. 创建多维表格，复制 `app_token`（URL 中的 base64 串）
5. 写入 `feishu_config.yaml`

**PRISM-OS 提供辅助脚本**：
```bash
python feishu_setup.py   # 一键创建表（带 schema 校验）
```

### 7.3 配置示例

`config/feishu_config.yaml`：

```yaml
app_id: "cli_xxxxx"
app_secret: "xxxxx"
app_token: "bascnxxxxxx"   # 多维表格 token
table_id: "tblxxxxx"        # 目标表 ID
sync_schedule: "03:00"      # 每天同步时间
```

### 7.4 CLI 命令（仅供调试/手动触发）

```bash
# 一键建表（首次配置）
python feishu_setup.py

# 手动触发同步
python prism_os.py metrics sync

# 查看当前反哺状态
python prism_os.py metrics status

# 列出本地 snapshot
python prism_os.py metrics list
```

**日常使用**：用户**不需要**跑这些命令，全部后台自动完成。

---

## 八、TDD 测试计划

### 8.1 测试原则
- 写测试 → 看红 → 实现 → 看绿 → 重构
- 每个测试一个断言
- 端到端测试用 mock 飞书 API（避免依赖真实凭证）

### 8.2 测试矩阵

| 测试文件 | 测试数 | 覆盖点 |
|----------|--------|--------|
| `test_feishu_bitable.py` | 8 | 鉴权、增删改查、分页、错误码处理 |
| `test_metrics_sync.py` | 10 | 增量拉取、行校验、幂等性、缺失容忍、时间点识别 |
| `test_template_scorer.py` | 12 | 策略分组、模块组合、置信区间、冷启动、样本过滤 |
| `test_calibration_engine.py` | 5 | 相关性计算、权重归一化、触发条件、6.1 延后 |
| `test_e2e_phase6.py` | 4 | 端到端：mock 飞书 → sync → score → apply |
| **合计** | **39** | |

### 8.3 关键测试用例

**`test_metrics_sync.py::test_idempotent_sync`**：
- 同步同一行 3 次 → snapshot 中只有 1 条记录
- 防止重复同步导致数据污染

**`test_template_scorer.py::test_insufficient_sample`**：
- 只有 1 篇样本 → 不推荐任何策略
- 验证冷启动行为

**`test_template_scorer.py::test_platform_separation`**：
- 公众号数据驱动型 8% 互动率 ≠ 小红书数据驱动型 8% 互动率
- 验证按平台分组正确

**`test_e2e_phase6.py::test_full_loop`**：
- 准备 5 篇历史文章（含完整 metrics）
- 跑 sync → score → calibration
- 验证 calibration.yaml 中样本量、策略排序、置信区间

---

## 九、E2E 测试计划

### 9.1 测试目标

验证端到端数据流：
1. 文章生成（已有 v1.2.0 E2E）
2. 飞书表创建（feishu_setup.py）
3. 模拟用户填数据（直接写 mock 数据到 snapshot）
4. 同步 + 评分 + 校准（metrics_sync + template_scorer）
5. 校准应用于下次生成（narrate 步骤）

### 9.2 测试步骤

```python
def test_phase6_e2e():
    # 1. Mock 飞书 API（避免真实凭证）
    mock_feishu = MockFeishuBitable()
    mock_feishu.create_table(schema=PHASE6_SCHEMA)
    
    # 2. 准备历史数据：5 篇文章，每篇 3 个时间点
    history = generate_test_articles(count=5, snapshots=3)
    mock_feishu.bulk_insert(history)
    
    # 3. 触发同步
    sync_result = metrics_sync.run(mock_feishu)
    assert sync_result['new_rows'] == 15
    
    # 4. 触发评分
    calibration = template_scorer.run(platform='wechat')
    assert len(calibration['by_platform_strategy']['wechat']) > 0
    
    # 5. 验证下次生成用新校准
    narrative = narrate('新命题', platform='wechat')
    assert 'selected_strategy' in narrative
    # 注：具体策略选择取决于 calibration 结果，是 smoke test
```

### 9.3 真实环境验证（手动）

用户跑一遍：
1. `python feishu_setup.py` → 飞书多维表格创建成功
2. 用 PRISM-OS 生成 1 篇文章
3. 把文章手动复制到飞书表的「自动列」（PRISM-OS 同步过来）
4. 7 天后回填 T+7d 数据
5. 触发 `python prism_os.py metrics sync`
6. 打开 `data/feedback_calibration.yaml` 看是否有新策略

---

## 十、实施步骤

### Phase 6.0（v1.3.0 MVP — 模板优选 B）✅ 已完成

| 步骤 | 任务 | 验证 | 状态 |
|------|------|------|------|
| 1 | TDD 写 `feishu_bitable.py` 测试 | 8 测试通过 | ✅ |
| 2 | 实现 `feishu_bitable.py` | 8 测试通过 + 真实建表成功 | ✅ |
| 3 | TDD 写 `metrics_sync.py` 测试 | 11 测试通过 | ✅ |
| 4 | 实现 `metrics_sync.py` | 11 测试通过 | ✅ |
| 5 | TDD 写 `template_scorer.py` 测试 | 14 测试通过 | ✅ |
| 6 | 实现 `template_scorer.py` | 14 测试通过 | ✅ |
| 7 | CLI 集成 `prism_os.py metrics` | 4 E2E 测试通过 | ✅ |
| 8 | Windows 计划任务配置脚本 | setup_scheduler.ps1 | ✅ |
| 9 | CHANGELOG / SKILL / MEMORY 同步 | 文档一致 | ✅ |
| **10** | **真实环境 E2E** | **用户填 4 篇文章，wechat + 数据驱动型 = 11.68% 互动率** | ✅ |

**实际工作量**：1 天（5-7 天的预期被打脸）

**合并状态**：✅ commit 98a0be4 + merge 9131abf 已推送到 origin/main

### Phase 6.1（v1.3.1）— 已完成

**重要说明**：v1.3.1 实际实现的是 **calibration 接入 narrate**（模板优选反哺到生成），不是原计划中的 HKR 校准。
原计划的 HKR 校准延后到 Phase 6.2（样本 ≥30 篇后启动）。

**已完成**（v1.3.1）：
- `compute_calibration_boost()` — 根据历史表现为策略加分
- `evaluate_narrative_strategy` 接受 `calibration` + `platform` 参数
- `narrative_generation_workflow` / `interactive_narrative_workflow` 接入 calibration
- `prism_os.py narrate` 自动加载本地 calibration
- 11 个新测试全绿

完整方案见 `docs/development/Phase-6.1-Calibration-Integration-Plan.md`

### Phase 6.2（v1.4.0 — HKR 校准 A，待启动）

| 步骤 | 任务 | 触发 |
|------|------|------|
| 1 | TDD 写 `calibration_engine.py` 测试 | 样本 ≥30 篇 |
| 2 | 实现 `calibration_engine.py` | 5 测试通过 |
| 3 | prism 引擎接入新权重 | E2E 验证打分变化 |
| 4 | assassin 机制接入真实数据 | 刺客提醒可触发 |

### Phase 6.2（v1.4.0 — 主动推送洞察）

| 步骤 | 任务 | 触发 |
|------|------|------|
| 1 | 模板优选 → 主动建议「你最近表现最好的是 X」 | 模板优选稳定 |
| 2 | 缺口预测 → 提示「这种 CCOS 模块组合你还没试过」 | 样本 ≥50 篇 |

---

## 十一、风险点

| 风险 | 缓解策略 |
|------|----------|
| 飞书 API 凭证泄露 | 配置文件不入 git，提供 `.example` 模板；定期轮换 |
| 用户不填表 → 数据稀疏 | 缺失容忍设计：1 篇也行，置信区间反映不确定性 |
| 飞书表结构被人手动改坏 | schema 校验脚本，每次 sync 校验列名/类型，不匹配则告警 |
| 自动同步失败但用户不知道 | 失败时写日志 + 飞书消息通知用户（可选，Phase 6.2+） |
| 历史 0 篇时的反哺误判 | 冷启动：<3 篇不推荐任何策略；显式标注"数据不足" |
| 平台算法变化 → 历史规律失效 | 每个时间窗口的 calibration 单独计算，T+30d 数据更稳 |

---

## 十二、验收标准

### Phase 6.0 验收 ✅ 全部通过
- [x] `feishu_setup` 能在真实飞书环境创建表（21 列 + 3 视图）
- [x] `metrics_sync.py` 增量同步逻辑 100% 幂等
- [x] `template_scorer.py` 在 4 篇样本下输出合理 calibration（wechat + 数据驱动型 11.68%）
- [x] Windows 计划任务配置脚本 `setup_scheduler.ps1` 准备好，用户一次能跑通
- [x] 36 个单元测试 + 4 个 E2E 测试全部通过
- [x] CHANGELOG / SKILL / MEMORY 同步更新
- [x] 真实 E2E：用户填 4 篇文章数据，反哺配置正确更新

### Phase 6.1 验收 ✅ 全部通过
- [x] 11 个新测试 + 完整测试套件 66/66 通过
- [x] 无 calibration 时 narrate 行为不变（向后兼容）
- [x] 有 calibration 时高表现策略被优先选
- [x] E2E 验证：wechat + 数据驱动型 +0.668 boost 生效

### Phase 6.2 验收（待启动）
- [ ] 30 篇历史数据下，HKR 校准输出权重合理
- [ ] 棱镜引擎应用新权重后，新打分与历史表现的相关性提升

---

## 十三、参考文档

- `docs/development/Phase-5-Content-Generation-Plan.md` — Phase 5（已实现）
- 飞书多维表格 Open API：https://open.feishu.cn/document/server-docs/docs/bitable-v1/bitable-overview
- 飞书应用创建：https://open.feishu.cn/document/home/introduction-to-custom-app-development/self-built-application-development-process
- `skills/prism-os/CHANGELOG.md` — 版本演进
- `skills/prism-os/SKILL.md` — Skill 入口

---

**最后更新**：2026-06-03
