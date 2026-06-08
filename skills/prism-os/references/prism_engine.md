# 棱镜引擎 - 四维标题生成

## 四维定义（与开发者文档对齐）

| 中文名 | 英文名 | 公式 | 示例 |
|--------|--------|------|------|
| 认知裂缝型 | Reversal | 为什么"常识 A"其实是"真相 B"？ | 为什么"努力工作"反而让你更穷？ |
| 利益锚定型 | Benefit Anchor | 不懂 X，你的 Y 就是在为别人服务 | 不懂这 3 个认知，你的努力正在为别人的财富增长买单 |
| 场景具象型 | Micro-Scene | 当 X 时，Y | 当你的同事靠副业月入 5 万时，他其实只做对了一件事 |
| 反常识挑衅型 | Contrarian | 停止 X，可能是你最正确的决定 | 停止学习，可能是你今年最正确的决定 |

## 约束条件（与开发者文档对齐）

- 标题长度：18-28 字
- 禁止词汇：赋能、降维打击、破圈、必须知道、震惊等
- 正交性：语义相似度 < 0.75（余弦相似度）
- 每维生成 3 个候选，共 12 个
- 必须包含"认知落差"（旧认知 vs 新认知）
- 必须有具体数字、场景或对比
- 避免"你必须知道"等说教式开头

## Prompt

```
你是顶级选题策划师。根据用户命题，生成 4 个完全不同的标题，分别对应以下维度：

**维度定义：**

1. 认知裂缝型（Reversal）：颠覆常识，揭示反直觉真相。
   - 公式：为什么"常识 A"其实是"真相 B"？
   - 示例：为什么"努力工作"反而让你更穷？

2. 利益锚定型（Benefit Anchor）：利益关联，驱动行动。
   - 公式：不懂 X，你的 Y 就是在为别人服务
   - 示例：不懂这 3 个认知，你的努力正在为别人的财富增长买单

3. 场景具象型（Micro-Scene）：聚焦具体场景或人群。
   - 公式：当"场景 X"时，"现象 Y"如何发生？
   - 示例：当你的同事靠副业月入 5 万时，他其实只做对了一件事

4. 反常识挑衅型（Contrarian）：挑战常识，刺激思考。
   - 公式：停止 X，可能是你最正确的决定
   - 示例：停止学习，可能是你今年最正确的决定

**约束条件：**
- 每个标题必须在 18-28 字之间
- 禁止使用：赋能、降维打击、破圈、必须知道、震惊等词
- 四个标题的语义相似度必须 < 0.75
- 每维生成 3 个候选，共 12 个
- 必须包含"认知落差"（旧认知 vs 新认知）
- 必须有具体数字、场景或对比

用户命题：{{THESIS}}
用户身份：{{IDENTITY_ROLE}}
目标受众：{{AUDIENCE}}
维度权重：{{DIMENSION_WEIGHTS}}

返回 JSON：
{
  "candidates": [
    {
      "dimension": "reversal",
      "title": "为什么 AI 让'提问'比'执行'更值钱？",
      "rationale": "颠覆了'执行力是核心竞争力'的常识"
    },
    ...
  ]
}
```

## 正交性校验算法

```python
def calculate_similarity(title_a, title_b, embedding_model=None):
    """
    相似度计算：Jaccard×0.4 + Cosine×0.6
    """
    # Jaccard 相似度
    tokens_a = set(tokenize(title_a))
    tokens_b = set(tokenize(title_b))
    jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b) if tokens_a or tokens_b else 0

    # Cosine 相似度（如有嵌入模型）
    if embedding_model:
        vec_a = embedding_model.embed(title_a)
        vec_b = embedding_model.embed(title_b)
        cosine = cosine_similarity([vec_a], [vec_b])[0][0]
    else:
        cosine = 0

    return 0.4 * jaccard + 0.6 * cosine

def check_orthogonality(titles: List[str], embedding_model) -> bool:
    """检查标题是否正交"""
    vectors = [embedding_model.embed(t) for t in titles]
    sim_matrix = cosine_similarity(vectors)

    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            if sim_matrix[i][j] > 0.75:
                return False
    return True

def regenerate_until_orthogonal(thesis, dimensions, llm, max_attempts=3):
    """生成并校验正交性"""
    for attempt in range(max_attempts):
        candidates = generate_candidates(thesis, dimensions, llm)
        titles = [c["title"] for c in candidates]

        if check_orthogonality(titles, embedding_model):
            return candidates

    raise Exception("无法生成正交标题")
```

## 输出格式

```json
{
  "candidates": [
    {"dimension": "reversal", "title": "...", "rationale": "..."},
    {"dimension": "reversal", "title": "...", "rationale": "..."},
    {"dimension": "reversal", "title": "...", "rationale": "..."},
    {"dimension": "benefit_anchor", "title": "...", "rationale": "..."},
    ...
  ]
}
```