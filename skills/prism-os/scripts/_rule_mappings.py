#!/usr/bin/env python3
"""
PRISM-OS Phase 4.7: 规则映射表
将 LLM 调用替换为查表操作，降低延迟和成本

内容目标映射 / 用户动机映射 / 选题类型分类 / 推进方式映射
"""

import re
from typing import Dict, List, Any, Optional

# ============ 内容目标映射 ============

# 关键词 → 内容目标（扩充版 Phase 4.7 修正）
CONTENT_GOAL_KEYWORDS: Dict[str, str] = {
    # 认知升级
    "认知升级": "认知升级",
    "理解": "认知升级",
    "重新认识": "认知升级",
    "看清": "认知升级",
    "本质": "认知升级",
    "底层逻辑": "认知升级",
    "核心": "认知升级",
    "真相": "认知升级",
    "实质": "认知升级",
    "为什么": "认知升级",
    "是什么": "认知升级",
    # 情绪共鸣
    "共鸣": "情绪共鸣",
    "感受": "情绪共鸣",
    "情绪": "情绪共鸣",
    "情感": "情绪共鸣",
    "代入": "情绪共鸣",
    "迷茫": "情绪共鸣",
    "焦虑": "情绪共鸣",
    "困惑": "情绪共鸣",
    "后悔": "情绪共鸣",
    "故事": "情绪共鸣",
    "经历": "情绪共鸣",
    # 实操教学
    "方法": "实操教学",
    "怎么": "实操教学",
    "如何": "实操教学",
    "步骤": "实操教学",
    "教程": "实操教学",
    "技巧": "实操教学",
    "操作": "实操教学",
    "落地": "实操教学",
    "学习": "实操教学",
    "指南": "实操教学",
    "攻略": "实操教学",
    "秘诀": "实操教学",
    # 趋势分析
    "趋势": "趋势分析",
    "未来": "趋势分析",
    "变化": "趋势分析",
    "预测": "趋势分析",
    "风口": "趋势分析",
    "崛起": "趋势分析",
    "爆发": "趋势分析",
    "AI": "趋势分析",
    "数字": "趋势分析",
    "技术": "趋势分析",
    "互联网": "趋势分析",
    # 观点表达
    "观点": "观点表达",
    "看法": "观点表达",
    "认为": "观点表达",
    "应该": "观点表达",
    "反对": "观点表达",
    "立场": "观点表达",
    "反思": "观点表达",
    "批判": "观点表达",
    "是不是": "观点表达",
    "真的吗": "观点表达",
    "真的吗": "观点表达",
    "对吗": "观点表达",
    # 信息整理
    "整理": "信息整理",
    "总结": "信息整理",
    "汇总": "信息整理",
    "分类": "信息整理",
    "清单": "信息整理",
    # 身份认同
    "我们": "身份认同",
    "一起": "身份认同",
    "大家": "身份认同",
    "同类": "身份认同",
    "群体": "身份认同",
    "00后": "身份认同",
    "90后": "身份认同",
    "小镇": "身份认同",
    # 转化成交
    "购买": "转化成交",
    "付费": "转化成交",
    "转化": "转化成交",
    "成交": "转化成交",
    "卖": "转化成交",
    "变现": "转化成交",
    "赚钱": "转化成交",
}

# alignment 字段优先级
CONTENT_GOAL_ALIGNMENT_RULES: Dict[str, str] = {
    "方向_机会": "趋势分析",
    "方向_焦虑": "实操教学",
    "方向_趋势": "趋势分析",
    "方向_方法": "实操教学",
    "方向_观点": "观点表达",
    "立场_明确": "观点表达",
}


