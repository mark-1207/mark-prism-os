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


class FullPrismPipeline(PrismPipeline):
    """完整 PRISM-OS Pipeline：串联所有 Phase"""

    def phases(self) -> list:
        return [
            IntentPhase(),
            GatewayPhase(),
            BackupCheckPhase(),
            PrismPhase(),
            RealityPhase(),
            TwinPhase(),
            CCOSPhase(),
            GapPhase(),
            LogicPhase(),
            StoragePhase(),
            NarratePhase(),
        ]


__all__ = [
    "Phase", "PhaseResult", "PipelineState", "PipelineConfig", "PrismPipeline",
    "FullPrismPipeline",
    "IntentPhase", "GatewayPhase", "BackupCheckPhase", "PrismPhase",
    "RealityPhase", "TwinPhase", "CCOSPhase", "GapPhase",
    "LogicPhase", "StoragePhase", "NarratePhase",
]
