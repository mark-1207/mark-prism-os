"""Phase 0: 意图识别"""
from .base import Phase, PhaseResult, PipelineState, PipelineConfig


class IntentPhase(Phase):
    """Phase 0: 意图识别 — 判断输入是否触发 PRISM-OS"""

    @property
    def name(self) -> str:
        return "intent"

    def should_run(self, state: PipelineState, config: PipelineConfig) -> bool:
        return True  # 永远跑

    def execute(self, state: PipelineState, config: PipelineConfig) -> PhaseResult:
        from prism_os import classify_intent
        intent = classify_intent(state.thesis)

        if not intent["trigger"]:
            return PhaseResult(
                status="rejected",
                data=intent,
                message="未触发 PRISM-OS（需要写作/选题相关意图）",
            )

        return PhaseResult(status="success", data=intent)

    def display_result(self, result: PhaseResult, state: PipelineState) -> None:
        import sys
        trigger = result.data.get("trigger", False)
        conf = result.data.get("confidence", 0)
        reason = result.data.get("reason", "")
        if result.status == "rejected":
            print(f"[Phase 0] 意图: trigger={trigger}, conf={conf:.2f}, 原因:{reason}", file=sys.stderr)
        else:
            print(f"[Phase 0] 意图: trigger={trigger}, conf={conf:.2f}, 原因:{reason}", file=sys.stderr)
