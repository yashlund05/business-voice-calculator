"""faster-whisper offline speech recognition engine implementation.

Integrates the faster-whisper (CTranslate2) candidate ASR engine behind the ASREngine protocol.
Guarantees:
- Fully offline inference (strictly requires local model files; never auto-downloads).
- Configurable model path/size, device ('cpu', 'cuda', 'auto'), and compute type ('int8', 'float16', etc.).
- Hardware-aware for 4 GB VRAM Windows GPU (RTX 3050 Laptop GPU) or multi-threaded CPU fallback.
- Deterministic error mapping (ModelMissingError, ModelLoadError).
- Raw uncalibrated confidence/probabilities are never treated as calibrated (returns confidence=None).
- Privacy-safe logging (no raw audio or spoken transcripts in INFO logs).
"""

from dataclasses import dataclass
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
from voice_calculator.config import (
    AUDIO_SAMPLE_RATE,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL_PATH,
)

logger = logging.getLogger("voice_calculator.asr.whisper")


@dataclass(frozen=True)
class WhisperConfig:
    """Configuration parameters for faster-whisper candidate engine."""

    model_path_or_size: Union[str, Path] = WHISPER_MODEL_PATH
    device: str = WHISPER_DEVICE
    compute_type: str = WHISPER_COMPUTE_TYPE
    cpu_threads: int = 4
    beam_size: int = 1
    language: str = "en"
    initial_prompt: Optional[str] = None


class FasterWhisperEngine:
    """Offline candidate ASR engine powered by faster-whisper (CTranslate2)."""

    def __init__(
        self,
        model_path_or_size: Optional[Union[str, Path]] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        cpu_threads: int = 4,
        beam_size: int = 1,
        language: str = "en",
        initial_prompt: Optional[str] = None,
        name: str = "faster-whisper",
    ) -> None:
        self.name = name
        self.model_path_or_size = (
            Path(model_path_or_size)
            if model_path_or_size is not None
            else WHISPER_MODEL_PATH
        )
        self.device = (device or WHISPER_DEVICE).lower()
        self.compute_type = (compute_type or WHISPER_COMPUTE_TYPE).lower()
        self.cpu_threads = max(1, cpu_threads)
        self.beam_size = max(1, beam_size)
        self.language = language
        self.initial_prompt = initial_prompt

        self._model = None
        self._is_loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        """Returns True if the faster-whisper model is loaded into memory."""
        return self._is_loaded and self._model is not None

    def load(self) -> None:
        """Loads the local faster-whisper model into memory.

        Raises:
            ModelMissingError: If the configured local model path does not exist.
            ModelLoadError: If faster-whisper is not installed or model fails to initialize.
        """
        if self._is_loaded and self._model is not None:
            return

        # Check local path existence if model_path_or_size points to a filesystem path
        if isinstance(self.model_path_or_size, Path) or "/" in str(self.model_path_or_size) or "\\" in str(self.model_path_or_size):
            p = Path(self.model_path_or_size)
            if not p.exists():
                raise ModelMissingError(
                    f"faster-whisper model directory not found at: {p.resolve()}. "
                    "Please place the model folder in models/ or set VOICE_CALC_WHISPER_MODEL_PATH."
                )

        try:
            import faster_whisper
        except ImportError as e:
            self._is_loaded = False
            self._model = None
            raise ModelLoadError(
                "faster-whisper package is not installed. "
                "Please install it in your virtual environment: pip install faster-whisper"
            ) from e

        try:
            logger.info(
                "Loading faster-whisper model from %s (device=%s, compute_type=%s)...",
                self.model_path_or_size,
                self.device,
                self.compute_type,
            )
            model_str = str(self.model_path_or_size)
            self._model = faster_whisper.WhisperModel(
                model_size_or_path=model_str,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
                local_files_only=True,
            )
            self._is_loaded = True
            logger.info("faster-whisper model loaded successfully.")

        except Exception as e:
            self._is_loaded = False
            self._model = None
            raise ModelLoadError(
                f"Failed to load faster-whisper model from {self.model_path_or_size}: {e}"
            ) from e

    def transcribe(
        self,
        pcm_data: Union[bytes, np.ndarray],
        sample_rate: int = AUDIO_SAMPLE_RATE,
    ) -> ASRResult:
        """Transcribes a 16-bit mono PCM audio buffer using faster-whisper.

        Args:
            pcm_data: Raw 16-bit mono PCM bytes or numpy ndarray.
            sample_rate: Audio sampling frequency in Hz (default: 16000).

        Returns:
            ASRResult containing recognized candidate text, timing, and status.
            Note: confidence is returned as None (uncalibrated score policy).
        """
        if isinstance(pcm_data, np.ndarray):
            raw_bytes = pcm_data.tobytes()
            audio_int16 = pcm_data.astype(np.int16) if pcm_data.dtype != np.int16 else pcm_data
        else:
            raw_bytes = pcm_data
            audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16) if raw_bytes else np.array([], dtype=np.int16)

        if len(raw_bytes) == 0 or len(audio_int16) == 0:
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
            # Convert 16-bit int PCM to float32 normalized in [-1.0, 1.0] for Whisper
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            transcribe_kwargs = {
                "language": self.language,
                "task": "transcribe",
                "beam_size": self.beam_size,
                "temperature": 0.0,
                "vad_filter": False,  # Audio is already segmented by upstream VAD
            }
            if self.initial_prompt:
                transcribe_kwargs["initial_prompt"] = self.initial_prompt

            segments, info = self._model.transcribe(audio_float32, **transcribe_kwargs)
            segment_list = list(segments)

            raw_text = " ".join(
                seg.text.strip() for seg in segment_list if seg.text and seg.text.strip()
            ).strip()

            elapsed_ms = (time.monotonic() - start_time) * 1000.0

            # Normalize transcript punctuation for downstream number parser:
            # 1. Remove commas inside digits (e.g. "1,500" -> "1500")
            # 2. Convert remaining clause commas to spaces (e.g. "one hundred, and fifty" -> "one hundred and fifty")
            # 3. Strip currency signs and collapse whitespace
            import re
            cleaned_text = re.sub(r"(?<=\d),(?=\d)", "", raw_text)
            cleaned_text = re.sub(r",", " ", cleaned_text)
            cleaned_text = cleaned_text.replace("$", "")
            cleaned_text = " ".join(cleaned_text.split())

            status = ASRStatus.SUCCESS if cleaned_text else ASRStatus.NO_SPEECH

            # Confidence is set to None: raw logprob / token scores are uncalibrated
            # and MUST NOT trigger automatic additions without empirical calibration.
            return ASRResult(
                text=cleaned_text,
                confidence=None,
                engine=self.name,
                elapsed_ms=elapsed_ms,
                status=status,
            )

        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000.0
            logger.error("faster-whisper transcription runtime error: %s", e)
            return ASRResult(
                text="",
                confidence=None,
                engine=self.name,
                elapsed_ms=elapsed_ms,
                status=ASRStatus.ERROR,
                error_message=str(e),
            )
