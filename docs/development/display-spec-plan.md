# PRISM-OS 展示规范方案

> 状态：方案阶段，等用户确认后再改代码
> 创建：2026-06-05
> 用户决策：
> - **3 确认点全详细 + 自动环节只展示汇总**
> - **数字分身 bug 这次一起修**
> - **苏格拉底只在 need_clarification 时问**
> - **加 --dry-run + 错位时 panic**

---

## 1. 11 个 Phase 一览（自动/确认）

| Phase | 类型 | 是否需要用户确认 | 展示详细度 |
|-------|------|------------------|------------|
| Phase 0 意图识别 | 自动 | ❌ trigger=false 直接退出 | 汇总 |
| Phase 1 苏格拉底网关 | 半自动 | ✅ **只在 need_clarification 时问** | 汇总 |
| Phase 1.5 备选检查 | 自动 | ❌ | 汇总 |
| Phase 2 棱镜引擎 | 自动 | ❌ | 汇总（4 维计数）|
| Phase 3 现实校验 | 自动 | ❌ | 汇总（rejected 数 + 原因） |
| Phase 3.5 数字分身 | 自动 | ❌ | 汇总（降权数）— **bug 修复** |
| 🚦 决策点 1 选标题 | **确认** | ✅ **必选** | **详细**（每个候选全展开）|
| Phase 4.5 CCOS | 自动 | ❌ | 汇总 |
| 🚦 决策点 2 CCOS 审核 | **确认** | ✅ **必审** c/r/q | **详细**（完整 CCOS）|
| Phase 4.6 Gap 分析 | 自动 | ❌ | 汇总 |
| 🚦 决策点 3 Gap 决策 | **确认** | ✅ **必决** 1/2/3/q | **详细**（4 个缺失证据）|
| Phase 5 逻辑+认知 | 自动 | ❌ | 汇总 |
| Phase 6 存储 | 自动 | ❌ | 汇总（cumulative_count）|
| Phase 7 刺客 | 自动 | ❌ | 汇总 |

---

## 2. 自动环节展示规范（"只展示汇总"）

### Phase 0 意图识别

```
[Phase 0] 意图: trigger=True, conf=0.60, 原因:讨论趋势话题
```

### Phase 1 苏格拉底网关

```
[Phase 1] 网关: status=need_clarification, score=0.40, HKR=0.10
        └─ 决策点 0.5 触发（need_clarification）
```

如果不需要问（ready_for_generation）：
```
[Phase 1] 网关: status=ready_for_generation, score=0.62, HKR=0.55
        └─ 跳过追问
```

### Phase 1.5 备选检查

```
[Phase 1.5] 备选: 0 个匹配
```

### Phase 2 棱镜引擎

```
[Phase 2] 棱镜: 9 个候选（reversal 2 / micro_scene 3 / systemic_flaw 2 / bridge 2）
        HKR 分布: ≥0.5=0 / 0.3-0.5=0 / <0.3=9（全部 low_hkr）
```

### Phase 3 现实校验

如果全过：
```
[Phase 3] 校验: 9/9 通过，无 reject
```

如果有 reject：
```
[Phase 3] 校验: 7/9 通过，reject 2 个
  - "标题1"（重复度过高，相似度 0.92）
  - "标题2"（竞争过于激烈，红海）
```

### Phase 3.5 数字分身

```
[Phase 3.5] 数字分身: 9→7 候选（降权 2 个）
  - 降权 "标题1"（不符合思维特征：反常识）
  - 降权 "标题2"（维度不匹配：bridge vs reversal）
```

如果加载失败（**修复后 panic，不静默降级**）：
```
[Phase 3.5] 数字分身: ❌ 加载失败 (bad operand type for unary -: 'str')
[PANIC] cognitive_crack.py:learn_thinking_pattern 出错，停止流程
```

### Phase 4.5 CCOS（自动部分）

```
[Phase 4.5] CCOS: 已生成（认知升级型 / 拆解推进）
  立场: AI时代下裁员为何会成为常态化潜规则？
  冲突: 实际裁员可能是个别现象
  └─ 决策点 2 等待审核
```

### Phase 4.6 Gap 分析（自动部分）

```
[Phase 4.6] Gap: score=0.67（较大）, 就绪度=33%, 缺失 4 个证据
  └─ 决策点 3 等待决策
```

### Phase 5 逻辑+认知

```
[Phase 5] 逻辑: 6 条审计, 认知旅程 avg_distance=0.62
```

### Phase 6 存储

```
[Phase 6] 存储: topic_log.yaml cumulative_count=170（+1）
```

### Phase 7 刺客

```
[Phase 7] 刺客: 历史 169 条命题, 反转 0 条（未触发）
```

---

## 3. 确认点展示规范（"全部详细"）

### 🚦 决策点 0.5（Phase 1 → 2）：苏格拉底追问

**仅在 need_clarification 时触发**：
```
━━━ 苏格拉底追问 ━━━
  1. 您认为AI时代裁员成为潜规则的主要原因是什么？
  2. 您是否担心AI技术的发展会对特定行业或职业产生更大的影响？
  3. 面对AI时代可能的裁员趋势，您认为企业和个人应该采取哪些措施？
━━━━━━━━━━━━━━━━━━━━
请直接回答（也可 skip 跳过）:
```

