# PRISM-OS Phase 6.1 Calibration 接入 Narrate 方案

> 版本：1.0 | 日期：2026-06-03 | 状态：**✅ 已完成（合并到 main）**
>
> 关联：v1.3.1 | 父方案：docs/development/Phase-6-Data-Feedback-Loop-Plan.md

---

## 一、目标

把 `feedback_calibration.yaml`（Phase 6.0 产出的反哺配置）接入 `narrate` 步骤，让生成时**自动用历史上跑得通的策略组合**。

## 二、现状

**当前 narrate 选策略的逻辑**（`content_generator.py:1688 evaluate_narrative_strategy`）：

```python
# 关键词评分（素材类型 → 策略得分）
# 案例素材 → 人物线索型 +分
# 数据素材 → 数据驱动型 +分
# 洞察素材 → 悬念解密型 +分
# ...

# CCOS 主结构加权
# 故事驱动型 → 人物线索型 +2
# 认知升级型 → 观点碰撞/悬念解密 +1
# 问题拆解型 → 数据驱动型 +1
# ...

# 选最高分
best_strategy = max(scores, key=lambda k: scores[k])
```

**问题**：纯基于素材和内容目标选策略，**完全不知道历史真实表现**。

## 三、目标行为

**接入 calibration 后**：

```python
# 原有逻辑 + 历史表现加权
# 历史 wechat + 数据驱动型 = 11.68% 互动率
# 在 wechat 平台时，优先推荐该策略

scores[strategy] += calibration_boost  # 历史表现越好，加分越多
```

**实际效果**：
- 用户在 wechat 写新文章时，narrate 优先推荐「数据驱动型」（历史 11.68% 转化）
- 在 xiaohongshu 写新文章时，按默认权重（样本不足）
- 样本 ≥3 篇的策略才有 calibration 权重；不足则不调整

## 四、关键设计

### 4.1 Calibration 加载

```python
def load_calibration_for_platform(platform: str) -> Optional[Dict]:
    """从 feedback_calibration.yaml 加载某平台的 calibration

    Returns:
        {
            "by_platform_strategy": {
                "wechat": {
                    "数据驱动型": {
                        "avg_engagement": 0.1168,
                        "sample_size": 4,
                        "confidence_low": 0.1082,
                        "confidence_high": 0.1254
                    }
                }
            },
            "by_platform_module_combo": {...}
        }
    """
```

### 4.2 Calibration Boost 计算

**核心公式**：

```python
def compute_calibration_boost(calibration: Dict, platform: str, strategy: str) -> float:
    """根据历史表现为某个策略加分

    规则：
    - 样本 < 3：boost = 0（不调整）
    - 样本 3-9：boost = (avg_engagement - baseline) * scale
    - 样本 ≥ 10：boost = (avg_engagement - baseline) * scale * 1.5（更信任）

    baseline：所有策略平均互动率（参考线）
    scale：增益系数（默认 10，让 1% 差异 = 0.1 分）
    """
    if not calibration or not calibration.get("by_platform_strategy"):
        return 0.0

    platform_data = calibration.get("by_platform_strategy", {}).get(platform, {})
    strategy_data = platform_data.get(strategy, {})
    sample_size = strategy_data.get("sample_size", 0)
    avg_engagement = strategy_data.get("avg_engagement", 0)

    if sample_size < 3:
        return 0.0  # 冷启动不调整

    # 计算平台 baseline（所有策略的平均）
    all_engagements = [s["avg_engagement"] for s in platform_data.values() if s["sample_size"] >= 1]
    baseline = sum(all_engagements) / len(all_engagements) if all_engagements else 0

    scale = 10
    sample_boost = 1.5 if sample_size >= 10 else 1.0

    return (avg_engagement - baseline) * scale * sample_boost
```

### 4.3 evaluate_narrative_strategy 改造

```python
def evaluate_narrative_strategy(
    topic: str,
    ccos_outline: Dict,
    materials: List[Dict],
    search_results: List[Dict],
    calibration: Optional[Dict] = None,  # ← 新增参数
    platform: str = "wechat",             # ← 新增参数
) -> Dict:
    # ... 原有逻辑 ...

    # 原有评分
    scores = {name: 0.0 for name in NARRATIVE_STRATEGIES}
    # ... keyword + CCOS + content_goal 加分 ...

    # 新增：calibration 加分
    if calibration:
        for strategy in scores:
            boost = compute_calibration_boost(calibration, platform, strategy)
            scores[strategy] += boost

    best_strategy = max(scores, key=lambda k: scores[k])
    # ...
```

### 4.4 narrative_generation_workflow 改造

```python
def narrative_generation_workflow(
    topic: str,
    ccos_outline: Dict,
    platform: str,
    vault_path: Path = None,
    search_results: List[Dict] = None,
    auto_scrape: bool = False,
    calibration: Optional[Dict] = None,  # ← 新增参数
) -> Dict:
    # ...

    # Step 3: 策略评估（传入 calibration）
    strategy = evaluate_narrative_strategy(
        topic, ccos_outline, all_materials, search_results,
        calibration=calibration,  # ← 传入
        platform=platform,        # ← 传入
    )
    result["strategy"] = strategy
```

