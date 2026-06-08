# 认知旅程规划 - Cognitive Journey Mapping

## 目标

确保选题的认知深度是线性递进，而非原地打转。

## 核心概念

**语义距离**：当前命题与历史选题的平均余弦距离。

- 距离 < 0.3 → 认知原地打转，输出警告
- 距离 >= 0.3 → 认知有进步，正常通过

## 阈值说明

| 阈值 | 含义 |
|------|------|
| 0.3 | 经验值，确保选题之间有足够差异 |
| 0.5 | 严格模式，要求更高区分度 |

## 首次使用处理

如果是首次使用（无历史选题），跳过此阶段并输出提示：

```
首次使用，认知旅程将在您有历史选题后开始记录。
```

## Prompt

```
你是认知路径规划师。计算当前选题与历史选题的语义距离。

当前命题：{{THESIS}}
历史选题：{{HISTORY_TOPICS}}（最近5条）

计算方法：
1. 用 Embedding 将当前命题和历史选题转为向量
2. 计算余弦距离
3. 平均距离 < 0.3 表示认知原地打转

返回 JSON：
{
  "avg_distance": 0.45,
  "cognitive_progress": "正常/原地打转",
  "warning": "如原地打转，给出警告",
  "recommendation": "如需调整，给出建议"
}

注意：如果是首次使用（无历史选题），返回：
{
  "status": "first_time",
  "message": "首次使用，跳过认知旅程校验"
}
```

## 计算算法

```python
def calculate_cognitive_distance(current_thesis: str, history: List[str]) -> float:
    current_vec = embedding_model.embed(current_thesis)

    distances = []
    for past_thesis in history:
        past_vec = embedding_model.embed(past_thesis)
        dist = 1 - cosine_similarity([current_vec], [past_vec])[0][0]
        distances.append(dist)

    return np.mean(distances)

def check_cognitive_progress(current: str, history: List[str], threshold: float = 0.3) -> bool:
    distance = calculate_cognitive_distance(current, history[-5:])
    return distance >= threshold
```

## 输出格式

```json
{
  "avg_distance": 0.45,
  "cognitive_progress": "正常",
  "warning": null,
  "recommendation": null
}
```

或

```json
{
  "status": "first_time",
  "message": "首次使用，跳过认知旅程校验"
}
```

或

```json
{
  "avg_distance": 0.22,
  "cognitive_progress": "原地打转",
  "warning": "当前命题与最近5个历史选题的平均语义距离仅为0.22，存在认知重复风险",
  "recommendation": "建议从不同角度切入，如：受众群体、时效性、场景差异"
}
```