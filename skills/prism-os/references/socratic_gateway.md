# 苏格拉底网关 - Socratic Gateway

## 功能

强制意图澄清，防止模糊输入导致的泛化输出。

## 输入

- `user_raw_input`: 用户原始输入（字符串）
- `user_config`: 用户配置文档（JSON 对象）

## 处理逻辑

### 1. 检测输入类型

```python
def classify_input(user_raw_input):
    """检测输入类型"""
    if len(user_raw_input.split()) <= 2:
        return "keyword"  # "AI"、"写作"等
    elif "?" not in user_raw_input:
        return "sentence"  # 陈述句
    else:
        return "question"  # 问句
```

### 2. 根据类型生成追问

| 输入类型 | 追问策略 |
|----------|----------|
| keyword | 核心观点是什么、受众关联、期望行动 |
| sentence | 背后假设、反驳角度、具体场景 |
| question | 标准答案、打破常识、差异化答案 |

```python
def generate_clarification_questions(user_raw_input):
    """根据输入类型生成追问"""
    input_type = classify_input(user_raw_input)

    if input_type == "keyword":
        return [
            "你想表达的核心观点是什么？",
            "你希望读者看完后产生什么行动？",
            "这个话题与你的受众有什么利益关联？"
        ]
    elif input_type == "sentence":
        return [
            "这句话背后的假设是什么？",
            "如果读者不同意这个假设，你会如何反驳？",
            "能否用一个具体场景来说明这个观点？"
        ]
    else:  # question
        return [
            "这个问题的标准答案是什么？你的答案有何不同？",
            "回答这个问题需要打破哪个常识？"
        ]
```

### 3. 提取关键要素

```python
def extract_elements(user_input, user_config):
    """提取核心要素"""
    return {
        "core_claim": extract_claim(user_input),  # 核心论点
        "target_emotion": infer_emotion(user_config["audience"]),  # 目标情绪
        "cognitive_crack": identify_crack(user_input, user_config)  # 认知裂缝
    }

def identify_crack(user_input, user_config):
    """识别认知裂缝（旧认知 vs 新认知）"""
    old_belief = extract_implicit_assumption(user_input)
    new_belief = generate_counter_narrative(
        old_belief,
        user_config["positioning"]["core_value"]
    )
    return {
        "old": old_belief,
        "new": new_belief,
        "tension": calculate_tension(old_belief, new_belief)
    }
```

### 4. 判断是否就绪

```python
def is_ready_for_generation(extracted_elements):
    """判断是否可以进入生成阶段"""
    return len(extracted_elements["core_claim"]) > 10  # 至少 10 字
```

## 输出

```json
{
  "clarification_questions": ["追问1", "追问2", "追问3"],
  "extracted_elements": {
    "core_claim": "核心论点内容",
    "target_emotion": "目标情绪",
    "cognitive_crack": {"old": "旧认知", "new": "新认知", "tension": 0.8}
  },
  "ready_for_generation": true
}
```

## 熵值计算

### 公式

```
Entropy = Object_Clarity × 0.4 + Conflict_Tension × 0.4 + Fact_Support × 0.2
```

### 维度定义

| 维度 | 1.0 | 0.5 | 0.0 |
|------|-----|-----|-----|
| Object_Clarity | 明确对象（如"自媒体创作者"） | 模糊对象（如"年轻人"） | 无对象（如"感觉很迷茫"） |
| Conflict_Tension | 强矛盾（如"AI让执行者失业"） | 弱矛盾（如"AI改变工作方式"） | 无矛盾（如"AI很强大"） |
| Fact_Support | 有具体案例或数据 | 有模糊描述 | 纯情绪表达 |

### 决策规则

**实际实现采用 0-1 范围**（sub-scores 0-1，公式 Object×0.4 + Conflict×0.4 + Fact×0.2 = max 1.0）

| Entropy 范围 | 决策 | 处理 |
|--------------|------|------|
| >= 0.8 | pass | 直接进入棱镜引擎 |
| 0.5 ~ 0.8 | clarify | 迫选追问，2-3 个选项 |
| < 0.5（短文本/疑问句） | clarify | 转追问，不直接 block |
| < 0.5（正常文本） | blocked | 拦截重构，说明原因 |

## Prompt

```
你是严格的命题审查员。评估用户输入的命题质量，按三个维度打分（0-1）：

1. Object_Clarity（对象清晰度）：命题是否指向具体对象？
   - 1.0：明确对象（如"自媒体创作者"、"初级程序员"）
   - 0.5：模糊对象（如"年轻人"、"打工人"）
   - 0.0：无对象（如"感觉很迷茫"、"想做点什么"）

2. Conflict_Tension（冲突张力）：命题是否包含矛盾或反常识元素？
   - 1.0：强矛盾（如"AI 让执行者失业"、"越努力越贫穷"）
   - 0.5：弱矛盾（如"AI 改变工作方式"）
   - 0.0：无矛盾（如"AI 很强大"、"要努力工作"）

3. Fact_Support（事实支撑）：命题是否基于具体现象？
   - 1.0：有具体案例或数据
   - 0.5：有模糊描述
   - 0.0：纯情绪表达

计算公式：Entropy = Object×0.4 + Conflict×0.4 + Fact×0.2

返回 JSON：
{
  "object_clarity": 0.8,
  "conflict_tension": 0.6,
  "fact_support": 0.5,
  "entropy_score": 0.68,
  "decision": "clarify",
  "reason": "命题有一定张力，但缺乏具体案例支撑"
}

决策规则：
- Entropy >= 0.8 → "pass"
- 0.5 <= Entropy < 0.8 → "clarify"
- Entropy < 0.5（短文本/疑问句）→ "clarify"（转追问）
- Entropy < 0.5（正常文本）→ "blocked"
```

## 示例

| 输入 | 类型 | Entropy | 决策 | 追问 |
|------|------|---------|------|------|
| "AI" | keyword | 0.0 | blocked | "你想表达的核心观点是什么？" |
| "我想写篇文章" | sentence | 0.2 | clarify | "这句话背后的假设是什么？" |
| "为什么努力工作让我更穷？" | question | 0.85 | pass | - |