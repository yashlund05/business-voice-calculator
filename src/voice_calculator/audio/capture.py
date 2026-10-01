"""Microphone audio capture abstraction and streaming layer.

Provides:
- AudioFrame: Immutable representation of a captured PCM audio slice.
- AudioSource: Protocol defining the audio source interface.
- MicrophoneCapture: sounddevice-based real-time capture stream.
- FakeAudioSource: Deterministic audio source for testing without physical hardware.
- Typed audio errors: MicNotFound, MicLost, MicBusy, StreamError.
"""

import logging
import queue
import time
from dataclasses import dataclass
from typing import List, Optional, Protocol, Union

import numpy as np
import sounddevice as sd

from voice_calculator.config import (
    AUDIO_BLOCK_SAMPLES,
    AUDIO_CHANNELS,
    AUDIO_DTYPE,
    AUDIO_QUEUE_MAX_BLOCKS,
    AUDIO_SAMPLE_RATE,
)

logger = logging.getLogger("voice_calculator.audio")


# --- Typed Audio Errors (per architecture.md §12, prd.md §9) ---


class AudioError(Exception):
    """Base exception for all audio capture errors."""


class MicNotFound(AudioError):
    """Raised when no suitable input device is found."""


class MicLost(AudioError):
    """Raised when an active microphone stream is disconnected or lost."""


class MicBusy(AudioError):
    """Raised when the microphone is locked by another application or permission denied."""


class StreamError(AudioError):
    """Raised on internal PortAudio or stream configuration errors."""


# --- Data Structures ---


@dataclass(frozen=True)
class AudioFrame:
    """Represents a single fixed-duration slice of PCM audio."""

    data: bytes
    sample_rate: int
    channels: int
    timestamp_ns: int
    samples_count: int
    overflow: bool = False

    @property
    def duration_ms(self) -> float:
        """Duration of the frame in milliseconds."""
        if self.sample_rate <= 0:
            return 0.0
        return (self.samples_count / self.sample_rate) * 1000.0


class AudioSource(Protocol):
    """Protocol for audio input sources."""

    def start(self) -> None:
        """Starts audio capture."""
        ...

    def stop(self) -> None:
        """Stops audio capture cleanly."""
        ...

    def is_active(self) -> bool:
        """Returns True if the source is currently capturing."""
        ...

    def get_frame(self, timeout: Optional[float] = None) -> Optional[AudioFrame]:
        """Retrieves the next available audio frame, or None if timeout expires."""
        ...

    def drain(self) -> List[AudioFrame]:
        """Drains and returns all pending audio frames from the queue."""
        ...

    @property
    def overflow_count(self) -> int:
        """Returns the number of dropped/overflow frames."""
        ...


