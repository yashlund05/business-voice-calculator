"""Utterance segmentation layer between AudioSource and ASR engines.

Maintains an online finite state machine:
  SILENCE -> SPEECH_ACTIVE -> SPEECH_HANGOVER -> (emits Utterance or discards noise)

Guarantees:
- Pre-roll ring buffer preservation (includes onset context).
- Trailing silence hangover window (avoids clipping word endings).
- Minimum speech duration enforcement (discards clicks, taps, and short noise spikes).
- Maximum utterance duration cap (prevents unbounded memory growth; flags TOO_LONG).
- Overflow/damage detection tracking from AudioSource queue drops.
- Clean reset and flush lifecycles.
- Zero raw audio logging or network access.
"""

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Deque, List, Optional, Union

import numpy as np

from voice_calculator.audio.capture import AudioFrame
from voice_calculator.audio.vad import EnergyVAD, VADDetector, extract_int16_samples
from voice_calculator.config import (
    AUDIO_CHANNELS,
    AUDIO_SAMPLE_RATE,
    MAX_UTTERANCE_MS,
    MIN_UTTERANCE_MS,
    VAD_HANGOVER_MS,
    VAD_PRE_ROLL_MS,
)


class SegmenterState(Enum):
    """Finite state machine states for utterance segmentation."""

    SILENCE = "SILENCE"
    SPEECH_ACTIVE = "SPEECH_ACTIVE"
    SPEECH_HANGOVER = "SPEECH_HANGOVER"


@dataclass(frozen=True)
class Utterance:
    """Immutable representation of a segmented speech utterance and its metadata.

    Attributes:
        pcm_data: Complete 16-bit mono PCM audio bytes of the utterance.
        duration_ms: Total duration of the utterance in milliseconds.
        sample_rate: Audio sampling frequency in Hz.
        channels: Channel count (1 for mono).
        peak_amplitude: Maximum absolute sample value (0 - 32768).
        rms_energy: Root-Mean-Square signal energy.
        is_clipped: True if peak amplitude reaches full scale (>= 32767).
        is_damaged: True if audio queue overflow occurred during capture.
        is_too_long: True if utterance reached maximum allowed duration cap.
        start_timestamp_ns: Timestamp of the first frame in the utterance.
        end_timestamp_ns: Timestamp of the last frame in the utterance.
        frame_count: Number of AudioFrames included in the utterance.
    """

    pcm_data: bytes
    duration_ms: float
    sample_rate: int = AUDIO_SAMPLE_RATE
    channels: int = AUDIO_CHANNELS
    peak_amplitude: int = 0
    rms_energy: float = 0.0
    is_clipped: bool = False
    is_damaged: bool = False
    is_too_long: bool = False
    start_timestamp_ns: int = 0
    end_timestamp_ns: int = 0
    frame_count: int = 0


