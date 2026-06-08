"""Pipeline 重构测试：验证 Phase 串联能跑通"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_pipeline_phases_count():
    """FullPrismPipeline 应有 11 个 Phase"""
    from phases import FullPrismPipeline, PipelineConfig
    pipeline = FullPrismPipeline(PipelineConfig())
    assert len(pipeline.phases()) == 12


def test_pipeline_state_to_dict():
    """PipelineState.to_dict 应返回 run_prism_os 兼容格式"""
    from phases import PipelineState
    state = PipelineState(
        thesis="测试",
        phase="complete",
        status="success",
        intent={"trigger": True},
        ccos_outline={"wechat_cognitive_outline": {}},
    )
    d = state.to_dict()
    assert d["phase"] == "complete"
    assert d["status"] == "success"
    assert d["intent"]["trigger"] is True
    assert "ccos_outline" in d


def test_pipeline_config_defaults():
    """PipelineConfig 默认值应正确"""
    from phases import PipelineConfig
    config = PipelineConfig()
    assert config.platform == "both"
    assert config.interactive is True
    assert config.skip_gateway is False
    assert config.include_phase_4_8 is True
    assert config.include_narrate is True
    # PRD 重构新增字段
    assert config.prism_flavor == "prd"
    assert config.include_logic is True
    assert config.include_assassin is True
    assert config.include_digital_twin is True
    assert config.include_crack_capture is True
    assert config.gap_auto_reject_threshold == 0.3


def test_pipeline_state_new_fields():
    """PipelineState 新增字段默认值"""
    from phases import PipelineState
    state = PipelineState()
    assert state.assassin_reversals == []
    assert state.assassin_topology == {}
    assert state.digital_twin_result == {}
    assert state.crack_detections == []
    assert state.crack_queue_ids == []


def test_intent_phase_rejects_small_talk():
    """IntentPhase 应拒绝闲聊输入"""
    from phases import IntentPhase, PipelineState, PipelineConfig
    phase = IntentPhase()
    state = PipelineState(thesis="你好")
    config = PipelineConfig()
    result = phase.execute(state, config)
    assert result.status == "rejected"


def test_intent_phase_accepts_writing_intent():
    """IntentPhase 应接受写作意图"""
    from phases import IntentPhase, PipelineState, PipelineConfig
    phase = IntentPhase()
    state = PipelineState(thesis="我想写一篇关于AI的文章")
    config = PipelineConfig()
    result = phase.execute(state, config)
    assert result.status == "success"
    assert result.data.get("trigger") is True
