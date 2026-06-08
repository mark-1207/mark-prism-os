"""Phase 5: 逻辑压力测试 + 认知旅程"""
from .base import Phase, PhaseResult, PipelineState, PipelineConfig


class LogicPhase(Phase):
    """Phase 5: 逻辑压力测试 + 认知旅程"""

    @property
    def name(self) -> str:
        return "logic"

    def should_run(self, state: PipelineState, config: PipelineConfig) -> bool:
        return config.include_phase_4_8 and bool(state.candidates)

    def execute(self, state: PipelineState, config: PipelineConfig) -> PhaseResult:
        from logic_pressure import logic_pressure
        try:
            lp_result = logic_pressure(state.candidates, config.history_topics)
            return PhaseResult(status="success", data={
                "logic_audit": lp_result.get("logic_audit", []),
                "cognitive_journey": lp_result.get("cognitive_journey", {}),
            })
        except Exception as e:
            return PhaseResult(status="success", data={
                "logic_audit": [],
                "cognitive_journey": {},
            }, message=str(e))

    def display_result(self, result: PhaseResult, state: PipelineState) -> None:
        import sys
        audit = result.data.get("logic_audit", [])
        journey = result.data.get("cognitive_journey", {})
        avg_dist = journey.get("avg_distance", 0)
        print(f"[Phase 5] 逻辑: {len(audit)} 条审计, 认知旅程 avg_distance={avg_dist:.2f}", file=sys.stderr)
