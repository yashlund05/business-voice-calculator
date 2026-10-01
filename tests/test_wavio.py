"""Unit tests for WAV serialization, deserialization, and format validation."""

import io
import struct
from pathlib import Path

import pytest
from voice_calculator.audio.wavio import (
    WavFormatError,
    read_wav,
    write_wav,
    write_wav_bytes,
)


def test_wav_round_trip_bytes():
    """Verify in-memory WAV serialization and deserialization preserves raw PCM bytes."""
    # Create sample 16-bit PCM waveform (e.g. 100 samples)
    samples = [int(32767 * (i % 10 - 5) / 5) for i in range(100)]
    pcm_data = struct.pack(f"<{len(samples)}h", *samples)

    wav_bytes = write_wav_bytes(pcm_data, sample_rate=16000, channels=1, sample_width=2)
    assert len(wav_bytes) > len(pcm_data)  # Contains RIFF header

    read_pcm, sample_rate, channels = read_wav(wav_bytes)

    assert read_pcm == pcm_data
    assert sample_rate == 16000
    assert channels == 1


def test_wav_round_trip_file(tmp_path: Path):
    """Verify file-based WAV write and read round-trip."""
    file_path = tmp_path / "audio" / "test.wav"
    pcm_data = b"\x12\x34\x56\x78" * 100  # 400 bytes

    write_wav(file_path, pcm_data, sample_rate=16000, channels=1, sample_width=2)
    assert file_path.is_file()

    read_pcm, sample_rate, channels = read_wav(file_path)
    assert read_pcm == pcm_data
    assert sample_rate == 16000
    assert channels == 1


def test_wav_empty_pcm_round_trip():
    """Verify empty PCM data round-trips without error."""
    empty_pcm = b""
    wav_bytes = write_wav_bytes(empty_pcm, sample_rate=16000, channels=1, sample_width=2)

    read_pcm, sample_rate, channels = read_wav(wav_bytes)
    assert read_pcm == b""
    assert sample_rate == 16000
    assert channels == 1


def test_wav_boundary_pcm_values():
    """Verify int16 extreme values (-32768, 0, 32767) are preserved exactly."""
    pcm_data = struct.pack("<hhh", -32768, 0, 32767)
    wav_bytes = write_wav_bytes(pcm_data, sample_rate=16000, channels=1, sample_width=2)

    read_pcm, _, _ = read_wav(wav_bytes)
    unpacked = struct.unpack("<hhh", read_pcm)
    assert unpacked == (-32768, 0, 32767)


def test_wav_rejects_wrong_sample_rate():
    """Verify WavFormatError is raised when sample rate is not 16 kHz."""
    pcm_data = b"\x00\x00" * 100
    wav_44k = write_wav_bytes(pcm_data, sample_rate=44100, channels=1, sample_width=2)

    with pytest.raises(WavFormatError, match="Unsupported sample rate: 44100 Hz"):
        read_wav(wav_44k, expected_sample_rate=16000)


def test_wav_rejects_stereo_channels():
    """Verify WavFormatError is raised when channel count is not 1 (mono)."""
    pcm_data = b"\x00\x00\x00\x00" * 50  # 2 channels
    wav_stereo = write_wav_bytes(pcm_data, sample_rate=16000, channels=2, sample_width=2)

    with pytest.raises(WavFormatError, match="Unsupported channel count: 2"):
        read_wav(wav_stereo, expected_channels=1)


def test_wav_rejects_wrong_sample_width():
    """Verify WavFormatError is raised when sample width is not 2 bytes (16-bit)."""
    pcm_data = b"\x80" * 100  # 8-bit PCM
    wav_8bit = write_wav_bytes(pcm_data, sample_rate=16000, channels=1, sample_width=1)

    with pytest.raises(WavFormatError, match="Unsupported sample width: 1 bytes"):
        read_wav(wav_8bit, expected_sample_width=2)


def test_wav_rejects_malformed_truncated_data():
    """Verify WavFormatError is raised on truncated or corrupt WAV bytes."""
    corrupt_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt "  # Incomplete header

    with pytest.raises(WavFormatError, match="Malformed or truncated WAV file"):
        read_wav(corrupt_bytes)


def test_wav_file_not_found():
    """Verify FileNotFoundError is raised when file does not exist."""
    with pytest.raises(FileNotFoundError):
        read_wav("non_existent_audio_file.wav")


def test_wav_write_invalid_parameters():
    """Verify write_wav rejects invalid sample rates, channels, or widths."""
    buf = io.BytesIO()
    with pytest.raises(WavFormatError):
        write_wav(buf, b"", sample_rate=0)

    with pytest.raises(WavFormatError):
        write_wav(buf, b"", channels=0)

    with pytest.raises(WavFormatError):
        write_wav(buf, b"", sample_width=3)
