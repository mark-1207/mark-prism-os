#!/usr/bin/env python3
"""
PRISM-OS Phase 1: 苏格拉底网关（Socratic Gateway）
熵值计算脚本

用法:
    python socratic_gateway.py classify "<用户输入>"
    python socratic_gateway.py entropy "<用户输入>"
    python socratic_gateway.py gateway "<用户输入>"
"""

import sys
import json
import os
import re
from typing import Dict, List, Optional

# ============ 常量 ============
FALLBACK_TITLE_LENGTH = 10

# ============ Phase 1: 输入分类 ============

def classify_input(user_raw_input: str) -> str:
    """
    检测输入类型: keyword / sentence / question

    Args:
        user_raw_input: 用户原始输入

    Returns:
        输入类型: "keyword" | "sentence" | "question"
    """
    user_raw_input = user_raw_input.strip()

    # 检测是否包含问号（中文或英文）或疑问词模式
    has_question_mark = "?" in user_raw_input or "：" in user_raw_input

    # 检测中文疑问词模式
    chinese_question_patterns = ["为什么", "怎么", "如何", "怎麼", "是不是", "好不好", "要不要", "会不会", "能不能", "是谁", "是什么", "在哪", "几", "多少"]
    has_chinese_question = any(p in user_raw_input for p in chinese_question_patterns)

    # 对于中文：用字符数判断 keyword；英文：用空格数
    # keyword: 中文 < 10 个字符且无完整语义，英文 < 3 个单词
    # sentence: 中文 >= 10 个字符或表达完整语义
    is_keyword = False
    if " " in user_raw_input:
        # 英文，按空格分割
        is_keyword = len(user_raw_input.split()) <= 2
    else:
        # 中文，按字符数判断
        # 10 个字符以下通常是片段，10+ 才算完整句子
        is_keyword = len(user_raw_input) < 10

    if is_keyword:
        return "keyword"
    elif has_question_mark or has_chinese_question:
        return "question"
    else:
        return "sentence"


def generate_clarification_questions(user_input: str, input_type: str) -> List[str]:
    """
    根据输入类型生成追问选项

    Args:
        user_input: 用户输入
        input_type: classify_input 返回的类型

    Returns:
        2-3 个追问选项
    """
    base_prompt = f"""用户输入类型: {input_type}
用户输入: "{user_input}"

请生成 2-3 个追问，帮助用户将模糊意图明确化。

追问原则：
- keyword 类型: 追问核心观点、受众关联、期望行动
- sentence 类型: 追问背后假设、反驳角度、具体场景
- question 类型: 追问标准答案、打破常识、差异化答案

返回 JSON:
{{"questions": ["追问1", "追问2", "追问3"]}}
"""
    raw_result = _call_llm_raw(base_prompt)
    if not raw_result:
        return []

    # 解析 JSON
    try:
        data = json.loads(raw_result)
        questions = data.get("questions", [])
        if isinstance(questions, list) and len(questions) > 0:
            return questions
    except (json.JSONDecodeError, ValueError):
        pass

    # fallback: 尝试从字符串中提取
    try:
        match = re.search(r'\[.*\]', raw_result, re.DOTALL)
        if match:
            questions = json.loads(match.group(0))
            if isinstance(questions, list):
                return questions
    except (json.JSONDecodeError, ValueError):
        pass

    return []


# ============ Phase 1: HKR 内容价值评估 ============

