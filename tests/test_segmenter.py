"""Unit tests for UtteranceSegmenter and audio stream segmentation state machine."""

import numpy as np
import pytest

from voice_calculator.audio.capture import AudioFrame, FakeAudioSource
from voice_calculator.audio.segmenter import SegmenterState, Utterance, UtteranceSegmenter
from voice_calculator.audio.vad import EnergyVAD
from voice_calculator.config import AUDIO_SAMPLE_RATE


def make_frame(
    is_speech: bool,
    duration_ms: float = 30.0,
    timestamp_ns: int = 0,
    overflow: bool = False,
    is_clipped: bool = False,
    sample_rate: int = AUDIO_SAMPLE_RATE,
) -> AudioFrame:
    """Helper to generate synthetic AudioFrame containing speech or silence."""
    n_samples = int(sample_rate * (duration_ms / 1000.0))
    if is_speech:
        if is_clipped:
            samples = np.full(n_samples, fill_value=32767, dtype=np.int16)
        else:
            # Amplitude 2000 has RMS ≈ 1414 (above default 500 threshold)
            t = np.linspace(0, duration_ms / 1000.0, n_samples, endpoint=False)
            samples = (2000 * np.sin(2 * np.pi * 440.0 * t)).astype(np.int16)
    else:
        samples = np.zeros(n_samples, dtype=np.int16)

    return AudioFrame(
        data=samples.tobytes(),
        sample_rate=sample_rate,
        channels=1,
        timestamp_ns=timestamp_ns,
        samples_count=n_samples,
        overflow=overflow,
    )


# --- 1. Initialization and Parameter Validation ---


def test_segmenter_init_and_validation() -> None:
    seg = UtteranceSegmenter(
        pre_roll_ms=250,
        hangover_ms=700,
        min_utterance_ms=200,
        max_utterance_ms=5000,
    )
    assert seg.pre_roll_ms == 250
    assert seg.hangover_ms == 700
    assert seg.min_utterance_ms == 200
    assert seg.max_utterance_ms == 5000
    assert seg.state == SegmenterState.SILENCE
    assert seg.is_in_speech is False

    with pytest.raises(ValueError, match="Invalid duration parameters"):
        UtteranceSegmenter(min_utterance_ms=1000, max_utterance_ms=500)

    with pytest.raises(ValueError, match="Invalid duration parameters"):
        UtteranceSegmenter(pre_roll_ms=-10)


# --- 2. Silence Only Stream ---


def test_segmenter_silence_only() -> None:
    seg = UtteranceSegmenter(
        vad=EnergyVAD(energy_threshold=500.0),
        hangover_ms=300,
    )

    # Feed 20 silence frames (600 ms)
    for i in range(20):
        frame = make_frame(is_speech=False, timestamp_ns=i * 30_000_000)
        result = seg.process_frame(frame)
        assert result is None
        assert seg.state == SegmenterState.SILENCE
        assert seg.is_in_speech is False


# --- 3. Speech Onset, Pre-roll, and Utterance Completion ---


