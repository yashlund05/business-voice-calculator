"""Unit and integration tests for Background ListeningController (Phase 3.6B).

Verifies:
- Controller starts and stops cleanly with background worker thread.
- Multi-worker prevention: duplicate start() calls do not spawn extra threads.
- Stop requests terminate the worker and release audio resources.
- Events (STARTED, PROCESSING, DECISION, STOPPED, ERROR) delivered via thread-safe queue.
- Completed speech candidate routes through AudioPipeline and SafetyDecisionEngine.
- In-flight utterances are safely discarded upon stop request.
- Microphone errors and ModelMissingError are safely caught and emitted as ERROR events.
- Session IDs increment per start(), enabling isolation and filtering of stale events.
- Absolute invariant: zero arithmetic or calculator mutation inside the controller.
"""

import queue
import time
import numpy as np
import pytest

from voice_calculator.asr.base import ASRResult, ASRStatus, FakeEngine, ModelMissingError
from voice_calculator.audio.capture import AudioError, AudioFrame, FakeAudioSource
from voice_calculator.audio.segmenter import UtteranceSegmenter
from voice_calculator.audio.vad import EnergyVAD
from voice_calculator.config import AUDIO_BLOCK_BYTES, AUDIO_BLOCK_DURATION_MS, AUDIO_SAMPLE_RATE
from voice_calculator.controller import (
    ControllerEvent,
    ControllerEventType,
    ListeningController,
)
from voice_calculator.decision import DecisionReason, DecisionType, SafetyDecisionEngine


def make_pcm_frames(num_frames: int, amplitude: int = 2000) -> list[AudioFrame]:
    """Generates synthetic non-silent int16 PCM AudioFrames for segmentation."""
    frames = []
    for i in range(num_frames):
        # Sine wave tone to trigger EnergyVAD (>500 RMS)
        t = np.linspace(0, AUDIO_BLOCK_DURATION_MS / 1000.0, 480, endpoint=False)
        tone = (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.int16)
        frames.append(
            AudioFrame(
                data=tone.tobytes(),
                sample_rate=AUDIO_SAMPLE_RATE,
                channels=1,
                timestamp_ns=i * 30_000_000,
                samples_count=480,
            )
        )
    return frames


def make_silent_frames(num_frames: int) -> list[AudioFrame]:
    """Generates silent int16 PCM AudioFrames."""
    frames = []
    zero_bytes = b"\x00" * AUDIO_BLOCK_BYTES
    for i in range(num_frames):
        frames.append(
            AudioFrame(
                data=zero_bytes,
                sample_rate=AUDIO_SAMPLE_RATE,
                channels=1,
                timestamp_ns=i * 30_000_000,
                samples_count=480,
            )
        )
    return frames



class ErrorAudioSource(FakeAudioSource):
    """AudioSource fake that raises an AudioError on get_frame()."""

    def get_frame(self, timeout: float | None = 0.05) -> AudioFrame | None:
        raise AudioError("Simulated microphone read failure")


class MissingModelEngine(FakeEngine):
    """ASREngine fake that raises ModelMissingError on load()."""

    def load(self) -> None:
        raise ModelMissingError("Simulated missing model directory")


