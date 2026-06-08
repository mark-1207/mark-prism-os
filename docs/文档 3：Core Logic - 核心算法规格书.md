# 文档 3：Core Logic - 核心算法规格书


## 一、算法设计原则

PRISM-OS 的核心算法遵循以下原则：

1. **数学化可验证**：所有决策逻辑必须可量化、可复现。

2. **正交性保证**：四维生成的标题必须在语义空间中互斥。

3. **反馈闭环**：用户选择和改词行为自动修正系统权重。

---

## 二、算法 1：意图熵值计算（Entropy Score）

### 目标

拦截模糊、情绪化的输入，强制用户进行命题澄清。

### 公式

$Score = (Object\_Clarity \times 0.4) + (Conflict\_Tension \times 0.4) + (Fact\_Support \times 0.2)$

其中：

- **Object_Clarity（对象清晰度）**：命题是否指向具体对象？

  - 1.0：明确对象（如“自媒体创作者”）

  - 0.5：模糊对象（如“年轻人”）

  - 0.0：无对象（如“感觉很迷茫”）

- **Conflict_Tension（冲突张力）**：命题是否包含矛盾或反常识元素？

  - 1.0：强矛盾（如“AI 让执行者失业”）

  - 0.5：弱矛盾（如“AI 改变工作方式”）

  - 0.0：无矛盾（如“AI 很强大”）

- **Fact_Support（事实支撑）**：命题是否基于具体现象？

  - 1.0：有具体案例或数据

  - 0.5：有模糊描述

  - 0.0：纯情绪表达

### 决策逻辑

```python
def calculate_entropy(user_input: str, llm: ILLMRouter) -> float:
    """
    调用 LLM 计算意图熵值。
    """
    prompt = f"""
    分析以下用户输入的命题质量，按 0-1 评分：
    
    输入：{user_input}
    
    请返回 JSON：
    {{
        "object_clarity": 0.8,
        "conflict_tension": 0.6,
        "fact_support": 0.5
    }}
    """
    
    response = llm.call(model="claude-3-5-haiku-20241022", prompt=prompt)
    scores = json.loads(response)
    
    entropy = (
        scores["object_clarity"] * 0.4 +
        scores["conflict_tension"] * 0.4 +
        scores["fact_support"] * 0.2
    )
    
    return entropy

def gate_decision(entropy: float) -> str:
    """
    根据熵值决定是否放行。
    """
    if entropy < 1.5:
        return "blocked"  # 拦截重构
    elif entropy < 2.5:
        return "clarify"  # 迫选追问
    else:
        return "pass"  # 直接放行
```

### 示例

| 输入 | Object | Conflict | Fact | Score | 决策 |
| --- | --- | --- | --- | --- | --- |
| “我想做自媒体但不知道写什么” | 0.5 | 0.0 | 0.0 | **0.2** | blocked |
| “AI 时代提问比执行更值钱” | 1.0 | 0.8 | 0.6 | **0.84** | clarify |
| “为什么 GPT-4 让初级程序员失业率上升 30%？” | 1.0 | 1.0 | 1.0 | **1.0** | pass |

---

## 三、算法 2：四维正交性校验（Orthogonality Check）

### 目标

确保生成的 4 个标题在语义空间中互不重叠，避免“换汤不换药”。

### 实现步骤

1. **向量化**：使用 Embedding 模型将 4 个标题转换为向量。

2. **计算相似度**：计算任意两个标题的余弦相似度。

3. **强制重生成**：如果 $Cosine_Sim(T_i, T_j) > 0.75$，则重新生成 $T_j$。

### 代码实现

```python
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

def check_orthogonality(titles: List[str], embedding_model) -> bool:
    """
    检查标题是否正交。
    """
    # 1. 向量化
    vectors = [embedding_model.embed(t) for t in titles]
    
    # 2. 计算相似度矩阵
    sim_matrix = cosine_similarity(vectors)
    
    # 3. 检查非对角线元素
    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            if sim_matrix[i][j] > 0.75:
                return False  # 不正交
    
    return True

def regenerate_until_orthogonal(
    thesis: str,
    dimensions: List[str],
    llm: ILLMRouter,
    max_attempts: int = 3
) -> List[Dict]:
    """
    生成并校验正交性，失败则重试。
    """
    for attempt in range(max_attempts):
        candidates = generate_candidates(thesis, dimensions, llm)
        titles = [c["title"] for c in candidates]
        
        if check_orthogonality(titles, embedding_model):
            return candidates
        
        # 如果不正交，标记相似度最高的维度重新生成
        # （此处省略具体实现）
    
    raise Exception("无法生成正交标题，请调整命题")
```

### 为什么阈值是 0.75？

- **经验值**：余弦相似度 > 0.75 表示两个标题在语义上高度重叠。

- **可调整**：用户可以在配置中修改此阈值。

---

## 四、算法 3：数学化反馈回路（Feedback Loop）

### 目标

根据用户的选择和改词行为，自动调整系统权重和生成偏好。

### 3.1 维度权重偏移

每次用户选择某个维度的标题，该维度的权重自动增加：

$W_k^{new} = W_k^{old} \times (1 + \alpha)$

其中 $\alpha$ 为学习率（建议 0.1）。