def test_segmenter_silence_speech_silence_cycle() -> None:
    seg = UtteranceSegmenter(
        vad=EnergyVAD(energy_threshold=500.0),
        pre_roll_ms=90,     # ~3 frames pre-roll
        hangover_ms=90,     # ~3 frames hangover
        min_utterance_ms=100,
        max_utterance_ms=3000,
    )

    # 1. 5 silence frames (150 ms) -> fills pre-roll ring buffer
    for i in range(5):
        res = seg.process_frame(make_frame(is_speech=False, timestamp_ns=i * 30_000_000))
        assert res is None
        assert seg.state == SegmenterState.SILENCE

    # 2. 5 speech frames (150 ms)
    for i in range(5, 10):
        res = seg.process_frame(make_frame(is_speech=True, timestamp_ns=i * 30_000_000))
        assert res is None
        assert seg.state == SegmenterState.SPEECH_ACTIVE
        assert seg.is_in_speech is True

    # 3. 2 hangover silence frames (60 ms) -> not yet completed
    res = seg.process_frame(make_frame(is_speech=False, timestamp_ns=10 * 30_000_000))
    assert res is None
    assert seg.state == SegmenterState.SPEECH_HANGOVER

    res = seg.process_frame(make_frame(is_speech=False, timestamp_ns=11 * 30_000_000))
    assert res is None
    assert seg.state == SegmenterState.SPEECH_HANGOVER

    # 4. 3rd hangover silence frame (reaching 90 ms hangover) -> should complete and emit Utterance!
    res = seg.process_frame(make_frame(is_speech=False, timestamp_ns=12 * 30_000_000))
    assert res is not None
    assert isinstance(res, Utterance)
    assert res.is_too_long is False
    assert res.is_damaged is False

    # Duration includes pre-roll (3 frames = 90ms) + speech (5 frames = 150ms) + hangover (3 frames = 90ms) = 330ms (11 frames)
    assert res.frame_count == 11
    assert pytest.approx(res.duration_ms, rel=1e-3) == 330.0

    # State reset back to SILENCE
    assert seg.state == SegmenterState.SILENCE
    assert seg.is_in_speech is False


# --- 4. Short Noise Burst Rejection (< min_utterance_ms) ---


def test_segmenter_short_noise_burst_rejected() -> None:
    seg = UtteranceSegmenter(
        vad=EnergyVAD(energy_threshold=500.0),
        pre_roll_ms=60,
        hangover_ms=60,       # 2 frames hangover
        min_utterance_ms=200, # Requires at least 200 ms speech
    )

    # 1. 2 frames of silence
    seg.process_frame(make_frame(is_speech=False))
    seg.process_frame(make_frame(is_speech=False))

    # 2. 1 frame of noise spike (30 ms < 200 ms min)
    seg.process_frame(make_frame(is_speech=True))
    assert seg.state == SegmenterState.SPEECH_ACTIVE

    # 3. 2 frames of hangover silence (60 ms) -> hangover expires
    res1 = seg.process_frame(make_frame(is_speech=False))
    assert res1 is None
    res2 = seg.process_frame(make_frame(is_speech=False))

    # Should be discarded as short noise burst (speech duration was only ~90 ms with pre-roll < 200 ms)
    assert res2 is None
    assert seg.state == SegmenterState.SILENCE
    assert seg.is_in_speech is False


# --- 5. Speech Resumed During Hangover ---


def test_segmenter_speech_resumed_during_hangover() -> None:
    seg = UtteranceSegmenter(
        vad=EnergyVAD(energy_threshold=500.0),
        hangover_ms=90,       # 3 frames hangover
        min_utterance_ms=100,
    )

    # Speech onset
    seg.process_frame(make_frame(is_speech=True))
    seg.process_frame(make_frame(is_speech=True))
    assert seg.state == SegmenterState.SPEECH_ACTIVE

    # 1 silence frame -> hangover
    seg.process_frame(make_frame(is_speech=False))
    assert seg.state == SegmenterState.SPEECH_HANGOVER

    # Speech resumes on next frame!
    seg.process_frame(make_frame(is_speech=True))
    assert seg.state == SegmenterState.SPEECH_ACTIVE
    assert seg.is_in_speech is True


# --- 6. Maximum Utterance Duration Cap ---


def test_segmenter_max_duration_cap() -> None:
    seg = UtteranceSegmenter(
        vad=EnergyVAD(energy_threshold=500.0),
        max_utterance_ms=300,  # Cap at 300 ms (10 frames)
        min_utterance_ms=100,
        hangover_ms=200,
    )

    result = None
    for i in range(12):
        res = seg.process_frame(make_frame(is_speech=True, timestamp_ns=i * 30_000_000))
        if res is not None:
            result = res
            break

    assert result is not None
    assert result.is_too_long is True
    assert result.duration_ms >= 300.0
    # State reset after cap
    assert seg.state == SegmenterState.SILENCE


