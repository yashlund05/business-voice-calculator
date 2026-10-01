"""Unit tests for ASR engine abstractions and FakeEngine."""

import numpy as np
import pytest
from voice_calculator.asr.base import (
    ASREngine,
    ASRError,
    ASRResult,
    ASRStatus,
    FakeEngine,
    ModelLoadError,
    ModelMissingError,
)


def test_asr_result_properties():
    """Verify ASRResult fields, defaults, and immutability."""
    res = ASRResult(
        text="one hundred and fifty",
        confidence=0.95,
        alternatives=["one hundred fifty"],
        engine="test_engine",
        elapsed_ms=12.5,
        status=ASRStatus.SUCCESS,
    )

    assert res.text == "one hundred and fifty"
    assert res.confidence == 0.95
    assert res.alternatives == ["one hundred fifty"]
    assert res.engine == "test_engine"
    assert res.elapsed_ms == 12.5
    assert res.status == ASRStatus.SUCCESS
    assert res.error_message is None

    # Immutability check
    with pytest.raises(Exception):
        res.text = "two hundred"  # type: ignore


def test_fake_engine_lifecycle_and_default_transcribe():
    """Verify FakeEngine load state, call tracking, and default transcription."""
    engine = FakeEngine(name="mock_asr", default_text="forty five")
    assert not engine.is_loaded
    assert engine.transcribe_calls == 0

    engine.load()
    assert engine.is_loaded

    pcm = b"\x00" * 960  # 480 samples of int16
    res = engine.transcribe(pcm)

    assert res.status == ASRStatus.SUCCESS
    assert res.text == "forty five"
    assert res.engine == "mock_asr"
    assert engine.transcribe_calls == 1
    assert engine.last_pcm_size == 960


def test_fake_engine_numpy_input():
    """Verify FakeEngine accepts numpy array input seamlessly."""
    engine = FakeEngine(name="mock_asr", default_text="twenty")
    audio_array = np.zeros(480, dtype=np.int16)

    res = engine.transcribe(audio_array)
    assert res.status == ASRStatus.SUCCESS
    assert res.text == "twenty"
    assert engine.last_pcm_size == 480 * 2


def test_fake_engine_scripted_responses():
    """Verify FakeEngine returns scripted sequence of responses in FIFO order."""
    script = ["one", "two", "three"]
    engine = FakeEngine()
    engine.set_script(script)

    res1 = engine.transcribe(b"\x00" * 100)
    res2 = engine.transcribe(b"\x00" * 100)
    res3 = engine.transcribe(b"\x00" * 100)

    assert res1.text == "one"
    assert res2.text == "two"
    assert res3.text == "three"
    assert engine.transcribe_calls == 3

    # Subsequent call falls back to default
    res4 = engine.transcribe(b"\x00" * 100)
    assert res4.status == ASRStatus.NO_SPEECH


def test_fake_engine_no_speech_and_empty_input():
    """Verify FakeEngine properly flags NO_SPEECH on empty buffer or when configured."""
    engine = FakeEngine(should_return_no_speech=True)
    res = engine.transcribe(b"\x00" * 500)
    assert res.status == ASRStatus.NO_SPEECH
    assert res.text == ""

    # Empty audio buffer always yields NO_SPEECH
    engine2 = FakeEngine(default_text="should not see this")
    res_empty = engine2.transcribe(b"")
    assert res_empty.status == ASRStatus.NO_SPEECH


def test_fake_engine_failure_mode():
    """Verify FakeEngine returns ERROR status with message when simulated failure is enabled."""
    engine = FakeEngine(should_fail=True, error_message="Acoustic model exception")
    res = engine.transcribe(b"\x00" * 400)

    assert res.status == ASRStatus.ERROR
    assert res.text == ""
    assert res.error_message == "Acoustic model exception"


def test_typed_asr_exceptions():
    """Verify inheritance hierarchy of ASR exception classes."""
    assert issubclass(ModelMissingError, ASRError)
    assert issubclass(ModelLoadError, ASRError)
