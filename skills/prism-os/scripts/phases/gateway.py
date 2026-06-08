"""Phase 1: 苏格拉底网关"""
from .base import Phase, PhaseResult, PipelineState, PipelineConfig
import sys


class GatewayPhase(Phase):
    """Phase 1: 苏格拉底网关 — 熵值判断 + 7 类追问"""

    @property
    def name(self) -> str:
        return "gateway"

    def should_run(self, state: PipelineState, config: PipelineConfig) -> bool:
        return not config.skip_gateway

    def execute(self, state: PipelineState, config: PipelineConfig) -> PhaseResult:
        from socratic_gateway import socratic_gateway

        # 如果有用户回复，用回复重新跑网关
        if state.user_reply:
            gateway_result = socratic_gateway(
                state.thesis,
                user_clarification=state.user_reply,
            )
            # 无论结果如何都继续（用户已给出答复）
            return PhaseResult(status="success", data=gateway_result)

        gateway_result = socratic_gateway(
            state.thesis,
            user_clarification=config.user_clarification,
        )

        if gateway_result["status"] == "blocked":
            return PhaseResult(
                status="rejected",
                data=gateway_result,
                message="命题熵值过低，被拦截",
            )

        # need_clarification：返回 need_input，让 Pipeline 暂停
        if gateway_result["status"] == "need_clarification" and config.interactive:
            prompt = self._format_clarification_prompt(gateway_result)
            return PhaseResult(
                status="need_input",
                data=gateway_result,
                prompt=prompt,
                input_type="clarification",
            )

        return PhaseResult(status="success", data=gateway_result)

    def _format_clarification_prompt(self, gateway_result: dict) -> str:
        """格式化苏格拉底问题展示"""
        questions = gateway_result.get("questions", [])
        directions = gateway_result.get("directions", [])

        lines = ["\n━━━ 苏格拉底追问 ━━━"]
        for i, q in enumerate(questions, 1):
            lines.append(f"  {i}. {q}")
        if directions:
            lines.append("\n可选方向（参考）：")
            for i, d in enumerate(directions, 1):
                lines.append(f"  {i}. {d}")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("请直接回答上述问题（也可以 skip 跳过）:")
        return "\n".join(lines)

    def display_result(self, result: PhaseResult, state: PipelineState) -> None:
        import sys
        if result.status == "rejected":
            print(f"[Phase 1] 被拦截: {result.message}", file=sys.stderr)
        elif result.status == "need_input":
            print(result.prompt, file=sys.stderr)
        else:
            status = result.data.get("status", "")
            score = result.data.get("combined_score", 0)
            hkr = result.data.get("hkr", {})
            hkr_avg = hkr.get("hkr_avg", 0)
            print(f"[Phase 1] 网关: status={status}, score={score:.2f}, HKR={hkr_avg:.2f}", file=sys.stderr)
            if status == "need_clarification":
                print(f"        └─ 决策点 0.5 触发（need_clarification）", file=sys.stderr)
