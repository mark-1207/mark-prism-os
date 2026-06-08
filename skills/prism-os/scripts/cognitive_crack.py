#!/usr/bin/env python3
"""
PRISM-OS Phase 8: 认知裂缝捕捉 & 主动推送 & 数字分身
自动监控信息源发现认知裂缝 + 模拟创作者思维筛选

用法:
    python cognitive_crack.py detect "<信息源>" "<内容摘要>"
    python cognitive_crack.py twin "[<候选选题>]" "<思维特征>"
"""

import sys
import json
import os
import re
from typing import Dict, List, Optional

# ============ Phase 8: 认知裂缝捕捉 ============

def detect_cognitive_crack(source: str, content_summary: str) -> Dict:
    """
    分析信息源内容，判断是否存在认知裂缝

    Args:
        source: 信息源
        content_summary: 内容摘要

    Returns:
        {
            "has_crack": true/false,
            "crack_type": str,
            "consensus": str,
            "reality": str,
            "confidence": float,
            "suggested_topic": str
        }
    """
    prompt = f"""你是认知裂缝猎人。分析信息源中发现的内容，判断是否存在裂缝。

信息源：{source}
内容摘要：{content_summary}

裂缝类型：
- 数据裂缝：共识认为 X，但数据显示 Y
- 逻辑裂缝：共识基于 A，但 A 已被证伪
- 时效性裂缝：2020 年的共识已不适用 2026 年
- 人群裂缝：某些群体的经验与主流叙事不符

返回 JSON：
{{
  "has_crack": true/false,
  "crack_type": "数据裂缝/逻辑裂缝/时效性裂缝/人群裂缝",
  "consensus": "当前社会共识是什么",
  "reality": "实际情况是什么",
  "confidence": 0.0-1.0,
  "suggested_topic": "建议的选题方向"
}}"""

    result = _call_llm_raw(prompt)
    if not result:
        return {
            "has_crack": False,
            "crack_type": "",
            "consensus": "",
            "reality": "",
            "confidence": 0.0,
            "suggested_topic": ""
        }

    parsed = _parse_llm_json(result)
    if not parsed:
        return {
            "has_crack": False,
            "crack_type": "",
            "consensus": "",
            "reality": "",
            "confidence": 0.0,
            "suggested_topic": ""
        }

    return parsed


# ============ Phase 8: 主动推送 ============

def format_push_message(crack_result: Dict) -> str:
    """
    格式化认知裂缝推送消息

    Args:
        crack_result: detect_cognitive_crack 返回结果

    Returns:
        格式化的推送消息
    """
    if not crack_result.get("has_crack"):
        return ""

    crack_type = crack_result.get("crack_type", "")
    consensus = crack_result.get("consensus", "")
    reality = crack_result.get("reality", "")
    confidence = crack_result.get("confidence", 0.0)
    suggested = crack_result.get("suggested_topic", "")

    confidence_pct = int(confidence * 100) if confidence else 0

    message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【PRISM-OS 主动发现】

💡 检测到认知裂缝

共识：{consensus}
现实：{reality}

裂缝类型：{crack_type} | 置信度：{confidence_pct}%

建议选题方向：
{suggested}

是否基于这个裂缝生成标题？（yes/no）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return message.strip()


# ============ Phase 8: 数字分身 ============

