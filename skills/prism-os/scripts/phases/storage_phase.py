"""Phase 6: 数据持久化"""
from .base import Phase, PhaseResult, PipelineState, PipelineConfig


class StoragePhase(Phase):
    """Phase 6: 写入 topic_log.yaml"""

    @property
    def name(self) -> str:
        return "storage"

    def should_run(self, state: PipelineState, config: PipelineConfig) -> bool:
        return config.include_phase_4_8 and bool(state.candidates)

    def execute(self, state: PipelineState, config: PipelineConfig) -> PhaseResult:
        from storage import append_log
        try:
            log_entry = {
                "thesis": state.thesis,
                "candidates_count": len(state.candidates),
                "entropy_score": state.gateway.get("entropy_score", 0) if state.gateway else 0,
                "candidates": [{"title": c.get("title", ""), "dimension": c.get("dimension", "")} for c in state.candidates[:5]],
                "ccos_outline": state.ccos_outline,
            }
            result = append_log(log_entry)
            return PhaseResult(status="success", data={"storage_result": result})
        except Exception as e:
            return PhaseResult(status="success", data={}, message=str(e))

    def display_result(self, result: PhaseResult, state: PipelineState) -> None:
        import sys
        count = len(state.candidates) if state.candidates else 0
        cumulative = result.data.get("storage_result", {}).get("cumulative_count", "?")
        print(f"[Phase 6] 存储: topic_log.yaml cumulative_count={cumulative}（+1）", file=sys.stderr)
