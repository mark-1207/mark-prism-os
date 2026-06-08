#!/usr/bin/env python3
"""prism_os.py 集成测试 — 流程逻辑和边界情况"""

import os
import sys
import unittest
from unittest.mock import patch, Mock
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from prism_os import classify_intent, format_prism_os_output, run_prism_os


class TestClassifyIntent(unittest.TestCase):
    """Rule-based path tests (no LLM call)"""

    def test_small_talk_not_triggered(self):
        result = classify_intent("你好啊")
        self.assertFalse(result["trigger"])
        self.assertGreater(result["confidence"], 0.8)

    def test_weather_not_triggered(self):
        result = classify_intent("天气怎么样")
        self.assertFalse(result["trigger"])

    def test_today_not_triggered(self):
        result = classify_intent("今天几号")
        self.assertFalse(result["trigger"])

    def test_strong_intent_triggered(self):
        result = classify_intent("帮我写一篇关于AI的文章")
        self.assertTrue(result["trigger"])
        self.assertGreater(result["confidence"], 0.9)

    def test_generate_triggered(self):
        result = classify_intent("生成标题")
        self.assertTrue(result["trigger"])

    def test_short_question_triggered(self):
        result = classify_intent("AI会取代人类吗")
        self.assertTrue(result["trigger"])
        self.assertGreater(result["confidence"], 0.5)

    def test_short_question_no_write_keyword_triggered(self):
        result = classify_intent("人工智能是什么")
        self.assertTrue(result["trigger"])

    @patch('call_llm.call_llm')
    def test_llm_failure_falls_back_to_trigger(self, mock_call_llm):
        """LLM call fails → fallback to trigger=True"""
        mock_call_llm.side_effect = ImportError("module not found")
        result = classify_intent("一个复杂但无关键词的话题讨论")
        self.assertTrue(result["trigger"])
        self.assertEqual(result["confidence"], 0.3)

    @patch('call_llm.call_llm')
    def test_llm_returns_error_falls_back(self, mock_call_llm):
        mock_call_llm.return_value = {"error": "timeout"}
        result = classify_intent("值得讨论的深度话题")
        self.assertTrue(result["trigger"])


class TestFormatPrismOsOutput(unittest.TestCase):
    def test_empty_candidates_no_crash(self):
        result = {
            "candidates": [],
            "status": "no_candidates",
            "message": "所有候选均未通过现实校验"
        }
        output = format_prism_os_output(result)
        self.assertIsInstance(output, str)
        self.assertNotIn("候选标题", output)

    def test_with_candidates(self):
        result = {
            "candidates": [
                {"title": "AI时代如何学习", "dimension": "bridge",
                 "competition_level": "蓝海", "novelty_score": 0.8}
            ],
            "status": "success"
        }
        output = format_prism_os_output(result)
        self.assertIsInstance(output, str)
        self.assertIn("候选标题", output)
        self.assertIn("AI时代如何学习", output)

    def test_error_status_output(self):
        result = {"status": "error", "message": "标题生成失败"}
        output = format_prism_os_output(result)
        self.assertIsInstance(output, str)


class TestRunPrismOsEdgeCases(unittest.TestCase):
    @patch('call_llm.call_llm')
    @patch('reality_anchor.reality_anchor')
    @patch('prism_engine.prism_engine')
    def test_phase2_exception_returns_error_status(self, mock_pe, mock_ra, mock_call_llm):
        """Phase 2 crash → returns error status, does not raise"""
        mock_call_llm.return_value = {
            "content": '{"trigger": true, "reason": "test"}',
            "error": None
        }
        mock_pe.side_effect = RuntimeError("simulated engine crash")
        result = run_prism_os("测试话题", include_phase_4_8=False, skip_gateway=True)
        self.assertEqual(result["status"], "error")
        self.assertIn("标题生成异常", result["message"])

    @patch('call_llm.call_llm')
    @patch('reality_anchor.reality_anchor')
    @patch('prism_engine.prism_engine')
    def test_phase3_exception_graceful_degradation(self, mock_pe, mock_ra, mock_call_llm):
        """Phase 3 crash → graceful degradation, keeps candidates"""
        mock_call_llm.return_value = {
            "content": '{"trigger": true, "reason": "test"}',
            "error": None
        }
        mock_pe.return_value = {
            "status": "ok",
            "candidates": [{"title": "测试标题12345678901234567890", "dimension": "reversal"}]
        }
        mock_ra.side_effect = subprocess.TimeoutExpired(cmd="curl", timeout=30)
        result = run_prism_os("测试话题", include_phase_4_8=False, skip_gateway=True)
        self.assertIn(result["status"], ["success", "no_candidates"])
        self.assertGreaterEqual(len(result.get("candidates", [])), 0)
        self.assertEqual(result["reality"]["status"], "partial")


if __name__ == "__main__":
    unittest.main()