def digital_twin_filter(candidates: List[Dict], thinking_pattern: str, dimension_weights: Dict = None, style_keywords: List = None) -> Dict:
    """
    模拟创作者进行初步选题筛选

    Args:
        candidates: 候选选题列表
        thinking_pattern: 创作者思维特征（字符串或结构化特征）
        dimension_weights: 维度偏好权重（可选）
        style_keywords: 风格关键词（可选）

    Returns:
        {
            "selected_topics": [...],
            "rejected_topics": [...],
            "digital_twin_confidence": float
        }
    """
    if not candidates:
        return {
            "selected_topics": [],
            "rejected_topics": [],
            "digital_twin_confidence": 0.0
        }

    candidates_str = json.dumps(candidates, ensure_ascii=False)

    # 构建增强的思维特征描述
    enhanced_pattern = thinking_pattern
    if dimension_weights:
        # 找出偏好维度
        sorted_dims = sorted(dimension_weights.items(), key=lambda x: x[1], reverse=True)
        top_dims = [d[0] for d in sorted_dims if d[1] > 0.3]
        if top_dims:
            dim_names = {
                "reversal": "逆向拆解",
                "micro_scene": "微观切片",
                "systemic_flaw": "系统归因",
                "bridge": "认知脚手架"
            }
            dim_str = "、".join([dim_names.get(d, d) for d in top_dims])
            enhanced_pattern += f"，偏好{dim_str}维度"

    if style_keywords:
        keywords_str = "、".join(style_keywords[:5])
        enhanced_pattern += f"，常用词汇：{keywords_str}"

    prompt = f"""你是数字分身的选题筛选模块。你的任务是模拟创作者进行初步筛选。

候选选题：{candidates_str}
创作者思维特征：{enhanced_pattern}

筛选原则：
1. 优先选择符合创作者思维特征的选题
2. 考虑维度偏好权重（如有）
3. 保留具有"认知落差"的选题
4. 过滤过于模式化或缺乏新意的选题

返回 JSON：
{{
  "selected_topics": [
    {{"topic": "选题", "selection_reason": "选择理由", "confidence": 0.0-1.0}}
  ],
  "rejected_topics": [
    {{"topic": "选题", "rejection_reason": "拒绝理由", "confidence": 0.0-1.0}}
  ],
  "digital_twin_confidence": 0.0-1.0
}}"""

    result = _call_llm_raw(prompt)
    if not result:
        return {
            "selected_topics": [],
            "rejected_topics": [],
            "digital_twin_confidence": 0.0
        }

    parsed = _parse_llm_json(result)
    if not parsed:
        return {
            "selected_topics": [],
            "rejected_topics": [],
            "digital_twin_confidence": 0.0
        }

    return parsed


# ============ Phase 8: 思维特征学习 ============

def learn_thinking_pattern(history_limit: int = 50) -> Dict:
    """
    从历史选题中学习创作者思维特征

    Args:
        history_limit: 加载历史记录数量

    Returns:
        {
            "thinking_pattern": str,  # 思维特征描述
            "dimension_weights": Dict[str, float],  # 维度偏好权重
            "style_keywords": List[str],  # 风格关键词
            "confidence": float  # 学习置信度（基于数据量）
        }
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from storage import load_log

    # 加载历史选题
    history = load_log(limit=history_limit)
    if not history:
        return {
            "thinking_pattern": "理性、克制、反常识",
            "dimension_weights": {"reversal": 0.25, "micro_scene": 0.25, "systemic_flaw": 0.25, "bridge": 0.25},
            "style_keywords": [],
            "confidence": 0.0
        }

    # 分析维度分布
    dimension_counts = {"reversal": 0, "micro_scene": 0, "systemic_flaw": 0, "bridge": 0}
    all_thesis = []

    for entry in history:
        thesis = entry.get("thesis", "")
        if thesis:
            all_thesis.append(thesis)

    # 使用 LLM 分析思维特征
    if all_thesis:
        thesis_sample = all_thesis[:10]  # 取前 10 条作为样本
        thesis_str = "\n".join([f"- {t}" for t in thesis_sample])

        prompt = f"""分析以下用户选题历史，提取完整的创作者模型。

用户选题：
{thesis_str}

分析维度：
1. 维度偏好：倾向于哪种选题角度？
   - reversal（逆向拆解）：颠覆常识，揭示反直觉真相
   - micro_scene（微观切片）：聚焦具体场景或人群
   - systemic_flaw（系统归因）：指向结构性问题
   - bridge（认知脚手架）：提供方法论或工具

2. 风格关键词：常用哪些词汇或句式？

3. 思维特征：用 3-5 个词概括用户的选题风格

4. 成长阶段（根据选题演变判断）：
   - 工具型：多工具教程、Prompt技巧
   - 方法型：工作流、效率方法、系统搭建
   - 系统型：方法论沉淀、行业洞察
   - 思想型：社会观察、价值观输出

5. 敏感方向：用户更容易对哪些主题产生表达欲？
   （如：个体竞争力、职业发展、AI影响、技术教育、认知升级等）

6. 世界观：用一句话概括用户的世界结构（如：技术进步与个体成长并行；效率至上；长期主义等）