def calculate_hkr(user_input: str) -> Dict:
    """
    计算 HKR 三维内容价值评分（规则版，不调用 LLM）

    H (Happy/愉悦度): 话题是否自带趣味性/传播性
    K (Knowledge/知识增量): 话题是否包含新知/洞察
    R (Resonance/情感共鸣): 话题是否引发"这说的就是我"的共鸣

    Returns:
        {"h": float, "k": float, "r": float, "hkr_avg": float}
    """
    text = user_input.strip()
    if not text:
        return {"h": 0.0, "k": 0.0, "r": 0.0, "hkr_avg": 0.0}

    # --- H: 愉悦度/传播性 ---
    h_keywords_strong = ["离谱", "笑死", "绝了", "震惊", "刺激", "神奇", "惊艳", "治愈", "炸裂", "疯狂"]
    h_keywords_moderate = ["有趣", "好笑", "好玩", "反转", "意外", "没想到", "居然", "竟然", "如何", "怎么", "如何", "怎样"]
    h_patterns = ["!", "！", "？？", "!!"]

    h_score = 0.0
    strong_h = sum(1 for kw in h_keywords_strong if kw in text)
    moderate_h = sum(1 for kw in h_keywords_moderate if kw in text)
    h_score += min(strong_h * 0.4, 1.0)
    h_score += min(moderate_h * 0.2, 0.4)
    if any(p in text for p in h_patterns):
        h_score += 0.1
    # 极短且有趣的输入
    if len(text) < 30 and strong_h > 0:
        h_score += 0.2
    h_score = min(h_score, 1.0)

    # --- K: 知识增量 ---
    k_keywords_strong = ["研究", "数据", "真相", "原理", "规律", "模型", "框架", "方法论", "机制", "策略", "思路"]
    k_keywords_moderate = ["发现", "分析", "拆解", "解读", "趋势", "报告", "实验", "调查", "应对", "转型", "提升", "适应", "核心", "如何", "怎么", "怎样", "问题"]
    k_patterns = [r"\d+%", r"\d+万", r"\d+亿", r"\d+年"]

    k_score = 0.0
    strong_k = sum(1 for kw in k_keywords_strong if kw in text)
    moderate_k = sum(1 for kw in k_keywords_moderate if kw in text)
    k_score += min(strong_k * 0.4, 1.0)
    k_score += min(moderate_k * 0.2, 0.4)
    if any(re.search(p, text) for p in k_patterns):
        k_score += 0.2
    # 因果推理结构加分
    if any(kw in text for kw in ["因为", "所以", "导致", "原因", "根源", "本质"]):
        k_score += 0.15
    k_score = min(k_score, 1.0)

    # --- R: 情感共鸣 ---
    r_keywords_strong = ["我", "我们", "每个人", "自己", "亲身", "经历"]
    r_keywords_moderate = ["共鸣", "同样", "压抑", "焦虑", "迷茫", "困惑", "担忧", "害怕"]
    # 2026-06-01 扩展：增加职场/年龄/危机类共同经历
    r_shared_exp = [
        "打工人", "社畜", "普通人", "年轻人", "中年人", "父母", "孩子",
        "程序员", "设计师", "运营", "销售", "医生", "律师", "老师",
        "35岁", "大龄", "中年", "职场", "打工人", "应届", "毕业生",
        "裁员", "失业", "转型", "被裁",
    ]

    r_score = 0.0
    strong_r = sum(1 for kw in r_keywords_strong if kw in text)
    moderate_r = sum(1 for kw in r_keywords_moderate if kw in text)
    shared = sum(1 for kw in r_shared_exp if kw in text)
    r_score += min(strong_r * 0.3, 0.7)
    r_score += min(moderate_r * 0.2, 0.4)
    r_score += min(shared * 0.3, 0.5)
    r_score = min(r_score, 1.0)

    avg = (h_score + k_score + r_score) / 3

    return {
        "h": round(h_score, 2),
        "k": round(k_score, 2),
        "r": round(r_score, 2),
        "hkr_avg": round(avg, 2)
    }


# ============ Phase 1: 熵值计算（规则版 Phase 4.7） ============

