"""Unit tests for the single-utterance audio processing pipeline orchestration layer."""

import numpy as np
import pytest

from voice_calculator.asr.base import ASRResult, ASRStatus, FakeEngine
from voice_calculator.audio.capture import AudioFrame, FakeAudioSource, MicLost
from voice_calculator.audio.segmenter import Utterance, UtteranceSegmenter
from voice_calculator.audio.vad import EnergyVAD
from voice_calculator.config import AUDIO_SAMPLE_RATE
from voice_calculator.numparse import RejectReason
from voice_calculator.pipeline import AudioPipeline, PipelineResult, PipelineStatus


def make_sine_pcm(amplitude: int = 2000, duration_ms: float = 30.0, freq_hz: float = 440.0) -> bytes:
    """Generates synthetic 16-bit mono sine wave PCM."""
    n_samples = int(AUDIO_SAMPLE_RATE * (duration_ms / 1000.0))
    t = np.linspace(0, duration_ms / 1000.0, n_samples, endpoint=False)
    samples = (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.int16)
    return samples.tobytes()


def make_silence_pcm(duration_ms: float = 30.0) -> bytes:
    """Generates synthetic 16-bit mono silence PCM."""
    n_samples = int(AUDIO_SAMPLE_RATE * (duration_ms / 1000.0))
    return np.zeros(n_samples, dtype=np.int16).tobytes()


def make_frame(
    is_speech: bool,
    duration_ms: float = 30.0,
    timestamp_ns: int = 0,
    overflow: bool = False,
) -> AudioFrame:
    """Helper to generate an AudioFrame."""
    pcm = make_sine_pcm(duration_ms=duration_ms) if is_speech else make_silence_pcm(duration_ms=duration_ms)
    n_samples = len(pcm) // 2
    return AudioFrame(
        data=pcm,
        sample_rate=AUDIO_SAMPLE_RATE,
        channels=1,
        timestamp_ns=timestamp_ns,
        samples_count=n_samples,
        overflow=overflow,
    )


def create_pipeline(
    default_text: str = "forty two",
    should_fail_asr: bool = False,
    should_return_no_speech: bool = False,
    pre_roll_ms: int = 60,
    hangover_ms: int = 60,
    min_utterance_ms: int = 90,
) -> AudioPipeline:
    """Helper to construct an AudioPipeline with deterministic test fakes."""
    source = FakeAudioSource()
    source.start()

    vad = EnergyVAD(energy_threshold=500.0)
    segmenter = UtteranceSegmenter(
        vad=vad,
        pre_roll_ms=pre_roll_ms,
        hangover_ms=hangover_ms,
        min_utterance_ms=min_utterance_ms,
    )

    engine = FakeEngine(
        name="test_fake_engine",
        default_text=default_text,
        should_fail=should_fail_asr,
        should_return_no_speech=should_return_no_speech,
    )
    engine.load()

    return AudioPipeline(source=source, segmenter=segmenter, engine=engine)


# --- 1. Silence Only ---


def test_pipeline_silence_only_produces_none() -> None:
    pipeline = create_pipeline()

    # Push 10 silence frames (300 ms)
    for _ in range(10):
        pipeline.source.push_pcm_bytes(make_silence_pcm())

    # Process all frames from source
    for _ in range(10):
        result = pipeline.process_next_frame(timeout=0.01)
        assert result is None


# --- 2. Speech -> ASR Success -> Parser Success (PARSED) ---


def test_pipeline_speech_to_parsed_success() -> None:
    pipeline = create_pipeline(default_text="forty two")

    # Push 4 speech frames (120 ms) + 3 hangover silence frames (90 ms)
    for _ in range(4):
        pipeline.source.push_pcm_bytes(make_sine_pcm(amplitude=2000))
    for _ in range(3):
        pipeline.source.push_pcm_bytes(make_silence_pcm())

    results = []
    for _ in range(7):
        res = pipeline.process_next_frame(timeout=0.01)
        if res is not None:
            results.append(res)

    assert len(results) == 1
    result = results[0]

    assert result.status == PipelineStatus.PARSED
    assert result.parsed_value == 42
    assert result.recognized_text == "forty two"
    assert result.total_latency_ms >= 0.0
    assert result.utterance is not None
    assert result.utterance.duration_ms == 180.0


# --- 3. Speech -> ASR Text -> Parser Rejection (PARSER_REJECTED) ---