def recognize_content_goal_rule(topic: str, alignment_result: Dict) -> Dict:
    """规则版内容目标识别"""
    topic_lower = topic.lower()
    topic_parsed = alignment_result.get("parsed", {})

    # 1. 优先用 alignment 字段
    direction = topic_parsed.get("方向", "")
    if direction:
        direction_key = f"方向_{direction}"
        if direction_key in CONTENT_GOAL_ALIGNMENT_RULES:
            goal = CONTENT_GOAL_ALIGNMENT_RULES[direction_key]
            return {"内容目标": goal, "置信度": 0.8}

    # 2. 关键词匹配
    scores: Dict[str, float] = {}
    for keyword, goal in CONTENT_GOAL_KEYWORDS.items():
        if keyword in topic_lower:
            scores[goal] = scores.get(goal, 0) + 1.0

    if scores:
        top_goal = max(scores, key=scores.get)
        # 归一化置信度：命中1个=0.7，2个=0.8，3个+=0.9
        match_count = max(scores.values())
        confidence = min(0.9, 0.6 + match_count * 0.1)
        return {"内容目标": top_goal, "置信度": confidence}

    # 3. 默认
    return {"内容目标": "认知升级", "置信度": 0.5}


# ============ 用户动机映射 ============

MOTIVATION_KEYWORDS: Dict[str, List[str]] = {
    "焦虑": ["焦虑", "担心", "害怕", "迷茫", "困难", "解决不了", "后悔", "内卷", "压力"],
    "好奇": ["好奇", "新鲜", "新事物", "趋势", "是什么", "为什么", "到底", "如何"],
    "认同": ["共鸣", "同样", "一样", "我们", "一起", "同类", "00后", "90后", "小镇"],
    "学习": ["学习", "提升", "成长", "方法", "技巧", "能力", "怎么", "如何"],
    "决策": ["决定", "选择", "判断", "犹豫", "对比", "决策", "还是", "应该"],
    "转化": ["影响", "推动", "带领", "说服", "变现", "赚钱", "成交", "付费"],
}

MOTIVATION_PAIRS: Dict[str, List[str]] = {
    "焦虑": ["学习", "好奇"],
    "好奇": ["焦虑", "学习"],
    "学习": ["焦虑", "决策"],
    "决策": ["焦虑", "认同"],
    "认同": ["好奇", "转化"],
    "转化": ["认同", "决策"],
}


def recognize_user_motivation_rule(topic: str, alignment_result: Dict) -> Dict:
    """规则版用户动机识别"""
    topic_lower = topic.lower()
    topic_parsed = alignment_result.get("parsed", {})

    # 1. alignment 方向推导
    direction = topic_parsed.get("方向", "")
    emotion = topic_parsed.get("情绪", "")
    direction_motivation_map = {
        "机会": "好奇",
        "焦虑": "焦虑",
        "趋势": "好奇",
        "方法": "学习",
        "观点": "认同",
    }
    if direction:
        primary = direction_motivation_map.get(direction, "好奇")
        secondary = MOTIVATION_PAIRS.get(primary, ["焦虑", "学习"])
        return {"用户动机": primary, "二级动机": secondary[:2]}

    # 2. 关键词匹配
    scores: Dict[str, float] = {}
    for motivation, keywords in MOTIVATION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in topic_lower:
                scores[motivation] = scores.get(motivation, 0) + 1.0

    if scores:
        top_motivation = max(scores, key=scores.get)
        secondary = MOTIVATION_PAIRS.get(top_motivation, ["焦虑", "好奇"])
        return {"用户动机": top_motivation, "二级动机": secondary[:2]}

    # 3. 默认
    return {"用户动机": "好奇", "二级动机": ["焦虑", "学习"]}


# ============ 选题类型分类 ============

TOPIC_TYPE_PATTERNS: Dict[str, Dict[str, Any]] = {
    "趋势型": {
        "keywords": ["趋势", "未来", "变化", "新", "崛起", "爆发", "风口", "机会", "方向"],
        "question_patterns": [r"为什么.*会", r".*将.*趋势", r"如何抓住.*机会", r".*赛道.*机会"],
        "weight": 1.0,
    },
    "方法型": {
        "keywords": ["方法", "怎么", "如何", "技巧", "步骤", "流程", "教程", "指南", "攻略", "秘诀", "秘诀"],
        "question_patterns": [r"如何.*", r"怎么.*", r".*技巧", r".*方法", r".*步骤"],
        "weight": 1.0,
    },
    "观点型": {
        "keywords": ["观点", "看法", "认为", "应该", "必须", "反对", "批判", "反思", "真相", "本质"],
        "question_patterns": [r"是否应该", r".*是对的吗", r".*的真相", r".*的本质"],
        "weight": 1.0,
    },
    "情绪型": {
        "keywords": ["共鸣", "感受", "情绪", "心理", "内心", "故事", "经历", "感悟", "心情"],
        "question_patterns": [r".*感受", r".*心情", r".*经历"],
        "weight": 1.0,
    },
    "行业型": {
        "keywords": ["行业", "产业", "市场", "赛道", "领域", "职业", "岗位", "公司", "产品", "品牌"],
        "question_patterns": [r".*行业.*", r".*市场.*", r".*职业.*", r".*赛道.*"],
        "weight": 1.0,
    },
}


