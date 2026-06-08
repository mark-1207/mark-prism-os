# 意图识别 Prompt

用于判断用户输入是否触发 PRISM-OS 选题流程。

## Prompt

```
分析用户输入，判断是否需要生成选题或标题。

用户输入：{{USER_INPUT}}

返回 JSON：
{
  "trigger": true/false,
  "confidence": 0.0-1.0,
  "reason": "简短理由"
}

触发条件：用户想生成文章选题、拟定标题、策划内容方向、讨论写什么。
不触发：用户只是想聊天、问技术问题、做其他任务。

**Fallback 策略（v1.0.10）**：无法判断时默认触发（安全侧），confidence=0.3。
**实现位置**：`scripts/prism_os.py` → `classify_intent()` 函数。通过 `call_llm()` 调用 LLM 判断，LLM 不可用时走规则匹配 fallback。
```

## 调用示例

```python
import json

prompt = """分析用户输入，判断是否需要生成选题或标题。

用户输入：最近想写篇关于AI时代的文章

返回 JSON：
{
  "trigger": true/false,
  "confidence": 0.0-1.0,
  "reason": "简短理由"
}"""

# 调用 LLM
response = call_llm(prompt)
result = json.loads(response)
```

## 触发判断标准

| 触发 | 不触发 |
|------|--------|
| "帮我生成几个标题" | "帮我写代码" |
| "我想写篇文章" | "今天天气怎么样" |
| "有什么选题方向吗" | "解释一下 Python" |
| "最近想创作" | "闲聊" |

## 阈值建议

- confidence >= 0.7 → 直接触发
- 0.4 <= confidence < 0.7 → 追问确认
- confidence < 0.4 → 不触发