```python
def update_dimension_weight(selected_dimension: str, config: Dict, alpha: float = 0.1):
    """
    更新维度权重。
    """
    current_weight = config["dimension_weights"][selected_dimension]
    config["dimension_weights"][selected_dimension] = current_weight * (1 + alpha)
    
    # 归一化（可选）
    total = sum(config["dimension_weights"].values())
    for k in config["dimension_weights"]:
        config["dimension_weights"][k] /= total
```

### 3.2 改词向量修正

当用户修改标题时，系统提取改词前后的向量差，作为后续生成的“负偏置”：

$\vec{V}_{edit} = \vec{V}_{after} - \vec{V}_{before}$

```python
def record_edit_bias(original: str, edited: str, storage: IStorage):
    """
    记录改词偏好。
    """
    vec_before = embedding_model.embed(original)
    vec_after = embedding_model.embed(edited)
    
    edit_vector = vec_after - vec_before
    
    storage.update_fingerprint(
        word=edited,
        vector=edit_vector.tolist(),
        preference=1  # 标记为偏好
    )
```

在后续生成时，系统会：

1. 检索历史改词向量。

2. 将生成的标题向量与改词向量进行点积。

3. 如果点积为负（即方向相反），则降低该标题的排序。

---

## 五、算法 4：素材缺口分析（Gap Analysis）

### 目标

计算命题所需的“证据链”与现有素材的匹配度。

### 实现步骤

1. **提取证据链**：调用 LLM 分析命题，提取所需的论据类型。

2. **语义匹配**：将证据链与知识网关返回的素材进行 Embedding 匹配。

3. **计算缺口**：未匹配的证据占比即为缺口分数。

```python
def analyze_gap(thesis: str, knowledge: IKnowledgeGateway, llm: ILLMRouter) -> Dict:
    """
    分析素材缺口。
    """
    # 1. 提取证据链
    prompt = f"""
    分析以下命题需要哪些证据支撑：
    
    命题：{thesis}
    
    返回 JSON 列表：
    ["数据类型1", "案例类型2", "理论依据3"]
    """
    evidence_chain = json.loads(llm.call("claude-3-5-sonnet-20241022", prompt))
    
    # 2. 检索素材
    context = knowledge.fetch_context(thesis, limit=20)
    
    # 3. 匹配计算
    matched = 0
    for evidence in evidence_chain:
        for material in context:
            if cosine_similarity(
                embedding_model.embed(evidence),
                embedding_model.embed(material["content"])
            ) > 0.7:
                matched += 1
                break
    
    gap_score = 1 - (matched / len(evidence_chain))
    
    return {
        "gap_score": gap_score,
        "missing_evidence": [e for e in evidence_chain if e not in matched],
        "readiness": 1 - gap_score
    }
```

---

## 六、算法 5：逻辑压力测试（Logic Stress Test）

### 目标

替代多 Agent 对抗，通过形式逻辑检查器识别命题漏洞。

### 检测的逻辑谬误类型

1. **循环论证**：结论即前提。

2. **幸存者偏差**：只关注成功案例。

3. **因果倒置**：混淆因果关系。

4. **滑坡谬误**：夸大连锁反应。

### 实现

```python
def logic_stress_test(title: str, llm: ILLMRouter) -> Dict:
    """
    对标题进行逻辑压力测试。
    """
    prompt = f"""
    作为逻辑审计员，分析以下标题是否存在逻辑谬误：
    
    标题：{title}
    
    检查项：
    1. 是否存在循环论证？
    2. 是否存在幸存者偏差？
    3. 是否混淆因果关系？
    4. 是否存在滑坡谬误？
    
    返回 JSON：
    {{
        "has_fallacy": true/false,
        "fallacy_type": "循环论证",
        "explanation": "...",
        "severity": 0.8  // 0-1
    }}
    """
    
    result = json.loads(llm.call("claude-opus-4-20250514", prompt))
    return result
```

---

## 七、算法 6：认知旅程规划（Cognitive Journey）

### 目标

确保选题的认知深度是线性递进，而非原地打转。

### 实现

```python
def calculate_cognitive_distance(current_thesis: str, history: List[str]) -> float:
    """
    计算当前选题与历史选题的平均语义距离。
    """
    current_vec = embedding_model.embed(current_thesis)
    
    distances = []
    for past_thesis in history:
        past_vec = embedding_model.embed(past_thesis)
        dist = 1 - cosine_similarity([current_vec], [past_vec])[0][0]
        distances.append(dist)
    
    return np.mean(distances)

def check_cognitive_progress(current: str, history: List[str], threshold: float = 0.3) -> bool:
    """
    检查认知是否有进步。
    """
    distance = calculate_cognitive_distance(current, history[-5:])  # 只看最近 5 次
    
    if distance < threshold:
        return False  # 认知原地打转
    return True
```

---

## 八、性能优化建议

1. **缓存 Embedding**：对常见词汇和历史标题缓存向量，避免重复计算。

2. **批量调用 LLM**：将多个检查任务合并为一次 API 调用。

3. **异步执行**：现实校验和素材检索可并行执行。

---

## 九、下一步

参考 **文档 4：Adapter Contract - 接口适配协议**，了解如何实现具体的外部服务适配器。