返回 JSON：
{{
  "dimension_weights": {{"reversal": 0.0, "micro_scene": 0.0, "systemic_flaw": 0.0, "bridge": 0.0}},
  "style_keywords": ["关键词1", "关键词2"],
  "thinking_pattern": "特征1、特征2",
  "growth_stage": "系统型",
  "sensitive_directions": ["方向1", "方向2"],
  "worldview": "一句话世界观描述"
}}"""

        result = _call_llm_raw(prompt)
        if result:
            parsed = _parse_llm_json(result)
            if parsed:
                # 计算置信度（基于数据量）
                confidence = min(1.0, len(all_thesis) / 20)  # 20 条以上满置信度
                parsed["confidence"] = confidence
                # 确保新字段存在
                parsed.setdefault("growth_stage", "方法型")
                parsed.setdefault("sensitive_directions", [])
                parsed.setdefault("worldview", "")
                return parsed

    # 默认返回
    return {
        "thinking_pattern": "理性、克制、反常识",
        "dimension_weights": {"reversal": 0.25, "micro_scene": 0.25, "systemic_flaw": 0.25, "bridge": 0.25},
        "style_keywords": [],
        "confidence": 0.0,
        "growth_stage": "方法型",
        "sensitive_directions": [],
        "worldview": ""
    }


def record_twin_feedback(thesis: str, twin_selected: List[str], user_selected: str) -> Dict:
    """
    记录数字分身反馈

    Args:
        thesis: 用户命题
        twin_selected: 分身推荐的选题列表
        user_selected: 用户实际选择的选题

    Returns:
        {
            "status": "ok",
            "match": bool,
            "accuracy": Dict
        }
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from storage import save_twin_feedback, calculate_twin_accuracy

    # 判断是否匹配
    match = user_selected in twin_selected

    # 保存反馈
    feedback = {
        "thesis": thesis,
        "twin_selected": twin_selected,
        "user_selected": user_selected,
        "match": match
    }
    save_twin_feedback(feedback)

    # 计算匹配度
    accuracy = calculate_twin_accuracy()

    return {
        "status": "ok",
        "match": match,
        "accuracy": accuracy
    }


# ============ Phase D: creator_match 计算 ============

def compute_creator_match(crack_entry: Dict, creator_model: Dict) -> Dict:
    """
    根据裂缝的 signals 和创作者数字分身模型，计算 creator_match

    Args:
        crack_entry: 含 signals{trend,emotion,contradiction} 的队列条目
        creator_model: learn_thinking_pattern() 返回的模型，含
                       growth_stage/sensitive_directions/worldview

    Returns:
        {
            "growth_stage": "系统型",
            "sensitive_directions": ["个体竞争力"],
            "match_score": 0.75
        }
    """
    signals = crack_entry.get("signals", {})
    trend = signals.get("trend", "")
    emotions = signals.get("emotion", [])
    contradiction = signals.get("contradiction", "")

    creator_sensitive = creator_model.get("sensitive_directions", [])
    growth_stage = creator_model.get("growth_stage", "方法型")

    if not creator_sensitive:
        return {
            "growth_stage": growth_stage,
            "sensitive_directions": [],
            "match_score": 0.0
        }

    # LLM 语义匹配：裂缝 signals vs 敏感方向
    signal_text = " | ".join(filter(None, [trend, "/".join(emotions), contradiction]))

    prompt = f"""判断以下裂缝信号与创作者敏感方向的匹配程度。

创作者敏感方向：{", ".join(creator_sensitive)}
裂缝信号：{signal_text}

分析：
1. 裂缝触发了哪些敏感方向？（从创作者敏感方向中选择匹配的）
2. 匹配度高/中/低？

返回 JSON：
{{
  "matched_directions": ["匹配的方向1", "匹配的方向2"],
  "match_score": 0.0-1.0,
  "reasoning": "简要说明"
}}"""

    result = _call_llm_raw(prompt)
    if result:
        parsed = _parse_llm_json(result)
        if parsed:
            return {
                "growth_stage": growth_stage,
                "sensitive_directions": parsed.get("matched_directions", []),
                "match_score": parsed.get("match_score", 0.0)
            }

    # fallback
    return {
        "growth_stage": growth_stage,
        "sensitive_directions": [],
        "match_score": 0.0
    }


# ============ Phase 8: 主流程 ============

def cognitive_crack_hunter(source: str = "", content: str = "", candidates: List[Dict] = None, thinking_pattern: str = "") -> Dict:
    """
    Phase 8 完整流程：认知裂缝捕捉 + 数字分身

    Args:
        source: 信息源
        content: 内容摘要
        candidates: 候选选题（用于数字分身）
        thinking_pattern: 思维特征（用于数字分身）

    Returns:
        {
            "crack_detection": {...},
            "push_message": str,
            "digital_twin": {...}
        }
    """
    result = {
        "phase": "cognitive_crack",
        "crack_detection": {},
        "push_message": "",
        "digital_twin": {}
    }

    # 认知裂缝检测
    if source and content:
        crack_result = detect_cognitive_crack(source, content)
        result["crack_detection"] = crack_result
        result["push_message"] = format_push_message(crack_result)

    # 数字分身筛选
    if candidates and thinking_pattern:
        result["digital_twin"] = digital_twin_filter(candidates, thinking_pattern)

    return result


