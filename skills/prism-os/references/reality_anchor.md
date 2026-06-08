# 现实校验锚 - Reality Check Anchor

> **实现状态**：已实现（v1.0.10）
> **实现文件**：`scripts/reality_anchor.py`
> **API 调用方式**：curl subprocess（`-k` 绕过 Windows SSL）
> **搜索降级链**：Tavily API → Firecrawl API → 跳过查重

## 功能

通过搜索 API 验证标题的新颖性与话题热度。

## 输入

- `candidates`: 棱镜引擎输出的候选标题列表

## 处理逻辑

### 1. 查重检测

```python
def reality_check(candidates, search_api, vocab_fingerprint_db):
    validated = []

    for candidate in candidates:
        # 1. 查重检测
        search_results = search_api.search(candidate["title"])
        similarity_scores = [
            calculate_similarity(candidate["title"], result["title"])
            for result in search_results[:10]
        ]
        max_similarity = max(similarity_scores) if similarity_scores else 0

        # 2. 词汇指纹检测
        fingerprint = extract_fingerprint(candidate["title"])
        is_cliche = check_cliche(fingerprint, vocab_fingerprint_db)

        # 3. 话题热度
        trend_score = get_trend_score(candidate["title"], search_api)

        # 4. 综合判定
        candidate["novelty_score"] = 1 - max_similarity
        candidate["is_cliche"] = is_cliche
        candidate["trend_score"] = trend_score
        candidate["final_score"] = (
            candidate["score"] * 0.5 +
            candidate["novelty_score"] * 0.3 +
            trend_score * 0.2
        )

        # 5. 负向筛选
        if max_similarity > 0.8:
            candidate["rejection_reason"] = "与现有内容重复度过高"
        elif is_cliche:
            candidate["rejection_reason"] = "使用陈词滥调"
        else:
            candidate["rejection_reason"] = None
            validated.append(candidate)

    return sorted(validated, key=lambda x: x["final_score"], reverse=True)[:6]
```

### 2. 相似度计算

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
```

### 3. 话题热度评估

```python
def get_trend_score(title, search_api):
    """
    获取话题热度评分（0-1）
    基于搜索结果中的最新内容数量和互动量
    """
    results = search_api.search(title, num_results=20)

    # 计算最近 30 天内的内容占比
    recent_count = 0
    total_engagement = 0

    for result in results:
        if result.get("published_date"):
            days_ago = (today - result["published_date"]).days
            if days_ago <= 30:
                recent_count += 1
        total_engagement += result.get("engagement", 0)

    # 热度评分 = 最近内容占比 × 0.6 + 互动量归一化 × 0.4
    recent_ratio = recent_count / len(results) if results else 0
    engagement_score = min(total_engagement / 10000, 1.0)  # 假设 10000 为基准

    return recent_ratio * 0.6 + engagement_score * 0.4
```

### 4. 词汇指纹检测

```python
def check_cliche(title, vocab_fingerprint_db):
    """
    检测标题是否使用陈词滥调
    """
    import re
    for pattern in vocab_fingerprint_db["cliche_patterns"]:
        if re.search(pattern["pattern"], title):
            return {
                "is_cliche": True,
                "matched_pattern": pattern["pattern"],
                "reason": pattern["reason"],
                "suggestion": get_replacement(title, pattern, vocab_fingerprint_db)
            }
    return {"is_cliche": False}

def get_replacement(title, pattern, vocab_fingerprint_db):
    """获取替换建议"""
    replacement_map = vocab_fingerprint_db.get("replacement_map", {})
    for word, replacement in replacement_map.items():
        if word in title:
            return title.replace(word, replacement)
    return title  # 无替换建议时返回原标题
```

## 综合评分公式

```
final_score = score × 0.5 + novelty × 0.3 + trend × 0.2
```

其中：
- `score`: 棱镜引擎生成的原始评分
- `novelty`: 1 - 查重率（新颖度）
- `trend`: 话题热度评分

## 竞争度标注

| 查重率 | 竞争度 | 说明 |
|--------|--------|------|
| < 0.3 | 蓝海 | 市场空白，值得尝试 |
| 0.3-0.7 | 黄海 | 有竞争，需差异化 |
| > 0.7 | 红海 | 高度饱和，谨慎 |

## 过滤规则

| 条件 | 过滤原因 | 处理 |
|------|----------|------|
| 查重率 > 0.8 | 与现有内容重复度过高 | 直接过滤 |
| is_cliche = True | 使用陈词滥调 | 直接过滤 |
| 其他 | - | 保留，进入排序 |

## 输出

- 通过校验的 Top 6 候选标题
- 每个标题附带完整评分与拒绝理由

```json
{
  "title": "为什么 AI 让'提问'比'执行'更值钱？",
  "dimension": "reversal",
  "score": 0.85,
  "novelty_score": 0.85,
  "trend_score": 0.65,
  "final_score": 0.78,
  "competition_level": "蓝海",
  "duplicate_rate": 0.15,
  "rejection_reason": null
}
```

## Prompt

```
你是内容竞争分析师。根据搜索结果评估选题新颖度。

搜索结果：{{SEARCH_RESULTS}}
待评估标题：{{TITLE}}

评估标准：
1. 查重率 = 标题与最相似搜索结果的相似度（0-1）
   - > 0.8：高度重复
   - 0.5-0.8：部分重复
   - < 0.5：基本原创

2. 竞争度标注：
   - 蓝海：查重率 < 0.3
   - 黄海：查重率 0.3-0.7
   - 红海：查重率 > 0.7

返回 JSON：
{
  "duplicate_rate": 0.15,
  "competition_level": "蓝海",
  "novelty_score": 0.85,
  "trend_score": 0.65,
  "final_score": 0.78,
  "top_similar_results": [
    {"title": "相似标题1", "url": "...", "similarity": 0.82}
  ],
  "recommendation": "建议执行"
}
```