def _rule_object_clarity(text: str) -> float:
    """规则计算对象清晰度（0-1）"""
    # 明确写作意图
    if any(kw in text for kw in ["帮我写", "帮我做", "写一篇", "生成标题", "策划"]):
        return 1.0

    # 明确的具体对象
    specific_patterns = [
        r"^(老板|员工|程序员|设计师|运营|销售|医生|老师|学生|家长|小孩|男性|女性)\s",
        r"(老板|员工|程序员|设计师|运营|销售|医生|老师|学生|家长|小孩|男性|女性)的",
        r"自媒体(创作者|人|账号)|(小红书|公众号|抖音|B站)(创作者|博主|账号)",
        r"(初级|中级|高级|资深)\s", r"(00后|90后|80后|70后)\s",
        r"(创业|互联网|金融|教育|医疗|电商|AI)\s",
        r"(字节|腾讯|阿里|百度|美团|拼多多|京东)\s",
        r"(个体户|小工作室|个人开发者|独立开发者|自由职业|外包|接单)",
        # 2026-06-01 扩展：年龄+职业、年龄类、危机类、具体职业群
        r"\d+岁(程序员|打工人|员工|人|人士|医生|律师|教师|设计师)",
        r"(大龄|中老年|青年|青少年|初入职场|职场新人)",
        r"(失业|裁员|下岗|毕业|求职|面试|跳槽|转行|晋升|涨薪|降薪|被裁|优化)",
        r"(全职妈妈|宝爸|退休|应届|实习生|外包|合同工|临时工)",
    ]
    for p in specific_patterns:
        if re.search(p, text):
            return 1.0

    # 模糊对象
    vague_patterns = [r"(年轻人|打工人|普通人|大家|人们|所有人|很多人)", r"(一个人|某人|有人)"]
    for p in vague_patterns:
        if re.search(p, text):
            return 0.5

    # 短标题/疑问句（隐含对象）：有具体关键词就给 0.6
    short_keywords = [
        "AI", "个体", "工作室", "创业", "职业", "工作", "赚钱", "生存", "发展",
        "失业", "裁员", "危机", "转型", "管理", "产品", "技术", "运营",
    ]
    if len(text) < 40 and any(kw in text for kw in short_keywords):
        return 0.6

    # 无对象
    no_object_patterns = [r"^(很|觉得|感觉|好像|如何|怎么|为什么)", r"(迷茫|焦虑|困惑|无聊)"]
    for p in no_object_patterns:
        if re.search(p, text):
            return 0.0

    return 0.3


def _rule_conflict_tension(text: str) -> float:
    """规则计算冲突张力（0-1）"""
    # 强矛盾关键词
    strong_conflict = [
        "越", "却", "反而", "然而", "但", "事实上", "其实", "真相是",
        "表面上", "实际上", "并非", "不是", "反而", "竟然", "居然",
        "越X越Y", "越来越", "一边X一边Y",
    ]
    # 反常识关键词（2026-06-01 扩展：增加职场/转型/年龄相关）
    anti_common = [
        "反直觉", "不对", "错了", "不是这样", "误区", "陷阱",
        "淘汰", "失业", "崩塌", "危机", "终结", "消亡",
        "裁员", "下岗", "降薪", "被裁", "优化", "被替代", "淘汰",
        "打破", "逆转", "反转", "错位", "错配", "撕裂",
    ]

    text_lower = text.lower()
    strong_count = sum(1 for kw in strong_conflict if kw in text_lower)
    anti_count = sum(1 for kw in anti_common if kw in text_lower)

    if strong_count >= 2 or anti_count >= 2:
        return 1.0
    elif strong_count >= 1 or anti_count >= 1:
        return 0.7
    elif strong_count > 0:
        return 0.5
    return 0.3


def _rule_fact_support(text: str) -> float:
    """规则计算事实支撑度（0-1）"""
    # 有具体数据
    if re.search(r"\d+%|\d+万|\d+亿|\d+年|\d+月|\d+日|\d+岁", text):
        return 1.0
    # 有具体案例
    case_patterns = [r"(比如|例如|有个|曾经|一次|身边|朋友|同事|公司)", r"(案例|故事|经历|现象)"]
    if any(re.search(p, text) for p in case_patterns):
        return 0.7
    # 有现象描述
    phenomenon = ["发现", "看到", "感觉", "觉得", "似乎", "好像", "看起来"]
    if any(kw in text for kw in phenomenon):
        return 0.4
    # 2026-06-01 扩展：含行动/方法/原因关键词的视为有事实支撑
    action_keywords = [
        "如何", "怎么", "怎样", "方法", "步骤", "做法", "建议", "策略",
        "原因", "根源", "本质", "因为", "导致", "所以",
    ]
    if any(kw in text for kw in action_keywords):
        return 0.4
    # 纯情绪
    emotion_only = ["开心", "难过", "焦虑", "迷茫", "无聊", "不爽", "好累", "好烦"]
    if all(kw in text for kw in emotion_only[:2]):
        return 0.0
    return 0.2


