# PRISM-OS 开发者实现文档

> **适用对象：** Claude Code、Cursor、Windsurf 等 AI 辅助开发工具\
> **目标：** 将架构设计转化为可执行的代码/逻辑实现

---

## 一、系统概览

**PRISM-OS** 是一个基于 YouMind Board 的选题生成系统，核心流程为：

```plaintext
用户意图 → 苏格拉底网关(澄清) → 棱镜引擎(生成) → 现实校验锚(验证) → 输出候选
```

**技术栈要求：**

- 运行环境： YouMind Skill / Claude API / 任何支持 Markdown 读写的 AI 系统

- 数据存储： 3 个 YouMind Craft 页面（用户配置、选题日志、词汇指纹库）

- 外部依赖： 搜索 API（用于查重与趋势验证）

---

## 二、核心模块实现规格

### 模块 1: 苏格拉底网关 (Socratic Gateway)

**功能：** 强制意图澄清，防止模糊输入导致的泛化输出。

**输入：**

- `user_raw_input`: 用户原始输入（字符串）

- `user_config`: 用户配置文档（JSON 对象）

**处理逻辑：**

```python
def socratic_gateway(user_raw_input, user_config):
    # 1. 检测输入类型
    input_type = classify_input(user_raw_input)  # "keyword" | "sentence" | "question"
    
    # 2. 根据类型生成追问
    if input_type == "keyword":
        questions = [
            "你想表达的核心观点是什么?",
            "你希望读者看完后产生什么行动?",
            "这个话题与你的受众有什么利益关联?"
        ]
    elif input_type == "sentence":
        questions = [
            "这句话背后的假设是什么?",
            "如果读者不同意这个假设,你会如何反驳?",
            "能否用一个具体场景来说明这个观点?"
        ]
    else:  # question
        questions = [
            "这个问题的标准答案是什么?你的答案有何不同?",
            "回答这个问题需要打破哪个常识?"
        ]
    
    # 3. 提取关键要素
    extracted = {
        "core_claim": extract_claim(user_raw_input),
        "target_emotion": infer_emotion(user_config["audience"]),
        "cognitive_crack": identify_crack(user_raw_input, user_config)
    }
    
    return {
        "clarification_questions": questions,
        "extracted_elements": extracted,
        "ready_for_generation": len(extracted["core_claim"]) > 10  # 至少 10 字
    }
```

**输出：**

- `clarification_questions`: 追问列表

- `extracted_elements`: 提取的核心要素

- `ready_for_generation`: 是否可进入生成阶段

---

### 模块 2: 棱镜引擎 (Prism Engine)

**功能：** 基于四维正交策略生成标题候选。

**输入：**

- `extracted_elements`: 网关输出的要素

- `user_config`: 用户配置

**四维生成策略：**

```python
def prism_engine(extracted_elements, user_config):
    core = extracted_elements["core_claim"]
    audience = user_config["audience"]
    
    # 维度 1: 认知裂缝型
    cognitive_titles = generate_cognitive_crack_titles(core, audience)
    # 示例: "为什么努力不一定有回报?因为你在用工业时代的逻辑玩信息时代的游戏"
    
    # 维度 2: 利益锚定型
    benefit_titles = generate_benefit_anchored_titles(core, audience)
    # 示例: "不懂这 3 个认知,你的努力正在为别人的财富增长买单"
    
    # 维度 3: 场景具象型
    scenario_titles = generate_scenario_titles(core, audience)
    # 示例: "当你的同事靠副业月入 5 万时,他其实只做对了一件事"
    
    # 维度 4: 反常识挑衅型
    contrarian_titles = generate_contrarian_titles(core, audience)
    # 示例: "停止学习,可能是你今年最正确的决定"
    
    # 合并并打分
    all_candidates = (
        cognitive_titles + benefit_titles + 
        scenario_titles + contrarian_titles
    )
    
    # 内部评分(基于用户配置的权重)
    scored = [
        {
            "title": t,
            "dimension": get_dimension(t),
            "score": calculate_score(t, user_config),
            "reasoning": explain_score(t, user_config)
        }
        for t in all_candidates
    ]
    
    # 返回 Top 12(每维度 3 个)
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:12]
```

**生成规则：**

- 每个标题必须包含“认知落差”（旧认知 vs 新认知）

- 长度控制在 18-28 字

- 避免使用“你必须知道”等说教式开头

- 必须有具体数字、场景或对比

---

### 模块 3: 现实校验锚 (Reality Check Anchor)

**功能：** 通过搜索 API 验证标题的新颖性与话题热度。

**输入：**

- `candidates`: 棱镜引擎输出的候选标题列表

**处理逻辑：**

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
        candidate["novelty_score"] = 1 - max_similarity  # 0-1
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

**输出：**

- 通过校验的 Top 6 候选标题

- 每个标题附带完整评分与拒绝理由

---

## 三、数据结构实现

### 1. 用户配置文档 (user_config.json)

```json
{
  "audience": {
    "age_range": "28-45",
    "occupation": "职场上升期/小老板",
    "pain_points": ["认知焦虑", "财富增长瓶颈", "AI 工具选择困难"],
    "aspiration": "成为认知升级的受益者"
  },
  "positioning": {
    "role": "揭秘者",
    "tone": "冷静、思辨、反常识",
    "core_value": "拆掉旧框架,建立新视角"
  },
  "preferences": {
    "title_length": [18, 28],
    "forbidden_words": ["你必须", "赶紧", "震惊"],
    "preferred_structures": ["为什么...因为...", "当...时,其实..."]
  },
  "weights": {
    "cognitive_crack": 0.4,
    "benefit_anchor": 0.3,
    "scenario": 0.2,
    "contrarian": 0.1
  }
}
```

