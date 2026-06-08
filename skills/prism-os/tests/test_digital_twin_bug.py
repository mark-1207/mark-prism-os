"""数字分身 bug 修复测试：cognitive_outline._load_authorial_identity 不应抛异常"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_load_authorial_identity_no_crash():
    """_load_authorial_identity 应返回有效结果，不抛 bad operand type"""
    from cognitive_outline import _load_authorial_identity
    result = _load_authorial_identity()
    assert isinstance(result, dict)
    assert "thinking_pattern" in result
    assert "dimension_weights" in result
    assert "style_keywords" in result


def test_load_log_with_bad_limit():
    """load_log 传入非 int limit 应 fallback 到默认 10，不崩"""
    from storage import load_log
    # 传空字符串应该不崩
    result = load_log(limit="")
    assert isinstance(result, list)

    # 传 None 应该不崩
    result = load_log(limit=None)
    assert isinstance(result, list)

    # 传负数应该不崩
    result = load_log(limit=-1)
    assert isinstance(result, list)


def test_learn_thinking_pattern_default():
    """learn_thinking_pattern 默认参数应正常工作"""
    from cognitive_crack import learn_thinking_pattern
    result = learn_thinking_pattern()
    assert isinstance(result, dict)
    assert "thinking_pattern" in result
    assert "dimension_weights" in result


def test_twin_phase_returns_rejected_topics():
    """TwinPhase.execute 应返回 twin_rejected 字段"""
    from phases.twin import TwinPhase
    from phases.base import PipelineState, PipelineConfig

    phase = TwinPhase()
    state = PipelineState(
        thesis="测试命题",
        candidates=[{"title": "测试标题1", "dimension": "reversal"}],
    )
    config = PipelineConfig()
    result = phase.execute(state, config)
    assert "twin_rejected" in result.data
    assert isinstance(result.data["twin_rejected"], list)


def test_twin_phase_panic_on_error():
    """panic_on_error=True 时，learn_thinking_pattern 失败应 raise"""
    from phases.twin import TwinPhase
    from phases.base import PipelineState, PipelineConfig

    phase = TwinPhase()
    state = PipelineState(
        thesis="测试命题",
        candidates=[{"title": "测试标题1", "dimension": "reversal"}],
    )
    config = PipelineConfig(panic_on_error=True)

    # 模拟 learn_thinking_pattern 失败
    import cognitive_crack
    original = cognitive_crack.learn_thinking_pattern
    cognitive_crack.learn_thinking_pattern = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("mock failure"))
    try:
        with pytest.raises(RuntimeError, match="mock failure"):
            phase.execute(state, config)
    finally:
        cognitive_crack.learn_thinking_pattern = original