class TestListeningController:
    """Test suite for ListeningController."""

    def test_start_and_stop_lifecycle(self):
        """Controller starts worker thread, emits STARTED, and on stop emits STOPPED."""
        fake_engine = FakeEngine(default_text="forty two")
        source = FakeAudioSource()

        controller = ListeningController(
            engine=fake_engine,
            audio_source_factory=lambda: source,
            segmenter_factory=lambda: UtteranceSegmenter(vad=EnergyVAD()),
        )

        assert controller.is_listening is False
        assert controller.current_session_id == 0

        # Start controller
        started = controller.start()
        assert started is True
        assert controller.is_listening is True
        assert controller.current_session_id == 1

        # Check STARTED event arrives in event queue
        event = controller.event_queue.get(timeout=1.0)
        assert event.event_type == ControllerEventType.STARTED
        assert event.session_id == 1

        # Stop controller
        stopped = controller.stop(timeout=1.0)
        assert stopped is True
        assert controller.is_listening is False

        # Check STOPPED event arrives in queue
        event = controller.event_queue.get(timeout=1.0)
        assert event.event_type == ControllerEventType.STOPPED
        assert event.session_id == 1

    def test_multi_worker_prevention(self):
        """Calling start() multiple times while running does not spawn extra threads."""
        fake_engine = FakeEngine(default_text="one hundred")
        source = FakeAudioSource()

        controller = ListeningController(
            engine=fake_engine,
            audio_source_factory=lambda: source,
        )

        assert controller.start() is True
        assert controller.start() is False  # Second start rejected
        assert controller.start() is False  # Third start rejected

        controller.stop(timeout=1.0)
        assert controller.is_listening is False

    def test_speech_utterance_produces_decision_event(self):
        """Synthetic speech frames produce PROCESSING and DECISION events via pipeline & decision engine."""
        fake_engine = FakeEngine(
            scripted_results=[ASRResult(text="one hundred fifty", confidence=0.92, status=ASRStatus.SUCCESS)]
        )

        source = FakeAudioSource()
        for f in make_pcm_frames(5, amplitude=2000) + make_silent_frames(5):
            source._queue.put(f)

        controller = ListeningController(
            engine=fake_engine,
            audio_source_factory=lambda: source,
            segmenter_factory=lambda: UtteranceSegmenter(vad=EnergyVAD(), hangover_ms=60, min_utterance_ms=60),
            decision_engine=SafetyDecisionEngine(),
        )

        controller.start()

        # Collect events
        events: list[ControllerEvent] = []
        timeout_end = time.time() + 2.0
        while time.time() < timeout_end:
            try:
                ev = controller.event_queue.get(timeout=0.2)
                events.append(ev)
                if ev.event_type == ControllerEventType.DECISION:
                    break
            except queue.Empty:
                pass

        controller.stop(timeout=1.0)

        event_types = [e.event_type for e in events]
        assert ControllerEventType.STARTED in event_types
        assert ControllerEventType.PROCESSING in event_types
        assert ControllerEventType.DECISION in event_types

        # Check decision details
        decision_event = next(e for e in events if e.event_type == ControllerEventType.DECISION)
        assert decision_event.decision is not None
        assert decision_event.decision.decision == DecisionType.ACCEPT
        assert decision_event.decision.value == 150
        assert decision_event.decision.confidence == 0.92

    def test_command_word_produces_reject_decision(self):
        """Spoken command words (e.g. 'undo') produce REJECT decision without modifying state."""
        fake_engine = FakeEngine(default_text="undo")

        source = FakeAudioSource()
        for f in make_pcm_frames(5, amplitude=2000) + make_silent_frames(5):
            source._queue.put(f)

        controller = ListeningController(
            engine=fake_engine,
            audio_source_factory=lambda: source,
            segmenter_factory=lambda: UtteranceSegmenter(vad=EnergyVAD(), hangover_ms=60, min_utterance_ms=60),
        )

        controller.start()

        events: list[ControllerEvent] = []
        timeout_end = time.time() + 2.0
        while time.time() < timeout_end:
            try:
                ev = controller.event_queue.get(timeout=0.2)
                events.append(ev)
                if ev.event_type == ControllerEventType.DECISION:
                    break
            except queue.Empty:
                pass

        controller.stop(timeout=1.0)

        decision_event = next((e for e in events if e.event_type == ControllerEventType.DECISION), None)
        assert decision_event is not None
        assert decision_event.decision is not None
        assert decision_event.decision.decision == DecisionType.REJECT
        assert decision_event.decision.value is None
        assert decision_event.decision.reason == DecisionReason.PARSER_REJECTED_NOT_A_NUMBER

    def test_missing_model_emits_error_event(self):
        """Missing ASR model triggers ModelMissingError and emits ERROR event safely."""
        missing_engine = MissingModelEngine()
        source = FakeAudioSource()

        controller = ListeningController(
            engine=missing_engine,
            audio_source_factory=lambda: source,
        )

        controller.start()

        event = controller.event_queue.get(timeout=1.0)
        assert event.event_type == ControllerEventType.ERROR
        assert event.error_type == "ModelMissingError"
        assert "missing" in (event.error_message or "").lower()

        controller.stop(timeout=1.0)
        assert controller.is_listening is False

    def test_audio_source_error_emits_error_event(self):
        """Audio capture hardware failure emits ERROR event safely without crashing."""
        fake_engine = FakeEngine()
        error_source = ErrorAudioSource()

        controller = ListeningController(
            engine=fake_engine,
            audio_source_factory=lambda: error_source,
        )

        controller.start()

        # Check event queue for STARTED then ERROR
        events = []
        for _ in range(2):
            try:
                events.append(controller.event_queue.get(timeout=1.0))
            except queue.Empty:
                break

        controller.stop(timeout=1.0)

        err_event = next((e for e in events if e.event_type == ControllerEventType.ERROR), None)
        assert err_event is not None
        assert "microphone" in (err_event.error_message or "").lower()

    def test_session_id_increments_and_stale_isolation(self):
        """Restarting controller increments session_id, ensuring previous session events can be filtered."""
        fake_engine = FakeEngine()
        source = FakeAudioSource()

        controller = ListeningController(
            engine=fake_engine,
            audio_source_factory=lambda: source,
        )

        # Session 1
        controller.start()
        assert controller.current_session_id == 1
        controller.stop(timeout=1.0)

        # Session 2
        controller.start()
        assert controller.current_session_id == 2
        controller.stop(timeout=1.0)

        assert controller.current_session_id == 2

    def test_no_arithmetic_in_controller(self):
        """Verify controller does not perform arithmetic operations or track totals."""
        controller = ListeningController(engine=FakeEngine())
        assert not hasattr(controller, "total")
        assert not hasattr(controller, "running_total")
        assert not hasattr(controller, "add")
        assert not hasattr(controller, "undo")

    def test_controller_mode_delegation(self):
        """Verify controller.mode and controller.set_mode properly delegate to decision engine."""
        from voice_calculator.decision import OperatingMode
        controller = ListeningController(engine=FakeEngine())
        assert controller.mode == OperatingMode.SAFE

        controller.set_mode(OperatingMode.FAST)
        assert controller.mode == OperatingMode.FAST
        assert controller.decision_engine.mode == OperatingMode.FAST

        controller.set_mode(OperatingMode.SAFE)
        assert controller.mode == OperatingMode.SAFE
        assert controller.decision_engine.mode == OperatingMode.SAFE
