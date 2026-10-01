"""Unit tests for Voice Activity Detection (VAD) layer."""

import numpy as np
import pytest

from voice_calculator.audio.capture import AudioFrame
from voice_calculator.audio.vad import EnergyVAD, extract_int16_samples
from voice_calculator.config import AUDIO_SAMPLE_RATE


def make_sine_pcm(amplitude: int, duration_ms: float = 30.0, freq_hz: float = 440.0, sample_rate: int = AUDIO_SAMPLE_RATE) -> bytes:
    """Generates synthetic 16-bit mono PCM sine wave."""
    n_samples = int(sample_rate * (duration_ms / 1000.0))
    t = np.linspace(0, duration_ms / 1000.0, n_samples, endpoint=False)
    samples = (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.int16)
    return samples.tobytes()


def make_silence_pcm(duration_ms: float = 30.0, sample_rate: int = AUDIO_SAMPLE_RATE) -> bytes:
    """Generates synthetic 16-bit mono silence PCM."""
    n_samples = int(sample_rate * (duration_ms / 1000.0))
    return (np.zeros(n_samples, dtype=np.int16)).tobytes()


def test_vad_init_and_threshold() -> None:
    vad = EnergyVAD(energy_threshold=400.0)
    assert vad.threshold == 400.0

    with pytest.raises(ValueError, match="non-negative"):
        EnergyVAD(energy_threshold=-1.0)


def test_vad_silence_detection() -> None:
    vad = EnergyVAD(energy_threshold=300.0)
    silence_bytes = make_silence_pcm(duration_ms=30.0)

    assert vad.compute_rms(silence_bytes) == 0.0
    assert vad.compute_peak(silence_bytes) == 0
    assert vad.is_speech(silence_bytes) is False

    is_sp, rms, peak = vad.analyze(silence_bytes)
    assert is_sp is False
    assert rms == 0.0
    assert peak == 0


def test_vad_speech_above_threshold() -> None:
    vad = EnergyVAD(energy_threshold=500.0)
    # Sine wave with amplitude 2000 has RMS ≈ 2000 / sqrt(2) ≈ 1414.2
    sine_bytes = make_sine_pcm(amplitude=2000, duration_ms=30.0)

    rms = vad.compute_rms(sine_bytes)
    peak = vad.compute_peak(sine_bytes)

    assert pytest.approx(rms, rel=1e-2) == 2000.0 / np.sqrt(2.0)
    assert peak <= 2000 and peak >= 1990
    assert vad.is_speech(sine_bytes) is True

    is_sp, r, p = vad.analyze(sine_bytes)
    assert is_sp is True
    assert r == rms
    assert p == peak


def test_vad_audio_below_threshold() -> None:
    vad = EnergyVAD(energy_threshold=500.0)
    # Sine wave with amplitude 200 has RMS ≈ 141.4 (below 500.0)
    quiet_bytes = make_sine_pcm(amplitude=200, duration_ms=30.0)

    assert vad.compute_rms(quiet_bytes) < 500.0
    assert vad.is_speech(quiet_bytes) is False


def test_vad_with_audio_frame() -> None:
    vad = EnergyVAD(energy_threshold=500.0)
    sine_bytes = make_sine_pcm(amplitude=3000, duration_ms=30.0)
    frame = AudioFrame(
        data=sine_bytes,
        sample_rate=AUDIO_SAMPLE_RATE,
        channels=1,
        timestamp_ns=1000,
        samples_count=480,
    )

    assert vad.is_speech(frame) is True
    is_sp, rms, peak = vad.analyze(frame)
    assert is_sp is True
    assert peak > 2900


def test_vad_with_numpy_array() -> None:
    vad = EnergyVAD(energy_threshold=500.0)
    samples = np.full(480, fill_value=1000, dtype=np.int16)
    assert vad.compute_rms(samples) == 1000.0
    assert vad.compute_peak(samples) == 1000
    assert vad.is_speech(samples) is True


def test_vad_empty_and_corrupt_bytes_safe() -> None:
    vad = EnergyVAD(energy_threshold=500.0)

    assert vad.compute_rms(b"") == 0.0
    assert vad.compute_peak(b"") == 0
    assert vad.is_speech(b"") is False

    # 1 byte (odd length for int16)
    assert vad.compute_rms(b"\x05") == 0.0
    assert vad.is_speech(b"\x05") is False

    is_sp, rms, peak = vad.analyze(b"")
    assert is_sp is False
    assert rms == 0.0
    assert peak == 0


def test_extract_int16_samples_variants() -> None:
    # From bytes
    b = b"\x01\x00\x02\x00"
    arr = extract_int16_samples(b)
    assert len(arr) == 2
    assert arr[0] == 1 and arr[1] == 2

    # From AudioFrame
    f = AudioFrame(data=b, sample_rate=16000, channels=1, timestamp_ns=0, samples_count=2)
    arr_f = extract_int16_samples(f)
    assert len(arr_f) == 2

    # From invalid object
    assert len(extract_int16_samples(None)) == 0  # type: ignore