class UtteranceSegmenter:
    """Segments continuous audio stream into discrete utterances using a VAD detector."""

    def __init__(
        self,
        vad: Optional[VADDetector] = None,
        pre_roll_ms: int = VAD_PRE_ROLL_MS,
        hangover_ms: int = VAD_HANGOVER_MS,
        min_utterance_ms: int = MIN_UTTERANCE_MS,
        max_utterance_ms: int = MAX_UTTERANCE_MS,
        sample_rate: int = AUDIO_SAMPLE_RATE,
        channels: int = AUDIO_CHANNELS,
    ) -> None:
        if pre_roll_ms < 0 or hangover_ms < 0 or min_utterance_ms < 0 or max_utterance_ms < min_utterance_ms:
            raise ValueError("Invalid duration parameters for UtteranceSegmenter.")

        self.vad: VADDetector = vad if vad is not None else EnergyVAD()
        self.pre_roll_ms = pre_roll_ms
        self.hangover_ms = hangover_ms
        self.min_utterance_ms = min_utterance_ms
        self.max_utterance_ms = max_utterance_ms
        self.sample_rate = sample_rate
        self.channels = channels

        # Pre-roll ring buffer (capacity calculated dynamically based on frame durations)
        # Default fallback size 15 frames (~450ms at 30ms/frame)
        self._pre_roll_buffer: Deque[AudioFrame] = deque()

        # Speech accumulation buffers
        self._speech_frames: List[AudioFrame] = []
        self._hangover_frames: List[AudioFrame] = []

        # State tracking
        self._state: SegmenterState = SegmenterState.SILENCE
        self._speech_duration_ms: float = 0.0
        self._hangover_duration_ms: float = 0.0
        self._has_overflow: bool = False

    @property
    def state(self) -> SegmenterState:
        """Current internal segmentation state."""
        return self._state

    @property
    def is_in_speech(self) -> bool:
        """True if currently accumulating active or hangover speech."""
        return self._state in (SegmenterState.SPEECH_ACTIVE, SegmenterState.SPEECH_HANGOVER)

    def reset(self) -> None:
        """Resets the segmenter state machine and clears all frame buffers."""
        self._state = SegmenterState.SILENCE
        self._pre_roll_buffer.clear()
        self._speech_frames.clear()
        self._hangover_frames.clear()
        self._speech_duration_ms = 0.0
        self._hangover_duration_ms = 0.0
        self._has_overflow = False

    def process_frame(self, frame: AudioFrame) -> Optional[Utterance]:
        """Processes a single AudioFrame and returns a completed Utterance if finished.

        Args:
            frame: Captured AudioFrame slice.

        Returns:
            Completed Utterance if end-of-speech or max-duration is reached, else None.
        """
        if frame.overflow:
            self._has_overflow = True

        is_sp, rms, peak = self.vad.analyze(frame)

        if self._state == SegmenterState.SILENCE:
            if is_sp:
                # Speech onset detected!
                self._state = SegmenterState.SPEECH_ACTIVE
                # Transfer pre-roll frames into speech accumulator
                self._speech_frames = list(self._pre_roll_buffer)
                self._pre_roll_buffer.clear()
                self._speech_frames.append(frame)
                self._speech_duration_ms = frame.duration_ms

                # Check max duration cap
                total_duration = sum(f.duration_ms for f in self._speech_frames)
                if total_duration >= self.max_utterance_ms:
                    return self._finalize_utterance(is_too_long=True)
                return None
            else:
                # Silence continues: buffer in pre-roll ring buffer
                self._append_pre_roll(frame)
                return None

        elif self._state == SegmenterState.SPEECH_ACTIVE:
            if is_sp:
                # Active speech continues
                self._speech_frames.append(frame)
                self._speech_duration_ms += frame.duration_ms

                # Check max duration cap
                total_duration = sum(f.duration_ms for f in self._speech_frames)
                if total_duration >= self.max_utterance_ms:
                    return self._finalize_utterance(is_too_long=True)
                return None
            else:
                # Speech paused -> enter hangover
                self._state = SegmenterState.SPEECH_HANGOVER
                self._hangover_frames = [frame]
                self._hangover_duration_ms = frame.duration_ms

                if self._hangover_duration_ms >= self.hangover_ms:
                    return self._evaluate_and_complete()
                return None

        elif self._state == SegmenterState.SPEECH_HANGOVER:
            if is_sp:
                # Speech resumed before hangover elapsed!
                self._state = SegmenterState.SPEECH_ACTIVE
                self._speech_frames.extend(self._hangover_frames)
                self._speech_frames.append(frame)
                self._speech_duration_ms += frame.duration_ms
                self._hangover_frames.clear()
                self._hangover_duration_ms = 0.0

                total_duration = sum(f.duration_ms for f in self._speech_frames)
                if total_duration >= self.max_utterance_ms:
                    return self._finalize_utterance(is_too_long=True)
                return None
            else:
                # Silence continues in hangover window
                self._hangover_frames.append(frame)
                self._hangover_duration_ms += frame.duration_ms

                total_duration = self._speech_duration_ms + self._hangover_duration_ms
                if total_duration >= self.max_utterance_ms:
                    return self._finalize_utterance(is_too_long=True)

                if self._hangover_duration_ms >= self.hangover_ms:
                    return self._evaluate_and_complete()
                return None

        return None

    def flush(self) -> Optional[Utterance]:
        """Flushes in-progress utterance on stream stop if minimum duration was met."""
        if self._state in (SegmenterState.SPEECH_ACTIVE, SegmenterState.SPEECH_HANGOVER):
            if self._speech_duration_ms >= self.min_utterance_ms:
                return self._finalize_utterance(is_too_long=False)
        self.reset()
        return None

    def _append_pre_roll(self, frame: AudioFrame) -> None:
        """Maintains bounded pre-roll frames ring buffer."""
        self._pre_roll_buffer.append(frame)
        # Evict oldest frames exceeding pre_roll_ms window
        current_dur = sum(f.duration_ms for f in self._pre_roll_buffer)
        while current_dur > self.pre_roll_ms and len(self._pre_roll_buffer) > 1:
            popped = self._pre_roll_buffer.popleft()
            current_dur -= popped.duration_ms

    def _evaluate_and_complete(self) -> Optional[Utterance]:
        """Evaluates completed hangover. Emits utterance if speech duration >= min_utterance_ms."""
        if self._speech_duration_ms >= self.min_utterance_ms:
            return self._finalize_utterance(is_too_long=False)
        else:
            # Noise spike/click shorter than min speech duration: discard cleanly
            self.reset()
            return None

    def _finalize_utterance(self, is_too_long: bool) -> Utterance:
        """Packages all accumulated frames into an Utterance and resets internal state."""
        all_frames = list(self._speech_frames)
        if self._hangover_frames:
            all_frames.extend(self._hangover_frames)

        pcm_bytes = b"".join(f.data for f in all_frames)
        total_duration = sum(f.duration_ms for f in all_frames)

        samples = extract_int16_samples(pcm_bytes)
        peak = int(np.max(np.abs(samples.astype(np.int32)))) if len(samples) > 0 else 0
        squares = samples.astype(np.float64) ** 2 if len(samples) > 0 else np.array([])
        rms = float(np.sqrt(np.mean(squares))) if len(squares) > 0 else 0.0
        is_clipped = peak >= 32767

        start_ts = all_frames[0].timestamp_ns if all_frames else 0
        end_ts = all_frames[-1].timestamp_ns if all_frames else 0
        damaged = self._has_overflow

        utterance = Utterance(
            pcm_data=pcm_bytes,
            duration_ms=total_duration,
            sample_rate=self.sample_rate,
            channels=self.channels,
            peak_amplitude=peak,
            rms_energy=rms,
            is_clipped=is_clipped,
            is_damaged=damaged,
            is_too_long=is_too_long,
            start_timestamp_ns=start_ts,
            end_timestamp_ns=end_ts,
            frame_count=len(all_frames),
        )

        self.reset()
        return utterance
