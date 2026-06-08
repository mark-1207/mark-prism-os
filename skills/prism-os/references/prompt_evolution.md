# Prompt 自动变异 - Prompt Evolution

## 目标

根据用户的"改词记录"和"维度偏好"，自动修改系统的 System Instruction，实现真正的自我优化。

## 变异机制

### 1. 改词向量学习

当用户修改标题时，记录改词前后的向量差：

```
V_edit = V_after - V_before
```

在后续生成时，将生成的标题向量与历史改词向量进行点积：
- 点积为负 → 该标题方向与用户偏好相反，降低排序

### 2. 维度权重调整

每次用户选择某个维度的标题，该维度权重增加：

```
W_new = W_old × (1 + α)
```

其中 α 为学习率（默认 0.1）。

### 3. Prompt 变异条件

以下条件满足时，触发 Prompt 变异：

| 条件 | 阈值 | 说明 |
|------|------|------|
| 维度选择偏差 | > 30% | 某维度被选次数远超其他 |
| 改词重复率 | > 40% | 同一类词被反复修改 |
| 生成采纳率 | < 50% | 用户不使用生成的标题 |

### 4. 变异策略

#### 策略 1：强化偏好维度

如果用户长期偏好某个维度，提高该维度权重：

```
原 Prompt：四维生成权重均等
变异后：reversal: 1.5, micro_scene: 1.0, systemic_flaw: 1.0, bridge: 1.0
```

#### 策略 2：替换陈词

根据用户改词记录，替换 Prompt 中的禁用词：

```
原禁用词：赋能、降维打击
用户频繁改词：将"赋能"改为"驱动"
变异后禁用词：降维打击、破圈（保留"驱动"为合法词）
```

#### 策略 3：调整生成风格

如果用户偏好更具体的场景，减少抽象表达：

```
原风格：倾向于宏观分析
变异后：增加 micro_scene 维度权重，引导更具体场景
```

## 数据记录

```json
{
  "edit_history": [
    {
      "timestamp": "2026-04-30T10:00:00Z",
      "original": "为什么 AI 赋能职场人？",
      "edited": "为什么 AI 驱动职场人？",
      "reason": "不喜欢'赋能'这个词"
    }
  ],
  "dimension_selection": {
    "reversal": 5,
    "micro_scene": 3,
    "systemic_flaw": 2,
    "bridge": 1
  },
  "adoption_rate": 0.45,
  "last_mutation": {
    "timestamp": "2026-04-15",
    "changes": ["reversal_weight: 1.0 → 1.3"]
  }
}
```

## Prompt 变异计算

```
当 dimension_selection['reversal'] / total_selections > 0.4 时：

new_reversal_weight = old_reversal_weight × 1.2
new_other_weights = old_weights × 0.9（归一化后）

触发条件：连续 3 次选择同一维度 或 改词重复率 > 40%
```

## 变异日志

```yaml
- timestamp: "2026-04-30T10:00:00Z"
  trigger: "dimension_selection_bias"
  old_config:
    reversal: 1.0
    micro_scene: 1.0
    systemic_flaw: 1.0
    bridge: 1.0
  new_config:
    reversal: 1.3
    micro_scene: 0.9
    systemic_flaw: 0.9
    bridge: 0.9
  reason: "用户连续5次选择reversal维度"
```

## 验收标准

- Prompt 变异有效性 > 70%
- 变异后用户采纳率提升 > 20%
- 无负面变异（用户满意度不下降）

## 安全约束

1. **最小干预**：每次变异不超过 2 个参数
2. **可回滚**：记录历史配置，支持恢复到任意版本
3. **用户确认**：重大变异（权重变化 > 50%）需要用户确认
4. **渐进调整**：每次调整幅度不超过 20%