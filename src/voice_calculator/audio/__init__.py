"""Audio package for Voice Calculator - capture, VAD, segmentation, and streaming."""

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
from voice_calculator.audio.segmenter import (
    SegmenterState,
    Utterance,
    UtteranceSegmenter,
)
from voice_calculator.audio.vad import (
    EnergyVAD,
    VADDetector,
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
    "EnergyVAD",
    "FakeAudioSource",
    "MicBusy",
    "MicLost",
    "MicNotFound",
    "MicrophoneCapture",
    "SegmenterState",
    "StreamError",
    "Utterance",
    "UtteranceSegmenter",
    "VADDetector",
    "WavFormatError",
    "read_wav",
    "write_wav",
    "write_wav_bytes",
]