### 2. 选题日志 (topic_log.jsonl)

每次生成后追加一行：

```json
{
  "timestamp": "2026-04-22T11:58:28Z",
  "user_input": "AI 让努力变得不值钱了",
  "clarified_intent": "揭示工业时代努力观在 AI 时代的失效",
  "generated_titles": [...],
  "selected_title": "为什么你越努力越焦虑?因为 AI 重新定义了'有价值的努力'",
  "performance": {
    "click_rate": null,  // 待用户反馈
    "user_rating": null
  }
}
```

### 3. 词汇指纹库 (vocab_fingerprint.json)

```json
{
  "cliche_patterns": [
    {"pattern": "必须知道的.*个.*", "reason": "标题党模板"},
    {"pattern": ".*让你.*", "reason": "说教式开头"},
    {"pattern": "震惊.*", "reason": "低质量引流词"}
  ],
  "user_vocabulary": {
    "high_performing_words": ["认知", "裂缝", "框架", "底层逻辑"],
    "low_performing_words": ["技巧", "方法", "秘诀"]
  }
}
```

---

## 四、YouMind API 集成

### 读取配置

```python
# 使用 YouMind read API
config_craft = read_craft(craft_id="<用户配置文档ID>")
user_config = parse_markdown_to_json(config_craft["content"])
```

### 写入日志

```python
# 使用 YouMind edit API
new_log_entry = format_log_entry(generation_result)
append_to_craft(
    craft_id="<选题日志ID>",
    content=new_log_entry
)
```

### 搜索查重

```python
# 使用 YouMind search API
existing_topics = search_board(
    board_id="<当前Board ID>",
    query=candidate_title,
    limit=10
)
```

---

## 五、部署检查清单

**开发前：**

- [ ]  确认 YouMind API 访问权限

- [ ]  准备搜索 API 密钥（Google/Bing）

- [ ]  创建 3 个初始化 Craft 页面

**开发中：**

- [ ]  实现苏格拉底网关的意图分类逻辑

- [ ]  实现棱镜引擎的四维生成函数

- [ ]  实现现实校验锚的相似度算法

- [ ]  编写单元测试（每个模块至少 3 个测试用例）

**部署后：**

- [ ]  使用 5 个真实案例测试完整流程

- [ ]  验证数据写入是否正常

- [ ]  检查错误处理机制（API 失败、空输入等）

---

## 六、关键算法伪代码

### 相似度计算 （用于查重）

```python
def calculate_similarity(title_a, title_b):
    # 使用 Jaccard 相似度 + 语义嵌入
    tokens_a = set(tokenize(title_a))
    tokens_b = set(tokenize(title_b))
    
    jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    
    # 如果有嵌入模型
    embedding_a = get_embedding(title_a)
    embedding_b = get_embedding(title_b)
    cosine = cosine_similarity(embedding_a, embedding_b)
    
    return 0.4 * jaccard + 0.6 * cosine
```

### 认知裂缝识别

```python
def identify_crack(user_input, user_config):
    # 提取用户输入中的"旧认知"
    old_belief = extract_implicit_assumption(user_input)
    
    # 基于用户定位生成"新认知"
    new_belief = generate_counter_narrative(
        old_belief, 
        user_config["positioning"]["core_value"]
    )
    
    return {
        "old": old_belief,
        "new": new_belief,
        "tension": calculate_tension(old_belief, new_belief)  # 张力分数
    }
```

---

## 七、错误处理

```python
class PRISMError(Exception):
    pass

def safe_generate(user_input, user_config):
    try:
        # 网关阶段
        gateway_result = socratic_gateway(user_input, user_config)
        if not gateway_result["ready_for_generation"]:
            return {"status": "need_clarification", "questions": gateway_result["clarification_questions"]}
        
        # 生成阶段
        candidates = prism_engine(gateway_result["extracted_elements"], user_config)
        if not candidates:
            raise PRISMError("生成失败:未产生有效候选")
        
        # 校验阶段
        validated = reality_check(candidates, search_api, vocab_db)
        if not validated:
            return {"status": "all_rejected", "reason": "所有候选均未通过现实校验"}
        
        return {"status": "success", "candidates": validated}
    
    except Exception as e:
        log_error(e)
        return {"status": "error", "message": str(e)}
```

---

## 八、性能优化建议

1. **缓存机制：** 对高频词汇的嵌入向量进行缓存

2. **并行生成：** 四维生成可并行执行

3. **增量更新：** 词汇指纹库每周批量更新，而非实时写入

4. **API 限流：** 搜索 API 调用加入重试与降级逻辑

---

## 九、测试用例

### 用例 1: 模糊输入

- **输入：** "AI"

- **期望：** 触发苏格拉底网关，返回 3 个追问

- **验证：** `gateway_result["ready_for_generation"] == False`

### 用例 2: 完整输入

- **输入：** “为什么 AI 时代，努力不再是成功的充分条件？”

- **期望：** 直接进入生成，输出 12 个候选

- **验证：** `len(candidates) == 12`

### 用例 3: 查重拦截

- **输入：** “AI 如何改变世界”（假设已有大量类似内容）

- **期望：** 现实校验阶段拒绝所有候选

- **验证：** `result["status"] == "all_rejected"`

---

**结语：**\
本文档提供了 PRISM-OS 的完整实现规格。开发者可基于此文档，在任何支持 AI API 调用与 Markdown 读写的环境中实现该系统。核心原则是：**保持逻辑闭环、强制意图澄清、避免泛化输出**。