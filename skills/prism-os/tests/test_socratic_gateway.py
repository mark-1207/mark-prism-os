#!/usr/bin/env python3
"""socratic_gateway.py 单元测试 — HKR评分 + entropy阈值修复 + 联合决策"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from socratic_gateway import (
    classify_input,
    calculate_entropy,
    calculate_hkr,
    socratic_gateway,
    _rule_object_clarity,
    _rule_conflict_tension,
    _rule_fact_support,
)


# ============ Mock LLM ============

def _mock_llm_raw(prompt, temperature=0.7, **kwargs):
    """模拟 LLM 返回"""
    prompt_lower = prompt.lower()
    if "directions" in prompt_lower:
        return json.dumps({"directions": ["方向A：深入分析行业趋势", "方向B：从个人经历出发", "方向C：对比国内外差异"]})
    if "questions" in prompt_lower or "追问" in prompt_lower:
        return json.dumps({"questions": ["你想表达的核心观点是什么？", "目标读者是谁？", "希望读者有什么行动？"]})
    return json.dumps({"questions": ["默认追问1", "默认追问2"]})


# ============ T-1: calculate_hkr 规则打分 ============

class TestCalculateHKR(unittest.TestCase):
    """HKR 三维评分测试 — 规则版，无 LLM 调用"""

    def test_hkr_returns_four_keys(self):
        result = calculate_hkr("AI时代普通人如何建立优势")
        for key in ("h", "k", "r", "hkr_avg"):
            self.assertIn(key, result, f"缺少 key: {key}")

    def test_hkr_scores_in_range(self):
        result = calculate_hkr("AI时代普通人如何建立优势")
        for key in ("h", "k", "r", "hkr_avg"):
            val = result[key]
            self.assertGreaterEqual(val, 0.0, f"{key} < 0")
            self.assertLessEqual(val, 1.0, f"{key} > 1")

    def test_h_happy_high_with_emotional_words(self):
        result = calculate_hkr("这太离谱了！AI居然能写出比人更好的文章，笑死了")
        self.assertGreater(result["h"], 0.3, f"H过低: {result['h']}")

    def test_h_happy_low_with_dry_input(self):
        result = calculate_hkr("企业数字化转型路径研究")
        self.assertLess(result["h"], 0.3, f"H过高: {result['h']}")

    def test_k_knowledge_high_with_research_words(self):
        result = calculate_hkr("研究发现：AI模型训练成本每年降低47%")
        self.assertGreater(result["k"], 0.3, f"K过低: {result['k']}")

    def test_k_knowledge_low_with_emotional_input(self):
        result = calculate_hkr("上班好累啊怎么会这么累")
        self.assertLess(result["k"], 0.3, f"K过高: {result['k']}")

    def test_r_resonance_high_with_first_person(self):
        result = calculate_hkr("我经历过三次裁员，每次都让我焦虑到睡不着")
        self.assertGreater(result["r"], 0.3, f"R过低: {result['r']}")

    def test_r_resonance_low_with_abstract_input(self):
        result = calculate_hkr("量子计算加密算法演进")
        self.assertLess(result["r"], 0.3, f"R过高: {result['r']}")

    def test_hkr_avg_is_correct(self):
        result = calculate_hkr("测试")
        expected_avg = (result["h"] + result["k"] + result["r"]) / 3
        self.assertAlmostEqual(result["hkr_avg"], expected_avg, places=4)

    def test_empty_input(self):
        result = calculate_hkr("")
        self.assertEqual(result["h"], 0.0)
        self.assertEqual(result["k"], 0.0)
        self.assertEqual(result["r"], 0.0)
        self.assertEqual(result["hkr_avg"], 0.0)

    def test_very_short_input(self):
        result = calculate_hkr("AI")
        for key in ("h", "k", "r"):
            self.assertGreaterEqual(result[key], 0.0)

    def test_balanced_input_all_dimensions(self):
        """既有知识增量、又有情感共鸣、又有趣味性的综合输入"""
        result = calculate_hkr(
            "我发现了一个离谱的真相：那些天天研究AI方法论的人，其实是最容易被替代的，我自己就是这样"
        )
        # 至少两个维度应该有分
        scores = [result["h"], result["k"], result["r"]]
        non_zero = sum(1 for s in scores if s > 0.1)
        self.assertGreaterEqual(non_zero, 2, f"至少2个维度应有分: h={result['h']} k={result['k']} r={result['r']}")


# ============ T-2: entropy 阈值修复 ============

class TestEntropyThresholdFix(unittest.TestCase):
    """验证 entropy >= 1.2 不可达的 bug 已修复"""

    def test_entropy_max_possible_is_1_0(self):
        """三个子维度最大各 1.0 → entropy = 1.0×0.4 + 1.0×0.4 + 1.0×0.2 = 1.0"""
        max_obj = 1.0
        max_conflict = 1.0
        max_fact = 1.0
        max_possible = max_obj * 0.4 + max_conflict * 0.4 + max_fact * 0.2
        self.assertAlmostEqual(max_possible, 1.0, places=2)
        self.assertLess(max_possible, 1.2, "理论最大值 1.0 < 1.2，旧阈值不可达")

    @patch("socratic_gateway._rule_object_clarity", return_value=1.0)
    @patch("socratic_gateway._rule_conflict_tension", return_value=1.0)
    @patch("socratic_gateway._rule_fact_support", return_value=1.0)
    def test_perfect_input_returns_pass(self, mock_fact, mock_conflict, mock_obj):
        """满分输入应该 pass 而非 clarify"""
        result = calculate_entropy("帮我写一篇关于AI替代程序员的分析文章，数据显示2024年裁员30%")
        self.assertEqual(result["decision"], "pass",
                         f"满分输入应 pass，实际: {result['decision']}")
        self.assertEqual(result["entropy_score"], 1.0)

    @patch("socratic_gateway._rule_object_clarity", return_value=0.95)
    @patch("socratic_gateway._rule_conflict_tension", return_value=0.95)
    @patch("socratic_gateway._rule_fact_support", return_value=0.8)
    def test_strong_input_returns_pass(self, mock_fact, mock_conflict, mock_obj):
        """高分输入应该 pass (0.95*0.4+0.95*0.4+0.8*0.2=0.92 >= 0.8)"""
        result = calculate_entropy("AI程序员裁员潮分析")
        expected = 0.95 * 0.4 + 0.95 * 0.4 + 0.8 * 0.2  # = 0.92
        self.assertAlmostEqual(result["entropy_score"], expected, places=2)
        self.assertEqual(result["decision"], "pass",
                         f"高分输入应 pass，实际: {result['decision']}")

    @patch("socratic_gateway._rule_object_clarity", return_value=0.4)
    @patch("socratic_gateway._rule_conflict_tension", return_value=0.3)
    @patch("socratic_gateway._rule_fact_support", return_value=0.2)
    def test_weak_input_returns_clarify(self, mock_fact, mock_conflict, mock_obj):
        """低分输入 (0.32) 应该 clarify"""
        result = calculate_entropy("迷茫")
        self.assertEqual(result["decision"], "clarify",
                         f"低分输入应 clarify，实际: {result['decision']}")

    @patch("socratic_gateway._rule_object_clarity", return_value=0.5)
    @patch("socratic_gateway._rule_conflict_tension", return_value=0.7)
    @patch("socratic_gateway._rule_fact_support", return_value=0.3)
    def test_mid_input_returns_clarify(self, mock_fact, mock_conflict, mock_obj):
        """中等输入 (0.54) 应该 clarify"""
        result = calculate_entropy("聊聊职场")
        self.assertEqual(result["decision"], "clarify")


# ============ T-3: entropy 返回格式 ============

class TestEntropyReturnFormat(unittest.TestCase):
    def test_all_keys_present(self):
        result = calculate_entropy("AI程序员如何不被替代")
        for key in ("object_clarity", "conflict_tension", "fact_support", "entropy_score", "decision", "reason"):
            self.assertIn(key, result, f"缺少 key: {key}")

    def test_scores_are_floats(self):
        result = calculate_entropy("测试输入")
        for key in ("object_clarity", "conflict_tension", "fact_support", "entropy_score"):
            self.assertIsInstance(result[key], float, f"{key} 不是 float: {type(result[key])}")

    def test_decision_is_valid(self):
        result = calculate_entropy("测试输入")
        self.assertIn(result["decision"], ("pass", "clarify", "blocked"))


# ============ T-4: socratic_gateway 集成 HKR ============

class TestGatewayHKRIntegration(unittest.TestCase):
    """验证 socratic_gateway 返回中包含 hkr 字段"""

    @patch("socratic_gateway.calculate_entropy")
    @patch("socratic_gateway.calculate_hkr")
    def test_pass_path_includes_hkr(self, mock_hkr, mock_entropy):
        mock_entropy.return_value = {
            "object_clarity": 0.9,
            "conflict_tension": 0.9,
            "fact_support": 0.6,
            "entropy_score": 0.84,
            "decision": "pass",
            "reason": "命题清晰、有张力"
        }
        mock_hkr.return_value = {"h": 0.6, "k": 0.8, "r": 0.7, "hkr_avg": 0.7}

        result = socratic_gateway("帮我写一篇AI替代程序员的文章")
        self.assertEqual(result["status"], "ready_for_generation")
        self.assertIn("hkr", result)
        self.assertEqual(result["hkr"]["h"], 0.6)
        self.assertEqual(result["hkr"]["k"], 0.8)
        self.assertEqual(result["hkr"]["r"], 0.7)

    @patch("socratic_gateway.calculate_entropy")
    @patch("socratic_gateway.calculate_hkr")
    @patch("socratic_gateway._call_llm_raw", _mock_llm_raw)
    def test_clarify_path_includes_hkr(self, mock_hkr, mock_entropy):
        mock_entropy.return_value = {
            "object_clarity": 0.4,
            "conflict_tension": 0.3,
            "fact_support": 0.2,
            "entropy_score": 0.32,
            "decision": "clarify",
            "reason": "命题较简短"
        }
        mock_hkr.return_value = {"h": 0.2, "k": 0.5, "r": 0.3, "hkr_avg": 0.33}

        result = socratic_gateway("AI")
        self.assertEqual(result["status"], "need_clarification")
        self.assertIn("hkr", result)

    @patch("socratic_gateway.calculate_entropy")
    @patch("socratic_gateway.calculate_hkr")
    def test_blocked_path_includes_hkr(self, mock_hkr, mock_entropy):
        mock_entropy.return_value = {
            "object_clarity": 0.0,
            "conflict_tension": 0.1,
            "fact_support": 0.0,
            "entropy_score": 0.04,
            "decision": "blocked",
            "reason": "命题无效"
        }
        mock_hkr.return_value = {"h": 0.0, "k": 0.0, "r": 0.0, "hkr_avg": 0.0}

        result = socratic_gateway("你好")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("hkr", result)


# ============ T-5: 联合决策门槛 ============

class TestCombinedDecisionLogic(unittest.TestCase):
    """验证 硬门槛 + 加权排名 联合决策"""

    @patch("socratic_gateway.calculate_entropy")
    @patch("socratic_gateway.calculate_hkr")
    def test_both_below_threshold_clarify(self, mock_hkr, mock_entropy):
        """熵值<0.3 且 HKR<0.3 → clarify"""
        mock_entropy.return_value = {
            "object_clarity": 0.1, "conflict_tension": 0.2, "fact_support": 0.1,
            "entropy_score": 0.14, "decision": "clarify", "reason": "too vague"
        }
        mock_hkr.return_value = {"h": 0.1, "k": 0.2, "r": 0.1, "hkr_avg": 0.13}

        result = socratic_gateway("嗯")
        self.assertEqual(result["status"], "need_clarification")

    @patch("socratic_gateway.calculate_entropy")
    @patch("socratic_gateway.calculate_hkr")
    def test_entropy_low_hkr_high_clarify(self, mock_hkr, mock_entropy):
        """熵值<0.3 但 HKR高 → 硬门槛拦截，clarify"""
        mock_entropy.return_value = {
            "object_clarity": 0.1, "conflict_tension": 0.2, "fact_support": 0.1,
            "entropy_score": 0.14, "decision": "clarify", "reason": "too vague"
        }
        mock_hkr.return_value = {"h": 0.8, "k": 0.9, "r": 0.8, "hkr_avg": 0.83}

        result = socratic_gateway("感觉")
        self.assertEqual(result["status"], "need_clarification")

    @patch("socratic_gateway.calculate_entropy")
    @patch("socratic_gateway.calculate_hkr")
    def test_entropy_high_hkr_low_clarify(self, mock_hkr, mock_entropy):
        """熵值高 但 HKR<0.3 → 硬门槛拦截，clarify"""
        mock_entropy.return_value = {
            "object_clarity": 0.9, "conflict_tension": 0.8, "fact_support": 0.5,
            "entropy_score": 0.78, "decision": "pass", "reason": "clear"
        }
        mock_hkr.return_value = {"h": 0.1, "k": 0.2, "r": 0.1, "hkr_avg": 0.13}

        result = socratic_gateway("正确但无趣的命题")
        self.assertEqual(result["status"], "need_clarification")

    @patch("socratic_gateway.calculate_entropy")
    @patch("socratic_gateway.calculate_hkr")
    def test_both_above_threshold_pass(self, mock_hkr, mock_entropy):
        """熵值>0.5 且 HKR>0.5 → pass"""
        mock_entropy.return_value = {
            "object_clarity": 0.9, "conflict_tension": 0.8, "fact_support": 0.6,
            "entropy_score": 0.80, "decision": "pass", "reason": "clear"
        }
        mock_hkr.return_value = {"h": 0.7, "k": 0.8, "r": 0.7, "hkr_avg": 0.73}

        result = socratic_gateway("帮我写AI裁员背后的真实原因")
        self.assertEqual(result["status"], "ready_for_generation")

    @patch("socratic_gateway.calculate_entropy")
    @patch("socratic_gateway.calculate_hkr")
    def test_borderline_entropy_ok_hkr_ok_pass(self, mock_hkr, mock_entropy):
        """边界值：entropy=0.60, hkr=0.55 → combined=0.57 >= 0.5 → pass"""
        mock_entropy.return_value = {
            "object_clarity": 0.7, "conflict_tension": 0.6, "fact_support": 0.4,
            "entropy_score": 0.60, "decision": "pass", "reason": "borderline"
        }
        mock_hkr.return_value = {"h": 0.5, "k": 0.6, "r": 0.5, "hkr_avg": 0.55}

        result = socratic_gateway("职场内卷的原因分析")
        self.assertEqual(result["status"], "ready_for_generation")


# ============ T-6: classify_input 不变 ============

class TestClassifyInput(unittest.TestCase):
    def test_keyword_short(self):
        self.assertEqual(classify_input("AI"), "keyword")

    def test_sentence_long(self):
        self.assertEqual(classify_input("AI时代程序员面临的挑战和机遇"), "sentence")

    def test_question_with_mark(self):
        self.assertEqual(classify_input("为什么AI不能替代所有工作？"), "question")

    def test_question_with_pattern_long(self):
        self.assertEqual(classify_input("如何才能建立不被AI替代的个人品牌"), "question")

    def test_english_keyword(self):
        self.assertEqual(classify_input("hello world"), "keyword")


# ============ T-7: 规则函数边界 ============

class TestRuleFunctions(unittest.TestCase):
    def test_object_clarity_returns_float(self):
        score = _rule_object_clarity("测试")
        self.assertIsInstance(score, float)

    def test_conflict_tension_returns_float(self):
        score = _rule_conflict_tension("测试")
        self.assertIsInstance(score, float)

    def test_fact_support_returns_float(self):
        score = _rule_fact_support("测试")
        self.assertIsInstance(score, float)

    def test_object_clarity_writing_intent(self):
        self.assertEqual(_rule_object_clarity("帮我写一篇AI文章"), 1.0)

    def test_fact_support_with_number(self):
        self.assertEqual(_rule_fact_support("裁员30%的人"), 1.0)


if __name__ == "__main__":
    unittest.main()
