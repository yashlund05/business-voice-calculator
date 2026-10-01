"""Voice Calculator - Offline English speech-to-addition desktop application."""

from voice_calculator.calculator import (
    Calculator,
    CalculatorError,
    HistoryEntry,
    InvalidValueError,
)
from voice_calculator.decision import (
    DecisionConfig,
    DecisionReason,
    DecisionResult,
    DecisionType,
    SafetyDecisionEngine,
    evaluate_candidate,
)
from voice_calculator.controller import (
    ControllerEvent,
    ControllerEventType,
    ListeningController,
)
from voice_calculator.gui import UIState, VoiceCalculatorApp
from voice_calculator.pipeline import AudioPipeline, PipelineResult, PipelineStatus

__version__ = "0.1.0"

__all__ = [
    "AudioPipeline",
    "Calculator",
    "CalculatorError",
    "ControllerEvent",
    "ControllerEventType",
    "DecisionConfig",
    "DecisionReason",
    "DecisionResult",
    "DecisionType",
    "HistoryEntry",
    "InvalidValueError",
    "ListeningController",
    "PipelineResult",
    "PipelineStatus",
    "SafetyDecisionEngine",
    "UIState",
    "VoiceCalculatorApp",
    "evaluate_candidate",
    "__version__",
]




