# Phase 1.5 备选检查（Backup Check）

> 流程位置：Phase 1 苏格拉底网关之后，Phase 2 棱镜引擎之前
> 详见 [SKILL.md § 完整工作流](../SKILL.md)

## 目标

在进入棱镜引擎前，先查 `crack_queue` 里是否有相关历史裂缝，避免重复造轮子。

## 入口

```python
from assassin import check_related_backups
matched = check_related_backups(user_input)
```

## 数据源

`data/crack_queue.yaml`（由 `cognitive_crack_hunter.py` 写入）

## 输出

```json
{
  "matched": [
    {
      "id": "crack_2026_06_05_xxx",
      "consensus": "AI 让程序员大量失业",
      "reality": "最新数据显示程序员需求增长 15%",
      "crack_type": "数据裂缝",
      "confidence": 0.88,
      "match_score": 0.72
    }
  ]
}
```

## 行为

- 找到匹配 → 在棱镜引擎 Prompt 里加 "避免重复竞品角度" 约束
- 无匹配 → 跳过，正常进入 Phase 2
- 致命异常 → 优雅降级，按无匹配处理（不阻塞流程）
