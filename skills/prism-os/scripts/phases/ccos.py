"""Phase 4.5: CCOS 大纲生成 + 决策点 2（审核）"""
from .base import Phase, PhaseResult, PipelineState, PipelineConfig
from prism_os import _format_ccos_review
import sys


class CCOSPhase(Phase):
    """Phase 4.5: CCOS v2.0 认知推进流大纲生成"""

    @property
    def name(self) -> str:
        return "ccos"

    def should_run(self, state: PipelineState, config: PipelineConfig) -> bool:
        return config.include_phase_4_8 and state.selected_candidate is not None

    def execute(self, state: PipelineState, config: PipelineConfig) -> PhaseResult:
        from cognitive_outline import cognitive_outline_workflow, generate_dual_platform_outline

        # 如果有用户回复，处理审核决定
        if state.user_reply and state.ccos_outline:
            return self._handle_user_reply(state, config)

        title = state.selected_candidate.get("title", "")
        dimension = state.selected_candidate.get("dimension", "")

        try:
            if state.platform == "both":
                ccos_result = generate_dual_platform_outline(title, dimension)
            else:
                ccos_result = cognitive_outline_workflow(title, dimension, state.platform)
        except Exception as e:
            state.ccos_failed = True
            return PhaseResult(status="success", data={"ccos_outline": None}, message=str(e))

        # 决策点 2：CCOS 审核
        if config.interactive and not config.skip_ccos_review:
            display = _format_ccos_review(ccos_result, title, state.platform)
            prompt = display + "\n请选择：\n  [c] 继续 (使用此大纲)\n  [r] 重新生成\n  [q] 退出"
            return PhaseResult(
                status="need_input",
                data={"ccos_outline": ccos_result, "ccos_review_pending": True},
                prompt=prompt,
                input_type="ccos_review",
            )

        return PhaseResult(status="success", data={
            "ccos_outline": ccos_result,
            "ccos_review_passed": True,
        })

    def _handle_user_reply(self, state: PipelineState, config: PipelineConfig) -> PhaseResult:
        """处理用户对 CCOS 审核的回复"""
        reply = state.user_reply.strip().lower()

        if reply == "q":
            return PhaseResult(
                status="rejected",
                data={"ccos_outline": state.ccos_outline, "ccos_review_passed": False},
                message="用户拒绝 CCOS 大纲",
            )

        # c / "" / 其他：默认通过
        return PhaseResult(status="success", data={
            "ccos_outline": state.ccos_outline,
            "ccos_review_passed": True,
        })

    def display_result(self, result: PhaseResult, state: PipelineState) -> None:
        import sys
        if result.status == "rejected":
            print(f"[Phase 4.5] CCOS 未通过: {result.message}", file=sys.stderr)
        elif result.status == "need_input":
            print(result.prompt, file=sys.stderr)
        else:
            outline = result.data.get("ccos_outline")
            if outline is None:
                print(f"[Phase 4.5] CCOS: 生成失败（{result.message or 'outline=None'}）", file=sys.stderr)
                print(f"        ⚠️ 后续流程继续，但 narrate 不会执行", file=sys.stderr)
            else:
                结构 = outline.get("主结构", "")
                推进 = outline.get("推进方式", "")
                立场 = outline.get("内容立场", "")
                print(f"[Phase 4.5] CCOS: 已生成（{结构} / {推进}）", file=sys.stderr)
                if 立场:
                    print(f"        立场: {立场[:40]}", file=sys.stderr)
                print(f"        └─ 决策点 2 等待审核", file=sys.stderr)
