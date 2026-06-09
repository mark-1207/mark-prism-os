"""GapPhase 补素材功能测试"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from phases.gap import GapPhase
from phases.base import PipelineState, PipelineConfig, PhaseResult


class TestGapReply1ReturnsNeedInput(unittest.TestCase):
    """选 1 后应返回 need_input 让用户输入素材"""

    def test_gap_reply_1_returns_need_input_add_material(self):
        """用户选 1 → status=need_input, input_type=add_material"""
        phase = GapPhase()
        state = PipelineState(thesis="测试命题")
        state.gap_analysis = {"gap_score": 0.8, "readiness": 0.2}
        state.user_reply = "1"

        result = phase._handle_user_reply(state)

        self.assertEqual(result.status, "need_input",
                         "选 1 应返回 need_input 让用户输入素材")
        self.assertEqual(result.input_type, "add_material",
                         "input_type 应为 add_material")


class TestGapMaterialStoredInState(unittest.TestCase):
    """素材文本应存入 state.user_added_materials"""

    def test_state_has_user_added_materials_field(self):
        """PipelineState 应有 user_added_materials 字段"""
        state = PipelineState()
        self.assertTrue(hasattr(state, "user_added_materials"),
                        "PipelineState 应有 user_added_materials 字段")
        self.assertEqual(state.user_added_materials, "")

    def test_gap_stores_material_on_resume(self):
        """素材回复后应存入 state.user_added_materials"""
        phase = GapPhase()
        state = PipelineState(thesis="测试命题")
        state.gap_analysis = {"gap_score": 0.8, "readiness": 0.2}
        state.gap_decision = "add_material"
        state.user_reply = "这是用户补充的素材内容"

        config = PipelineConfig(interactive=False)
        # execute 应检测到素材回复并存入 state
        result = phase.execute(state, config)

        self.assertEqual(state.user_added_materials, "这是用户补充的素材内容",
                         "素材应存入 state.user_added_materials")


class TestGapMaterialTriggersRerun(unittest.TestCase):
    """素材补充后应重新跑 gap 分析"""

    @patch("gap_analysis.analyze_gap")
    def test_gap_reruns_analysis_on_first_material_reply(self, mock_analyze):
        """首次收到素材文本时重新跑 gap 分析，readiness 应提升"""
        mock_analyze.return_value = {
            "gap_score": 0.3,
            "readiness": 0.7,
            "missing_evidence": [],
        }

        phase = GapPhase()
        state = PipelineState(thesis="测试命题")
        state.gap_analysis = {"gap_score": 0.8, "readiness": 0.2}
        state.gap_decision = "add_material"
        state.user_reply = "补充的素材"
        state.user_added_materials = ""  # 尚未存储

        config = PipelineConfig(interactive=False)
        result = phase.execute(state, config)

        # 应重新调用 analyze_gap
        mock_analyze.assert_called_once()
        # 素材应存入 state
        self.assertEqual(state.user_added_materials, "补充的素材")
        # 结果应包含新的 gap_analysis
        self.assertEqual(result.data.get("gap_analysis", {}).get("readiness"), 0.7)


class TestGapSkipsPromptWhenMaterialExists(unittest.TestCase):
    """已有素材时不再弹补充提示"""

    def test_gap_skips_prompt_when_material_already_added(self):
        """state.user_added_materials 非空时，不弹素材输入提示"""
        phase = GapPhase()
        state = PipelineState(thesis="测试命题")
        state.gap_analysis = {"gap_score": 0.8, "readiness": 0.2}
        state.gap_decision = "add_material"
        state.user_added_materials = "已有素材"

        config = PipelineConfig(interactive=False)
        result = phase.execute(state, config)

        # 不应返回 need_input，应直接继续
        self.assertNotEqual(result.status, "need_input",
                            "已有素材时不应再弹素材输入提示")


class TestGapDecisionSerialization(unittest.TestCase):
    """user_added_materials 应序列化到 to_dict()"""

    def test_to_dict_includes_user_added_materials(self):
        state = PipelineState()
        state.user_added_materials = "测试素材"
        d = state.to_dict()
        self.assertEqual(d.get("user_added_materials"), "测试素材")


if __name__ == "__main__":
    unittest.main()
