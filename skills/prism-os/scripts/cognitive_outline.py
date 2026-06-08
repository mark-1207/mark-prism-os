#!/usr/bin/env python3
"""
PRISM-OS Phase 4.5: CCOS v2.0 认知推进流动态大纲
Layer 0-8 → 14项动态认知大纲生成

用法:
    python cognitive_outline.py outline "<标题>" "<dimension>" "<平台>"
    python cognitive_outline.py dual "<标题>" "<dimension>"
    python cognitive_outline.py alignment "<标题>" "<平台>"
    python cognitive_outline.py legacy "<标题>"
"""

import sys
import json
import os
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============ 规则映射表（Phase 4.7） ============
from _rule_mappings import (
    recognize_content_goal_rule,
    recognize_user_motivation_rule,
    classify_topic_type_rule,
    decide_progression_method_rule,
)

# ============ YAML 配置加载 ============

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def _load_ccos_settings() -> Dict:
    """加载 ccos_settings.yaml 配置"""
    settings_path = Path(__file__).parent.parent / "data" / "ccos_settings.yaml"
    if not settings_path.exists():
        return {}
    with open(settings_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if data else {}


def _get_config(path: List[str], default: Any = None) -> Any:
    """从 ccos_settings.yaml 中按路径获取配置"""
    settings = _load_ccos_settings()
    for key in path:
        if isinstance(settings, dict):
            settings = settings.get(key, {})
        else:
            return default
    return settings if settings else default


# ============ T-1: 基础辅助函数 ============

def _call_llm_raw(prompt: str, temperature: float = 0.7) -> Optional[str]:
    from call_llm import call_llm_raw
    return call_llm_raw(prompt, temperature=temperature, scene="writing-cn", error_prefix="[LLM Error]")


def _parse_llm_json(text: str) -> Optional[Dict]:
    """从 LLM 输出解析 JSON（含 code block 提取）"""
    if not text:
        return None
    # 防御：如果收到的是 dict（直接返回了 LLM result 的情况），提取 content 后解析
    if isinstance(text, dict):
        if "content" in text:
            inner = text["content"]
            if isinstance(inner, str):
                try:
                    return json.loads(inner)
                except Exception:
                    pass
        return None
    # 尝试提取 code block
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    match = re.search(code_block_pattern, text)
    if match:
        text = match.group(1)
    else:
        # 尝试直接解析整个文本
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试用正则提取 JSON 对象
        json_pattern = r"\{[\s\S]*\}"
        match = re.search(json_pattern, text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


def _safe_print(obj: Any) -> None:
    """Windows GBK 安全输出"""
    try:
        text = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
        sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
    except Exception as e:
        print(f"[Print Error] {e}", file=sys.stderr)


# ============ T-2: 平台差异化配置 ============

def _get_platform_hints(platform: str) -> Dict:
    """返回公众号/小红书/两者的 prompt 差异化配置"""
    wechat_hints = {
        "focus": "逻辑推进 / 认知升级 / 信息密度",
        "tone": "深度 / 理性 / 逻辑严密",
        "style": "更像思想产品",
        "length_hint": "3000-5000字",
        "key_modules": ["HOOK", "EXPLAIN", "MODEL", "COUNTER"]
    }
    xiaohongshu_hints = {
        "focus": "情绪冲击 / 场景代入 / 高频刺激",
        "tone": "视觉化 / 情绪化 / 可操作",
        "style": "更像情绪化信息产品",
        "length_hint": "800-1200字",
        "key_modules": ["HOOK", "CASE", "ACTION", "BOUNDARY"]
    }
    both_hints = {
        "focus": "双平台兼顾",
        "tone": "深度 + 情绪兼顾",
        "style": "逻辑与共鸣并重",
        "length_hint": "公众号3000-5000字 / 小红书800-1200字",
        "key_modules": ["HOOK", "CASE", "EXPLAIN", "MODEL", "ACTION", "BOUNDARY"]
    }

    if platform == "wechat":
        return wechat_hints
    elif platform == "xiaohongshu":
        return xiaohongshu_hints
    else:
        return both_hints


def _get_dimension_hints(dimension: str) -> Dict:
    """返回 dimension 的结构推荐"""
    dimension_config = _get_config(["dimension_difficulty"], {})
    difficulty = dimension_config.get(dimension, 1.0)

    hints = {
        "reversal": {
            "description": "逆向拆解 - 推翻大众常识",
            "difficulty": 1.2,
            "structure_hint": "冲突推进优先，先建立共识再打破",
            "module_hint": "COUNTER + EVIDENCE 组合强化反直觉感"
        },
        "micro_scene": {
            "description": "微观切片 - 具体场景切入",
            "difficulty": 1.0,
            "structure_hint": "故事驱动优先，具体微观场景建立代入感",
            "module_hint": "CASE 必有，通过微观场景建立共鸣"
        },
        "systemic_flaw": {
            "description": "系统归因 - 深层结构分析",
            "difficulty": 1.2,
            "structure_hint": "信息重构型优先，分类归纳建立框架感",
            "module_hint": "MODEL + EXPLAIN 组合强化认知密度"
        },
        "bridge": {
            "description": "认知脚手架 - 帮助理解复杂事物",
            "difficulty": 0.8,
            "structure_hint": "问题拆解型优先，步骤化降低理解成本",
            "module_hint": "ACTION 必有，步骤化让读者知道怎么做"
        }
    }
    return hints.get(dimension, hints.get("micro_scene", {}))


# ============ T-3: 作者性数据加载 ============

def _load_authorial_identity() -> Dict:
    """从数字分身加载 thinking_pattern/dimension_weights/style_keywords"""
    # 复用 cognitive_crack 的数字分身数据
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from cognitive_crack import learn_thinking_pattern, digital_twin_filter
        # learn_thinking_pattern 返回 {"thinking_pattern": {...}, ...}
        pattern_result = learn_thinking_pattern(50)
        twin_result = digital_twin_filter([], pattern_result.get("thinking_pattern", ""))

        thinking_pattern = pattern_result.get("thinking_pattern", {})
        dimension_weights = pattern_result.get("dimension_weights", {})
        style_keywords = pattern_result.get("style_keywords", [])
        audience = twin_result.get("audience", "")

        return {
            "thinking_pattern": thinking_pattern,
            "dimension_weights": dimension_weights,
            "style_keywords": style_keywords,
            "audience": audience
        }
    except Exception as e:
        print(f"[Warning] 加载数字分身失败: {e}，使用默认配置", file=sys.stderr)
        return {
            "thinking_pattern": {},
            "dimension_weights": {},
            "style_keywords": [],
            "audience": ""
        }


# ============ T-4: Layer 0 认知对齐 ============

def generate_alignment_questions(topic: str, platform: str = "both") -> List[Dict]:
    """生成七类追问列表"""
    config = _get_config(["alignment_questions", platform], {})
    emphasis_list = config.get("emphasis", [
        "方向追问", "立场追问", "案例追问", "情绪追问",
        "反直觉追问", "用户画像追问", "边界追问"
    ])

    questions = [
        {
            "类型": "方向追问",
            "内容": "你更想讲：机会、焦虑、趋势、方法还是观点？",
            "可选方向": ["机会", "焦虑", "趋势", "方法", "观点"]
        },
        {
            "类型": "立场追问",
            "内容": "你真正不同意大众的什么观点？",
            "可选方向": None
        },
        {
            "类型": "情绪追问",
            "内容": "你希望读者看完后获得什么情绪？",
            "可选方向": ["共鸣", "清晰", "紧迫", "信心", "释然"]
        },
        {
            "类型": "案例追问",
            "内容": "有没有一个真实案例，让你开始相信这个观点？",
            "可选方向": None
        },
        {
            "类型": "反直觉追问",
            "内容": "这个领域有没有一个'看起来对，其实错'的地方？",
            "可选方向": None
        },
        {
            "类型": "用户画像追问",
            "内容": "你真正想写给谁？",
            "可选方向": ["新手", "从业者", "管理者", "创业者", "普通读者"]
        },
        {
            "类型": "边界追问",
            "内容": "你的观点在哪些情况下不成立？",
            "可选方向": None
        }
    ]

    # 根据平台优先级调整
    priority_map = {
        "wechat": ["立场追问", "反直觉追问", "边界追问", "方向追问", "情绪追问", "用户画像追问", "案例追问"],
        "xiaohongshu": ["案例追问", "情绪追问", "用户画像追问", "方向追问", "立场追问", "边界追问", "反直觉追问"],
        "both": emphasis_list
    }
    priority = priority_map.get(platform, emphasis_list)
    priority_map = {q["类型"]: i for i, q in enumerate(priority) for q in questions}
    questions.sort(key=lambda q: priority_map.get(q["类型"], 99))

    return questions


def parse_user_alignment_response(questions: List[Dict], user_input: str) -> Dict:
    """解析用户对七类追问的回答"""
    # 支持：直接回答 / 选项编号(1-7) / skip(跳过全部)
    result = {
        "方向": "",
        "立场": "",
        "情绪": "",
        "案例": "",
        "读者画像": "",
        "边界": ""
    }

    user_lower = user_input.lower().strip()

    # 跳过全部
    if user_lower in ["skip", "跳过", "s"]:
        return result

    # 选项编号解析
    option_pattern = r"^(\d+)[\s,，]*(.*)$"
    match = re.match(option_pattern, user_input.strip())
    if match:
        idx = int(match.group(1)) - 1
        rest = match.group(2).strip()
        if 0 <= idx < len(questions):
            q = questions[idx]
            q_type = q["类型"]
            if q_type == "方向追问" and rest:
                result["方向"] = rest
            elif q_type == "立场追问" and rest:
                result["立场"] = rest
            elif q_type == "情绪追问" and rest:
                result["情绪"] = rest
            elif q_type == "案例追问" and rest:
                result["案例"] = rest
            elif q_type == "用户画像追问" and rest:
                result["读者画像"] = rest
            elif q_type == "边界追问" and rest:
                result["边界"] = rest
            return result

    # 直接回答：按内容猜测类型
    if any(kw in user_lower for kw in ["机会", "焦虑", "趋势", "方法", "观点"]):
        result["方向"] = user_input
    elif any(kw in user_lower for kw in ["不同意", "反对", "错", "不对"]):
        result["立场"] = user_input
    elif any(kw in user_lower for kw in ["共鸣", "清晰", "紧迫", "信心", "读者"]):
        result["情绪"] = user_input
    elif any(kw in user_lower for kw in ["案例", "有个", "曾经", "朋友"]):
        result["案例"] = user_input
    else:
        # 默认作为立场处理
        result["立场"] = user_input

    return result


def cognitive_alignment_layer0(topic: str, platform: str = "both", user_input: str = "") -> Dict:
    """
    Layer 0 完整流程
    - 生成七类追问
    - 解析用户输入
    - 收敛输出
    """
    questions = generate_alignment_questions(topic, platform)

    if not user_input:
        # 返回问题列表供 CLI 显示
        return {"questions": questions, "status": "awaiting_response"}

    parsed = parse_user_alignment_response(questions, user_input)
    return {
        "questions": questions,
        "parsed": parsed,
        "status": "converged"
    }


# ============ T-7: Layer 1 内容意图识别 ============

def recognize_content_goal(topic: str, alignment_result: Dict) -> Dict:
    """识别8类内容目标（规则版 Phase 4.7）"""
    return recognize_content_goal_rule(topic, alignment_result)


def recognize_user_motivation(topic: str, alignment_result: Dict) -> Dict:
    """识别用户阅读动机（规则版 Phase 4.7）"""
    return recognize_user_motivation_rule(topic, alignment_result)


# ============ T-8: Phase 4.7 Layer 2 并行化 ============

def _parallel_layer2(topic: str) -> Dict:
    """并行执行 Layer 2 的 3个 LLM 调用（Phase 4.7）"""
    with ThreadPoolExecutor(max_workers=3) as executor:
        f1 = executor.submit(extract_core_problem, topic)
        f2 = executor.submit(extract_cognitive_tension, topic)
        f3 = executor.submit(infer_potential_directions, topic)
        core_problem = f1.result()
        cognitive_tension = f2.result()
        potential_directions = f3.result()
    return {
        "core_problem": core_problem,
        "cognitive_tension": cognitive_tension,
        "potential_directions": potential_directions,
    }


# ============ T-9~T-12: Layer 2 选题解析 ============

def classify_topic_type(topic: str) -> Dict:
    """识别5类选题类型"""
    prompt = f"""分析命题类型。

命题：{topic}

五类选题类型：
1. 趋势型：关注新事物/新变化
2. 方法型：提供解决方案/步骤
3. 观点型：表达立场/看法
4. 情绪型：建立共鸣/情感连接
5. 行业型：分析某个领域/行业

返回 JSON：
{{"类型": "类型名", "置信度": 0.0-1.0}}"""

    raw = _call_llm_raw(prompt)
    if not raw:
        return {"类型": "观点型", "置信度": 0.5}
    parsed = _parse_llm_json(raw)
    return parsed if parsed else {"类型": "观点型", "置信度": 0.5}


def extract_core_problem(topic: str) -> Dict:
    """提取核心问题链"""
    prompt = f"""从命题中提取核心问题链。

命题：{topic}

示例：AI让内容生产更容易 → 内容同质化严重 → 普通人如何建立优势？

返回 JSON：
{{"核心问题": "一句话核心问题", "问题链": ["问题1", "问题2", "问题3"]}}"""

    raw = _call_llm_raw(prompt)
    if not raw:
        return {"核心问题": topic, "问题链": [topic]}
    parsed = _parse_llm_json(raw)
    if not parsed:
        return {"核心问题": topic, "问题链": [topic]}
    return parsed


def extract_cognitive_tension(topic: str) -> Dict:
    """提取认知张力：大众以为 vs 现实是"""
    prompt = f"""分析命题的认知张力（大众以为 vs 现实是）。

命题：{topic}

返回 JSON：
{{"认知张力": {{"大众以为": "多数人的错误认知", "现实是": "实际情况"}}}}"""

    raw = _call_llm_raw(prompt)
    if not raw:
        return {"认知张力": {"大众以为": "应该跟随大众", "现实是": "独立思考才能突破"}}
    parsed = _parse_llm_json(raw)
    if not parsed:
        return {"认知张力": {"大众以为": "应该跟随大众", "现实是": "独立思考才能突破"}}
    return parsed


def infer_potential_directions(topic: str) -> List[Dict]:
    """推演2-4个潜在方向供用户选择"""
    prompt = f"""为命题推演潜在方向。

命题：{topic}

返回 JSON 数组：
[
  {{"方向": "方向名", "描述": "方向描述"}},
  ...
]

推演2-4个差异化方向（机会方向/焦虑方向/反直觉方向等）"""

    raw = _call_llm_raw(prompt)
    if not raw:
        return [{"方向": "机会方向", "描述": "从正面角度切入"}, {"方向": "焦虑方向", "描述": "从问题角度切入"}]
    parsed = _parse_llm_json(raw)
    if not parsed:
        return [{"方向": "机会方向", "描述": "从正面角度切入"}, {"方向": "焦虑方向", "描述": "从问题角度切入"}]
    if isinstance(parsed, list):
        return parsed
    return [parsed]


# ============ T-13~T-14: Layer 3 结构决策 ============

def select_main_structure(topic_type: str, alignment_result: Dict) -> Dict:
    """根据选题类型和用户立场推荐主结构"""
    structures = _get_config(["structures"], {})
    content_goals = _get_config(["content_goals"], {})

    stance = alignment_result.get("parsed", {}).get("立场", "")
    direction = alignment_result.get("parsed", {}).get("方向", "")

    # 结构推荐映射
    structure_map = {
        "观点型": "认知升级型",
        "趋势型": "认知升级型",
        "方法型": "问题拆解型",
        "行业型": "问题拆解型",
        "情绪型": "故事驱动型"
    }

    recommended = structure_map.get(topic_type, "认知升级型")
    structure_info = structures.get(recommended, {})

    return {
        "主结构": recommended,
        "description": structure_info.get("description", ""),
        "progression": structure_info.get("progression", ["递进推进"]),
        "module_requirements": structure_info.get("module_requirements", {})
    }


def decide_progression_method(structure: str, topic: str, alignment_result: Optional[Dict] = None) -> Dict:
    """决定6种推进方式中的一种或组合"""
    prompt = f"""根据主结构选择推进方式。

主结构：{structure}
命题：{topic}

六种推进方式：
1. 递进推进：层层深入
2. 拆解推进：模块化拆解
3. 情绪推进：情绪曲线驱动
4. 对比推进：强反差
5. 冲突推进：认知碰撞
6. 案例推进：从案例抽象

返回 JSON：
{{"推进方式": "方式名", "描述": "方式说明"}}"""

    raw = _call_llm_raw(prompt)
    if not raw:
        return {"推进方式": "冲突推进", "描述": "制造认知落差"}
    parsed = _parse_llm_json(raw)
    if not parsed:
        return {"推进方式": "冲突推进", "描述": "制造认知落差"}
    return parsed


# ============ T-15~T-16: Layer 4 认知模块编排 ============

COGNITIVE_MODULES = {
    "HOOK": {"name": "制造停留", "description": "用钩子让读者停下来，产生好奇或共鸣", "requirement": "必须有", "length_hint": "20字以内一句话"},
    "CASE": {"name": "建立真实感", "description": "具体场景或人物案例，建立代入感", "requirement": "至少有1个", "length_hint": "2-3句具体描述"},
    "EXPLAIN": {"name": "建立理解", "description": "对案例或观点进行解读", "requirement": "每篇必备", "length_hint": "2-3句分析"},
    "MODEL": {"name": "提升认知密度", "description": "提炼可复用的认知模型或框架", "requirement": "至少有1个认知模型", "length_hint": "3-5句，含模型名称和框架"},
    "COUNTER": {"name": "制造记忆点", "description": "反直觉观点，建立记忆点", "requirement": "建议有", "length_hint": "2-3句反直觉内容"},
    "EVIDENCE": {"name": "增强可信度", "description": "数据、案例、引用支撑观点", "requirement": "支撑必须有", "length_hint": "数据或案例描述"},
    "ACTION": {"name": "提供落地", "description": "给出具体行动步骤", "requirement": "实操类必须有", "length_hint": "步骤化描述"},
    "BOUNDARY": {"name": "提升高级感", "description": "说明观点的适用边界", "requirement": "建议有", "length_hint": "1-2句边界条件"}
}


def generate_cognitive_module_flow(topic: str, structure: str, authorial_identity: Dict, platform: str) -> List[Dict]:
    """生成认知模块流"""
    prompt = f"""根据命题和结构生成认知模块流。

命题：{topic}
主结构：{structure}
平台：{platform}
作者性：{json.dumps(authorial_identity, ensure_ascii=False)}

八大认知模块：
- HOOK：制造停留（必须有）
- CASE：建立真实感（场景/人物案例）
- EXPLAIN：建立理解（分析解读）
- MODEL：提升认知密度（认知模型/框架）
- COUNTER：制造记忆点（反直觉观点）
- EVIDENCE：增强可信度（数据/案例支撑）
- ACTION：提供落地（步骤化行动）
- BOUNDARY：提升高级感（适用边界）

规则：
- HOOK 必有
- 实操类必须有 ACTION
- 至少1个 MODEL
- COUNTER/BOUNDARY 建议有

返回 JSON 数组：
[
  {{"模块": "HOOK", "内容摘要": "一句话描述", "功能": "制造停留"}},
  ...
]"""

    raw = _call_llm_raw(prompt)
    if not raw:
        return [{"模块": "HOOK", "内容摘要": "开场钩子", "功能": "制造停留"}, {"模块": "EXPLAIN", "内容摘要": "观点解读", "功能": "建立理解"}]
    parsed = _parse_llm_json(raw)
    if not parsed:
        return [{"模块": "HOOK", "内容摘要": "开场钩子", "功能": "制造停留"}, {"模块": "EXPLAIN", "内容摘要": "观点解读", "功能": "建立理解"}]
    if isinstance(parsed, list):
        return parsed
    return [parsed]


# ============ T-17: Layer 7 作者性注入 ============

def inject_authorial_identity(thinking_pattern: Dict, dimension_weights: Dict, style_keywords: List[str]) -> Dict:
    """整合数字分身数据为 Layer 7 注入格式"""
    return {
        "认知倾向": thinking_pattern.get("倾向", "分析优先"),
        "表达气质": thinking_pattern.get("气质", "理性深刻"),
        "价值倾向": dimension_weights.get("primary", "独立思考"),
        "长期母题": ", ".join(style_keywords[:3]) if style_keywords else "认知升级"
    }


# ============ T-18: Layer 8 内容势能设计 ============

def generate_narrative_energy(topic: str, module_flow: List[Dict], platform: str) -> Dict:
    """生成势能曲线"""
    prompt = f"""为命题设计内容势能曲线。

命题：{topic}
平台：{platform}
模块流：{json.dumps(module_flow, ensure_ascii=False)}

势能设计维度：
1. 张力变化：何时抛冲突/给答案/反转
2. 情绪曲线：预设每段情绪走向（好奇→震惊→共鸣→清晰→行动）
3. 认知落差：先A后B的设计
4. 节奏变化：抽象→案例→模型→情绪→观点 循环
5. 认知奖励点：每隔一段的新观点/新模型/新视角

返回 JSON：
{{
  "张力变化": ["节点1描述", "节点2描述", ...],
  "情绪曲线": ["情绪1", "情绪2", ...],
  "认知落差设计": "先A后B的设计描述",
  "节奏变化": "节奏设计描述",
  "认知奖励点": ["奖励点1", "奖励点2", ...]
}}"""

    raw = _call_llm_raw(prompt)
    if not raw:
        return {"张力变化": ["开场冲突"], "情绪曲线": ["好奇"], "认知落差设计": "先破后立", "节奏变化": "递进", "认知奖励点": ["新视角"]}
    parsed = _parse_llm_json(raw)
    if not parsed:
        return {"张力变化": ["开场冲突"], "情绪曲线": ["好奇"], "认知落差设计": "先破后立", "节奏变化": "递进", "认知奖励点": ["新视角"]}
    return parsed


# ============ T-19: CCOS 主函数 ============

def cognitive_outline_workflow(
    topic: str,
    dimension: str,
    platform: str,
    alignment_result: Optional[Dict] = None,
    shared_layer2_result: Optional[Dict] = None,
) -> Dict:
    """
    Phase 4.5 完整流程：14项动态认知大纲生成
    顺序调用 T-7/T-8/T-9/T-10/T-11/T-12/T-13/T-14/T-16/T-17/T-18

    Phase 4.7 优化：
    - shared_layer2_result: 双平台共用 Layer 2 结果，传入则复用
    - Layer 2 LLM 调用并行化（通过 shared_layer2_result 或 _parallel_layer2）
    """
    if alignment_result is None:
        alignment_result = {}
    if not alignment_result.get("parsed"):
        alignment_result["parsed"] = {}

    # Layer 1: 内容意图识别（规则版，无 LLM）
    content_goal = recognize_content_goal(topic, alignment_result)
    user_motivation = recognize_user_motivation(topic, alignment_result)

    # Layer 2: 选题解析（规则版 + LLM，并行化）
    topic_type_info = classify_topic_type(topic)
    topic_type = topic_type_info.get("类型", "观点型")
    if shared_layer2_result:
        core_problem = shared_layer2_result["core_problem"]
        cognitive_tension = shared_layer2_result["cognitive_tension"]
        potential_directions = shared_layer2_result["potential_directions"]
    else:
        layer2 = _parallel_layer2(topic)
        core_problem = layer2["core_problem"]
        cognitive_tension = layer2["cognitive_tension"]
        potential_directions = layer2["potential_directions"]

    # Layer 3: 结构决策（规则版，无 LLM）
    structure_info = select_main_structure(topic_type, alignment_result)
    main_structure = structure_info.get("主结构", "认知升级型")
    progression_info = decide_progression_method(main_structure, topic, alignment_result)
    progression_method = progression_info.get("推进方式", "冲突推进")

    # Layer 4: 认知模块编排（LLM，平台相关）
    authorial = _load_authorial_identity()
    authorial_identity = inject_authorial_identity(
        authorial.get("thinking_pattern", {}),
        authorial.get("dimension_weights", {}),
        authorial.get("style_keywords", [])
    )
    module_flow = generate_cognitive_module_flow(topic, main_structure, authorial_identity, platform)

    # Layer 8: 内容势能设计（LLM，平台相关）
    narrative_energy = generate_narrative_energy(topic, module_flow, platform)

    # 收敛立场
    parsed = alignment_result.get("parsed", {})
    content_stance = parsed.get("立场", core_problem.get("核心问题", topic))

    # 案例插入点
    case_insert_points = [m["内容摘要"] for m in module_flow if m["模块"] == "CASE"]

    # 信息密度要求（强制规则）
    info_density = (
        "每段必须有信息增量；禁止同义反复/空洞总结/正确废话/情绪堆砌；"
        "强制：真实细节/微观行为/时间感/决策过程/心理变化"
    )

    # Anti-AI要求（强制规则）
    anti_ai = (
        "禁止：模板感/套话/平均化表达/AI式升华/空洞口号；"
        "强制：观点化表达/人类思考感（犹豫/推演/局部经验/不确定性）"
    )

    # 语言风格
    platform_hints = _get_platform_hints(platform)
    language_style = f"{platform_hints['tone']} / {platform_hints['style']} / {platform_hints['focus']}"

    # 最终动态认知大纲（综合输出）
    final_outline = _generate_final_outline_text(topic, main_structure, progression_method, module_flow, narrative_energy, platform)

    # 14项输出
    result = {
        "内容目标": content_goal.get("内容目标", "认知升级"),
        "用户动机": user_motivation.get("用户动机", "好奇"),
        "核心认知冲突": cognitive_tension.get("认知张力", {}).get("现实是", topic),
        "内容立场": content_stance,
        "作者性设定": authorial_identity,
        "主结构": main_structure,
        "推进方式": progression_method,
        "认知模块流": module_flow,
        "势能曲线": narrative_energy,
        "案例插入点": case_insert_points,
        "信息密度要求": info_density,
        "语言风格": language_style,
        "Anti-AI要求": anti_ai,
        "最终动态认知大纲": final_outline
    }

    return result


def _generate_final_outline_text(topic: str, structure: str, progression: str, module_flow: List[Dict], narrative_energy: Dict, platform: str) -> str:
    """生成最终动态认知大纲文本"""
    tension_points = narrative_energy.get("张力变化", [])
    energy_curve = " → ".join(narrative_energy.get("情绪曲线", []))

    modules_desc = " / ".join([f"{m['模块']}({m['功能']})" for m in module_flow])

    text = f"""【{structure}】{topic}
通过【{progression}】推进，
模块流：{modules_desc}
张力节奏：{energy_curve}
核心张力点：{' / '.join(tension_points[:3]) if tension_points else '待设置'}"""

    return text


# ============ T-20: 双平台分别生成 ============

def generate_dual_platform_outline(topic: str, dimension: str) -> Dict:
    """
    同时生成公众号+小红书两套14项大纲（Phase 4.7 优化）
    - Layer 2 共用一次并行计算
    - 双平台只各自调用 Layer 4 + Layer 8（共 6次 LLM）
    """
    # Layer 2 共享结果（3个 LLM 并行算1次）
    shared_layer2 = _parallel_layer2(topic)

    # 公众号版本
    wechat_outline = cognitive_outline_workflow(
        topic, dimension, "wechat", shared_layer2_result=shared_layer2
    )
    # 小红书版本
    xiaohongshu_outline = cognitive_outline_workflow(
        topic, dimension, "xiaohongshu", shared_layer2_result=shared_layer2
    )

    return {
        "wechat_cognitive_outline": wechat_outline,
        "xiaohongshu_cognitive_outline": xiaohongshu_outline
    }


# ============ CLI 入口 ============

def main():
    if len(sys.argv) < 2:
        print("用法: python cognitive_outline.py <outline|dual|alignment|legacy> [args...]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "outline":
        # python cognitive_outline.py outline "<标题>" "<dimension>" "<平台>"
        if len(sys.argv) < 5:
            print("用法: outline <标题> <dimension> <平台>", file=sys.stderr)
            sys.exit(1)
        topic = sys.argv[2]
        dimension = sys.argv[3]
        platform = sys.argv[4]
        result = cognitive_outline_workflow(topic, dimension, platform)
        _safe_print(result)

    elif cmd == "dual":
        # python cognitive_outline.py dual "<标题>" "<dimension>"
        if len(sys.argv) < 4:
            print("用法: dual <标题> <dimension>", file=sys.stderr)
            sys.exit(1)
        topic = sys.argv[2]
        dimension = sys.argv[3]
        result = generate_dual_platform_outline(topic, dimension)
        _safe_print(result)

    elif cmd == "alignment":
        # python cognitive_outline.py alignment "<标题>" "<平台>"
        if len(sys.argv) < 4:
            print("用法: alignment <标题> <平台>", file=sys.stderr)
            sys.exit(1)
        topic = sys.argv[2]
        platform = sys.argv[3]
        result = cognitive_alignment_layer0(topic, platform)
        _safe_print(result)

    elif cmd == "legacy":
        # 调试用，输出旧版格式
        if len(sys.argv) < 3:
            print("用法: legacy <标题>", file=sys.stderr)
            sys.exit(1)
        topic = sys.argv[2]
        print(f"[Legacy] {topic} - generate_outlines 已废弃，请使用 outline 或 dual", file=sys.stderr)

    else:
        print(f"未知命令: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()