class MicrophoneCapture:
    """Microphone audio capture source backed by sounddevice.InputStream."""

    def __init__(
        self,
        sample_rate: int = AUDIO_SAMPLE_RATE,
        channels: int = AUDIO_CHANNELS,
        dtype: str = AUDIO_DTYPE,
        block_samples: int = AUDIO_BLOCK_SAMPLES,
        queue_max_blocks: int = AUDIO_QUEUE_MAX_BLOCKS,
        device_index: Optional[Union[int, str]] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.block_samples = block_samples
        self.queue_max_blocks = queue_max_blocks
        self.device_index = device_index

        self._queue: queue.Queue[AudioFrame] = queue.Queue(maxsize=self.queue_max_blocks)
        self._stream: Optional[sd.InputStream] = None
        self._is_capturing: bool = False
        self._overflow_count: int = 0
        self._frames_captured: int = 0
        self._has_pending_overflow: bool = False

    @property
    def overflow_count(self) -> int:
        """Total number of frame drop events due to queue overflow."""
        return self._overflow_count

    @property
    def frames_captured(self) -> int:
        """Total number of frames successfully queued."""
        return self._frames_captured

    def is_active(self) -> bool:
        """Returns whether audio capture is currently running."""
        return self._is_capturing and self._stream is not None and self._stream.active

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """High-priority sounddevice audio callback.

        Must be extremely fast and non-blocking. No disk I/O, no logging of audio data.
        """
        if not self._is_capturing:
            return

        is_overflow = bool(status.input_overflow) or self._has_pending_overflow
        self._has_pending_overflow = False

        # Fast conversion to raw PCM bytes
        frame = AudioFrame(
            data=indata.tobytes(),
            sample_rate=self.sample_rate,
            channels=self.channels,
            timestamp_ns=time.monotonic_ns(),
            samples_count=frames,
            overflow=is_overflow,
        )

        try:
            self._queue.put_nowait(frame)
            self._frames_captured += 1
        except queue.Full:
            self._overflow_count += 1
            self._has_pending_overflow = True

    def start(self) -> None:
        """Starts the microphone audio stream."""
        if self._is_capturing:
            return

        # Check for input device availability
        try:
            devices = sd.query_devices()
            if not devices:
                raise MicNotFound("No audio devices reported by system.")

            # Validate input device selection
            default_input = sd.default.device[0] if self.device_index is None else self.device_index
            if default_input is None or default_input < 0:
                raise MicNotFound("No default microphone configured on system.")
        except sd.PortAudioError as e:
            logger.error("PortAudio error querying devices: %s", type(e).__name__)
            raise MicNotFound(f"Microphone device query failed: {e}") from e

        # Clear queue and counters
        self.drain()
        self._overflow_count = 0
        self._frames_captured = 0
        self._has_pending_overflow = False
        self._is_capturing = True

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=self.block_samples,
                device=self.device_index,
                callback=self._audio_callback,
            )
            self._stream.start()
            logger.info("Microphone audio stream started successfully.")
        except sd.PortAudioError as e:
            self._is_capturing = False
            err_msg = str(e).lower()
            if "device unavailable" in err_msg or "busy" in err_msg:
                raise MicBusy(f"Microphone is busy or in use: {e}") from e
            elif "invalid device" in err_msg or "device not found" in err_msg:
                raise MicNotFound(f"Microphone device not found: {e}") from e
            else:
                raise StreamError(f"Failed to start audio stream: {e}") from e
        except Exception as e:
            self._is_capturing = False
            raise StreamError(f"Unexpected error starting audio stream: {e}") from e

    def stop(self) -> None:
        """Stops and closes the microphone stream cleanly."""
        if not self._is_capturing and self._stream is None:
            return

        self._is_capturing = False

        if self._stream is not None:
            try:
                if self._stream.active:
                    self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning("Error closing audio stream: %s", e)
            finally:
                self._stream = None

        logger.info("Microphone audio stream stopped.")

    def get_frame(self, timeout: Optional[float] = None) -> Optional[AudioFrame]:
        """Retrieves next AudioFrame from the queue."""
        try:
            return self._queue.get(block=True, timeout=timeout)
        except queue.Empty:
            return None

    def drain(self) -> List[AudioFrame]:
        """Empties and returns all currently queued frames."""
        frames: List[AudioFrame] = []
        while True:
            try:
                frames.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return frames

    def __enter__(self) -> "MicrophoneCapture":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


class FakeAudioSource:
    """Deterministic simulated audio source for tests and headless pipelines."""

    def __init__(
        self,
        sample_rate: int = AUDIO_SAMPLE_RATE,
        channels: int = AUDIO_CHANNELS,
        block_samples: int = AUDIO_BLOCK_SAMPLES,
        queue_max_blocks: int = AUDIO_QUEUE_MAX_BLOCKS,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_samples = block_samples
        self.queue_max_blocks = queue_max_blocks

        self._queue: queue.Queue[AudioFrame] = queue.Queue(maxsize=self.queue_max_blocks)
        self._is_capturing: bool = False
        self._overflow_count: int = 0
        self._frames_captured: int = 0

    @property
    def overflow_count(self) -> int:
        return self._overflow_count

    @property
    def frames_captured(self) -> int:
        return self._frames_captured

    def is_active(self) -> bool:
        return self._is_capturing

    def start(self) -> None:
        self._is_capturing = True

    def stop(self) -> None:
        self._is_capturing = False

    def push_pcm_bytes(self, pcm_data: bytes, overflow: bool = False) -> bool:
        """Pushes raw PCM bytes as an AudioFrame into the queue.

        Returns:
            True if queued successfully, False if dropped due to queue overflow.
        """
        if not self._is_capturing:
            return False

        samples_count = len(pcm_data) // (2 * self.channels)
        frame = AudioFrame(
            data=pcm_data,
            sample_rate=self.sample_rate,
            channels=self.channels,
            timestamp_ns=time.monotonic_ns(),
            samples_count=samples_count,
            overflow=overflow,
        )

        try:
            self._queue.put_nowait(frame)
            self._frames_captured += 1
            return True
        except queue.Full:
            self._overflow_count += 1
            return False

    def push_silence(self, duration_ms: float) -> int:
        """Pushes zeroed PCM frames corresponding to duration_ms. Returns frames queued."""
        frame_bytes = self.block_samples * 2 * self.channels
        silence_chunk = b"\x00" * frame_bytes
        num_frames = int((duration_ms / 1000.0) * self.sample_rate / self.block_samples)

        pushed = 0
        for _ in range(num_frames):
            if self.push_pcm_bytes(silence_chunk):
                pushed += 1
        return pushed

    def get_frame(self, timeout: Optional[float] = None) -> Optional[AudioFrame]:
        try:
            return self._queue.get(block=True, timeout=timeout)
        except queue.Empty:
            return None

    def drain(self) -> List[AudioFrame]:
        frames: List[AudioFrame] = []
        while True:
            try:
                frames.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return frames
