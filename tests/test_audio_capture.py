"""Unit tests for the audio capture layer and frame streaming."""

import queue
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import sounddevice as sd

from voice_calculator.audio.capture import (
    AudioError,
    AudioFrame,
    FakeAudioSource,
    MicBusy,
    MicLost,
    MicNotFound,
    MicrophoneCapture,
    StreamError,
)
from voice_calculator.config import (
    AUDIO_BLOCK_BYTES,
    AUDIO_BLOCK_SAMPLES,
    AUDIO_CHANNELS,
    AUDIO_QUEUE_MAX_BLOCKS,
    AUDIO_SAMPLE_RATE,
)


# --- 1. AudioFrame Tests ---


def test_audio_frame_properties():
    """Verify AudioFrame field access, duration calculation, and immutability."""
    raw_data = b"\x00" * 960  # 480 samples of 16-bit PCM
    frame = AudioFrame(
        data=raw_data,
        sample_rate=16000,
        channels=1,
        timestamp_ns=time.monotonic_ns(),
        samples_count=480,
        overflow=False,
    )

    assert frame.sample_rate == 16000
    assert frame.channels == 1
    assert frame.samples_count == 480
    assert frame.duration_ms == 30.0
    assert frame.overflow is False

    # Immutability check
    with pytest.raises(Exception):
        frame.overflow = True  # type: ignore


# --- 2. Callback & Bounded Queue Tests ---


def test_audio_callback_queue_insertion():
    """Verify sounddevice callback converts numpy buffer to AudioFrame and queues it."""
    capture = MicrophoneCapture(
        sample_rate=16000,
        channels=1,
        block_samples=480,
        queue_max_blocks=10,
    )
    capture._is_capturing = True

    # Simulate 480 samples of int16 zeros
    indata = np.zeros((480, 1), dtype=np.int16)
    time_info = {}
    status = sd.CallbackFlags()

    capture._audio_callback(indata, 480, time_info, status)

    assert capture.frames_captured == 1
    assert capture.overflow_count == 0

    frame = capture.get_frame(timeout=0.1)
    assert frame is not None
    assert frame.samples_count == 480
    assert len(frame.data) == 480 * 2
    assert frame.overflow is False


def test_audio_callback_queue_overflow_handling():
    """Verify that queue overflow does not block callback and flags subsequent frames."""
    capture = MicrophoneCapture(
        sample_rate=16000,
        channels=1,
        block_samples=480,
        queue_max_blocks=2,  # Bounded to only 2 blocks
    )
    capture._is_capturing = True

    indata = np.zeros((480, 1), dtype=np.int16)
    status = sd.CallbackFlags()

    # Fill queue (2 frames)
    capture._audio_callback(indata, 480, {}, status)
    capture._audio_callback(indata, 480, {}, status)
    assert capture.frames_captured == 2
    assert capture.overflow_count == 0

    # Next push overflows queue (non-blocking)
    capture._audio_callback(indata, 480, {}, status)
    assert capture.overflow_count == 1
    assert capture.frames_captured == 2  # Not incremented on drop

    # Drain one item, then push next frame to verify overflow flag is propagated
    frame1 = capture.get_frame(timeout=0.1)
    assert frame1 is not None
    assert frame1.overflow is False

    capture._audio_callback(indata, 480, {}, status)
    frame2 = capture.get_frame(timeout=0.1)
    frame3 = capture.get_frame(timeout=0.1)

    assert frame2 is not None
    assert frame3 is not None
    assert frame3.overflow is True  # Flagged damaged due to previous dropped frame


def test_queue_drain_functionality():
    """Verify drain() empties all pending items without blocking."""
    capture = MicrophoneCapture(queue_max_blocks=10)
    capture._is_capturing = True

    indata = np.zeros((480, 1), dtype=np.int16)
    for _ in range(5):
        capture._audio_callback(indata, 480, {}, sd.CallbackFlags())

    drained = capture.drain()
    assert len(drained) == 5
    assert capture.get_frame(timeout=0.01) is None


# --- 3. Lifecycle & Error Mocking Tests ---


@patch("sounddevice.query_devices")
@patch("sounddevice.InputStream")
def test_microphone_start_stop_lifecycle(mock_stream_cls, mock_query):
    """Verify stream creation, start, stop, and idempotency."""
    mock_query.return_value = [{"name": "Default Mic", "max_input_channels": 1}]
    mock_stream_instance = MagicMock()
    mock_stream_instance.active = True
    mock_stream_cls.return_value = mock_stream_instance

    capture = MicrophoneCapture()
    assert not capture.is_active()

    # Start capture
    capture.start()
    assert capture._is_capturing is True
    mock_stream_cls.assert_called_once()
    mock_stream_instance.start.assert_called_once()

    # Repeated start is idempotent
    capture.start()
    assert mock_stream_cls.call_count == 1

    # Stop capture
    capture.stop()
    assert capture._is_capturing is False
    mock_stream_instance.stop.assert_called_once()
    mock_stream_instance.close.assert_called_once()

    # Repeated stop is idempotent
    capture.stop()


@patch("sounddevice.query_devices")
def test_mic_not_found_on_empty_devices(mock_query):
    """Verify MicNotFound is raised when no audio devices are detected."""
    mock_query.return_value = []
    capture = MicrophoneCapture()

    with pytest.raises(MicNotFound):
        capture.start()


@patch("sounddevice.query_devices")
@patch("sounddevice.InputStream")
def test_mic_busy_error_mapping(mock_stream_cls, mock_query):
    """Verify PortAudio device unavailable error maps to MicBusy."""
    mock_query.return_value = [{"name": "Busy Mic", "max_input_channels": 1}]
    mock_stream_cls.side_effect = sd.PortAudioError("Device unavailable (busy)")

    capture = MicrophoneCapture()
    with pytest.raises(MicBusy):
        capture.start()


@patch("sounddevice.query_devices")
@patch("sounddevice.InputStream")
def test_context_manager_clean_exit(mock_stream_cls, mock_query):
    """Verify context manager automatically starts and stops stream."""
    mock_query.return_value = [{"name": "Test Mic", "max_input_channels": 1}]
    mock_stream_instance = MagicMock()
    mock_stream_instance.active = True
    mock_stream_cls.return_value = mock_stream_instance

    with MicrophoneCapture() as mic:
        assert mic._is_capturing is True

    mock_stream_instance.stop.assert_called_once()
    mock_stream_instance.close.assert_called_once()


# --- 4. FakeAudioSource Tests ---


def test_fake_audio_source_operations():
    """Verify FakeAudioSource deterministic queuing, silence push, and overflow tracking."""
    fake = FakeAudioSource(
        sample_rate=16000,
        channels=1,
        block_samples=480,
        queue_max_blocks=5,
    )
    assert not fake.is_active()

    fake.start()
    assert fake.is_active()

    # Push 60 ms of silence (2 blocks of 30 ms)
    pushed = fake.push_silence(duration_ms=60.0)
    assert pushed == 2
    assert fake.frames_captured == 2

    # Get frame
    frame = fake.get_frame(timeout=0.05)
    assert frame is not None
    assert frame.samples_count == 480
    assert frame.duration_ms == 30.0

    # Drain remaining
    drained = fake.drain()
    assert len(drained) == 1

    # Test overflow behavior on fake
    for _ in range(10):
        fake.push_pcm_bytes(b"\x00" * 960)

    assert fake.overflow_count > 0

    fake.stop()
    assert not fake.is_active()
