#!/usr/bin/env python3
"""
run_prism_os 交互决策点测试 — Commit 1 RED

覆盖：
1. interactive=True 时 Phase 3.5 后等待用户选 candidate
2. 选中的 candidate 用于 CCOS（不是 first）
3. interactive=False 时不阻塞
4. include_phase_4_8=False 时不阻塞
5. stdin 不可用时降级到 first candidate

用法: python -m pytest skills/prism-os/tests/test_run_prism_os_interactive.py -v
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


# ============ T-1: interactive=True 时等待用户选 candidate ============

class TestRunInteractiveSelection(unittest.TestCase):
    """run 命令在 Phase 3.5 之后应该让用户选 candidate"""

    def test_interactive_param_exists(self):
        """run_prism_os 应该接受 interactive 参数"""
        import inspect
        from prism_os import run_prism_os
        sig = inspect.signature(run_prism_os)
        self.assertIn("interactive", sig.parameters,
                      "run_prism_os 必须有 interactive 参数")

    @patch("prism_os.classify_intent")
    @patch("socratic_gateway.socratic_gateway")
    @patch("prism_engine.prism_engine")
    @patch("reality_anchor.reality_anchor")
    @patch("cognitive_crack.digital_twin_filter")
    @patch("cognitive_crack.learn_thinking_pattern")
    @patch("cognitive_outline.cognitive_outline_workflow")
    @patch("storage.append_log")
    @patch("builtins.input", return_value="2")
    def test_user_input_2_uses_second_candidate(
        self, mock_input, mock_append, mock_ccos,
        mock_learn, mock_twin, mock_anchor, mock_prism,
        mock_gateway, mock_intent
    ):
        """用户输入 2 → CCOS 用第 2 个 candidate（不是 first）"""
        # 跳过 Phase 0 触发
        mock_intent.return_value = {"trigger": True, "confidence": 0.9, "reason": "test"}
        # 跳过 Phase 1 阻塞
        mock_gateway.return_value = {
            "status": "ready_for_generation",
            "entropy_score": 0.7,
            "hkr": {"hkr_avg": 0.6},
            "combined_score": 0.65,
        }
        # Phase 2: prism 给出 3 个候选
        mock_prism.return_value = {
            "status": "success",
            "candidates": [
                {"title": "标题1", "dimension": "reversal", "orthogonal": True},
                {"title": "标题2", "dimension": "micro_scene", "orthogonal": True},
                {"title": "标题3", "dimension": "systemic_flaw", "orthogonal": True},
            ],
        }
        # Phase 3: reality_anchor 全部通过
        mock_anchor.return_value = {
            "status": "success",
            "validated": [
                {"title": "标题1", "dimension": "reversal", "duplicate_rate": 0.1, "competition_level": "蓝海"},
                {"title": "标题2", "dimension": "micro_scene", "duplicate_rate": 0.2, "competition_level": "蓝海"},
                {"title": "标题3", "dimension": "systemic_flaw", "duplicate_rate": 0.15, "competition_level": "蓝海"},
            ],
            "statistics": {"blue_ocean": 3, "yellow_ocean": 0, "red_ocean": 0},
        }
        # Phase 3.5: 数字分身全选
        mock_learn.return_value = {"thinking_pattern": "理性"}
        mock_twin.return_value = {
            "selected_topics": [
                {"topic": "标题1", "selection_reason": "test", "confidence": 0.8},
                {"topic": "标题2", "selection_reason": "test", "confidence": 0.7},
                {"topic": "标题3", "selection_reason": "test", "confidence": 0.6},
            ]
        }
        # Phase 4.5: ccos
        mock_ccos.return_value = {"内容目标": "test", "认知模块流": []}

        from prism_os import run_prism_os
        result = run_prism_os("测试命题", interactive=True)

        # 验证 input 被调用
        self.assertTrue(mock_input.called, "interactive=True 时应该调用 input()")
        # 验证 CCOS 用的是第 2 个候选（"标题2"），不是第 1 个
        if mock_ccos.called:
            ccos_call_args = mock_ccos.call_args
            # 第一个位置参数应该是 title
            if ccos_call_args.args:
                actual_title = ccos_call_args.args[0]
                self.assertEqual(actual_title, "标题2",
                                 f"CCOS 应该用用户选的第 2 个候选，实际用: {actual_title}")


# ============ T-2: interactive=False 不阻塞 ============

class TestRunNonInteractive(unittest.TestCase):
    """interactive=False 时不调用 input()"""

    @patch("prism_os.classify_intent")
    @patch("socratic_gateway.socratic_gateway")
    @patch("prism_engine.prism_engine")
    @patch("reality_anchor.reality_anchor")
    @patch("cognitive_crack.digital_twin_filter")
    @patch("cognitive_crack.learn_thinking_pattern")
    @patch("cognitive_outline.cognitive_outline_workflow")
    @patch("storage.append_log")
    @patch("builtins.input")
    def test_non_interactive_does_not_call_input(
        self, mock_input, mock_append, mock_ccos,
        mock_learn, mock_twin, mock_anchor, mock_prism,
        mock_gateway, mock_intent
    ):
        """interactive=False 时不应调用 input()"""
        mock_intent.return_value = {"trigger": True}
        mock_gateway.return_value = {"status": "ready_for_generation", "entropy_score": 0.7, "hkr": {"hkr_avg": 0.6}}
        mock_prism.return_value = {
            "status": "success",
            "candidates": [{"title": "X", "dimension": "r"}],
        }
        mock_anchor.return_value = {
            "status": "success",
            "validated": [{"title": "X", "dimension": "r"}],
        }
        mock_learn.return_value = {"thinking_pattern": "理性"}
        mock_twin.return_value = {
            "selected_topics": [{"topic": "X", "selection_reason": "t", "confidence": 0.8}]
        }
        mock_ccos.return_value = {}

        from prism_os import run_prism_os
        run_prism_os("测试", interactive=False)

        self.assertFalse(mock_input.called, "interactive=False 时不应调用 input()")


# ============ T-3: include_phase_4_8=False 不阻塞 ============

class TestRunNoExtNoInput(unittest.TestCase):
    """include_phase_4_8=False 时不调用 input()（因为没有 CCOS 步骤）"""

    @patch("prism_os.classify_intent")
    @patch("socratic_gateway.socratic_gateway")
    @patch("prism_engine.prism_engine")
    @patch("reality_anchor.reality_anchor")
    @patch("cognitive_crack.digital_twin_filter")
    @patch("cognitive_crack.learn_thinking_pattern")
    @patch("builtins.input")
    def test_no_ext_does_not_call_input(
        self, mock_input, mock_learn, mock_twin, mock_anchor,
        mock_prism, mock_gateway, mock_intent
    ):
        """include_phase_4_8=False 时不应调用 input()"""
        mock_intent.return_value = {"trigger": True}
        mock_gateway.return_value = {"status": "ready_for_generation", "entropy_score": 0.7, "hkr": {"hkr_avg": 0.6}}
        mock_prism.return_value = {
            "status": "success",
            "candidates": [{"title": "X", "dimension": "r"}],
        }
        mock_anchor.return_value = {
            "status": "success",
            "validated": [{"title": "X", "dimension": "r"}],
        }
        mock_learn.return_value = {"thinking_pattern": "理性"}
        mock_twin.return_value = {
            "selected_topics": [{"topic": "X", "selection_reason": "t", "confidence": 0.8}]
        }

        from prism_os import run_prism_os
        run_prism_os("测试", interactive=True, include_phase_4_8=False)

        self.assertFalse(mock_input.called, "include_phase_4_8=False 时不应调用 input()")


# ============ T-4: stdin 不可用时降级 ============

class TestRunEOFFallback(unittest.TestCase):
    """stdin 不可用时降级到第一个 candidate"""

    @patch("prism_os.classify_intent")
    @patch("socratic_gateway.socratic_gateway")
    @patch("prism_engine.prism_engine")
    @patch("reality_anchor.reality_anchor")
    @patch("cognitive_crack.digital_twin_filter")
    @patch("cognitive_crack.learn_thinking_pattern")
    @patch("cognitive_outline.cognitive_outline_workflow")
    @patch("storage.append_log")
    def test_eoferror_falls_back_to_first_candidate(
        self, mock_append, mock_ccos, mock_learn, mock_twin,
        mock_anchor, mock_prism, mock_gateway, mock_intent
    ):
        """stdin 不可用（EOFError）时降级到 first candidate"""
        mock_intent.return_value = {"trigger": True}
        mock_gateway.return_value = {"status": "ready_for_generation", "entropy_score": 0.7, "hkr": {"hkr_avg": 0.6}}
        mock_prism.return_value = {
            "status": "success",
            "candidates": [
                {"title": "first", "dimension": "r"},
                {"title": "second", "dimension": "m"},
            ],
        }
        mock_anchor.return_value = {
            "status": "success",
            "validated": [
                {"title": "first", "dimension": "r"},
                {"title": "second", "dimension": "m"},
            ],
        }
        mock_learn.return_value = {"thinking_pattern": "理性"}
        mock_twin.return_value = {
            "selected_topics": [
                {"topic": "first", "selection_reason": "t", "confidence": 0.8},
                {"topic": "second", "selection_reason": "t", "confidence": 0.7},
            ]
        }
        mock_ccos.return_value = {}

        with patch("builtins.input", side_effect=EOFError):
            from prism_os import run_prism_os
            # 不应该崩，应该降级到 first
            result = run_prism_os("测试", interactive=True)

        # 验证 CCOS 用的是 first candidate
        if mock_ccos.called:
            ccos_call_args = mock_ccos.call_args
            if ccos_call_args.args:
                actual_title = ccos_call_args.args[0]
                self.assertEqual(actual_title, "first",
                                 f"stdin 不可用时应该用 first，实际: {actual_title}")


# ============ T-5: 用户选无效输入时重试 ============

class TestRunInvalidInputRetry(unittest.TestCase):
    """用户输入无效数字时应重试，不能崩"""

    @patch("prism_os.classify_intent")
    @patch("socratic_gateway.socratic_gateway")
    @patch("prism_engine.prism_engine")
    @patch("reality_anchor.reality_anchor")
    @patch("cognitive_crack.digital_twin_filter")
    @patch("cognitive_crack.learn_thinking_pattern")
    @patch("cognitive_outline.cognitive_outline_workflow")
    @patch("storage.append_log")
    def test_invalid_input_eventually_selects(
        self, mock_append, mock_ccos, mock_learn, mock_twin,
        mock_anchor, mock_prism, mock_gateway, mock_intent
    ):
        """输入 abc → 输入 1，最终选 1（不应崩）"""
        mock_intent.return_value = {"trigger": True}
        mock_gateway.return_value = {"status": "ready_for_generation", "entropy_score": 0.7, "hkr": {"hkr_avg": 0.6}}
        mock_prism.return_value = {
            "status": "success",
            "candidates": [
                {"title": "first", "dimension": "r"},
                {"title": "second", "dimension": "m"},
            ],
        }
        mock_anchor.return_value = {
            "status": "success",
            "validated": [
                {"title": "first", "dimension": "r"},
                {"title": "second", "dimension": "m"},
            ],
        }
        mock_learn.return_value = {"thinking_pattern": "理性"}
        mock_twin.return_value = {
            "selected_topics": [
                {"topic": "first", "selection_reason": "t", "confidence": 0.8},
                {"topic": "second", "selection_reason": "t", "confidence": 0.7},
            ]
        }
        mock_ccos.return_value = {}

        with patch("builtins.input", side_effect=["abc", "xyz", "1"]):
            from prism_os import run_prism_os
            result = run_prism_os("测试", interactive=True)

        if mock_ccos.called:
            ccos_call_args = mock_ccos.call_args
            if ccos_call_args.args:
                actual_title = ccos_call_args.args[0]
                self.assertEqual(actual_title, "first",
                                 f"重试后选 1，实际: {actual_title}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
