# PRISM-OS LLM 调用优化方案

> 版本：1.0 | 日期：2026-05-19 | 状态：已规划，待开发

---

## 一、背景问题

### 1.1 当前 LLM 调用问题

| 问题 | 严重度 | 影响 |
|------|--------|------|
| **cognitive_outline.py 9个调用无 Scene** | 🔴 Bug | 空 scene → 默认 8192 tokens，内容分析任务用错配置 |
| **双平台 18→6 调用可优化** | 🔴 性能 | 12个平台无关结果算两遍（~67% 重复） |
| **6个 Layer 1-2 调用串行执行** | 🟡 性能 | 本可并行，总耗时 /6 |
| **熵值计算用 LLM（公式却调 API）** | 🟡 浪费 | 完全是确定性公式，无需 LLM |
| **prism_engine 4维串行** | 🟡 性能 | 本可并行 |
| **logic_pressure N个审计串行** | 🟡 性能 | 本可并行 |

### 1.2 当前调用计数

```
Phase 1: socratic_gateway      → 3次（reasoning scene）
Phase 2: prism_engine          → 4次（writing-cn scene）← 串行
Phase 3.5: learn_thinking     → 1次
Phase 3.5: digital_twin_filter→ 1次
Phase 4: cognitive_outline     → 18次（无 scene）← 🔴 BUG + 重复
Phase 5: logic_pressure        → 1 + N次
Phase 7: assassin_mechanism   → N次 + 1次

最大总计：~29 + N_audit + N_reverse
```

---

## 二、重构方案

### 2.1 cognitive_outline.py 拆分（必须 LLM vs 规则）

| 函数 | 当前 | 重构后 | 方式 |
|------|------|--------|------|
| `recognize_content_goal` | LLM | **规则** | 关键词/维度→内容目标映射表 |
| `recognize_user_motivation` | LLM | **规则** | 关键词→动机映射表 |
| `classify_topic_type` | LLM | **规则** | 正则+疑问词检测 |
| `extract_core_problem` | LLM | **保留** | 推理内容生成 |
| `extract_cognitive_tension` | LLM | **保留** | 推理内容生成 |
| `infer_potential_directions` | LLM | **保留** | 推理内容生成 |
| `decide_progression_method` | LLM | **查配置表** | 主结构→推进方式直接映射 |
| `generate_cognitive_module_flow` | LLM | **保留** | 编排创意 |
| `generate_narrative_energy` | LLM | **保留** | 张力创意 |

**结果：单平台 9次 → 4次（-56%），双平台 18次 → 6次（-67%）**

### 2.2 熵值计算 → 纯公式（Phase 1）

```python
# socratic_gateway.py 新增规则版
def calculate_entropy_fast(text: str) -> Dict:
    object_score = _rule_based_object_clarity(text)  # 规则
    conflict_score = _rule_based_conflict_tension(text)  # 规则
    fact_score = _rule_based_fact_support(text)  # 规则
    entropy = object_score * 0.4 + conflict_score * 0.4 + fact_score * 0.2
    return {
        "object_clarity": object_score,
        "conflict_tension": conflict_score,
        "fact_support": fact_score,
        "entropy_score": entropy,
        "decision": "pass" if entropy >= 2.5 else "clarify" if entropy >= 1.5 else "blocked"
    }
```

**结果：Phase 1 熵值计算节省 1次 LLM（100%→0）**

### 2.3 双平台缓存共享

```
# generate_dual_platform_outline() 重构
shared = {
    "topic_type": classify_topic_type(topic),          # 只算1次
    "core_problem": extract_core_problem(topic),        # 只算1次
    "cognitive_tension": extract_cognitive_tension,   # 只算1次
    "potential_directions": infer_potential_directions, # 只算1次
    "main_structure": select_main_structure(...),       # 规则
    "progression_method": decide_progression(...),     # 规则
}
wechat_result = build_outline(shared, platform="wechat")   # 平台相关各1次
xhs_result = build_outline(shared, platform="xiaohongshu")
```

**结果：双平台 18次 → 6次**

### 2.4 并行化剩余 LLM 调用

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(extract_core_problem, topic),
        executor.submit(extract_cognitive_tension, topic),
        executor.submit(infer_potential_directions, topic),
        executor.submit(generate_cognitive_module_flow, ...),
    ]
    # 并行等待结果
```

**结果：4次串行 → 1次并行（耗时 /4）**

---

## 三、重构后效果对比

| 指标 | 重构前 | 重构后 | 改善 |
|------|--------|--------|------|
| cognitive_outline 单平台 LLM 调用 | 9次 | 4次 | **-56%** |
| cognitive_outline 双平台 LLM 调用 | 18次 | 6次 | **-67%** |
| Phase 1 熵值计算 | 1次 LLM | 0次 | **-100%** |
| 剩余 LLM 调用是否并行 | 否 | 是 | **耗时 /4** |
| Scene 设置正确性 | 空（BUG） | writing-cn | **配置正确** |
| **完整流程最大调用** | **~29** | **~14** | **-50%** |

---

## 四、执行计划

| 顺序 | 任务 | 改动范围 | 风险 |
|------|------|----------|------|
| P0 | 新建 `_rule_mappings.py` — 内容目标/动机/类型/推进方式映射表 | 新建1文件 | 无 |
| P1 | `classify_topic_type` → 规则版 | cognitive_outline.py | 低（有 fallback） |
| P2 | `recognize_content_goal` + `recognize_user_motivation` → 规则版 | cognitive_outline.py | 低 |
| P3 | `decide_progression_method` → 查配置表 | cognitive_outline.py | 无（直接映射） |
| P4 | `cognitive_outline_workflow` 加 shared_result 缓存 | cognitive_outline.py | 中（需测试） |
| P5 | `generate_dual_platform_outline` 改为共享缓存 | cognitive_outline.py | 中（需测试） |
| P6 | Layer 1-2 剩余 LLM 调用并行化 | cognitive_outline.py | 中（需测试） |
| P7 | `socratic_gateway.py` 熵值计算规则版 | socratic_gateway.py | 中（需验证等效性） |
| P8 | cognitive_outline._call_llm_raw 设置 `GATEWAY_SCENE=writing-cn` | cognitive_outline.py | 无（配置修复） |

**预计代码改动量：~200行**
**预计测试：57项单元测试继续通过 + 新增规则函数测试**

---

## 五、修复收益

1. **成本降低**：减少 50% LLM API 消耗（Kimi 按量付费直接省钱）
2. **速度提升**：并行化后耗时从 N×T 降到 max(T, 并行池)
3. **稳定性提升**：规则替代的调用不再受 LLM 服务可用性影响
4. **配置正确**：cognitive_outline 终于用上正确的 scene 和 max_tokens
5. **维护性**：映射表可配置，无需改代码就能调整分类规则

---

## 六、后续优化（可选）

| 优化项 | 说明 | 优先级 |
|--------|------|--------|
| prism_engine 4维并行 | generate_dimension_titles() × 4 并行 | P2 |
| logic_pressure 审计并行 | audit_title() × N 并行 | P2 |
| LLM 响应缓存 | 相同 prompt 相同结果缓存，减少重复调用 | P3 |
| 批量 API | Kimi/OpenRouter 支持批量调用，当前单次逐条 | P3 |