"""Voice Activity Detection (VAD) abstraction and energy-based baseline detector.

Provides:
- VADDetector: Protocol for voice activity detection implementations.
- EnergyVAD: Fast, deterministic, zero-ML energy/RMS-based voice activity detector.
- Audio signal measurement helpers (RMS energy, peak amplitude, clipping detection).
"""

from typing import Protocol, Tuple, Union

import numpy as np

from voice_calculator.audio.capture import AudioFrame
from voice_calculator.config import VAD_ENERGY_THRESHOLD


class VADDetector(Protocol):
    """Protocol defining the interface for voice activity detectors."""

    @property
    def threshold(self) -> float:
        """Operating decision threshold."""
        ...

    def is_speech(self, audio: Union[AudioFrame, bytes, np.ndarray]) -> bool:
        """Returns True if the audio block contains speech above the threshold."""
        ...

    def analyze(self, audio: Union[AudioFrame, bytes, np.ndarray]) -> Tuple[bool, float, int]:
        """Analyzes audio block and returns (is_speech, rms_energy, peak_amplitude)."""
        ...


def extract_int16_samples(audio: Union[AudioFrame, bytes, np.ndarray]) -> np.ndarray:
    """Extracts int16 numpy array from an AudioFrame, bytes, or ndarray safely."""
    if isinstance(audio, AudioFrame):
        raw_bytes = audio.data
    elif isinstance(audio, bytes):
        raw_bytes = audio
    elif isinstance(audio, np.ndarray):
        if audio.dtype == np.int16:
            return audio
        return audio.astype(np.int16)
    else:
        return np.array([], dtype=np.int16)

    if not raw_bytes or len(raw_bytes) < 2:
        return np.array([], dtype=np.int16)

    # Ensure even number of bytes for 16-bit integer conversion
    even_len = len(raw_bytes) - (len(raw_bytes) % 2)
    return np.frombuffer(raw_bytes[:even_len], dtype=np.int16)


class EnergyVAD:
    """Lightweight energy-based VAD for 16 kHz 16-bit mono PCM audio.

    Calculates Root-Mean-Square (RMS) amplitude and classifies frames as speech
    when RMS exceeds the configured energy threshold.

    Note: Designed as an initial deterministic quiet-room baseline.
    Threshold calibration is pending real speech data (docs/research.md).
    """

    def __init__(self, energy_threshold: float = VAD_ENERGY_THRESHOLD) -> None:
        if energy_threshold < 0:
            raise ValueError(f"Energy threshold must be non-negative, got {energy_threshold}")
        self._threshold = float(energy_threshold)

    @property
    def threshold(self) -> float:
        """The RMS energy decision threshold."""
        return self._threshold

    def compute_rms(self, audio: Union[AudioFrame, bytes, np.ndarray]) -> float:
        """Computes Root-Mean-Square (RMS) signal amplitude."""
        samples = extract_int16_samples(audio)
        if len(samples) == 0:
            return 0.0
        # Cast to float64 to avoid integer overflow during squaring
        squares = samples.astype(np.float64) ** 2
        return float(np.sqrt(np.mean(squares)))

    def compute_peak(self, audio: Union[AudioFrame, bytes, np.ndarray]) -> int:
        """Computes maximum absolute peak amplitude (0 - 32768)."""
        samples = extract_int16_samples(audio)
        if len(samples) == 0:
            return 0
        return int(np.max(np.abs(samples.astype(np.int32))))

    def is_speech(self, audio: Union[AudioFrame, bytes, np.ndarray]) -> bool:
        """Returns True if the audio block has RMS energy >= threshold."""
        rms = self.compute_rms(audio)
        return rms >= self._threshold

    def analyze(self, audio: Union[AudioFrame, bytes, np.ndarray]) -> Tuple[bool, float, int]:
        """Performs full frame analysis returning (is_speech, rms_energy, peak_amplitude)."""
        samples = extract_int16_samples(audio)
        if len(samples) == 0:
            return False, 0.0, 0
        squares = samples.astype(np.float64) ** 2
        rms = float(np.sqrt(np.mean(squares)))
        peak = int(np.max(np.abs(samples.astype(np.int32))))
        is_sp = rms >= self._threshold
        return is_sp, rms, peak
