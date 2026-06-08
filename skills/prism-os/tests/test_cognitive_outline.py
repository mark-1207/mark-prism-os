#!/usr/bin/env python3
"""
cognitive_outline.py (CCOS v2.0) 单元测试
覆盖 Layer 0-8 / 14项输出 / 双平台 / CLI 入口

用法: python -m pytest skills/prism-os/tests/test_cognitive_outline.py -v
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

# ============ Mock LLM 响应 ============

def _mock_llm_raw(prompt):
    """统一 mock：返回合理的结构化 JSON"""
    prompt_lower = prompt.lower()

    if "内容目标" in prompt:
        return '{"内容目标": "认知升级", "置信度": 0.85}'
    if "用户动机" in prompt:
        return '{"用户动机": "焦虑", "二级动机": ["好奇", "学习"]}'
    if "命题类型" in prompt:
        return '{"类型": "观点型", "置信度": 0.8}'
    if "核心问题链" in prompt:
        return '{"核心问题": "AI让内容生产更容易", "问题链": ["AI让内容生产更容易", "内容同质化", "普通人如何建立优势"]}'
    if "认知张力" in prompt:
        return '{"认知张力": {"大众以为": "应该跟随大众", "现实是": "独立思考才能突破"}}'
    if "潜在方向" in prompt:
        return '[{"方向": "机会方向", "描述": "从正面角度切入"}, {"方向": "焦虑方向", "描述": "从问题角度切入"}]'
    if "推进方式" in prompt:
        return '{"推进方式": "冲突推进", "描述": "制造认知落差"}'
    if "认知模块流" in prompt:
        return json.dumps([
            {"模块": "HOOK", "内容摘要": "开场钩子", "功能": "制造停留"},
            {"模块": "CASE", "内容摘要": "一个创业者的真实故事", "功能": "建立代入感"},
            {"模块": "EXPLAIN", "内容摘要": "为什么会出现这种情况", "功能": "建立理解"},
            {"模块": "MODEL", "内容摘要": "认知升级模型", "功能": "提升认知密度"}
        ])
    if "势能曲线" in prompt:
        return json.dumps({
            "张力变化": ["开场冲突", "揭示真相", "认知升级", "行动号召"],
            "情绪曲线": ["好奇", "震惊", "共鸣", "清晰", "行动"],
            "认知落差设计": "先A后B，先建立共识再打破",
            "节奏变化": "抽象→案例→模型→情绪→观点",
            "认知奖励点": ["新视角", "新模型", "新框架"]
        })
    # 默认
    return '{"error": "unhandled mock"}'


def _mock_llm_raw_empty(prompt):
    """空响应 mock"""
    return None


# ============ 被测模块导入 ============

from cognitive_outline import (
    _call_llm_raw,
    _parse_llm_json,
    _get_platform_hints,
    _get_dimension_hints,
    generate_alignment_questions,
    parse_user_alignment_response,
    cognitive_alignment_layer0,
    recognize_content_goal,
    recognize_user_motivation,
    classify_topic_type,
    extract_core_problem,
    extract_cognitive_tension,
    infer_potential_directions,
    select_main_structure,
    decide_progression_method,
    generate_cognitive_module_flow,
    inject_authorial_identity,
    generate_narrative_energy,
    cognitive_outline_workflow,
    generate_dual_platform_outline,
    COGNITIVE_MODULES,
)


# ============ T-1 基础辅助函数 ============

class TestParseJson(unittest.TestCase):
    def test_code_block_json(self):
        text = '```json\n{"key": "value"}\n```'
        result = _parse_llm_json(text)
        self.assertEqual(result, {"key": "value"})

    def test_plain_json(self):
        text = '{"key": "value"}'
        result = _parse_llm_json(text)
        self.assertEqual(result, {"key": "value"})

    def test_invalid_json(self):
        text = "not json at all"
        result = _parse_llm_json(text)
        self.assertIsNone(result)

    def test_none_input(self):
        result = _parse_llm_json(None)
        self.assertIsNone(result)


class TestPlatformHints(unittest.TestCase):
    def test_wechat_hints(self):
        hints = _get_platform_hints("wechat")
        self.assertEqual(hints["focus"], "逻辑推进 / 认知升级 / 信息密度")
        self.assertIn("HOOK", hints["key_modules"])

    def test_xiaohongshu_hints(self):
        hints = _get_platform_hints("xiaohongshu")
        self.assertEqual(hints["focus"], "情绪冲击 / 场景代入 / 高频刺激")
        self.assertIn("CASE", hints["key_modules"])

    def test_both_hints(self):
        hints = _get_platform_hints("both")
        self.assertEqual(hints["focus"], "双平台兼顾")


class TestDimensionHints(unittest.TestCase):
    def test_reversal_hints(self):
        hints = _get_dimension_hints("reversal")
        self.assertEqual(hints["difficulty"], 1.2)
        self.assertIn("冲突推进", hints["structure_hint"])

    def test_micro_scene_hints(self):
        hints = _get_dimension_hints("micro_scene")
        self.assertEqual(hints["difficulty"], 1.0)

    def test_unknown_dimension(self):
        hints = _get_dimension_hints("unknown_dim")
        self.assertIn("description", hints)


# ============ T-4~T-6 Layer 0 认知对齐 ============

class TestAlignmentQuestions(unittest.TestCase):
    def test_wechat_seven_questions(self):
        questions = generate_alignment_questions("AI时代内容创作", "wechat")
        self.assertEqual(len(questions), 7)

    def test_xiaohongshu_seven_questions(self):
        questions = generate_alignment_questions("AI时代内容创作", "xiaohongshu")
        self.assertEqual(len(questions), 7)

    def test_both_seven_questions(self):
        questions = generate_alignment_questions("AI时代内容创作", "both")
        self.assertEqual(len(questions), 7)

    def test_all_question_types_covered(self):
        questions = generate_alignment_questions("AI时代内容创作", "both")
        types = [q["类型"] for q in questions]
        expected = ["方向追问", "立场追问", "情绪追问", "案例追问", "反直觉追问", "用户画像追问", "边界追问"]
        for exp in expected:
            self.assertIn(exp, types)

    def test_questions_have_required_fields(self):
        questions = generate_alignment_questions("AI时代内容创作", "both")
        for q in questions:
            self.assertIn("类型", q)
            self.assertIn("内容", q)
            self.assertIn("可选方向", q)


class TestParseAlignmentResponse(unittest.TestCase):
    def test_skip(self):
        result = parse_user_alignment_response([], "skip")
        self.assertEqual(result["方向"], "")
        self.assertEqual(result["立场"], "")

    def test_skip_chinese(self):
        result = parse_user_alignment_response([], "跳过")
        self.assertEqual(result["立场"], "")

    def test_option_number_with_content(self):
        questions = [
            {"类型": "方向追问", "内容": "...", "可选方向": ["机会", "焦虑"]},
            {"类型": "立场追问", "内容": "...", "可选方向": None},
        ]
        result = parse_user_alignment_response(questions, "1 机会方向")
        self.assertEqual(result["方向"], "机会方向")

    def test_direct_answer_立场(self):
        questions = generate_alignment_questions("test", "both")
        result = parse_user_alignment_response(questions, "我不同意大众认为AI会取代人类")
        self.assertNotEqual(result["立场"], "")


class TestCognitiveAlignmentLayer0(unittest.TestCase):
    def test_awaiting_response_when_no_input(self):
        result = cognitive_alignment_layer0("AI时代创作", "wechat", "")
        self.assertEqual(result["status"], "awaiting_response")
        self.assertIn("questions", result)
        self.assertEqual(len(result["questions"]), 7)

    def test_converged_when_input_provided(self):
        result = cognitive_alignment_layer0("AI时代创作", "wechat", "skip")
        self.assertEqual(result["status"], "converged")


# ============ T-7~T-12 Layer 1-2 ============

class TestRecognizeContentGoal(unittest.TestCase):
    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    def test_recognizes_cognitive_upgrade(self):
        result = recognize_content_goal("AI时代内容创作", {})
        self.assertEqual(result["内容目标"], "认知升级")
        self.assertGreater(result["置信度"], 0)

    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw_empty)
    def test_fallback_on_llm_failure(self):
        result = recognize_content_goal("AI时代内容创作", {})
        self.assertEqual(result["内容目标"], "认知升级")
        self.assertEqual(result["置信度"], 0.5)


class TestClassifyTopicType(unittest.TestCase):
    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    def test_classifies_opinion_type(self):
        result = classify_topic_type("AI让人类变得更懒")
        self.assertEqual(result["类型"], "观点型")

    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw_empty)
    def test_fallback_type(self):
        result = classify_topic_type("test")
        self.assertEqual(result["类型"], "观点型")


class TestExtractCoreProblem(unittest.TestCase):
    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    def test_extracts_problem_chain(self):
        result = extract_core_problem("AI让内容创作更容易")
        self.assertIn("核心问题", result)
        self.assertIn("问题链", result)
        self.assertIsInstance(result["问题链"], list)


class TestExtractCognitiveTension(unittest.TestCase):
    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    def test_extracts_tension(self):
        result = extract_cognitive_tension("AI让内容创作更容易")
        tension = result.get("认知张力", {})
        self.assertIn("大众以为", tension)
        self.assertIn("现实是", tension)

    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw_empty)
    def test_fallback_tension(self):
        result = extract_cognitive_tension("test")
        tension = result.get("认知张力", {})
        self.assertNotEqual(tension.get("大众以为", ""), "")


class TestInferPotentialDirections(unittest.TestCase):
    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    def test_returns_direction_list(self):
        result = infer_potential_directions("AI时代内容创作")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIn("方向", result[0])

    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw_empty)
    def test_fallback_directions(self):
        result = infer_potential_directions("test")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)


# ============ T-13~T-14 Layer 3 结构决策 ============

class TestSelectMainStructure(unittest.TestCase):
    def test_opinion_type_selects_cognitive_upgrade(self):
        result = select_main_structure("观点型", {})
        self.assertEqual(result["主结构"], "认知升级型")

    def test_method_type_selects_problem_solving(self):
        result = select_main_structure("方法型", {})
        self.assertEqual(result["主结构"], "问题拆解型")

    def test_emotion_type_selects_story_driven(self):
        result = select_main_structure("情绪型", {})
        self.assertEqual(result["主结构"], "故事驱动型")


class TestDecideProgressionMethod(unittest.TestCase):
    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    def test_decides_progression(self):
        result = decide_progression_method("认知升级型", "AI时代内容创作")
        self.assertIn("推进方式", result)

    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw_empty)
    def test_fallback_progression(self):
        result = decide_progression_method("认知升级型", "test")
        self.assertEqual(result["推进方式"], "冲突推进")


# ============ T-15~T-16 Layer 4 认知模块编排 ============

class TestCognitiveModules(unittest.TestCase):
    def test_all_eight_modules_defined(self):
        expected = ["HOOK", "CASE", "EXPLAIN", "MODEL", "COUNTER", "EVIDENCE", "ACTION", "BOUNDARY"]
        for mod in expected:
            self.assertIn(mod, COGNITIVE_MODULES)
            self.assertIn("name", COGNITIVE_MODULES[mod])
            self.assertIn("requirement", COGNITIVE_MODULES[mod])

    def test_hook_must_have(self):
        self.assertEqual(COGNITIVE_MODULES["HOOK"]["requirement"], "必须有")

    def test_action_required_for_practical(self):
        self.assertEqual(COGNITIVE_MODULES["ACTION"]["requirement"], "实操类必须有")


class TestGenerateModuleFlow(unittest.TestCase):
    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    def test_generates_module_list(self):
        result = generate_cognitive_module_flow("AI时代内容创作", "认知升级型", {}, "wechat")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIn("模块", result[0])

    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw_empty)
    def test_fallback_module_flow(self):
        result = generate_cognitive_module_flow("test", "认知升级型", {}, "wechat")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)


# ============ T-17 Layer 7 作者性注入 ============

class TestInjectAuthorialIdentity(unittest.TestCase):
    def test_injects_all_fields(self):
        result = inject_authorial_identity(
            {"倾向": "分析优先", "气质": "理性深刻"},
            {"primary": "独立思考"},
            ["认知升级", "独立思考"]
        )
        self.assertIn("认知倾向", result)
        self.assertIn("表达气质", result)
        self.assertIn("价值倾向", result)
        self.assertIn("长期母题", result)

    def test_longterm_theme_join(self):
        result = inject_authorial_identity({}, {}, ["A", "B", "C", "D"])
        self.assertEqual(result["长期母题"], "A, B, C")


# ============ T-18 Layer 8 势能曲线 ============

class TestGenerateNarrativeEnergy(unittest.TestCase):
    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    def test_generates_energy_structure(self):
        module_flow = [{"模块": "HOOK", "内容摘要": "test", "功能": "test"}]
        result = generate_narrative_energy("AI时代内容创作", module_flow, "wechat")
        self.assertIn("张力变化", result)
        self.assertIn("情绪曲线", result)
        self.assertIn("认知落差设计", result)

    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw_empty)
    def test_fallback_energy(self):
        module_flow = [{"模块": "HOOK", "内容摘要": "test", "功能": "test"}]
        result = generate_narrative_energy("test", module_flow, "wechat")
        self.assertIn("张力变化", result)


# ============ T-19 CCOS 主函数 14项输出 ============

class TestCognitiveOutlineWorkflow(unittest.TestCase):
    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    @patch("cognitive_outline._load_authorial_identity", lambda: {"thinking_pattern": {}, "dimension_weights": {}, "style_keywords": [], "audience": ""})
    def test_outputs_14_fields(self):
        result = cognitive_outline_workflow("AI让内容创作更容易", "reversal", "wechat")
        expected_fields = [
            "内容目标", "用户动机", "核心认知冲突", "内容立场",
            "作者性设定", "主结构", "推进方式", "认知模块流",
            "势能曲线", "案例插入点", "信息密度要求",
            "语言风格", "Anti-AI要求", "最终动态认知大纲"
        ]
        for field in expected_fields:
            self.assertIn(field, result, f"Missing field: {field}")

    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    @patch("cognitive_outline._load_authorial_identity", lambda: {"thinking_pattern": {}, "dimension_weights": {}, "style_keywords": [], "audience": ""})
    def test_no_field_empty(self):
        result = cognitive_outline_workflow("AI让内容创作更容易", "reversal", "wechat")
        for field, value in result.items():
            self.assertTrue(value, f"Field '{field}' should not be empty")

    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    @patch("cognitive_outline._load_authorial_identity", lambda: {"thinking_pattern": {}, "dimension_weights": {}, "style_keywords": [], "audience": ""})
    def test_authorial_identity_fields(self):
        result = cognitive_outline_workflow("AI让内容创作更容易", "reversal", "wechat")
        authorial = result["作者性设定"]
        self.assertIn("认知倾向", authorial)
        self.assertIn("表达气质", authorial)
        self.assertIn("价值倾向", authorial)
        self.assertIn("长期母题", authorial)

    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    @patch("cognitive_outline._load_authorial_identity", lambda: {"thinking_pattern": {}, "dimension_weights": {}, "style_keywords": [], "audience": ""})
    def test_module_flow_has_hook(self):
        result = cognitive_outline_workflow("AI让内容创作更容易", "reversal", "wechat")
        modules = [m["模块"] for m in result["认知模块流"]]
        self.assertIn("HOOK", modules, "HOOK must be in module flow")

    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    @patch("cognitive_outline._load_authorial_identity", lambda: {"thinking_pattern": {}, "dimension_weights": {}, "style_keywords": [], "audience": ""})
    def test_xiaohongshu_different_from_wechat(self):
        """小红书和公众号输出结构不同（平台差异化）"""
        wechat_result = cognitive_outline_workflow("AI让内容创作更容易", "reversal", "wechat")
        xhs_result = cognitive_outline_workflow("AI让内容创作更容易", "reversal", "xiaohongshu")
        # 语言风格字段应包含各自平台特征
        self.assertNotEqual(wechat_result["语言风格"], xhs_result["语言风格"])


# ============ T-20 双平台生成 ============

class TestDualPlatformOutline(unittest.TestCase):
    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    @patch("cognitive_outline._load_authorial_identity", lambda: {"thinking_pattern": {}, "dimension_weights": {}, "style_keywords": [], "audience": ""})
    def test_both_platforms_present(self):
        result = generate_dual_platform_outline("AI让内容创作更容易", "reversal")
        self.assertIn("wechat_cognitive_outline", result)
        self.assertIn("xiaohongshu_cognitive_outline", result)

    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    @patch("cognitive_outline._load_authorial_identity", lambda: {"thinking_pattern": {}, "dimension_weights": {}, "style_keywords": [], "audience": ""})
    def test_both_have_14_fields(self):
        result = generate_dual_platform_outline("AI让内容创作更容易", "reversal")
        for platform in ["wechat_cognitive_outline", "xiaohongshu_cognitive_outline"]:
            outline = result[platform]
            self.assertIn("内容目标", outline)
            self.assertIn("主结构", outline)
            self.assertIn("最终动态认知大纲", outline)


# ============ 信息密度 / Anti-AI 规则验证 ============

class TestInfoDensityRules(unittest.TestCase):
    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    @patch("cognitive_outline._load_authorial_identity", lambda: {"thinking_pattern": {}, "dimension_weights": {}, "style_keywords": [], "audience": ""})
    def test_info_density_rules_present(self):
        result = cognitive_outline_workflow("test", "bridge", "wechat")
        self.assertIn("信息增量", result["信息密度要求"])
        self.assertIn("禁止", result["信息密度要求"])

    @patch("cognitive_outline._call_llm_raw", _mock_llm_raw)
    @patch("cognitive_outline._load_authorial_identity", lambda: {"thinking_pattern": {}, "dimension_weights": {}, "style_keywords": [], "audience": ""})
    def test_anti_ai_rules_present(self):
        result = cognitive_outline_workflow("test", "bridge", "wechat")
        self.assertIn("禁止", result["Anti-AI要求"])
        self.assertIn("模板感", result["Anti-AI要求"])


if __name__ == "__main__":
    unittest.main(verbosity=2)