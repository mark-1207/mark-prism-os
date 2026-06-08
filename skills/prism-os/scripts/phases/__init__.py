"""PRISM-OS Pipeline Phase 模块"""

from .base import Phase, PhaseResult, PipelineState, PipelineConfig, PrismPipeline
from .intent import IntentPhase
from .gateway import GatewayPhase
from .backup import BackupCheckPhase
from .prism import PrismPhase
from .reality import RealityPhase
from .twin import TwinPhase
from .ccos import CCOSPhase
from .gap import GapPhase
from .logic import LogicPhase
from .storage_phase import StoragePhase
from .narrate import NarratePhase
from .assassin_phase import AssassinPhase


class FullPrismPipeline(PrismPipeline):
    """完整 PRISM-OS Pipeline：按 PRD 分层"""

    def phases(self) -> list:
        phases = [
            # V1.0 MVP 核心闭环（必经）
            IntentPhase(),
            GatewayPhase(),
            BackupCheckPhase(),
            PrismPhase(),
            RealityPhase(),
            # V1.5 扩展（必经）
            CCOSPhase(),
            GapPhase(),
        ]
        # V2.0 进化（可选，默认开）
        if self.config.include_logic:
            phases.append(LogicPhase())
        # V3.0 刺客（可选，默认开）
        if self.config.include_assassin:
            phases.append(AssassinPhase())
        # V4.0 数字分身（可选，默认开，从 V1.0 移过来）
        if self.config.include_digital_twin:
            phases.append(TwinPhase())
        # 必经
        phases += [
            StoragePhase(),
            NarratePhase(),
        ]
        return phases


__all__ = [
    "Phase", "PhaseResult", "PipelineState", "PipelineConfig", "PrismPipeline",
    "FullPrismPipeline",
    "IntentPhase", "GatewayPhase", "BackupCheckPhase", "PrismPhase",
    "RealityPhase", "TwinPhase", "CCOSPhase", "GapPhase",
    "LogicPhase", "StoragePhase", "NarratePhase", "AssassinPhase",
]
