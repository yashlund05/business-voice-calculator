"""Unit and integration tests for FasterWhisperEngine."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

import numpy as np
import pytest

from voice_calculator.asr.base import ASREngine, ASRResult, ASRStatus, ModelLoadError, ModelMissingError
from voice_calculator.asr.whisper_engine import FasterWhisperEngine, WhisperConfig
from voice_calculator.config import (
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL_PATH,
)
from voice_calculator.decision import DecisionConfig, DecisionType, OperatingMode, SafetyDecisionEngine
from voice_calculator.pipeline import AudioPipeline, PipelineResult, PipelineStatus


# --- 1. Unit Tests (Model-Independent / Hardware-Independent) ---


def test_whisper_engine_initialization_defaults():
    """Verify engine name, default path, device, compute_type, and initial state."""
    engine = FasterWhisperEngine()
    assert engine.name == "faster-whisper"
    assert engine.model_path_or_size == WHISPER_MODEL_PATH
    assert engine.device == WHISPER_DEVICE.lower()
    assert engine.compute_type == WHISPER_COMPUTE_TYPE.lower()
    assert not engine.is_loaded


def test_whisper_engine_custom_config():
    """Verify custom configuration options are respected."""
    engine = FasterWhisperEngine(
        model_path_or_size="models/custom_whisper",
        device="cuda",
        compute_type="float16",
        cpu_threads=8,
        beam_size=2,
        language="en",
        initial_prompt="zero, one, two, three, calculator numbers",
        name="whisper-gpu",
    )
    assert engine.name == "whisper-gpu"
    assert engine.model_path_or_size == Path("models/custom_whisper")
    assert engine.device == "cuda"
    assert engine.compute_type == "float16"
    assert engine.cpu_threads == 8
    assert engine.beam_size == 2
    assert engine.language == "en"
    assert engine.initial_prompt == "zero, one, two, three, calculator numbers"


def test_whisper_config_dataclass():
    """Verify WhisperConfig dataclass defaults and immutability."""
    cfg = WhisperConfig()
    assert cfg.device == WHISPER_DEVICE
    assert cfg.compute_type == WHISPER_COMPUTE_TYPE
    assert cfg.beam_size == 1

    with pytest.raises(Exception):
        cfg.device = "cuda"  # Frozen dataclass


def test_whisper_engine_model_missing_error(tmp_path: Path):
    """Verify ModelMissingError is raised when model path does not exist."""
    non_existent = tmp_path / "missing_whisper_model"
    engine = FasterWhisperEngine(model_path_or_size=non_existent)

    with pytest.raises(ModelMissingError, match="faster-whisper model directory not found"):
        engine.load()


def test_whisper_engine_import_error_mock(tmp_path: Path):
    """Verify ModelLoadError is raised when faster-whisper package is not installed."""
    model_dir = tmp_path / "fake_whisper_dir"
    model_dir.mkdir()

    engine = FasterWhisperEngine(model_path_or_size=model_dir)

    with patch.dict(sys.modules, {"faster_whisper": None}):
        with pytest.raises(ModelLoadError, match="faster-whisper package is not installed"):
            engine.load()


def test_whisper_engine_model_load_mock(tmp_path: Path):
    """Verify load() succeeds and sets is_loaded when faster_whisper.WhisperModel initializes."""
    model_dir = tmp_path / "fake_whisper_dir"
    model_dir.mkdir()

    mock_fw = MagicMock()
    mock_model_inst = MagicMock()
    mock_fw.WhisperModel.return_value = mock_model_inst

    with patch.dict(sys.modules, {"faster_whisper": mock_fw}):
        engine = FasterWhisperEngine(model_path_or_size=model_dir, device="cpu", compute_type="int8")
        engine.load()

        assert engine.is_loaded
        mock_fw.WhisperModel.assert_called_once_with(
            model_size_or_path=str(model_dir),
            device="cpu",
            compute_type="int8",
            cpu_threads=4,
            local_files_only=True,
        )

        # Idempotent: second load does not re-instantiate
        engine.load()
        assert mock_fw.WhisperModel.call_count == 1


def test_whisper_engine_model_load_error_mock(tmp_path: Path):
    """Verify ModelLoadError is raised when WhisperModel throws during initialization."""
    model_dir = tmp_path / "corrupted_whisper_dir"
    model_dir.mkdir()

    mock_fw = MagicMock()
    mock_fw.WhisperModel.side_effect = RuntimeError("CUDA out of memory or corrupted weights")

    with patch.dict(sys.modules, {"faster_whisper": mock_fw}):
        engine = FasterWhisperEngine(model_path_or_size=model_dir)
        with pytest.raises(ModelLoadError, match="Failed to load faster-whisper model"):
            engine.load()


def test_whisper_engine_transcribe_empty_audio():
    """Verify empty audio input immediately returns NO_SPEECH without invoking model."""
    engine = FasterWhisperEngine()
    res = engine.transcribe(b"")

    assert res.status == ASRStatus.NO_SPEECH
    assert res.text == ""
    assert res.engine == "faster-whisper"
    assert res.confidence is None


def test_whisper_engine_transcribe_success_mock(tmp_path: Path):
    """Verify transcription result mapping and punctuation cleanup when faster-whisper returns segments."""
    model_dir = tmp_path / "fake_whisper_dir"
    model_dir.mkdir()

    mock_seg1 = MagicMock()
    mock_seg1.text = " 1,500 "
    mock_seg2 = MagicMock()
    mock_seg2.text = " and fifty. "

    mock_fw = MagicMock()
    mock_model_inst = MagicMock()
    mock_model_inst.transcribe.return_value = ([mock_seg1, mock_seg2], MagicMock())
    mock_fw.WhisperModel.return_value = mock_model_inst

    with patch.dict(sys.modules, {"faster_whisper": mock_fw}):
        engine = FasterWhisperEngine(model_path_or_size=model_dir)
        pcm_bytes = b"\x00" * 960

        res = engine.transcribe(pcm_bytes)

        assert res.status == ASRStatus.SUCCESS
        # Note: comma in 1,500 stripped to 1500
        assert res.text == "1500 and fifty."
        assert res.engine == "faster-whisper"
        assert res.confidence is None  # Uncalibrated score invariant
        assert res.elapsed_ms >= 0.0


def test_whisper_engine_transcribe_numpy_input_mock(tmp_path: Path):
    """Verify transcribe accepts numpy ndarray and normalizes to float32."""
    model_dir = tmp_path / "fake_whisper_dir"
    model_dir.mkdir()

    mock_seg = MagicMock()
    mock_seg.text = " forty five "

    mock_fw = MagicMock()
    mock_model_inst = MagicMock()
    mock_model_inst.transcribe.return_value = ([mock_seg], MagicMock())
    mock_fw.WhisperModel.return_value = mock_model_inst

    with patch.dict(sys.modules, {"faster_whisper": mock_fw}):
        engine = FasterWhisperEngine(model_path_or_size=model_dir)
        audio_arr = np.zeros(480, dtype=np.int16)

        res = engine.transcribe(audio_arr)
        assert res.status == ASRStatus.SUCCESS
        assert res.text == "forty five"

        # Verify float32 audio passed to model
        called_args = mock_model_inst.transcribe.call_args[0]
        passed_audio = called_args[0]
        assert isinstance(passed_audio, np.ndarray)
        assert passed_audio.dtype == np.float32


def test_whisper_engine_transcribe_missing_model_returns_error():
    """Verify transcribe returns ASRStatus.ERROR when model path does not exist."""
    engine = FasterWhisperEngine(model_path_or_size="non_existent_whisper_path")
    res = engine.transcribe(b"\x00" * 480)

    assert res.status == ASRStatus.ERROR
    assert res.error_message is not None
    assert "faster-whisper model directory not found" in res.error_message


def test_whisper_engine_transcribe_runtime_error_mock(tmp_path: Path):
    """Verify transcribe returns ASRStatus.ERROR when model.transcribe raises an exception."""
    model_dir = tmp_path / "fake_whisper_dir"
    model_dir.mkdir()

    mock_fw = MagicMock()
    mock_model_inst = MagicMock()
    mock_model_inst.transcribe.side_effect = RuntimeError("Inference kernel failure")
    mock_fw.WhisperModel.return_value = mock_model_inst

    with patch.dict(sys.modules, {"faster_whisper": mock_fw}):
        engine = FasterWhisperEngine(model_path_or_size=model_dir)
        res = engine.transcribe(b"\x00" * 480)

        assert res.status == ASRStatus.ERROR
        assert "Inference kernel failure" in res.error_message


def test_whisper_engine_uncalibrated_confidence_forces_confirmation(tmp_path: Path):
    """Verify safety decision engine strictly enforces manual confirmation on faster-whisper outputs.

    Even in Fast Mode with auto_accept_enabled=True, missing/uncalibrated confidence (None)
    MUST NOT be silently added.
    """
    model_dir = tmp_path / "fake_whisper_dir"
    model_dir.mkdir()

    mock_seg = MagicMock()
    mock_seg.text = "one hundred"

    mock_fw = MagicMock()
    mock_model_inst = MagicMock()
    mock_model_inst.transcribe.return_value = ([mock_seg], MagicMock())
    mock_fw.WhisperModel.return_value = mock_model_inst

    with patch.dict(sys.modules, {"faster_whisper": mock_fw}):
        engine = FasterWhisperEngine(model_path_or_size=model_dir)
        res = engine.transcribe(b"\x00" * 960)

        # Decision engine evaluation in Fast Mode with auto_accept_enabled
        decision_config = DecisionConfig(
            mode=OperatingMode.FAST,
            auto_accept_enabled=True,
            min_confidence=0.85,
        )
        decision_engine = SafetyDecisionEngine(config=decision_config)

        from voice_calculator.numparse import parse
        parse_res = parse(res.text)

        pipeline_result = PipelineResult(
            status=PipelineStatus.PARSED,
            asr_result=res,
            parse_result=parse_res,
        )

        decision = decision_engine.evaluate(pipeline_result)

        assert decision.decision == DecisionType.ACCEPT
        assert decision.value == 100
        # CRITICAL SAFETY INVARIANT: requires_confirmation MUST remain True because confidence is None
        assert decision.requires_confirmation is True


def test_whisper_engine_conforms_to_asr_engine_protocol():
    """Verify FasterWhisperEngine satisfies ASREngine protocol requirements."""
    engine = FasterWhisperEngine()
    assert hasattr(engine, "name")
    assert hasattr(engine, "is_loaded")
    assert hasattr(engine, "load")
    assert hasattr(engine, "transcribe")
    assert callable(engine.load)
    assert callable(engine.transcribe)


# --- 2. Local Model Integration Test (Cleanly Skipped When Model / Lib Absent) ---


@pytest.mark.skipif(
    not WHISPER_MODEL_PATH.exists() or not WHISPER_MODEL_PATH.is_dir(),
    reason="Local faster-whisper model not present in models/ directory (expected in clean repo)",
)
def test_whisper_real_model_integration():
    """Live integration test: loads real local faster-whisper model and transcribes silence if present."""
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        pytest.skip("faster-whisper package not installed in environment")

    engine = FasterWhisperEngine(model_path_or_size=WHISPER_MODEL_PATH)
    engine.load()
    assert engine.is_loaded

    # Transcribe 1 second of silence
    silence_pcm = b"\x00" * (16000 * 2)
    res = engine.transcribe(silence_pcm)
    assert res.status in (ASRStatus.SUCCESS, ASRStatus.NO_SPEECH)