def test_pipeline_speech_to_parser_rejection_command_word() -> None:
    pipeline = create_pipeline(default_text="undo")

    # Push speech + hangover
    for _ in range(4):
        pipeline.source.push_pcm_bytes(make_sine_pcm(amplitude=2000))
    for _ in range(3):
        pipeline.source.push_pcm_bytes(make_silence_pcm())

    results = []
    for _ in range(7):
        res = pipeline.process_next_frame(timeout=0.01)
        if res is not None:
            results.append(res)

    assert len(results) == 1
    result = results[0]

    assert result.status == PipelineStatus.PARSER_REJECTED
    assert result.parsed_value is None
    assert result.recognized_text == "undo"
    assert result.reject_reason == RejectReason.NOT_A_NUMBER


def test_pipeline_speech_to_parser_rejection_malformed() -> None:
    pipeline = create_pipeline(default_text="ten hundred")

    for _ in range(4):
        pipeline.source.push_pcm_bytes(make_sine_pcm(amplitude=2000))
    for _ in range(3):
        pipeline.source.push_pcm_bytes(make_silence_pcm())

    results = []
    for _ in range(7):
        res = pipeline.process_next_frame(timeout=0.01)
        if res is not None:
            results.append(res)

    assert len(results) == 1
    result = results[0]

    assert result.status == PipelineStatus.PARSER_REJECTED
    assert result.parsed_value is None
    assert result.recognized_text == "ten hundred"
    assert result.reject_reason == RejectReason.MALFORMED


def test_pipeline_speech_to_parser_rejection_ambiguous() -> None:
    pipeline = create_pipeline(default_text="one twenty")

    for _ in range(4):
        pipeline.source.push_pcm_bytes(make_sine_pcm(amplitude=2000))
    for _ in range(3):
        pipeline.source.push_pcm_bytes(make_silence_pcm())

    results = []
    for _ in range(7):
        res = pipeline.process_next_frame(timeout=0.01)
        if res is not None:
            results.append(res)

    assert len(results) == 1
    result = results[0]

    assert result.status == PipelineStatus.PARSER_REJECTED
    assert result.parsed_value is None
    assert result.recognized_text == "one twenty"
    assert result.reject_reason == RejectReason.AMBIGUOUS


# --- 4. ASR No-Speech ---


def test_pipeline_asr_no_speech() -> None:
    pipeline = create_pipeline(should_return_no_speech=True)

    for _ in range(4):
        pipeline.source.push_pcm_bytes(make_sine_pcm(amplitude=2000))
    for _ in range(3):
        pipeline.source.push_pcm_bytes(make_silence_pcm())

    results = []
    for _ in range(7):
        res = pipeline.process_next_frame(timeout=0.01)
        if res is not None:
            results.append(res)

    assert len(results) == 1
    result = results[0]

    assert result.status == PipelineStatus.NO_SPEECH
    assert result.parsed_value is None


# --- 5. ASR Error ---


def test_pipeline_asr_error_isolated() -> None:
    pipeline = create_pipeline(should_fail_asr=True)

    for _ in range(4):
        pipeline.source.push_pcm_bytes(make_sine_pcm(amplitude=2000))
    for _ in range(3):
        pipeline.source.push_pcm_bytes(make_silence_pcm())

    results = []
    for _ in range(7):
        res = pipeline.process_next_frame(timeout=0.01)
        if res is not None:
            results.append(res)

    assert len(results) == 1
    result = results[0]

    assert result.status == PipelineStatus.ASR_ERROR
    assert result.parsed_value is None
    assert "Simulated ASR failure" in (result.error_message or "")


# --- 6. Source Overflow & Error Handling ---


def test_pipeline_source_overflow_flags_damaged() -> None:
    pipeline = create_pipeline(default_text="one hundred")

    # Push 3 speech frames normally
    for _ in range(3):
        pipeline.source.push_pcm_bytes(make_sine_pcm(amplitude=2000))

    # Push 1 speech frame with overflow flag
    pipeline.source.push_pcm_bytes(make_sine_pcm(amplitude=2000), overflow=True)

    # Push 3 hangover silence frames
    for _ in range(3):
        pipeline.source.push_pcm_bytes(make_silence_pcm())

    results = []
    for _ in range(7):
        res = pipeline.process_next_frame(timeout=0.01)
        if res is not None:
            results.append(res)

    assert len(results) == 1
    result = results[0]

    assert result.status == PipelineStatus.DAMAGED
    assert result.parsed_value is None
    assert result.utterance is not None
    assert result.utterance.is_damaged is True


