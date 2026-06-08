#!/usr/bin/env python3
"""
CCOS 大纲人工审核决策点测试 — Commit 8 RED

bug: CCOS 生成后直接用于下游，用户没有机会看和修改
fix: Phase 4.5 后插入 CCOS 审核决策点
    - 展示每个模块的：模块名 + 功能 + 篇幅
    - 用户选择：[c]继续 / [r]重生成 / [e]手动编辑 / [q]退出
    - --no-ccos-review 标志跳过
    - ccos_review: bool = True 参数到 run_prism_os

用法: python -m pytest skills/prism-os/tests/test_ccos_review.py -v
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


# ============ T-1: run_prism_os 加 ccos_review 参数 ============

class TestCCOSReviewParam(unittest.TestCase):
    """run_prism_os 应支持 ccos_review 参数"""

    def test_ccos_review_param_exists(self):
        """run_prism_os 接受 ccos_review 参数"""
        import inspect
        from prism_os import run_prism_os
        sig = inspect.signature(run_prism_os)
        self.assertIn("ccos_review", sig.parameters,
                      "run_prism_os 必须有 ccos_review 参数")


# ============ T-2: ccos_review=True 时阻塞等用户确认 ============

class TestCCOSReviewBlocking(unittest.TestCase):
    """ccos_review=True 时应在 CCOS 后阻塞"""

    @patch("prism_os.classify_intent")
    @patch("socratic_gateway.socratic_gateway")
    @patch("prism_engine.prism_engine")
    @patch("reality_anchor.reality_anchor")
    @patch("cognitive_crack.digital_twin_filter")
    @patch("cognitive_crack.learn_thinking_pattern")
    @patch("cognitive_outline.cognitive_outline_workflow")
    @patch("storage.append_log")
    @patch("builtins.input")
    def test_ccos_review_blocks_at_phase_45(
        self, mock_input, mock_append, mock_ccos, mock_learn, mock_twin,
        mock_anchor, mock_prism, mock_gateway, mock_intent
    ):
        """ccos_review=True 时 input() 应被调用（用户确认 CCOS）"""
        mock_intent.return_value = {"trigger": True}
        mock_gateway.return_value = {
            "status": "ready_for_generation",
            "entropy_score": 0.7, "hkr": {"hkr_avg": 0.6},
        }
        mock_prism.return_value = {
            "status": "success",
            "candidates": [
                {"title": "X", "dimension": "r"},
            ],
        }
        mock_anchor.return_value = {
            "status": "success",
            "validated": [{"title": "X", "dimension": "r"}],
        }
        mock_learn.return_value = {"thinking_pattern": "理性"}
        mock_twin.return_value = {
            "selected_topics": [{"topic": "X", "selection_reason": "t", "confidence": 0.8}]
        }
        mock_ccos.return_value = {
            "内容目标": "认知升级",
            "认知模块流": [
                {"模块": "HOOK", "功能": "制造停留", "篇幅": "200字"},
                {"模块": "CASE", "功能": "建立真实感", "篇幅": "600字"},
            ]
        }
        # 让 input() 返回 "c" 跳出 ccos_review 决策点循环
        mock_input.return_value = "c"

        from prism_os import run_prism_os
        run_prism_os("测试", ccos_review=True, skip_gateway=True, include_phase_4_8=True)

        # interactive=True 默认下，run 已经有 input 决策（Phase 3.5 选标题）
        # 但这里 candidates 只有 1 个，不进入选标题分支
        # 所以 input 是否被调用，取决于 ccos_review 是否阻塞
        # 由于 mock_candidates=1, len > 1 是 False，跳过选标题
        # 此时如果有 ccos_review 阻塞，input 应被调用
        # 如果没有 ccos_review 阻塞，input 不会被调用
        # 我们验证：ccos_review=True 时 input 被调用（阻塞了）
        self.assertTrue(mock_input.called, "ccos_review=True 时应阻塞等用户确认")


# ============ T-3: ccos_review=False 时不阻塞 ============

class TestCCOSReviewNonBlocking(unittest.TestCase):
    """ccos_review=False 时不阻塞"""

    @patch("prism_os.classify_intent")
    @patch("socratic_gateway.socratic_gateway")
    @patch("prism_engine.prism_engine")
    @patch("reality_anchor.reality_anchor")
    @patch("cognitive_crack.digital_twin_filter")
    @patch("cognitive_crack.learn_thinking_pattern")
    @patch("cognitive_outline.cognitive_outline_workflow")
    @patch("storage.append_log")
    @patch("builtins.input")
    def test_ccos_review_false_does_not_block(
        self, mock_input, mock_append, mock_ccos, mock_learn, mock_twin,
        mock_anchor, mock_prism, mock_gateway, mock_intent
    ):
        """ccos_review=False 时 input 不被调用"""
        mock_intent.return_value = {"trigger": True}
        mock_gateway.return_value = {
            "status": "ready_for_generation",
            "entropy_score": 0.7, "hkr": {"hkr_avg": 0.6},
        }
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
        mock_ccos.return_value = {
            "认知模块流": [{"模块": "HOOK", "功能": "x", "篇幅": "y"}]
        }

        from prism_os import run_prism_os
        run_prism_os("测试", ccos_review=False, skip_gateway=True, include_phase_4_8=True)

        self.assertFalse(mock_input.called, "ccos_review=False 时不应阻塞")


# ============ T-4: CCOS 展示包含每个模块的功能+篇幅 ============

class TestCCOSDisplay(unittest.TestCase):
    """CCOS 审核时显示每个模块的模块名+功能+篇幅"""

    def test_ccos_display_function_exists(self):
        """_format_ccos_review 函数存在"""
        from prism_os import _format_ccos_review
        self.assertTrue(callable(_format_ccos_review))

    def test_ccos_display_includes_module_name_function_length(self):
        """展示包含模块名+功能+篇幅"""
        from prism_os import _format_ccos_review
        ccos = {
            "内容目标": "认知升级",
            "主结构": "故事驱动型",
            "推进方式": "冲突推进",
            "认知模块流": [
                {"模块": "HOOK", "内容摘要": "开场钩子", "功能": "制造停留", "篇幅": "200字"},
                {"模块": "CASE", "内容摘要": "案例", "功能": "建立真实感", "篇幅": "600字"},
            ]
        }
        result = _format_ccos_review(ccos, "测试标题", "wechat")
        self.assertIn("HOOK", result)
        self.assertIn("制造停留", result)
        self.assertIn("200字", result)
        self.assertIn("CASE", result)
        self.assertIn("建立真实感", result)
        self.assertIn("600字", result)

    def test_ccos_display_handles_missing_module_function(self):
        """模块缺功能字段时降级处理"""
        from prism_os import _format_ccos_review
        ccos = {
            "认知模块流": [
                {"模块": "HOOK", "内容摘要": "开场钩子"},  # 无功能字段
            ]
        }
        result = _format_ccos_review(ccos, "测试标题", "wechat")
        # 不应崩
        self.assertIn("HOOK", result)


# ============ T-5: --no-ccos-review 标志解析 ============

class TestRunNoCCOSReviewFlag(unittest.TestCase):
    """run 命令 --no-ccos-review 标志"""

    def test_run_parses_no_ccos_review_flag(self):
        """--no-ccos-review 解析为 ccos_review=False"""
        import prism_os
        sys.argv = ["prism_os.py", "run", "测试", "--no-ccos-review"]

        with patch("prism_os.run_prism_os") as mock_run, \
             patch("prism_os._safe_print"), \
             patch("prism_os.format_prism_os_output"):
            try:
                prism_os.main()
            except SystemExit:
                pass

        if mock_run.called:
            kwargs = mock_run.call_args.kwargs
            self.assertIn("ccos_review", kwargs)
            self.assertEqual(kwargs["ccos_review"], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
