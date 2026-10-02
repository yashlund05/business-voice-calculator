"""ASR (Automatic Speech Recognition) base definitions and engine implementations."""

from voice_calculator.asr.base import (
    ASREngine,
    ASRError,
    ASRResult,
    ASRStatus,
    FakeEngine,
    ModelLoadError,
    ModelMissingError,
)
from voice_calculator.asr.vosk_engine import (
    DEFAULT_NUMBER_GRAMMAR,
    VoskEngine,
    get_default_number_grammar,
)
from voice_calculator.asr.whisper_engine import (
    FasterWhisperEngine,
    WhisperConfig,
)

__all__ = [
    "ASREngine",
    "ASRError",
    "ASRResult",
    "ASRStatus",
    "DEFAULT_NUMBER_GRAMMAR",
    "FakeEngine",
    "FasterWhisperEngine",
    "ModelLoadError",
    "ModelMissingError",
    "VoskEngine",
    "WhisperConfig",
    "get_default_number_grammar",
]