### 🚦 决策点 1（Phase 3.5 → 4.5）：选标题（**详细**）

```
━━━ 候选标题列表 ━━━
  1. ⚠️ AI正悄悄改变职场规则，你准备好了吗？
     HKR=0.10 | reversal | opinion_assertion
     字数=15 | 最高相似度=0.39
     理由: 反预期结果，激发好奇
  2. ...
━━━━━━━━━━━━━━━━━━━━
请选择标题编号（输入 q 退出，默认第一个）:
```

### 🚦 决策点 2（Phase 4.5 → 4.6）：CCOS 审核（**详细**）

```
━━━ CCOS 大纲审核 ━━━
  标题: ...
  立场: AI时代下裁员为何会成为常态化潜规则？
  核心冲突: 实际裁员可能是个别现象
  主结构: 认知升级型 / 推进: 拆解推进
  模块流:
    HOOK   | (内容摘要) | 制造停留
    CASE   | (内容摘要) | 建立真实感
    EXPLAIN| (内容摘要) | 建立理解
    MODEL  | (内容摘要) | 提升认知密度
    COUNTER| (内容摘要) | 制造记忆点
    EVIDENCE| (内容摘要) | 增强可信度
    ACTION | (内容摘要) | 提供落地
    BOUNDARY| (内容摘要) | 提升高级感
  情绪曲线: 好奇→震惊→共鸣→清晰→行动
━━━━━━━━━━━━━━━━━━━━
请选择: [c] 继续 [r] 重新生成 [q] 退出
```

### 🚦 决策点 3（Phase 4.6 → 5）：Gap 决策（**详细**）

```
━━━ Gap 决策 ━━━
  score: 0.67（缺口较大）
  readiness: 33%
  缺失证据:
    1. 企业裁员数据和认知提升的相关性分析
    2. 认知提升与职业发展成功率的统计数据
    3. 认知提升对提高工作效率和创新能力的案例研究
    4. 认知提升对避免重复性错误的影响研究
━━━━━━━━━━━━━━━━━━━━
请选择: [1] 补充素材 [2] 调整大纲 [3] 直接生成 [q] 退出
```

---

## 4. --dry-run 和 panic 模式

### --dry-run

每个 Phase 执行后，强制暂停展示（让用户看上一阶段输出再走下一步）：
```bash
python prism_os.py run "..." --dry-run
```

效果：
```
[Phase 2] 棱镜: 9 个候选...
--- dry-run: 按 Enter 继续 ---
[Phase 3] 校验...
```

### panic 模式

**修复 cognitive_crack.py 的 bug 后**，加载失败时直接 sys.exit(2) 不静默降级：
```python
# cognitive_crack.py
def learn_thinking_pattern(...):
    ...
    except Exception as e:
        if config.panic_on_error:
            raise  # 不再使用默认配置
```

CLI 加 `--panic` flag 默认开启 panic。

---

## 5. 实现步骤（按 TDD）

### Step 1：数字分身 bug 修复（**先修这个**）
- 找到 `bad operand type for unary -: 'str'` 位置
- 写 RED 测试（验证修复后不再抛）
- 修代码
- 跑测试确认 GREEN
- 跑全套测试无回归
- commit

### Step 2：加 panic 模式
- 数字分身：失败时 raise 而不是使用默认配置
- CLI 加 `--panic` flag
- RED 测试：故意让数字分身失败，断言 panic 行为
- 改代码
- commit

### Step 3：加 --dry-run
- PrismPipeline.run() 加 dry_run 标志
- 每个 Phase 完成后暂停等待
- RED 测试
- 改代码
- commit

### Step 4：调整 3 个确认点的 display
- PrismPhase：候选全展开（已在，需要确认格式）
- CCOSPhase：完整 CCOS 展示
- GapPhase：4 个缺失证据详细列
- 写测试验证展示内容
- 改代码
- commit

### Step 5：调整 8 个自动环节的 display
- 8 个 Phase 改为"汇总式"展示（1-3 行）
- 写测试
- 改代码
- commit

### Step 6：端到端验证
- 跑完整 run，用你给的命题
- 人工核对每个环节的展示
- 跑全量测试
- commit

---

## 6. 验证清单

跑完后我必须能回答这些问题：
- [ ] Phase 0 触发原因展示了？
- [ ] Phase 1 网关 score/HKR/决策展示了？
- [ ] Phase 1.5 备选数展示了？
- [ ] Phase 2 棱镜 4 维计数展示了？
- [ ] Phase 3 校验 reject 展示了？（全过也要展示"全过"）
- [ ] Phase 3.5 数字分身降权展示了？bug 修了？
- [ ] 决策点 1 标题全展开了？用户选了？
- [ ] Phase 4.5 CCOS 立场+模块流展示了？
- [ ] 决策点 2 CCOS 全文展示了？用户审了？
- [ ] Phase 4.6 Gap score+缺失项展示了？
- [ ] 决策点 3 Gap 4 个证据详细列了？用户决了？
- [ ] Phase 5 逻辑审计条数展示了？
- [ ] Phase 6 存储 cumulative_count 展示了？
- [ ] Phase 7 刺客反转数展示了？

---

**等你最终确认这 6 步后我开始改代码。每步独立 TDD，单独 commit，跑完再合并。**
