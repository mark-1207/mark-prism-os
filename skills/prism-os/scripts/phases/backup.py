"""Phase 1.5: 备选检查"""
from .base import Phase, PhaseResult, PipelineState, PipelineConfig


class BackupCheckPhase(Phase):
    """Phase 1.5: 检查是否有同主题草稿"""

    @property
    def name(self) -> str:
        return "backup_check"

    def should_run(self, state: PipelineState, config: PipelineConfig) -> bool:
        return state.intent is not None and state.intent.get("trigger")

    def execute(self, state: PipelineState, config: PipelineConfig) -> PhaseResult:
        from assassin import check_related_backups
        try:
            backups = check_related_backups(state.thesis)
            return PhaseResult(status="success", data={"backup_matches": backups})
        except Exception as e:
            return PhaseResult(status="success", data={"backup_matches": []}, message=str(e))

    def display_result(self, result: PhaseResult, state: PipelineState) -> None:
        import sys
        matches = result.data.get("backup_matches", [])
        if matches:
            print(f"[Phase 1.5] 备选: {len(matches)} 个匹配", file=sys.stderr)
        else:
            print(f"[Phase 1.5] 备选: 0 个匹配", file=sys.stderr)
