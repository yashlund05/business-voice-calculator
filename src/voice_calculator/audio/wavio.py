"""WAV file serialization and deserialization helpers for 16 kHz mono 16-bit PCM.

Guarantees:
- Uses Python standard library wave module (no heavy audio dependencies).
- Strictly validates 16 kHz, mono (1 channel), and 16-bit (2 bytes) sample format.
- Rejects unsupported, malformed, or corrupted WAV files cleanly.
- Never mutates or alters PCM audio bytes during read/write.
- Does not log raw audio data.
"""

import io
from pathlib import Path
from typing import BinaryIO, Tuple, Union
import wave

from voice_calculator.audio.capture import AudioError
from voice_calculator.config import AUDIO_CHANNELS, AUDIO_SAMPLE_RATE


class WavFormatError(AudioError):
    """Raised when a WAV file does not conform to the expected format (16 kHz mono int16)."""


def read_wav(
    source: Union[str, Path, bytes, BinaryIO],
    expected_sample_rate: int = AUDIO_SAMPLE_RATE,
    expected_channels: int = AUDIO_CHANNELS,
    expected_sample_width: int = 2,
) -> Tuple[bytes, int, int]:
    """Reads and validates a 16-bit mono PCM WAV file or bytes.

    Args:
        source: File path, Path object, raw WAV bytes, or file-like binary stream.
        expected_sample_rate: Required sampling rate in Hz (default: 16000).
        expected_channels: Required number of channels (default: 1).
        expected_sample_width: Required sample width in bytes (default: 2 for 16-bit PCM).

    Returns:
        Tuple of (pcm_bytes, sample_rate, channels).

    Raises:
        WavFormatError: If the WAV header is corrupt, or if sample rate, channels,
                        or sample width do not match the expected project contract.
        FileNotFoundError: If a specified file path does not exist.
    """
    file_obj: Union[io.BytesIO, BinaryIO]
    should_close = False

    if isinstance(source, bytes):
        file_obj = io.BytesIO(source)
    elif isinstance(source, (str, Path)):
        p = Path(source)
        if not p.is_file():
            raise FileNotFoundError(f"WAV file not found: {source}")
        file_obj = open(p, "rb")
        should_close = True
    else:
        file_obj = source

    try:
        try:
            with wave.open(file_obj, "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                num_frames = wf.getnframes()
                comptype = wf.getcomptype()

                if comptype != "NONE":
                    raise WavFormatError(f"Unsupported compression type: {comptype}. Expected uncompressed PCM.")

                if channels != expected_channels:
                    raise WavFormatError(
                        f"Unsupported channel count: {channels}. Expected {expected_channels} (mono)."
                    )

                if sample_rate != expected_sample_rate:
                    raise WavFormatError(
                        f"Unsupported sample rate: {sample_rate} Hz. Expected {expected_sample_rate} Hz."
                    )

                if sample_width != expected_sample_width:
                    raise WavFormatError(
                        f"Unsupported sample width: {sample_width} bytes ({sample_width * 8}-bit). Expected {expected_sample_width} bytes (16-bit)."
                    )

                pcm_data = wf.readframes(num_frames)
                return pcm_data, sample_rate, channels

        except (wave.Error, EOFError) as e:
            raise WavFormatError(f"Malformed or truncated WAV file: {e}") from e

    finally:
        if should_close:
            file_obj.close()


def write_wav(
    destination: Union[str, Path, BinaryIO],
    pcm_data: bytes,
    sample_rate: int = AUDIO_SAMPLE_RATE,
    channels: int = AUDIO_CHANNELS,
    sample_width: int = 2,
) -> None:
    """Writes raw PCM bytes to a WAV file or binary stream.

    Args:
        destination: File path, Path object, or writable binary stream.
        pcm_data: Raw PCM audio bytes.
        sample_rate: Sampling frequency in Hz (default: 16000).
        channels: Channel count (default: 1).
        sample_width: Sample width in bytes (default: 2 for 16-bit).

    Raises:
        WavFormatError: If arguments are invalid.
    """
    if sample_rate <= 0:
        raise WavFormatError(f"Invalid sample rate: {sample_rate}")
    if channels <= 0:
        raise WavFormatError(f"Invalid channel count: {channels}")
    if sample_width not in (1, 2, 4):
        raise WavFormatError(f"Invalid sample width: {sample_width}")

    file_obj: Union[io.BytesIO, BinaryIO]
    should_close = False

    if isinstance(destination, (str, Path)):
        p = Path(destination)
        p.parent.mkdir(parents=True, exist_ok=True)
        file_obj = open(p, "wb")
        should_close = True
    else:
        file_obj = destination

    try:
        with wave.open(file_obj, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
    except wave.Error as e:
        raise WavFormatError(f"Failed to write WAV file: {e}") from e
    finally:
        if should_close:
            file_obj.close()


def write_wav_bytes(
    pcm_data: bytes,
    sample_rate: int = AUDIO_SAMPLE_RATE,
    channels: int = AUDIO_CHANNELS,
    sample_width: int = 2,
) -> bytes:
    """Serializes raw PCM bytes into in-memory WAV formatted bytes."""
    buf = io.BytesIO()
    write_wav(buf, pcm_data, sample_rate=sample_rate, channels=channels, sample_width=sample_width)
    return buf.getvalue()
