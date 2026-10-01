"""Audio package for Voice Calculator - capture, segmentation, and streaming."""

from voice_calculator.audio.capture import (
    AudioError,
    AudioFrame,
    AudioSource,
    FakeAudioSource,
    MicBusy,
    MicLost,
    MicNotFound,
    MicrophoneCapture,
    StreamError,
)

__all__ = [
    "AudioError",
    "AudioFrame",
    "AudioSource",
    "FakeAudioSource",
    "MicBusy",
    "MicLost",
    "MicNotFound",
    "MicrophoneCapture",
    "StreamError",
]
