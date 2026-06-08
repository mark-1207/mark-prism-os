"""PRISM-OS Pipeline 基础设施：Phase 基类 + Pipeline 状态 + 配置"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import sys


@dataclass
class PhaseResult:
    """Phase 执行结果"""
    status: str = "success"  # success / rejected / failed / skipped / need_input
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    # need_input 时的相关信息
    prompt: str = ""  # 展示给用户的提示
    input_type: str = ""  # clarification / title_select / ccos_review / gap_decision

    def to_dict(self) -> dict:
        d = {"status": self.status}
        if self.message:
            d["message"] = self.message
        d.update(self.data)
        return d


@dataclass
class PipelineState:
    """Pipeline 共享状态：Phase 间传递数据"""
    # 输入
    thesis: str = ""
    platform: str = "both"
    interactive: bool = True
    # Phase 输出
    intent: Optional[dict] = None
    gateway: Optional[dict] = None
    candidates: List[dict] = field(default_factory=list)
    selected_candidate: Optional[dict] = None
    user_selected_candidate: bool = False
    ccos_outline: Optional[dict] = None
    ccos_review_passed: bool = False
    gap_analysis: Optional[dict] = None
    gap_decision: Optional[str] = None
    logic_audit: List[dict] = field(default_factory=list)
    cognitive_journey: dict = field(default_factory=dict)
    storage_result: Optional[dict] = None
    narrate_result: Optional[dict] = None
    # 决策记录
    decisions: Dict[str, str] = field(default_factory=dict)
    # 阶段标记
    phase: str = "init"
    status: str = "running"
    # 用户回复（用于跨步骤传递）
    user_reply: str = ""
    current_phase_index: int = 0
    # 待用户输入的 prompt（need_input 时填充）
    _pending_prompt: str = ""
    _pending_input_type: str = ""
    # V3.0 刺客
    assassin_reversals: List[dict] = field(default_factory=list)
    assassin_topology: dict = field(default_factory=dict)
    # V4.0 数字分身
    digital_twin_result: dict = field(default_factory=dict)
    # V4.0 裂缝捕捉
    crack_detections: List[dict] = field(default_factory=list)
    crack_queue_ids: List[str] = field(default_factory=list)
    # CCOS 失败标记
    ccos_failed: bool = False

    def update_from_result(self, phase_name: str, result: 'PhaseResult') -> None:
        """根据 Phase 结果更新状态"""
        setter = getattr(self, f"_set_{phase_name}", None)
        if setter:
            setter(result)
        else:
            # 通用更新：把 result.data 里的 key 写到 state
            for k, v in result.data.items():
                if hasattr(self, k):
                    setattr(self, k, v)

    def _set_intent(self, result: 'PhaseResult') -> None:
        self.intent = result.data

    def _set_gateway(self, result: 'PhaseResult') -> None:
        self.gateway = result.data

    def _set_prism(self, result: 'PhaseResult') -> None:
        self.candidates = result.data.get("candidates", [])
        if "selected_candidate" in result.data:
            self.selected_candidate = result.data["selected_candidate"]
            self.user_selected_candidate = result.data.get("user_selected_candidate", False)

    def _set_ccos(self, result: 'PhaseResult') -> None:
        self.ccos_outline = result.data.get("ccos_outline")
        self.ccos_review_passed = result.data.get("ccos_review_passed", False)

    def _set_gap(self, result: 'PhaseResult') -> None:
        self.gap_analysis = result.data.get("gap_analysis")
        self.gap_decision = result.data.get("gap_decision")

    def _set_logic(self, result: 'PhaseResult') -> None:
        self.logic_audit = result.data.get("logic_audit", [])
        self.cognitive_journey = result.data.get("cognitive_journey", {})

    def _set_narrate(self, result: 'PhaseResult') -> None:
        self.narrate_result = result.data

    def to_dict(self) -> dict:
        """转为 run_prism_os 兼容的 dict 格式"""
        d = {
            "phase": self.phase,
            "status": self.status,
            "user_input": self.thesis,
        }
        if self.ccos_failed:
            d["ccos_failed"] = True
        if self.intent:
            d["intent"] = self.intent
        if self.gateway:
            d["gateway"] = self.gateway
        if self.candidates:
            d["candidates"] = self.candidates
        if self.selected_candidate:
            d["selected_candidate"] = self.selected_candidate
            d["user_selected_candidate"] = self.user_selected_candidate
        if self.ccos_outline:
            d["ccos_outline"] = self.ccos_outline
        if self.ccos_review_passed:
            d["ccos_review_passed"] = True
        if self.gap_analysis:
            d["gap_analysis"] = self.gap_analysis
        if self.gap_decision:
            d["gap_decision"] = self.gap_decision
        if self.logic_audit:
            d["logic_audit"] = self.logic_audit
        if self.cognitive_journey:
            d["cognitive_journey"] = self.cognitive_journey
        if self.narrate_result:
            d["narrate"] = self.narrate_result
        return d


@dataclass
class PipelineConfig:
    """Pipeline 配置（来自 CLI 参数）"""
    platform: str = "both"
    interactive: bool = True
    skip_gateway: bool = False
    skip_ccos_review: bool = False
    include_phase_4_8: bool = True
    include_narrate: bool = True
    user_clarification: Optional[str] = None
    history_topics: List[str] = field(default_factory=list)
    from_queue: bool = False
    panic_on_error: bool = False
    dry_run: bool = False
    # V1.0/PRD 棱镜 4 维口味（"prd" 或 "legacy"）
    prism_flavor: str = "prd"
    # V2.0 逻辑审计
    include_logic: bool = True
    # V3.0 刺客机制
    include_assassin: bool = True
    # V4.0 数字分身
    include_digital_twin: bool = True
    # V4.0 裂缝捕捉
    include_crack_capture: bool = True
    # Gap < threshold 硬中断
    gap_auto_reject_threshold: float = 0.3


class Phase(ABC):
    """Phase 基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Phase 名称（用于日志和状态标记）"""

    @abstractmethod
    def should_run(self, state: PipelineState, config: PipelineConfig) -> bool:
        """判断是否需要执行"""

    @abstractmethod
    def execute(self, state: PipelineState, config: PipelineConfig) -> PhaseResult:
        """执行 Phase，返回结果"""

    def display_result(self, result: PhaseResult, state: PipelineState) -> None:
        """展示结果到 stderr（子类可覆盖）"""
        pass


class PrismPipeline:
    """PRISM-OS 流水线：串联所有 Phase"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.state = PipelineState(
            platform=config.platform,
            interactive=config.interactive,
        )

    def phases(self) -> List[Phase]:
        """返回有序 Phase 列表（子类可覆盖）"""
        return []

    def run(self, thesis: str, resume_state: PipelineState = None) -> PipelineState:
        """执行完整流水线，支持 need_input 暂停和 resume"""
        if resume_state is not None:
            self.state = resume_state
        self.state.thesis = thesis
        phases = self.phases()

        for i in range(self.state.current_phase_index, len(phases)):
            phase = phases[i]
            if not phase.should_run(self.state, self.config):
                continue

            self.state.phase = phase.name
            self.state.current_phase_index = i

            try:
                result = phase.execute(self.state, self.config)
            except Exception as e:
                if self.config.panic_on_error:
                    raise
                # 非 panic 模式：打印 warning 并跳过
                import sys
                print(f"[WARNING] Phase {phase.name} 失败: {e}", file=sys.stderr)
                result = PhaseResult(status="skipped", data={}, message=str(e))

            # 更新状态
            self.state.update_from_result(phase.name, result)
            phase.display_result(result, self.state)

            # dry_run：每个 Phase 后暂停让用户看输出
            if self.config.dry_run and result.status not in ("need_input", "rejected"):
                import sys
                print(f"[DRY-RUN] Phase {phase.name} 完成。按 Enter 继续...", file=sys.stderr)
                try:
                    sys.stdin.readline()
                except (EOFError, KeyboardInterrupt):
                    sys.exit(2)

            # need_input：暂停，把 prompt 展示到 stderr，返回状态
            if result.status == "need_input":
                self.state.status = "need_input"
                # 把 prompt 也写入 state 方便外部读取
                self.state._pending_prompt = result.prompt
                self.state._pending_input_type = result.input_type
                # 确保 display_result 也被调用展示 prompt
                return self.state

            # 检查是否被拒绝
            if result.status == "rejected":
                self.state.status = "rejected"
                return self.state

        self.state.phase = "complete"
        if self.state.ccos_failed:
            self.state.status = "partial_success"
        else:
            self.state.status = "success"
        return self.state
