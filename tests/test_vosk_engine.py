"""Unit and integration tests for VoskEngine."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from voice_calculator.asr.base import ASRResult, ASRStatus, ModelLoadError, ModelMissingError
from voice_calculator.asr.vosk_engine import (
    DEFAULT_NUMBER_GRAMMAR,
    VoskEngine,
    get_default_number_grammar,
)
from voice_calculator.config import VOSK_MODEL_PATH


# --- 1. Unit Tests (Model-Independent) ---


def test_vosk_engine_initialization_defaults():
    """Verify engine name, default path, and grammar configuration."""
    engine = VoskEngine()
    assert engine.name == "vosk"
    assert engine.model_path == VOSK_MODEL_PATH
    assert not engine.is_loaded
    assert len(engine.grammar) > 20
    assert "[unk]" in engine.grammar


def test_vosk_grammar_vocabulary_coverage():
    """Verify closed vocabulary includes all required number-words."""
    grammar = get_default_number_grammar()
    required_words = [
        "zero", "one", "two", "ten", "fifteen", "twenty", "fifty", "ninety",
        "hundred", "thousand", "and", "a", "[unk]"
    ]
    for word in required_words:
        assert word in grammar


def test_vosk_model_missing_error(tmp_path: Path):
    """Verify ModelMissingError is raised when model path does not exist."""
    non_existent = tmp_path / "missing_vosk_model"
    engine = VoskEngine(model_path=non_existent)

    with pytest.raises(ModelMissingError, match="Vosk model directory not found"):
        engine.load()


def test_vosk_model_load_mock(tmp_path: Path):
    """Verify load() succeeds and sets is_loaded when vosk.Model initializes."""
    model_dir = tmp_path / "fake_model_dir"
    model_dir.mkdir()

    with patch("vosk.Model") as mock_model_cls:
        mock_model_cls.return_value = MagicMock()
        engine = VoskEngine(model_path=model_dir)

        engine.load()
        assert engine.is_loaded

        # Repeated load is idempotent
        engine.load()
        assert mock_model_cls.call_count == 1


def test_vosk_model_load_error_mock(tmp_path: Path):
    """Verify ModelLoadError is raised when vosk.Model throws during initialization."""
    model_dir = tmp_path / "corrupted_model_dir"
    model_dir.mkdir()

    with patch("vosk.Model", side_effect=RuntimeError("Corrupted model file")):
        engine = VoskEngine(model_path=model_dir)
        with pytest.raises(ModelLoadError, match="Failed to load Vosk model"):
            engine.load()


def test_vosk_transcribe_empty_audio():
    """Verify empty audio input immediately returns NO_SPEECH without invoking model."""
    engine = VoskEngine()
    res = engine.transcribe(b"")

    assert res.status == ASRStatus.NO_SPEECH
    assert res.text == ""
    assert res.engine == "vosk"
    assert res.confidence is None


def test_vosk_transcribe_success_mock(tmp_path: Path):
    """Verify transcription result mapping when Vosk recognizer returns text."""
    model_dir = tmp_path / "fake_model_dir"
    model_dir.mkdir()

    with patch("vosk.Model"):
        with patch("vosk.KaldiRecognizer") as mock_rec_cls:
            mock_rec = MagicMock()
            mock_rec.FinalResult.return_value = json.dumps({"text": "one hundred and fifty"})
            mock_rec_cls.return_value = mock_rec

            engine = VoskEngine(model_path=model_dir)
            pcm_bytes = b"\x00" * 960

            res = engine.transcribe(pcm_bytes)

            assert res.status == ASRStatus.SUCCESS
            assert res.text == "one hundred and fifty"
            assert res.engine == "vosk"
            assert res.confidence is None
            assert res.elapsed_ms >= 0.0


def test_vosk_transcribe_unk_filtered_to_empty(tmp_path: Path):
    """Verify [unk] out-of-vocabulary tokens are filtered to empty NO_SPEECH."""
    model_dir = tmp_path / "fake_model_dir"
    model_dir.mkdir()

    with patch("vosk.Model"):
        with patch("vosk.KaldiRecognizer") as mock_rec_cls:
            mock_rec = MagicMock()
            mock_rec.FinalResult.return_value = json.dumps({"text": "[unk]"})
            mock_rec_cls.return_value = mock_rec

            engine = VoskEngine(model_path=model_dir)
            res = engine.transcribe(b"\x00" * 960)

            assert res.status == ASRStatus.NO_SPEECH
            assert res.text == ""


def test_vosk_transcribe_numpy_input_mock(tmp_path: Path):
    """Verify transcribe accepts numpy ndarray."""
    model_dir = tmp_path / "fake_model_dir"
    model_dir.mkdir()

    with patch("vosk.Model"):
        with patch("vosk.KaldiRecognizer") as mock_rec_cls:
            mock_rec = MagicMock()
            mock_rec.FinalResult.return_value = json.dumps({"text": "forty five"})
            mock_rec_cls.return_value = mock_rec

            engine = VoskEngine(model_path=model_dir)
            audio_arr = np.zeros(480, dtype=np.int16)

            res = engine.transcribe(audio_arr)
            assert res.status == ASRStatus.SUCCESS
            assert res.text == "forty five"


def test_vosk_transcribe_missing_model_returns_error():
    """Verify transcribe returns ASRStatus.ERROR when model is missing and cannot be loaded."""
    engine = VoskEngine(model_path="non_existent_path")
    res = engine.transcribe(b"\x00" * 480)

    assert res.status == ASRStatus.ERROR
    assert res.error_message is not None
    assert "Vosk model directory not found" in res.error_message


# --- 2. Local Model Integration Test (Cleanly Skipped When Model Absent) ---


@pytest.mark.skipif(
    not VOSK_MODEL_PATH.exists() or not VOSK_MODEL_PATH.is_dir(),
    reason="Local Vosk model not present in models/ directory (expected in clean repo)",
)
def test_vosk_real_model_integration():
    """Live integration test: loads real local Vosk model and transcribes silence if present."""
    engine = VoskEngine(model_path=VOSK_MODEL_PATH)
    engine.load()
    assert engine.is_loaded

    # Transcribe 1 second of silence
    silence_pcm = b"\x00" * (16000 * 2)
    res = engine.transcribe(silence_pcm)
    assert res.status in (ASRStatus.SUCCESS, ASRStatus.NO_SPEECH)