def classify_topic_type_rule(topic: str) -> Dict:
    """规则版选题类型分类"""
    topic_lower = topic.lower()
    scores: Dict[str, float] = {}

    for topic_type, config in TOPIC_TYPE_PATTERNS.items():
        score = 0.0

        # 关键词匹配
        for kw in config["keywords"]:
            if kw in topic_lower:
                score += 1.5

        # 疑问词模式匹配
        for pattern in config.get("question_patterns", []):
            if re.search(pattern, topic_lower):
                score += 2.0

        if score > 0:
            scores[topic_type] = score * config.get("weight", 1.0)

    if scores:
        top_type = max(scores, key=scores.get)
        max_score = max(scores.values())
        confidence = min(0.95, 0.5 + max_score * 0.1)
        return {"类型": top_type, "置信度": confidence}

    # 默认：观点型
    return {"类型": "观点型", "置信度": 0.5}


# ============ 推进方式映射 ============

PROGRESSION_METHOD_MAP: Dict[str, Dict[str, Any]] = {
    "认知升级型": {
        "default": "冲突推进",
        "options": ["冲突推进", "递进推进", "对比推进"],
        "condition": {
            "有反直觉": "冲突推进",
            "有数据": "递进推进",
            "有案例": "对比推进",
        }
    },
    "问题拆解型": {
        "default": "递进推进",
        "options": ["递进推进", "拆解推进", "案例推进"],
        "condition": {
            "多步骤": "拆解推进",
            "有案例": "案例推进",
        }
    },
    "故事驱动型": {
        "default": "情绪推进",
        "options": ["情绪推进", "案例推进", "递进推进"],
        "condition": {
            "情绪强": "情绪推进",
            "有故事": "案例推进",
        }
    },
    "信息重构型": {
        "default": "对比推进",
        "options": ["对比推进", "递进推进", "拆解推进"],
        "condition": {
            "有对比": "对比推进",
            "层级多": "递进推进",
        }
    },
}

# alignment 立场 → 推进方式
PROGRESSION_STANCE_MAP: Dict[str, str] = {
    "反直觉": "冲突推进",
    "多步骤": "拆解推进",
    "情绪化": "情绪推进",
    "有对比": "对比推进",
    "有案例": "案例推进",
    "层层深入": "递进推进",
}


def decide_progression_method_rule(structure: str, topic: str, alignment_result: Optional[Dict] = None) -> Dict:
    """规则版推进方式决策"""
    topic_lower = topic.lower()
    structure_config = PROGRESSION_METHOD_MAP.get(structure, PROGRESSION_METHOD_MAP["认知升级型"])

    # 1. alignment 结果推导
    if alignment_result:
        stance = alignment_result.get("parsed", {}).get("立场", "")
        if stance:
            for key, method in PROGRESSION_STANCE_MAP.items():
                if key in stance.lower():
                    return {"推进方式": method, "描述": _get_progression_description(method)}

    # 2. 主题关键词匹配
    for key, method in PROGRESSION_STANCE_MAP.items():
        if key in topic_lower:
            return {"推进方式": method, "描述": _get_progression_description(method)}

    # 3. 默认
    default = structure_config.get("default", "冲突推进")
    return {"推进方式": default, "描述": _get_progression_description(default)}


def _get_progression_description(method: str) -> str:
    """推进方式说明"""
    descriptions = {
        "递进推进": "层层深入，认知升级",
        "拆解推进": "模块化拆解，步骤化呈现",
        "情绪推进": "情绪曲线驱动，高潮+低谷",
        "对比推进": "强反差，认知落差",
        "冲突推进": "认知碰撞，制造张力",
        "案例推进": "从案例抽象到理论",
    }
    return descriptions.get(method, "制造认知落差")