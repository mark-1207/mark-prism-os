"""Phase 8: 认知裂缝捕捉"""
from .base import Phase, PhaseResult, PipelineState, PipelineConfig


class CognitiveCrackPhase(Phase):
    """Phase 8: 认知裂缝捕捉 — 检测信息源中的认知裂缝"""

    @property
    def name(self) -> str:
        return "cognitive_crack"

    def should_run(self, state: PipelineState, config: PipelineConfig) -> bool:
        return config.include_crack_capture and state.intent is not None

    def execute(self, state: PipelineState, config: PipelineConfig) -> PhaseResult:
        from cognitive_crack import detect_cognitive_crack
        from crack_queue import CrackQueue

        try:
            # 检测裂缝
            crack_result = detect_cognitive_crack("", state.thesis)

            # 入队
            queue_ids = []
            if crack_result.get("has_crack"):
                queue = CrackQueue()
                entry = {
                    "source": "pipeline",
                    "content_summary": state.thesis,
                    "crack_type": crack_result.get("crack_type", ""),
                    "consensus": crack_result.get("consensus", ""),
                    "reality": crack_result.get("reality", ""),
                    "confidence": crack_result.get("confidence", 0),
                    "suggested_topic": crack_result.get("suggested_topic", ""),
                }
                queue.add(entry)
                queue_ids.append(crack_result.get("suggested_topic", ""))

            return PhaseResult(status="success", data={
                "crack_detections": [crack_result],
                "crack_queue_ids": queue_ids,
            })
        except Exception as e:
            if config.panic_on_error:
                raise
            return PhaseResult(status="skipped", data={}, message=str(e))

    def display_result(self, result: PhaseResult, state: PipelineState) -> None:
        import sys
        detections = result.data.get("crack_detections", [])
        queue_ids = result.data.get("crack_queue_ids", [])
        if result.status == "skipped":
            print(f"[Phase 8] 裂缝: 跳过（{result.message}）", file=sys.stderr)
        else:
            has_crack = any(d.get("has_crack") for d in detections)
            print(f"[Phase 8] 裂缝: {'有' if has_crack else '无'}, 入队={len(queue_ids)}", file=sys.stderr)
