"""Base interfaces, protocols, and data structures for ASR engines.

Defines:
- ASRResult: Immutable dataclass carrying transcript, optional confidence, timings, and status.
- ASREngine: Protocol for speech recognition engines.
- FakeEngine: Deterministic test engine returning scripted or predefined results without models.
- Typed ASR exceptions: ASRError, ModelMissingError, ModelLoadError.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import List, Optional, Protocol, Union

import numpy as np

from voice_calculator.config import AUDIO_SAMPLE_RATE


# --- Typed ASR Errors (per architecture.md §12, prd.md §9) ---


class ASRError(Exception):
    """Base exception for ASR-related failures."""


class ModelMissingError(ASRError):
    """Raised when local ASR model files/directories cannot be found."""


class ModelLoadError(ASRError):
    """Raised when an ASR model fails to initialize or load into memory."""


# --- Result Data Structures ---


class ASRStatus(Enum):
    """Recognition outcome status."""

    SUCCESS = "SUCCESS"
    NO_SPEECH = "NO_SPEECH"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ASRResult:
    """Immutable result from an ASR transcription operation.

    Attributes:
        text: Recognized raw spoken text transcript.
        confidence: Optional acoustic/language model confidence score (0.0 - 1.0).
                    Note: Treated strictly as a weak signal, never as proof of correctness.
        alternatives: Optional list of alternative n-best text hypotheses.
        engine: Identifier name of the engine that produced this result.
        elapsed_ms: Inference duration in milliseconds.
        status: High-level status of the transcription (SUCCESS, NO_SPEECH, ERROR).
        error_message: Optional description if status == ERROR.
    """

    text: str = ""
    confidence: Optional[float] = None
    alternatives: List[str] = field(default_factory=list)
    engine: str = ""
    elapsed_ms: float = 0.0
    status: ASRStatus = ASRStatus.SUCCESS
    error_message: Optional[str] = None


# --- ASR Engine Protocol ---


class ASREngine(Protocol):
    """Protocol for offline speech-to-text engines."""

    name: str

    @property
    def is_loaded(self) -> bool:
        """Returns True if the engine model is loaded and ready for transcription."""
        ...

    def load(self) -> None:
        """Loads model weights/grammar into memory."""
        ...

    def transcribe(
        self,
        pcm_data: Union[bytes, np.ndarray],
        sample_rate: int = AUDIO_SAMPLE_RATE,
    ) -> ASRResult:
        """Transcribes PCM audio buffer into an ASRResult.

        Args:
            pcm_data: 16-bit mono PCM audio as bytes or numpy ndarray.
            sample_rate: Sampling frequency in Hz (default: 16000).

        Returns:
            ASRResult with recognized text, status, and metadata.
        """
        ...


# --- Deterministic Test Implementation ---


class FakeEngine:
    """Deterministic simulated ASR engine for unit and integration testing.

    Requires no model files, no internet connection, and generates reproducible results.
    """

    def __init__(
        self,
        name: str = "fake_asr",
        default_text: str = "",
        scripted_results: Optional[List[ASRResult]] = None,
        should_fail: bool = False,
        error_message: str = "Simulated ASR failure",
        should_return_no_speech: bool = False,
    ) -> None:
        self.name = name
        self.default_text = default_text
        self._scripted_results: List[ASRResult] = list(scripted_results) if scripted_results else []
        self.should_fail = should_fail
        self.error_message = error_message
        self.should_return_no_speech = should_return_no_speech

        self._is_loaded: bool = False
        self._transcribe_calls: int = 0
        self._last_pcm_size: int = 0

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def transcribe_calls(self) -> int:
        return self._transcribe_calls

    @property
    def last_pcm_size(self) -> int:
        return self._last_pcm_size

    def load(self) -> None:
        """Simulates loading model into memory."""
        self._is_loaded = True

    def queue_result(self, result: ASRResult) -> None:
        """Appends a predetermined ASRResult to the scripted responses queue."""
        self._scripted_results.append(result)

    def set_script(self, texts: List[str]) -> None:
        """Convenience method to set a sequence of successful text results."""
        self._scripted_results = [
            ASRResult(text=t, engine=self.name, status=ASRStatus.SUCCESS) for t in texts
        ]

    def transcribe(
        self,
        pcm_data: Union[bytes, np.ndarray],
        sample_rate: int = AUDIO_SAMPLE_RATE,
    ) -> ASRResult:
        """Transcribes PCM audio using scripted queue or default response."""
        self._transcribe_calls += 1
        raw_bytes = pcm_data.tobytes() if isinstance(pcm_data, np.ndarray) else pcm_data
        self._last_pcm_size = len(raw_bytes)

        start_time = time.monotonic()

        # Simulated failure mode
        if self.should_fail:
            return ASRResult(
                text="",
                engine=self.name,
                status=ASRStatus.ERROR,
                error_message=self.error_message,
                elapsed_ms=(time.monotonic() - start_time) * 1000.0,
            )

        # Simulated no-speech mode
        if self.should_return_no_speech or len(raw_bytes) == 0:
            return ASRResult(
                text="",
                engine=self.name,
                status=ASRStatus.NO_SPEECH,
                elapsed_ms=(time.monotonic() - start_time) * 1000.0,
            )

        # Return next scripted response if available
        if self._scripted_results:
            return self._scripted_results.pop(0)

        # Fall back to default static response
        return ASRResult(
            text=self.default_text,
            engine=self.name,
            status=ASRStatus.SUCCESS if self.default_text else ASRStatus.NO_SPEECH,
            elapsed_ms=(time.monotonic() - start_time) * 1000.0,
        )