### 4.5 CLI 接入

`prism_os.py narrate` 自动加载 calibration，无需新参数。

```python
# 在 prism_os.py narrate 命令里
from template_scorer import load_calibration

calibration = load_calibration()  # 加载本地 calibration

result = narrative_generation_workflow(
    topic, ccos_outline, platform,
    calibration=calibration,  # 传入
)
```

## 五、模块组合（Module Combo）也用 calibration

按同样逻辑，模块组合（如 HOOK+CASE+MODEL+ACTION）也可以用 calibration 调整。

但**优先级**：
1. **策略层（必做）**：先做叙事策略（数据驱动型 vs 观点碰撞型）
2. **模块层（延后）**：模块组合的 calibration 接入 Phase 6.2+

## 六、TDD 测试计划

### 6.1 测试文件

`tests/test_narrate_calibration.py`，约 10 个测试：

| 测试 | 覆盖点 |
|------|--------|
| `test_load_calibration_for_platform` | 加载指定平台 calibration |
| `test_boost_with_insufficient_sample` | 样本 <3 → boost=0 |
| `test_boost_with_sufficient_sample` | 样本 3+ → boost>0（高表现）|
| `test_boost_with_low_performance` | 样本 3+ 但低表现 → boost<0 |
| `test_no_calibration_returns_zero` | calibration=None → boost=0 |
| `test_platform_baseline_calculated` | baseline 用平台均值 |
| `test_large_sample_extra_boost` | 样本 ≥10 → boost *1.5 |
| `test_strategy_selection_changes_with_calibration` | 高表现策略被优先选 |
| `test_strategy_unchanged_with_no_calibration` | 无 calibration → 行为不变 |
| `test_e2e_narrate_uses_calibration` | E2E：跑 narrate 看 strategy 输出 |

### 6.2 关键测试用例

**`test_strategy_selection_changes_with_calibration`**：
- 给 calibrate = `{wechat: {数据驱动型: {avg_engagement: 0.20, sample_size: 5}}}`
- 关键词评分让"观点碰撞型"领先
- 加 calibration 后"数据驱动型"应超过"观点碰撞型"

## 七、E2E 验证

### 7.1 测试场景

用真实 calibration 数据（来自用户的 4 篇 wechat + 数据驱动型 11.68% 互动率）跑 E2E：

1. 准备 calibration：模拟你的 4 篇历史数据
2. 准备 CCOS 大纲（认知升级型 + 一些素材）
3. 跑 `narrative_generation_workflow` 传入 calibration
4. 验证：选中的 strategy 是"数据驱动型"（历史 11.68% 表现）
5. 验证：strategy["scores"]["数据驱动型"] 包含 calibration boost

### 7.2 回归验证

确认无 calibration 时行为不变：
- `narrative_generation_workflow(..., calibration=None)` 
- 输出和之前完全一致（同样的 strategy 选择逻辑）

## 八、实施步骤

| 步骤 | 任务 | 验证 |
|------|------|------|
| 1 | TDD 写 `test_narrate_calibration.py` | 10 测试，全红 |
| 2 | 实现 `compute_calibration_boost()` | 6 个 boost 测试绿 |
| 3 | 改造 `evaluate_narrative_strategy()` | 2 个 selection 测试绿 |
| 4 | 改造 `narrative_generation_workflow()` + `interactive_narrative_workflow()` | 1 个 E2E 测试绿 |
| 5 | CLI 接入（`prism_os.py narrate` 自动加载） | 手动测试 1 篇 |
| 6 | 写文档（CHANGELOG / SKILL / MEMORY） | 文档完整 |
| **7** | **真实 E2E**（用你的 calibration 数据） | **看到策略被推荐** |

**预计工作量**：2-3 小时

## 九、风险点

| 风险 | 缓解 |
|------|------|
| 冷启动时 calibration 干扰 | 样本 <3 → boost=0 |
| 历史表现不可靠时误导 | sample_size 决定 boost 强度（<10 时 1.0x，≥10 时 1.5x）|
| 不同平台 calibration 混用 | 按 platform 分组加载 |
| 用户没跑过 sync/score | narrate 检测不到 calibration 文件时降级到无 calibration 行为 |
| 某策略历史数据偏多被压制 | 限制单策略最大 boost（封顶 5 分）|

## 十、验收标准

- [ ] 10 个单元测试 + 1 个 E2E 测试全部通过
- [ ] 无 calibration 时，narrate 输出和之前完全一致（回归通过）
- [ ] 有 calibration 时，高表现策略被优先选（用真实 calibration 数据验证）
- [ ] CHANGELOG / SKILL / MEMORY 同步更新
- [ ] 用户用真实 calibration 跑一次 narrate，看到策略被反哺推荐

## 十一、参考

- `docs/development/Phase-6-Data-Feedback-Loop-Plan.md` — Phase 6 父方案
- `scripts/template_scorer.py` — calibration 生成逻辑
- `scripts/content_generator.py:1688 evaluate_narrative_strategy` — 当前策略选择
- `scripts/content_generator.py:1991 narrative_generation_workflow` — 主入口

---

**最后更新**：2026-06-03
