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
from voice_calculator.audio.wavio import (
    WavFormatError,
    read_wav,
    write_wav,
    write_wav_bytes,
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
    "WavFormatError",
    "read_wav",
    "write_wav",
    "write_wav_bytes",
]
