"""Voice Calculator - Offline English speech-to-addition desktop application."""

from voice_calculator.decision import (
    DecisionConfig,
    DecisionReason,
    DecisionResult,
    DecisionType,
    SafetyDecisionEngine,
    evaluate_candidate,
)
from voice_calculator.pipeline import AudioPipeline, PipelineResult, PipelineStatus

__version__ = "0.1.0"

__all__ = [
    "AudioPipeline",
    "DecisionConfig",
    "DecisionReason",
    "DecisionResult",
    "DecisionType",
    "PipelineResult",
    "PipelineStatus",
    "SafetyDecisionEngine",
    "evaluate_candidate",
    "__version__",
]