# --- 7. Multiple Consecutive Utterances ---


def test_segmenter_multiple_utterances_in_sequence() -> None:
    seg = UtteranceSegmenter(
        vad=EnergyVAD(energy_threshold=500.0),
        pre_roll_ms=60,
        hangover_ms=60,
        min_utterance_ms=90,
    )

    utterances = []

    def feed_utterance_sequence():
        # Speech 4 frames (120ms)
        for _ in range(4):
            r = seg.process_frame(make_frame(is_speech=True))
            if r:
                utterances.append(r)
        # Hangover silence 2 frames (60ms)
        for _ in range(2):
            r = seg.process_frame(make_frame(is_speech=False))
            if r:
                utterances.append(r)

    # First utterance
    feed_utterance_sequence()
    assert len(utterances) == 1

    # Inter-utterance silence 4 frames
    for _ in range(4):
        r = seg.process_frame(make_frame(is_speech=False))
        assert r is None

    # Second utterance
    feed_utterance_sequence()
    assert len(utterances) == 2


# --- 8. Overflow and Clipping Flags ---


def test_segmenter_tracks_overflow_and_clipping() -> None:
    seg = UtteranceSegmenter(
        vad=EnergyVAD(energy_threshold=500.0),
        hangover_ms=60,
        min_utterance_ms=60,
    )

    # Speech frame with clipping (32767)
    seg.process_frame(make_frame(is_speech=True, is_clipped=True))

    # Speech frame with overflow
    seg.process_frame(make_frame(is_speech=True, overflow=True))

    # Hangover to close
    seg.process_frame(make_frame(is_speech=False))
    res = seg.process_frame(make_frame(is_speech=False))

    assert res is not None
    assert res.is_clipped is True
    assert res.is_damaged is True


# --- 9. Flush and Reset ---


def test_segmenter_flush_active_speech() -> None:
    seg = UtteranceSegmenter(
        vad=EnergyVAD(energy_threshold=500.0),
        min_utterance_ms=60,
    )

    # 3 speech frames (90 ms > 60 ms min)
    seg.process_frame(make_frame(is_speech=True))
    seg.process_frame(make_frame(is_speech=True))
    seg.process_frame(make_frame(is_speech=True))

    # Flush on stop
    utt = seg.flush()
    assert utt is not None
    assert utt.duration_ms == 90.0
    assert seg.state == SegmenterState.SILENCE


def test_segmenter_flush_on_silence_returns_none() -> None:
    seg = UtteranceSegmenter()
    seg.process_frame(make_frame(is_speech=False))
    assert seg.flush() is None


def test_segmenter_manual_reset() -> None:
    seg = UtteranceSegmenter()
    seg.process_frame(make_frame(is_speech=True))
    assert seg.is_in_speech is True
    seg.reset()
    assert seg.state == SegmenterState.SILENCE
    assert seg.is_in_speech is False


# --- 10. Integration with FakeAudioSource ---


def test_segmenter_integration_with_fake_audio_source() -> None:
    # 5 speech frames (150ms) + 3 silence frames (90ms)
    frames = [make_frame(is_speech=True, timestamp_ns=i * 30_000_000) for i in range(5)]
    frames += [make_frame(is_speech=False, timestamp_ns=(5 + i) * 30_000_000) for i in range(3)]

    source = FakeAudioSource()
    source.start()
    for f in frames:
        source.push_pcm_bytes(f.data)

    seg = UtteranceSegmenter(
        vad=EnergyVAD(energy_threshold=500.0),
        hangover_ms=90,
        min_utterance_ms=100,
    )

    emitted_utterance = None
    while True:
        f = source.get_frame(timeout=0.01)
        if f is None:
            break
        res = seg.process_frame(f)
        if res:
            emitted_utterance = res

    source.stop()

    assert emitted_utterance is not None
    assert emitted_utterance.frame_count == 8
    assert pytest.approx(emitted_utterance.duration_ms, rel=1e-3) == 240.0