def calculate_entropy(user_input: str, user_config: Optional[Dict] = None) -> Dict:
    """
    计算命题熵值，评估用户输入的质量

    熵值公式: Entropy = Object×0.4 + Conflict×0.4 + Fact×0.2

    决策规则:
    - Entropy >= 1.2 → "pass"，直接放行
    - Entropy >= 0.7 → "clarify"，迫选追问（更宽松）
    - Entropy < 0.7 → "clarify"，短标题/疑问句不直接 block，转追问
    - Entropy < 0.5 → "clarify"，真正无效输入

    Returns:
        {
            "object_clarity": float,
            "conflict_tension": float,
            "fact_support": float,
            "entropy_score": float,
            "decision": "blocked" | "clarify" | "pass",
            "reason": str
        }
    """
    object_score = _rule_object_clarity(user_input)
    conflict_score = _rule_conflict_tension(user_input)
    fact_score = _rule_fact_support(user_input)
    entropy = object_score * 0.4 + conflict_score * 0.4 + fact_score * 0.2
    is_short = len(user_input.strip()) < 25

    if entropy >= 0.8:
        decision = "pass"
        reason = "命题清晰、有张力"
    elif entropy >= 0.5:
        decision = "clarify"
        reason = "命题基本合格，建议补充具体对象或事实"
    else:
        # entropy < 0.5：短标题/疑问句不直接 block，转追问
        if is_short:
            decision = "clarify"
            reason = "命题较简短，需要补充更多背景才能判断价值"
        else:
            decision = "clarify"
            reason = "命题过于模糊或空洞，需补充具体背景"

    return {
        "object_clarity": round(object_score, 2),
        "conflict_tension": round(conflict_score, 2),
        "fact_support": round(fact_score, 2),
        "entropy_score": round(entropy, 2),
        "decision": decision,
        "reason": reason
    }


# ============ Phase 1: 苏格拉底网关主流程 ============

def socratic_gateway(user_input: str, user_config: Optional[Dict] = None, user_clarification: Optional[str] = None) -> Dict:
    """
    苏格拉底网关主流程

    Args:
        user_input: 用户原始输入
        user_config: 用户配置（可选）

    Returns:
        {
            "status": "ready_for_generation" | "need_clarification" | "blocked",
            "input_type": "keyword" | "sentence" | "question",
            "entropy_score": float,
            "decision": "blocked" | "clarify" | "pass",
            "reason": str,
            "directions": [str, ...]  # 仅当 decision=clarify 时
            "questions": []           # 保持字段兼容
        }
    """
    # Step 1: 输入分类
    input_type = classify_input(user_input)

    # 如果提供了 user_clarification，合并到 user_input 后重新评估
    if user_clarification:
        user_input = f"{user_input}\n\n补充说明：{user_clarification}"

    # Step 2: 熵值计算 + HKR 价值评估
    entropy_result = calculate_entropy(user_input, user_config)
    hkr_result = calculate_hkr(user_input)

    if entropy_result["decision"] == "error":
        return {
            "status": "error",
            "input_type": input_type,
            "entropy_score": 0.0,
            "decision": "error",
            "reason": entropy_result["reason"],
            "hkr": hkr_result,
            "questions": []
        }

    # Step 3: 联合决策（硬门槛 + 加权排名）
    entropy_score = entropy_result["entropy_score"]
    hkr_avg = hkr_result["hkr_avg"]
    combined = entropy_score * 0.4 + hkr_avg * 0.6

    is_pass = False
    is_blocked = entropy_result["decision"] == "blocked"

    if not is_blocked:
        # 硬门槛：两维都必须 > 0.3
        if entropy_score > 0.3 and hkr_avg > 0.3:
            # 过门槛 → 加权排名
            if combined >= 0.5:
                is_pass = True
            else:
                is_pass = False  # clarify
        else:
            is_pass = False  # clarify（某个维度不达标）

    if is_blocked:
        return {
            "status": "blocked",
            "input_type": input_type,
            "entropy_score": entropy_score,
            "decision": "blocked",
            "reason": entropy_result["reason"],
            "hkr": hkr_result,
            "questions": []
        }

    elif is_pass:
        return {
            "status": "ready_for_generation",
            "input_type": input_type,
            "entropy_score": entropy_score,
            "decision": "pass",
            "reason": f"命题清晰有张力（熵值{entropy_score:.2f}，HKR{hkr_avg:.2f}）",
            "hkr": hkr_result,
            "questions": [],
            "user_clarification": user_clarification,
        }

    else:
        # clarify 路径
        # 生成具体原因
        clarify_reasons = []
        if entropy_score <= 0.3:
            clarify_reasons.append("命题清晰度不足")
        if hkr_avg <= 0.3:
            clarify_reasons.append("内容价值偏低（缺乏知识增量或情感共鸣）")
        clarify_reason = "；".join(clarify_reasons) if clarify_reasons else entropy_result["reason"]

        questions = generate_clarification_questions(user_input, input_type)
        if not questions:
            questions = [
                "你想表达的核心观点是什么？",
                "这篇文章的目标读者是谁？",
                "你希望读者看完后有什么行动？"
            ]

        directions = generate_directions(user_input, input_type)
        if not directions:
            # LLM 失败时不输出垃圾占位符，让用户自由回答
            directions = []

        return {
            "status": "need_clarification",
            "input_type": input_type,
            "entropy_score": entropy_score,
            "decision": "clarify",
            "reason": clarify_reason,
            "user_clarification_received": bool(user_clarification),
            "combined_score": round(combined, 2),
            "hkr": hkr_result,
            "questions": questions,
            "directions": directions
        }


