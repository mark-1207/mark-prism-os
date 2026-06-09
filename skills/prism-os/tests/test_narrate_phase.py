"""NarratePhase 测试：验证 narrate 使用选中标题而非 thesis"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from phases.narrate import NarratePhase
from phases.base import PipelineState, PipelineConfig


class TestNarrateUsesSelectedTitle(unittest.TestCase):
    """NarratePhase 应使用 selected_candidate.title 而非 thesis"""

    @patch("prism_os._run_narrate")
    def test_narrate_uses_selected_title(self, mock_run_narrate):
        """选中标题应作为 _run_narrate 第一个参数"""
        mock_run_narrate.return_value = {"full_draft": "test", "word_count": 100}

        phase = NarratePhase()
        state = PipelineState(
            thesis="原始用户输入",
            ccos_outline={"主结构": "测试"},
            ccos_failed=False,
        )
        state.selected_candidate = {"title": "选中的标题", "dimension": "micro_scene"}
        config = PipelineConfig()

        phase.execute(state, config)

        mock_run_narrate.assert_called_once()
        call_args = mock_run_narrate.call_args
        actual_topic = call_args[0][0] if call_args[0] else call_args[1].get("topic", "")
        self.assertEqual(actual_topic, "选中的标题",
                         "narrate 应使用 selected_candidate.title")

    @patch("prism_os._run_narrate")
    def test_narrate_fallback_to_thesis_when_no_selected(self, mock_run_narrate):
        """selected_candidate 为 None 时 fallback 到 thesis"""
        mock_run_narrate.return_value = {"full_draft": "test", "word_count": 100}

        phase = NarratePhase()
        state = PipelineState(
            thesis="原始用户输入",
            ccos_outline={"主结构": "测试"},
            ccos_failed=False,
        )
        state.selected_candidate = None
        config = PipelineConfig()

        phase.execute(state, config)

        mock_run_narrate.assert_called_once()
        call_args = mock_run_narrate.call_args
        actual_topic = call_args[0][0] if call_args[0] else call_args[1].get("topic", "")
        self.assertEqual(actual_topic, "原始用户输入",
                         "selected_candidate=None 时应 fallback 到 thesis")


if __name__ == "__main__":
    unittest.main()
