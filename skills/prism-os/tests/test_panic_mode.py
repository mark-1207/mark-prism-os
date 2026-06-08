"""panic 模式测试：Phase 失败时 panic 而不是静默降级"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_panic_mode_exits_on_phase_error():
    """panic_on_error=True 时 Phase 失败应抛异常"""
    from phases import FullPrismPipeline, PipelineConfig, PipelineState, Phase, PhaseResult

    class FailPhase(Phase):
        @property
        def name(self):
            return "fail"

        def should_run(self, state, config):
            return True

        def execute(self, state, config):
            raise RuntimeError("intentional failure")

    class TestPipeline(FullPrismPipeline):
        def phases(self):
            return [FailPhase()]

    config = PipelineConfig(panic_on_error=True)
    pipeline = TestPipeline(config)
    with pytest.raises(RuntimeError, match="intentional failure"):
        pipeline.run("测试")


def test_no_panic_silently_skips():
    """panic_on_error=False 时 Phase 失败应静默跳过"""
    from phases import FullPrismPipeline, PipelineConfig, PipelineState, Phase, PhaseResult

    class FailPhase(Phase):
        @property
        def name(self):
            return "fail"

        def should_run(self, state, config):
            return True

        def execute(self, state, config):
            raise RuntimeError("intentional failure")

    class TestPipeline(FullPrismPipeline):
        def phases(self):
            return [FailPhase()]

    config = PipelineConfig(panic_on_error=False)
    pipeline = TestPipeline(config)
    state = pipeline.run("测试")
    assert state.status == "success"  # 静默跳过后继续到 complete
