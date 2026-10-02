"""Background Listening Controller for Voice Calculator.

Coordinates:
- Background worker thread lifecycle (Start, Stop, clean shutdown).
- Audio capture -> Utterance segmentation -> ASR inference -> Deterministic parsing -> Candidate safety evaluation.
- Thread-safe event queue delivery to the Tkinter GUI main thread.
- Multi-worker prevention and session isolation (discarding stale results from previous sessions).
- Exception-safe error handling for microphone failures, missing models, and inference errors.

Safety Invariants:
- Zero arithmetic or running-total logic in the controller.
- Microphone capture, segmentation, and ASR inference NEVER run on the Tkinter main thread.
- Tkinter widgets are NEVER updated directly from the worker thread.
- Stop requests immediately flag worker termination and discard in-flight unconfirmed results.
- Stale events from previous sessions are strictly filtered out by session_id.
"""

from dataclasses import dataclass
from enum import Enum
import logging
import queue
import threading
import time
from typing import Callable, Optional

from voice_calculator.asr.base import ASREngine, ASRError, ModelMissingError
from voice_calculator.asr.vosk_engine import VoskEngine
from voice_calculator.audio.capture import AudioError, AudioSource, MicrophoneCapture
from voice_calculator.audio.segmenter import UtteranceSegmenter
from voice_calculator.audio.vad import EnergyVAD
from voice_calculator.decision import DecisionResult, OperatingMode, SafetyDecisionEngine
from voice_calculator.pipeline import AudioPipeline, PipelineResult, PipelineStatus

logger = logging.getLogger("voice_calculator.controller")


class ControllerEventType(Enum):
    """Types of structured events sent from ListeningController to GUI."""

    STARTED = "STARTED"          # Worker thread started; microphone capture active
    PROCESSING = "PROCESSING"    # Utterance detected; performing ASR & safety evaluation
    DECISION = "DECISION"        # Safety decision ready for GUI (ACCEPT / REPEAT / REJECT)
    STOPPED = "STOPPED"          # Worker thread stopped cleanly
    ERROR = "ERROR"              # Hardware, model, or unhandled runtime error


@dataclass(frozen=True)
class ControllerEvent:
    """Immutable structured event delivered across thread boundary to GUI.

    Attributes:
        event_type: Classification of the lifecycle event.
        session_id: Unique session sequence ID to detect and discard stale events.
        decision: Optional DecisionResult when event_type is DECISION.
        error_message: Optional user-friendly error description.
        error_type: Optional name of the underlying exception class.
        latency_ms: Optional total processing latency for performance tracking.
    """

    event_type: ControllerEventType
    session_id: int
    decision: Optional[DecisionResult] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    latency_ms: float = 0.0


