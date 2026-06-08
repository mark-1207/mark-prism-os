"""Phase 7: 刺客机制"""
from .base import Phase, PhaseResult, PipelineState, PipelineConfig


class AssassinPhase(Phase):
    """Phase 7: 刺客机制 — 扫描历史爆款并生成反转命题"""

    @property
    def name(self) -> str:
        return "assassin"

    def should_run(self, state: PipelineState, config: PipelineConfig) -> bool:
        return config.include_assassin and state.candidates is not None

    def execute(self, state: PipelineState, config: PipelineConfig) -> PhaseResult:
        from assassin import assassin_mechanism
        try:
            result = assassin_mechanism(
                historical_topics=config.history_topics,
                entities=None,
                relations=None,
            )
            return PhaseResult(status="success", data=result)
        except Exception as e:
            if config.panic_on_error:
                raise
            return PhaseResult(status="skipped", data={}, message=str(e))

    def display_result(self, result: PhaseResult, state: PipelineState) -> None:
        import sys
        reversals = result.data.get("reversals", [])
        topology = result.data.get("topology", {})
        if result.status == "skipped":
            print(f"[Phase 7] 刺客: 跳过（{result.message}）", file=sys.stderr)
        else:
            print(f"[Phase 7] 刺客: {len(reversals)} 个反转, 拓扑={'有' if topology else '无'}", file=sys.stderr)
