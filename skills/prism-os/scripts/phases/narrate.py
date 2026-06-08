"""Narrate: 内容生成"""
from .base import Phase, PhaseResult, PipelineState, PipelineConfig


class NarratePhase(Phase):
    """Narrate: 调用 _run_narrate 生成内容"""

    @property
    def name(self) -> str:
        return "narrate"

    def should_run(self, state: PipelineState, config: PipelineConfig) -> bool:
        return (config.include_narrate
                and state.status != "rejected"
                and state.ccos_outline is not None)

    def execute(self, state: PipelineState, config: PipelineConfig) -> PhaseResult:
        from prism_os import _run_narrate
        try:
            result = _run_narrate(state.thesis, state.platform)
            return PhaseResult(status="success", data=result)
        except Exception as e:
            return PhaseResult(status="failed", data={"error": str(e)}, message=str(e))

    def display_result(self, result: PhaseResult, state: PipelineState) -> None:
        import sys
        if result.status == "success":
            wc = result.data.get("word_count", 0)
            output_file = result.data.get("output_file", "")
            print(f"[Narrate] 内容生成: {wc} 字", file=sys.stderr)
            if output_file:
                print(f"        输出: {output_file}", file=sys.stderr)
        else:
            print(f"[Narrate] 生成失败: {result.message}", file=sys.stderr)