# ============ 辅助函数 ============

def _call_llm_raw(prompt: str) -> Optional[str]:
    from call_llm import call_llm_raw
    return call_llm_raw(prompt, temperature=0.7, scene="reasoning", error_prefix="[Error] LLM:")


def _parse_llm_json(text: str) -> Optional[Dict]:
    """从 LLM 输出中解析 JSON"""
    if not text:
        return None

    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[Warning] JSON 解析失败: {e}", file=sys.stderr)

    return None


# ============ CLI 入口 ============

def _safe_print(obj):
    output = json.dumps(obj, ensure_ascii=False)
    sys.stdout.buffer.write(output.encode("utf-8") + b"\n")


def main():
    if len(sys.argv) < 2:
        _safe_print({
            "error": "用法: cognitive_crack.py <命令> <数据>",
            "commands": {
                "detect": "cognitive_crack.py detect \"<信息源>\" \"<内容摘要>\" - 认知裂缝检测",
                "twin": "cognitive_crack.py twin '[{\"topic\":...}]' \"<思维特征>\" - 数字分身筛选",
                "full": "cognitive_crack.py full \"<信息源>\" \"<内容摘要>\" '[{\"topic\":...}]' \"<思维特征>\" - 完整流程",
                "learn": "cognitive_crack.py learn - 学习思维特征",
                "feedback": "cognitive_crack.py feedback '{\"thesis\":\"...\",\"twin_selected\":[...],\"user_selected\":\"...\"}' - 记录反馈",
                "accuracy": "cognitive_crack.py accuracy - 查看匹配度"
            }
        })
        sys.exit(1)

    command = sys.argv[1]

    if command == "detect":
        source = sys.argv[2] if len(sys.argv) > 2 else ""
        content = sys.argv[3] if len(sys.argv) > 3 else ""
        result = detect_cognitive_crack(source, content)
        _safe_print(result)

    elif command == "push":
        source = sys.argv[2] if len(sys.argv) > 2 else ""
        content = sys.argv[3] if len(sys.argv) > 3 else ""
        crack_result = detect_cognitive_crack(source, content)
        message = format_push_message(crack_result)
        _safe_print({"message": message})

    elif command == "twin":
        candidates_str = sys.argv[2] if len(sys.argv) > 2 else "[]"
        thinking_pattern = sys.argv[3] if len(sys.argv) > 3 else ""
        try:
            candidates = json.loads(candidates_str)
        except json.JSONDecodeError:
            candidates = []
        result = digital_twin_filter(candidates, thinking_pattern)
        _safe_print(result)

    elif command == "learn":
        result = learn_thinking_pattern()
        _safe_print(result)

    elif command == "feedback":
        if len(sys.argv) < 3:
            _safe_print({"error": "请提供反馈数据 JSON"})
            sys.exit(1)
        try:
            feedback_data = json.loads(sys.argv[2])
            result = record_twin_feedback(
                thesis=feedback_data.get("thesis", ""),
                twin_selected=feedback_data.get("twin_selected", []),
                user_selected=feedback_data.get("user_selected", "")
            )
            _safe_print(result)
        except json.JSONDecodeError:
            _safe_print({"error": "JSON 解析失败"})
            sys.exit(1)

    elif command == "accuracy":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from storage import calculate_twin_accuracy
        result = calculate_twin_accuracy()
        _safe_print(result)

    elif command == "full":
        source = sys.argv[2] if len(sys.argv) > 2 else ""
        content = sys.argv[3] if len(sys.argv) > 3 else ""
        candidates_str = sys.argv[4] if len(sys.argv) > 4 else "[]"
        thinking_pattern = sys.argv[5] if len(sys.argv) > 5 else ""
        try:
            candidates = json.loads(candidates_str)
        except json.JSONDecodeError:
            candidates = []
        result = cognitive_crack_hunter(source, content, candidates, thinking_pattern)
        _safe_print(result)

    else:
        _safe_print({"error": f"未知命令: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()