"""Vosk offline speech recognition engine with constrained number grammar.

Integrates the Vosk ASR baseline behind the ASREngine protocol.
Guarantees:
- Fully offline operation.
- Model path configured explicitly from config / environment (never auto-downloaded).
- Constrained grammar limited to documented English number words and [unk].
- Deterministic error mapping (ModelMissingError, ModelLoadError).
- Privacy-safe logging (no raw audio or spoken transcripts in INFO logs).
"""

import json
import logging
from pathlib import Path
import time
from typing import List, Optional, Union

import numpy as np

from voice_calculator.asr.base import (
    ASREngine,
    ASRResult,
    ASRStatus,
    ModelLoadError,
    ModelMissingError,
)
from voice_calculator.config import AUDIO_SAMPLE_RATE, VOSK_MODEL_PATH

logger = logging.getLogger("voice_calculator.asr.vosk")

# Default closed vocabulary for English number recognition (0-2000)
DEFAULT_NUMBER_GRAMMAR = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
    "hundred",
    "thousand",
    "and",
    "a",
    "[unk]",
]


def get_default_number_grammar() -> List[str]:
    """Returns a copy of the default closed number-word grammar list."""
    return list(DEFAULT_NUMBER_GRAMMAR)


class VoskEngine:
    """Offline ASR engine implementation powered by Vosk."""

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        grammar: Optional[List[str]] = None,
        name: str = "vosk",
    ) -> None:
        self.name = name
        self.model_path = Path(model_path) if model_path is not None else VOSK_MODEL_PATH
        self.grammar = list(grammar) if grammar is not None else get_default_number_grammar()

        self._grammar_json: str = json.dumps(self.grammar)
        self._model = None
        self._is_loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        """Returns True if the Vosk model is loaded in memory."""
        return self._is_loaded and self._model is not None

    def load(self) -> None:
        """Loads the local Vosk model from disk into memory.

        Raises:
            ModelMissingError: If the configured model directory does not exist.
            ModelLoadError: If the model fails to load into Vosk.
        """
        if self._is_loaded and self._model is not None:
            return

        if not self.model_path.exists() or not self.model_path.is_dir():
            raise ModelMissingError(
                f"Vosk model directory not found at: {self.model_path.resolve()}. "
                "Please place the model folder in models/ or set VOICE_CALC_VOSK_MODEL_PATH."
            )

        try:
            import vosk

            # Suppress verbose C++ stderr logging from Kaldi/Vosk
            vosk.SetLogLevel(-1)

            logger.info("Loading Vosk model from %s...", self.model_path)
            self._model = vosk.Model(str(self.model_path))
            self._is_loaded = True
            logger.info("Vosk model loaded successfully.")

        except Exception as e:
            self._is_loaded = False
            self._model = None
            raise ModelLoadError(f"Failed to load Vosk model from {self.model_path}: {e}") from e

    def transcribe(
        self,
        pcm_data: Union[bytes, np.ndarray],
        sample_rate: int = AUDIO_SAMPLE_RATE,
    ) -> ASRResult:
        """Transcribes a 16-bit mono PCM audio buffer using Vosk with grammar constraints.

        Args:
            pcm_data: Raw 16-bit mono PCM bytes or numpy ndarray.
            sample_rate: Audio sampling frequency in Hz (default: 16000).

        Returns:
            ASRResult containing recognized candidate text, timing, and status.
        """
        raw_bytes = pcm_data.tobytes() if isinstance(pcm_data, np.ndarray) else pcm_data

        if len(raw_bytes) == 0:
            return ASRResult(
                text="",
                confidence=None,
                engine=self.name,
                elapsed_ms=0.0,
                status=ASRStatus.NO_SPEECH,
            )

        # Lazy model loading if not already loaded
        if not self._is_loaded or self._model is None:
            try:
                self.load()
            except (ModelMissingError, ModelLoadError) as e:
                return ASRResult(
                    text="",
                    confidence=None,
                    engine=self.name,
                    elapsed_ms=0.0,
                    status=ASRStatus.ERROR,
                    error_message=str(e),
                )

        start_time = time.monotonic()

        try:
            import vosk

            # Create recognizer configured with the constrained grammar
            rec = vosk.KaldiRecognizer(self._model, sample_rate, self._grammar_json)
            rec.AcceptWaveform(raw_bytes)
            res_raw = rec.FinalResult()

            res_dict = json.loads(res_raw)
            text = res_dict.get("text", "").strip()

            elapsed_ms = (time.monotonic() - start_time) * 1000.0

            # Filter out [unk] tokens if returned standalone
            if text == "[unk]":
                text = ""

            status = ASRStatus.SUCCESS if text else ASRStatus.NO_SPEECH

            # Confidence is set to None because KaldiRecognizer without word alignment
            # does not provide calibrated utterance-level confidence.
            return ASRResult(
                text=text,
                confidence=None,
                engine=self.name,
                elapsed_ms=elapsed_ms,
                status=status,
            )

        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000.0
            logger.error("Vosk transcription runtime error: %s", e)
            return ASRResult(
                text="",
                confidence=None,
                engine=self.name,
                elapsed_ms=elapsed_ms,
                status=ASRStatus.ERROR,
                error_message=str(e),
            )