def test_pipeline_source_exception_handling() -> None:
    class ErroringSource(FakeAudioSource):
        def get_frame(self, timeout=None):
            raise MicLost("Microphone was disconnected during stream")

    source = ErroringSource()
    source.start()
    segmenter = UtteranceSegmenter()
    engine = FakeEngine()
    pipeline = AudioPipeline(source=source, segmenter=segmenter, engine=engine)

    res = pipeline.process_next_frame(timeout=0.01)
    assert res is not None
    assert res.status == PipelineStatus.SOURCE_ERROR
    assert "Microphone was disconnected" in (res.error_message or "")


# --- 7. Multiple Sequential Utterances ---


def test_pipeline_multiple_sequential_utterances() -> None:
    pipeline = create_pipeline()

    # Script two responses in fake engine
    fake_engine: FakeEngine = pipeline.engine  # type: ignore
    fake_engine.set_script(["fifteen", "one hundred"])

    def feed_speech():
        for _ in range(4):
            pipeline.source.push_pcm_bytes(make_sine_pcm(amplitude=2000))
        for _ in range(3):
            pipeline.source.push_pcm_bytes(make_silence_pcm())

    # Utterance 1
    feed_speech()
    res1 = None
    for _ in range(7):
        r = pipeline.process_next_frame(timeout=0.01)
        if r:
            res1 = r

    assert res1 is not None
    assert res1.status == PipelineStatus.PARSED
    assert res1.parsed_value == 15

    # Inter-utterance silence
    for _ in range(4):
        pipeline.source.push_pcm_bytes(make_silence_pcm())
        r = pipeline.process_next_frame(timeout=0.01)
        assert r is None

    # Utterance 2
    feed_speech()
    res2 = None
    for _ in range(7):
        r = pipeline.process_next_frame(timeout=0.01)
        if r:
            res2 = r

    assert res2 is not None
    assert res2.status == PipelineStatus.PARSED
    assert res2.parsed_value == 100


# --- 8. Reset and Flush ---


def test_pipeline_reset() -> None:
    pipeline = create_pipeline()

    # Feed in-progress speech
    pipeline.source.push_pcm_bytes(make_sine_pcm(amplitude=2000))
    pipeline.process_next_frame(timeout=0.01)
    assert pipeline.segmenter.is_in_speech is True

    # Reset
    pipeline.reset()
    assert pipeline.segmenter.is_in_speech is False


def test_pipeline_flush() -> None:
    pipeline = create_pipeline(default_text="fifty")

    # Feed 4 speech frames (120 ms > 90 ms min) without trailing silence
    for _ in range(4):
        pipeline.source.push_pcm_bytes(make_sine_pcm(amplitude=2000))
        pipeline.process_next_frame(timeout=0.01)

    assert pipeline.segmenter.is_in_speech is True

    # Flush on stop
    res = pipeline.flush()
    assert res is not None
    assert res.status == PipelineStatus.PARSED
    assert res.parsed_value == 50


# --- 9. Direct process_utterance Method ---


def test_pipeline_direct_process_utterance() -> None:
    pipeline = create_pipeline(default_text="two thousand")
    pcm = make_sine_pcm(duration_ms=500)
    utt = Utterance(
        pcm_data=pcm,
        duration_ms=500.0,
        sample_rate=AUDIO_SAMPLE_RATE,
        channels=1,
    )

    res = pipeline.process_utterance(utt)
    assert res.status == PipelineStatus.PARSED
    assert res.parsed_value == 2000


def test_pipeline_direct_process_utterance_too_long() -> None:
    pipeline = create_pipeline(default_text="two thousand")
    pcm = make_sine_pcm(duration_ms=7000)
    utt = Utterance(
        pcm_data=pcm,
        duration_ms=7000.0,
        sample_rate=AUDIO_SAMPLE_RATE,
        channels=1,
        is_too_long=True,
    )

    res = pipeline.process_utterance(utt)
    assert res.status == PipelineStatus.TOO_LONG
    assert res.parsed_value is None


# --- 10. Safety Invariant: No Arithmetic in Orchestrator ---


def test_pipeline_has_no_arithmetic_methods() -> None:
    pipeline = create_pipeline()
    # Ensure no arithmetic attributes or methods exist on pipeline or result
    assert not hasattr(pipeline, "total")
    assert not hasattr(pipeline, "add")
    assert not hasattr(pipeline, "sum")
    assert not hasattr(pipeline, "undo")
    assert not hasattr(pipeline, "running_total")

    res = PipelineResult(status=PipelineStatus.PARSED)
    assert not hasattr(res, "total")
    assert not hasattr(res, "running_total")
