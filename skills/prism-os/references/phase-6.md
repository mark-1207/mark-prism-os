# Phase 6 数据持久化

> 流程位置：Phase 5 逻辑压力测试之后，Phase 7 刺客机制之前
> 详见 [SKILL.md § 完整工作流](../SKILL.md)

## 目标

把每次 `run` 的完整结果写入 `data/topic_log.yaml`，供 Phase 7 刺客、Phase 6.0 数据闭环、后续语义距离计算使用。

## 写入位置

`skills/prism-os/data/topic_log.yaml`

## Schema

```yaml
- timestamp: "{{ISO_TIMESTAMP}}"
  thesis: "{{ORIGINAL_THESIS}}"
  clarified_intent: "{{CLARIFIED_INTENT}}"
  entropy_score: {{ENTROPY_SCORE}}
  candidates_count: {{CANDIDATES_COUNT}}
  selected_index: {{SELECTED_INDEX}}
  gap_report:
    gap_score: {{GAP_SCORE}}
    readiness: {{READINESS}}
    missing_evidence: [...]
  logic_audit:
    - title_index: 1
      has_fallacy: false
    - title_index: 2
      has_fallacy: true
      fallacy_type: "幸存者偏差"
      severity: 0.7
  cognitive_journey:
    avg_distance: {{AVG_DISTANCE}}
    status: "{{STATUS}}"
```

## 入口

```python
from storage import save_log
save_log(result)
```

## 行为

- 每次 `run` 跑完自动追加一条
- YAML 格式，可读可改
- 失败时 stderr 输出 warning，不阻塞流程
- 保留最近 100 条（超出自动归档到 `data/topic_log.archive.yaml`）
