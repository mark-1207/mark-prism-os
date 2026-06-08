"""Phase 4.6: Gap 分析 + 决策点 3"""
from .base import Phase, PhaseResult, PipelineState, PipelineConfig
import sys


class GapPhase(Phase):
    """Phase 4.6: 素材就绪度分析 + 用户决策"""

    @property
    def name(self) -> str:
        return "gap"

    def should_run(self, state: PipelineState, config: PipelineConfig) -> bool:
        return config.include_phase_4_8 and state.ccos_outline is not None

    def execute(self, state: PipelineState, config: PipelineConfig) -> PhaseResult:
        from gap_analysis import analyze_gap

        # 如果有用户回复，处理 Gap 决策
        if state.user_reply and state.gap_analysis:
            return self._handle_user_reply(state)

        try:
            gap_result = analyze_gap(state.thesis, "")
        except Exception as e:
            return PhaseResult(status="success", data={"gap_analysis": None}, message=str(e))

        # 决策点 3
        if config.interactive:
            prompt = self._format_gap_prompt(gap_result)
            return PhaseResult(
                status="need_input",
                data={"gap_analysis": gap_result, "gap_decision": "pending"},
                prompt=prompt,
                input_type="gap_decision",
            )

        return PhaseResult(status="success", data={
            "gap_analysis": gap_result,
            "gap_decision": "auto_continue",
        })

    def _format_gap_prompt(self, gap_result: dict) -> str:
        """格式化 Gap 决策提示"""
        score = gap_result.get("gap_score", 0)
        readiness = gap_result.get("readiness", 0)
        missing = gap_result.get("missing_evidence", [])
        lines = [
            "\n━━━ Gap 决策 ━━━",
            f"  score: {score:.2f}（{'较大' if score > 0.5 else '较小'}）",
            f"  readiness: {readiness:.0%}",
        ]
        if missing:
            lines.append("  缺失证据:")
            for i, evidence in enumerate(missing[:5], 1):
                lines.append(f"    {i}. {evidence}")
        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━",
            "请选择: [1] 补充素材 [2] 调整大纲 [3] 直接生成 [q] 退出",
        ])
        return "\n".join(lines)

    def _handle_user_reply(self, state: PipelineState) -> PhaseResult:
        """处理用户对 Gap 决策的回复"""
        reply = state.user_reply.strip()
        gap_result = state.gap_analysis

        if reply.lower() == "q":
            return PhaseResult(
                status="rejected",
                data={"gap_analysis": gap_result, "gap_decision": "exit"},
                message="用户在决策点 3 退出",
            )

        decision_map = {
            "1": "add_material",
            "2": "restart_ccos",
            "3": "go_narrate",
        }
        decision = decision_map.get(reply, "go_narrate")

        return PhaseResult(status="success", data={
            "gap_analysis": gap_result,
            "gap_decision": decision,
        })

    def display_result(self, result: PhaseResult, state: PipelineState) -> None:
        import sys
        if result.status == "need_input":
            print(result.prompt, file=sys.stderr)
        elif result.status == "rejected":
            print(f"[Phase 4.6] {result.message}", file=sys.stderr)
        else:
            ga = result.data.get("gap_analysis", {})
            decision = result.data.get("gap_decision", "")
            if ga:
                score = ga.get("gap_score", 0)
                readiness = ga.get("readiness", 0)
                missing = ga.get("missing_evidence", [])
                missing_count = len(missing)
                print(f"[Phase 4.6] Gap: score={score:.2f}（{'较大' if score > 0.5 else '较小'}）, 就绪度={readiness:.0%}, 缺失 {missing_count} 个证据", file=sys.stderr)
                print(f"        └─ 决策点 3 等待决策", file=sys.stderr)