# ============ 辅助函数 ============

def _call_llm_raw(prompt: str) -> Optional[str]:
    from call_llm import call_llm_raw
    return call_llm_raw(prompt, temperature=0.7, scene="reasoning", error_prefix="LLM 调用错误:")


def _parse_llm_json(text: str) -> Optional[Dict]:
    """从 LLM 输出中解析 JSON"""
    if not text:
        return None

    # 尝试提取 JSON 代码块
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试找到 JSON 对象
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        pass

    return None


# ============ 选题方向生成 ============

DIRECTION_PROMPT = """你是选题方向生成器。根据用户输入，生成 2-3 个具体的选题方向。

用户输入: "{user_input}"
输入类型: {input_type}

方向要求：
- 每个方向是一个完整的选题角度，不是追问
- 方向之间正交（覆盖不同角度）
- 包含具体对象和冲突张力

返回 JSON:
{{"directions": ["方向1", "方向2", "方向3"]}}"""


def generate_directions(user_input: str, input_type: str) -> List[str]:
    """
    生成 2-3 个具体方向选项（替代追问问题）
    Returns: ["方向1", "方向2", "方向3"]
    """
    prompt = DIRECTION_PROMPT.format(
        user_input=user_input,
        input_type=input_type
    )

    result = _call_llm_raw(prompt)
    if not result:
        return []

    parsed = _parse_llm_json(result)
    if not parsed:
        return []

    directions = parsed.get("directions", [])
    if isinstance(directions, list) and len(directions) > 0:
        return [d for d in directions if isinstance(d, str) and d.strip()]

    return []


# ============ CLI 入口 ============

def _safe_print(obj):
    """修复 Windows GBK 编码问题：使用 binary mode"""
    output = json.dumps(obj, ensure_ascii=False)
    sys.stdout.buffer.write(output.encode("utf-8") + b"\n")

def main():
    if len(sys.argv) < 3:
        _safe_print({
            "error": "用法: python socratic_gateway.py <命令> <输入>",
            "commands": {
                "classify": "python socratic_gateway.py classify <输入> - 输入分类",
                "entropy": "python socratic_gateway.py entropy <输入> - 熵值计算",
                "gateway": "python socratic_gateway.py gateway <输入> - 完整网关流程"
            }
        })
        sys.exit(1)

    command = sys.argv[1]
    user_input = sys.argv[2]

    if command == "classify":
        result = {"input_type": classify_input(user_input)}
        _safe_print(result)

    elif command == "entropy":
        result = calculate_entropy(user_input)
        _safe_print(result)

    elif command == "gateway":
        result = socratic_gateway(user_input)
        _safe_print(result)

    else:
        _safe_print({"error": f"未知命令: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()