class ListeningController:
    """Thread-safe controller managing background audio listening and event emission."""

    def __init__(
        self,
        engine: Optional[ASREngine] = None,
        audio_source_factory: Optional[Callable[[], AudioSource]] = None,
        segmenter_factory: Optional[Callable[[], UtteranceSegmenter]] = None,
        decision_engine: Optional[SafetyDecisionEngine] = None,
        event_queue: Optional[queue.Queue[ControllerEvent]] = None,
    ) -> None:
        self.engine = engine if engine is not None else VoskEngine()
        self.audio_source_factory = audio_source_factory or (lambda: MicrophoneCapture())
        self.segmenter_factory = segmenter_factory or (lambda: UtteranceSegmenter(vad=EnergyVAD()))
        self.decision_engine = decision_engine or SafetyDecisionEngine()
        self.event_queue: queue.Queue[ControllerEvent] = event_queue if event_queue is not None else queue.Queue()

        self._lock = threading.Lock()
        self._session_id: int = 0
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._active_source: Optional[AudioSource] = None

    @property
    def mode(self) -> OperatingMode:
        """Current operating mode of the decision engine (SAFE or FAST)."""
        return self.decision_engine.mode

    def set_mode(self, mode: OperatingMode) -> None:
        """Sets operating mode on the decision engine."""
        self.decision_engine.set_mode(mode)

    @property
    def is_listening(self) -> bool:
        """True if the worker thread is currently active and listening."""
        with self._lock:
            return self._worker_thread is not None and self._worker_thread.is_alive()

    @property
    def current_session_id(self) -> int:
        """The currently active or most recent session sequence ID."""
        with self._lock:
            return self._session_id

    def start(self) -> bool:
        """Starts the background listening worker thread.

        Returns:
            True if started successfully, False if already listening.
        """
        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                logger.warning("ListeningController.start() called while worker already active.")
                return False

            self._session_id += 1
            session_id = self._session_id
            self._stop_event.clear()

            try:
                source = self.audio_source_factory()
                segmenter = self.segmenter_factory()
                pipeline = AudioPipeline(source=source, segmenter=segmenter, engine=self.engine)
            except Exception as e:
                logger.error("Failed to construct audio pipeline components: %s", type(e).__name__)
                self.event_queue.put(
                    ControllerEvent(
                        event_type=ControllerEventType.ERROR,
                        session_id=session_id,
                        error_message=f"Failed to initialize audio components: {e}",
                        error_type=type(e).__name__,
                    )
                )
                return False

            self._active_source = source
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                args=(session_id, source, segmenter, pipeline),
                name=f"VoiceCalcWorker-{session_id}",
                daemon=True,
            )
            self._worker_thread.start()
            logger.info("ListeningController started worker thread (session_id=%d).", session_id)
            return True

    def stop(self, timeout: float = 2.0) -> bool:
        """Stops the background listening worker thread cleanly.

        Args:
            timeout: Maximum seconds to wait for worker thread shutdown.

        Returns:
            True if stopped cleanly.
        """
        with self._lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                logger.debug("ListeningController.stop() called when not running.")
                return True

            session_id = self._session_id
            logger.info("Requesting clean stop for worker thread (session_id=%d)...", session_id)
            self._stop_event.set()

            # Signal active audio source to unblock frame retrieval
            if self._active_source is not None:
                try:
                    self._active_source.stop()
                except Exception as e:
                    logger.debug("Exception stopping audio source during controller stop: %s", e)

            thread = self._worker_thread

        # Join outside the lock to avoid blocking other calls
        if thread is not None:
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger.warning("Worker thread did not terminate within %.1f s timeout.", timeout)

        with self._lock:
            self._active_source = None
            self._worker_thread = None

        self.event_queue.put(
            ControllerEvent(
                event_type=ControllerEventType.STOPPED,
                session_id=session_id,
            )
        )
        return True

    def _worker_loop(
        self,
        session_id: int,
        source: AudioSource,
        segmenter: UtteranceSegmenter,
        pipeline: AudioPipeline,
    ) -> None:
        """Worker thread main processing loop."""
        logger.info("Worker loop entered (session_id=%d).", session_id)

        try:
            # 1. Start audio source
            source.start()

            # 2. Ensure ASR engine is loaded
            try:
                self.engine.load()
            except ModelMissingError as e:
                logger.error("ASR Model missing: %s", e)
                self.event_queue.put(
                    ControllerEvent(
                        event_type=ControllerEventType.ERROR,
                        session_id=session_id,
                        error_message="A required speech model file is missing. Please install the model in models/ directory.",
                        error_type="ModelMissingError",
                    )
                )
                return
            except Exception as e:
                logger.error("Failed to load ASR engine: %s", type(e).__name__)
                self.event_queue.put(
                    ControllerEvent(
                        event_type=ControllerEventType.ERROR,
                        session_id=session_id,
                        error_message=f"Speech recognition engine failed to load: {e}",
                        error_type=type(e).__name__,
                    )
                )
                return

            # Signal GUI that listening has begun
            self.event_queue.put(
                ControllerEvent(
                    event_type=ControllerEventType.STARTED,
                    session_id=session_id,
                )
            )

            # 3. Continuous frame loop
            while not self._stop_event.is_set():
                try:
                    frame = source.get_frame(timeout=0.05)
                except AudioError as e:
                    if self._stop_event.is_set():
                        break
                    logger.error("Audio capture error: %s", type(e).__name__)
                    self.event_queue.put(
                        ControllerEvent(
                            event_type=ControllerEventType.ERROR,
                            session_id=session_id,
                            error_message=f"Microphone capture error: {e}",
                            error_type=type(e).__name__,
                        )
                    )
                    break

                if frame is None:
                    continue

                if self._stop_event.is_set():
                    break

                # Segment audio frame
                try:
                    utterance = segmenter.process_frame(frame)
                except Exception as e:
                    logger.error("Segmenter error: %s", type(e).__name__)
                    segmenter.reset()
                    continue

                if utterance is None:
                    continue

                # Utterance completed: process through pipeline
                if self._stop_event.is_set():
                    logger.info("Discarding in-flight utterance due to stop request.")
                    break

                # Notify GUI that utterance processing has begun
                self.event_queue.put(
                    ControllerEvent(
                        event_type=ControllerEventType.PROCESSING,
                        session_id=session_id,
                    )
                )

                pipe_result = pipeline.process_utterance(utterance)

                # Check if stop was requested while transcribing
                if self._stop_event.is_set():
                    logger.info("Discarding completed utterance result due to stop request.")
                    break

                # Evaluate through safety decision engine
                decision_res = self.decision_engine.evaluate(pipe_result)

                # Deliver decision result to GUI queue if session is still current
                if not self._stop_event.is_set():
                    self.event_queue.put(
                        ControllerEvent(
                            event_type=ControllerEventType.DECISION,
                            session_id=session_id,
                            decision=decision_res,
                            latency_ms=pipe_result.total_latency_ms,
                        )
                    )

        except Exception as e:
            if not self._stop_event.is_set():
                logger.error("Unexpected exception in worker thread: %s", type(e).__name__)
                self.event_queue.put(
                    ControllerEvent(
                        event_type=ControllerEventType.ERROR,
                        session_id=session_id,
                        error_message=f"Unexpected background error: {e}",
                        error_type=type(e).__name__,
                    )
                )
        finally:
            logger.info("Worker loop exiting; cleaning up audio resources (session_id=%d).", session_id)
            try:
                source.stop()
            except Exception:
                pass
            try:
                source.close()
            except Exception:
                pass
            pipeline.reset()
