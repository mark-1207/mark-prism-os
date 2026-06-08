#!/usr/bin/env python3
"""
熵值/HKR 规则过严 Bug 测试 — Commit 7 RED

bug: 合理命题（含 clarifications）打分过低，无法 pass
fix: 扩展关键词集合，让合理的命题能 pass

用法: python -m pytest skills/prism-os/tests/test_entropy_hkr_strict.py -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestEntropyPermissiveRules(unittest.TestCase):
    """合理命题应能 pass 熵值，不应被过严规则卡住"""

    def test_clear_topic_passes_entropy(self):
        """明确话题的命题应能 pass"""
        from socratic_gateway import calculate_entropy
        result = calculate_entropy(
            "35岁程序员面临的裁员危机"
        )
        # 之前的实现：object_clarity=0.6, conflict=0.7(因为"危机"), fact=0.2 → entropy=0.56
        # 应该是 ≥ 0.7 才能 pass（之前）
        # 我们期望 pass
        self.assertEqual(result["decision"], "pass",
                         f"明确话题应 pass，实际: {result['decision']}, score={result['entropy_score']}")

    def test_topic_with_clarification_passes(self):
        """含 clarifications 的命题应能 pass"""
        from socratic_gateway import calculate_entropy
        full = """35岁程序员面临的裁员危机
补充说明：裁员危机是核心问题；受众是职场大龄人士；期望行动是提升自我、转变思路、适应变化、不要固步自封"""
        result = calculate_entropy(full)
        self.assertEqual(result["decision"], "pass",
                         f"含 clarifications 的命题应 pass，实际: {result['decision']}, score={result['entropy_score']}")

    def test_topic_with_action_keywords_passes(self):
        """含具体行动建议的命题应能 pass"""
        from socratic_gateway import calculate_entropy
        result = calculate_entropy(
            "如何应对35岁程序员被裁危机：行动建议是学AI、转型管理岗、做独立开发者"
        )
        self.assertEqual(result["decision"], "pass",
                         f"含行动建议的命题应 pass，实际: {result['decision']}, score={result['entropy_score']}")


class TestHKRPermissiveRules(unittest.TestCase):
    """合理命题应能 pass HKR"""

    def test_topic_with_target_audience_passes(self):
        """含目标读者的命题应能 pass HKR"""
        from socratic_gateway import calculate_hkr
        result = calculate_hkr(
            "针对35岁程序员的裁员危机，职场大龄人士如何应对"
        )
        # R 维度应识别"35岁程序员"和"大龄人士"
        self.assertGreaterEqual(result["r"], 0.3,
                              f"目标读者关键词应贡献 R，实际: {result['r']}")

    def test_topic_with_clarification_passes(self):
        """含 clarifications 的命题应能 pass HKR"""
        from socratic_gateway import calculate_hkr
        full = """35岁程序员面临的裁员危机
补充说明：裁员危机是核心问题；受众是职场大龄人士；期望行动是提升自我、转变思路、适应变化、不要固步自封"""
        result = calculate_hkr(full)
        # 含"裁员"、"危机"、"焦虑"应贡献 R
        self.assertGreaterEqual(result["r"], 0.3,
                              f"含焦虑/危机关键词应贡献 R，实际: {result['r']}")

    def test_topic_with_action_passes(self):
        """含具体行动的命题应能 pass HKR"""
        from socratic_gateway import calculate_hkr
        result = calculate_hkr(
            "应对裁员危机：学AI提升技能、转型产品经理、做自由职业"
        )
        # K 维度应识别"学"、"提升技能"
        self.assertGreaterEqual(result["hkr_avg"], 0.3,
                              f"含行动的命题应过 HKR 门槛，实际: {result['hkr_avg']}")


class TestGatewayPassesReasonableTopic(unittest.TestCase):
    """端到端：合理命题应能 pass gateway"""

    def test_35yo_programmer_with_clarification_passes(self):
        from socratic_gateway import socratic_gateway
        full = """35岁程序员面临的裁员危机
补充说明：裁员危机是核心问题；受众是职场大龄人士；期望行动是提升自我、转变思路、适应变化、不要固步自封"""
        result = socratic_gateway(full)
        self.assertEqual(result["status"], "ready_for_generation",
                         f"合理命题应 pass gateway，实际: {result['status']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
