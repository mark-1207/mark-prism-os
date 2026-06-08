"""Phase 3.5: 数字分身筛选"""
from .base import Phase, PhaseResult, PipelineState, PipelineConfig
import sys


class TwinPhase(Phase):
    """Phase 3.5: 数字分身 — 思维特征加权筛选"""

    @property
    def name(self) -> str:
        return "twin"

    def should_run(self, state: PipelineState, config: PipelineConfig) -> bool:
        return bool(state.candidates)

    def execute(self, state: PipelineState, config: PipelineConfig) -> PhaseResult:
        from cognitive_crack import digital_twin_filter, learn_thinking_pattern

        # 不捕获异常 — panic 模式下异常会冒泡到 Pipeline.run()
        learn_result = learn_thinking_pattern(state.thesis)
        thinking_pattern = learn_result.get("thinking_pattern", "理性")

        twin_result = digital_twin_filter(state.candidates, thinking_pattern)
        selected = twin_result.get("selected_topics", [])
        rejected = twin_result.get("rejected_topics", [])

        return PhaseResult(status="success", data={
            "twin_learn": learn_result,
            "digital_twin": twin_result,
            "twin_selected": selected,
            "twin_rejected": rejected,
        })

    def display_result(self, result: PhaseResult, state: PipelineState) -> None:
        import sys
        selected = result.data.get("twin_selected", [])
        before = len(state.candidates) if state.candidates else 0
        after = len(selected)
        rejected = result.data.get("twin_rejected", [])
        if rejected:
            print(f"[Phase 3.5] 数字分身: {before}→{after} 候选（降权 {len(rejected)} 个）", file=sys.stderr)
            for r in rejected[:3]:
                topic = r.get("topic", "?")[:30]
                reason = r.get("rejection_reason", "?")
                print(f"        - \"{topic}\"（{reason}）", file=sys.stderr)
        else:
            print(f"[Phase 3.5] 数字分身: {before}→{after} 候选（无降权）", file=sys.stderr)
