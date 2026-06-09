"""Gap 警告模式测试：readiness < threshold 时展示警告但不中断"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_gap_low_readiness_shows_warning():
    """readiness < 0.3 时展示警告"""
    from phases.gap import GapPhase
    from phases.base import PipelineState, PipelineConfig

    phase = GapPhase()
    state = PipelineState(thesis="测试", ccos_outline={"主结构": "测试"})
    config = PipelineConfig(interactive=True, gap_auto_reject_threshold=0.3)

    # mock analyze_gap 返回低就绪度
    with patch("gap_analysis.analyze_gap") as mock_analyze:
        mock_analyze.return_value = {
            "gap_score": 0.8,
            "readiness": 0.1,
            "missing_evidence": ["证据1", "证据2"],
        }
        result = phase.execute(state, config)

    # 应返回 need_input（不是 rejected）
    assert result.status == "need_input"
    # prompt 应包含警告
    assert "⚠️" in result.prompt
    assert "就绪度" in result.prompt


def test_gap_low_readiness_still_shows_decision():
    """readiness < 0.3 时仍展示决策点 3"""
    from phases.gap import GapPhase
    from phases.base import PipelineState, PipelineConfig

    phase = GapPhase()
    state = PipelineState(thesis="测试", ccos_outline={"主结构": "测试"})
    config = PipelineConfig(interactive=True, gap_auto_reject_threshold=0.3)

    with patch("gap_analysis.analyze_gap") as mock_analyze:
        mock_analyze.return_value = {
            "gap_score": 0.8,
            "readiness": 0.05,
            "missing_evidence": ["证据1"],
        }
        result = phase.execute(state, config)

    # 应返回 need_input
    assert result.status == "need_input"
    assert result.input_type == "gap_decision"
    # prompt 应包含决策选项
    assert "补充素材" in result.prompt
    assert "直接生成" in result.prompt


def test_gap_user_can_choose_go_narrate_even_low_readiness():
    """用户选择"直接生成"时继续（即使 readiness 低）"""
    from phases.gap import GapPhase
    from phases.base import PipelineState, PipelineConfig

    phase = GapPhase()
    state = PipelineState(
        thesis="测试",
        ccos_outline={"主结构": "测试"},
        gap_analysis={"gap_score": 0.8, "readiness": 0.05, "missing_evidence": []},
        user_reply="3",  # 直接生成
    )
    config = PipelineConfig(interactive=True, gap_auto_reject_threshold=0.3)

    result = phase._handle_user_reply(state)

    # 应返回 success + go_narrate
    assert result.status == "success"
    assert result.data.get("gap_decision") == "go_narrate"


def test_gap_high_readiness_no_warning():
    """readiness >= 0.3 时无警告"""
    from phases.gap import GapPhase
    from phases.base import PipelineState, PipelineConfig

    phase = GapPhase()
    state = PipelineState(thesis="测试", ccos_outline={"主结构": "测试"})
    config = PipelineConfig(interactive=True, gap_auto_reject_threshold=0.3)

    with patch("gap_analysis.analyze_gap") as mock_analyze:
        mock_analyze.return_value = {
            "gap_score": 0.3,
            "readiness": 0.5,
            "missing_evidence": [],
        }
        result = phase.execute(state, config)

    # prompt 不应包含警告
    assert "⚠️" not in result.prompt
