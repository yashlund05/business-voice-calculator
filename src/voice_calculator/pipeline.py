"""Single-utterance audio processing pipeline orchestration layer.

Connects:
  AudioSource
  → VAD / UtteranceSegmenter
  → completed Utterance
  → ASREngine
  → ASRResult
  → deterministic number parser (numparse.parse)
  → structured PipelineResult

Guarantees:
- Pure orchestration using dependency injection (AudioSource, UtteranceSegmenter, ASREngine).
- Clean separation between speech detection, ASR transcription, and number parsing.
- Clear distinction between ASR success, parsed candidate integer, parser rejection, and silence/errors.
- Never performs arithmetic, running total calculation, or automatic addition decisions.
- Exception-safe error isolation (source errors, queue overflows, ASR failures, parser errors).
- Privacy-safe logging (no raw audio or full spoken transcripts logged).
"""

from dataclasses import dataclass
from enum import Enum
import logging
import time
from typing import Optional

from voice_calculator.asr.base import ASREngine, ASRResult, ASRStatus
from voice_calculator.audio.capture import AudioError, AudioFrame, AudioSource
from voice_calculator.audio.segmenter import Utterance, UtteranceSegmenter
from voice_calculator.numparse import ParseResult, ParseStatus, RejectReason, parse

logger = logging.getLogger("voice_calculator.pipeline")


class PipelineStatus(Enum):
    """Status classification of a completed pipeline processing cycle."""

    PARSED = "PARSED"                      # ASR transcribed speech and parser successfully produced candidate integer
    PARSER_REJECTED = "PARSER_REJECTED"    # ASR produced text, but parser rejected (non-number, malformed, out of range)
    NO_SPEECH = "NO_SPEECH"                # Segmented audio contained no recognizable speech or was silent
    ASR_ERROR = "ASR_ERROR"                # ASR engine raised an error or failed inference
    SOURCE_ERROR = "SOURCE_ERROR"          # Audio capture source failed (MicLost, StreamError, etc.)
    TOO_LONG = "TOO_LONG"                  # Utterance exceeded maximum allowed duration cap
    DAMAGED = "DAMAGED"                    # Utterance experienced audio frame drop/overflow during recording


@dataclass(frozen=True)
class PipelineResult:
    """Immutable structured result from the single-utterance audio pipeline.

    Attributes:
        status: High-level classification of the pipeline outcome.
        utterance: Optional Utterance containing audio stats, timing, and PCM bytes.
        asr_result: Optional ASRResult containing transcript and engine metadata.
        parse_result: Optional ParseResult containing parsed value and reject reason.
        total_latency_ms: Processing latency from utterance completion through parsing.
        error_message: Optional description if an error occurred.
    """

    status: PipelineStatus
    utterance: Optional[Utterance] = None
    asr_result: Optional[ASRResult] = None
    parse_result: Optional[ParseResult] = None
    total_latency_ms: float = 0.0
    error_message: Optional[str] = None

    @property
    def parsed_value(self) -> Optional[int]:
        """Returns the parsed candidate integer if status is PARSED, else None."""
        if self.status == PipelineStatus.PARSED and self.parse_result is not None:
            return self.parse_result.value
        return None

    @property
    def recognized_text(self) -> str:
        """Returns recognized raw ASR text, or empty string."""
        if self.asr_result is not None:
            return self.asr_result.text
        return ""

    @property
    def confidence(self) -> Optional[float]:
        """Returns optional ASR acoustic/language confidence score."""
        if self.asr_result is not None:
            return self.asr_result.confidence
        return None

    @property
    def reject_reason(self) -> Optional[RejectReason]:
        """Returns the parser RejectReason if the transcript was rejected."""
        if self.parse_result is not None:
            return self.parse_result.reason
        return None


class AudioPipeline:
    """Orchestrates audio capture, VAD segmentation, ASR, and deterministic parsing."""

    def __init__(
        self,
        source: AudioSource,
        segmenter: UtteranceSegmenter,
        engine: ASREngine,
    ) -> None:
        self.source = source
        self.segmenter = segmenter
        self.engine = engine

    def process_utterance(self, utterance: Utterance) -> PipelineResult:
        """Processes a completed Utterance through ASR and the number parser.

        Args:
            utterance: Segmented Utterance instance with PCM data and metadata.

        Returns:
            PipelineResult with status, ASR result, and parsed integer/rejection.
        """
        start_mono = time.monotonic()

        # 1. Check if utterance is damaged by queue overflow
        if utterance.is_damaged:
            logger.warning("Utterance flagged as damaged due to audio queue overflow.")
            return PipelineResult(
                status=PipelineStatus.DAMAGED,
                utterance=utterance,
                total_latency_ms=(time.monotonic() - start_mono) * 1000.0,
                error_message="Audio queue overflow occurred during utterance capture.",
            )

        # 2. Check if utterance exceeded maximum duration cap
        if utterance.is_too_long:
            logger.warning("Utterance exceeded maximum duration cap (%.1f ms).", utterance.duration_ms)
            return PipelineResult(
                status=PipelineStatus.TOO_LONG,
                utterance=utterance,
                total_latency_ms=(time.monotonic() - start_mono) * 1000.0,
                error_message=f"Utterance exceeded maximum duration ({utterance.duration_ms:.0f} ms).",
            )

        # 3. Transcribe audio with ASREngine
        try:
            asr_result = self.engine.transcribe(
                pcm_data=utterance.pcm_data,
                sample_rate=utterance.sample_rate,
            )
        except Exception as e:
            logger.error("Unexpected exception during ASR transcription: %s", type(e).__name__)
            return PipelineResult(
                status=PipelineStatus.ASR_ERROR,
                utterance=utterance,
                total_latency_ms=(time.monotonic() - start_mono) * 1000.0,
                error_message=f"ASR transcription exception: {e}",
            )

        # 4. Handle ASR status
        if asr_result.status == ASRStatus.ERROR:
            return PipelineResult(
                status=PipelineStatus.ASR_ERROR,
                utterance=utterance,
                asr_result=asr_result,
                total_latency_ms=(time.monotonic() - start_mono) * 1000.0,
                error_message=asr_result.error_message or "ASR inference error.",
            )

        if asr_result.status == ASRStatus.NO_SPEECH or not asr_result.text.strip():
            return PipelineResult(
                status=PipelineStatus.NO_SPEECH,
                utterance=utterance,
                asr_result=asr_result,
                total_latency_ms=(time.monotonic() - start_mono) * 1000.0,
            )

        # 5. Deterministic number parsing
        try:
            parse_result = parse(asr_result.text)
        except Exception as e:
            logger.error("Unexpected exception during number parsing: %s", type(e).__name__)
            return PipelineResult(
                status=PipelineStatus.PARSER_REJECTED,
                utterance=utterance,
                asr_result=asr_result,
                total_latency_ms=(time.monotonic() - start_mono) * 1000.0,
                error_message=f"Parser exception: {e}",
            )

        total_lat = (time.monotonic() - start_mono) * 1000.0

        # 6. Map ParseResult to PipelineResult
        if parse_result.status == ParseStatus.SUCCESS:
            return PipelineResult(
                status=PipelineStatus.PARSED,
                utterance=utterance,
                asr_result=asr_result,
                parse_result=parse_result,
                total_latency_ms=total_lat,
            )
        else:
            return PipelineResult(
                status=PipelineStatus.PARSER_REJECTED,
                utterance=utterance,
                asr_result=asr_result,
                parse_result=parse_result,
                total_latency_ms=total_lat,
            )

    def process_next_frame(self, timeout: Optional[float] = 0.05) -> Optional[PipelineResult]:
        """Pulls a single AudioFrame from the source and processes it through the pipeline.

        Args:
            timeout: Maximum seconds to wait for a frame from the AudioSource.

        Returns:
            PipelineResult if an utterance completed, else None.
        """
        try:
            frame = self.source.get_frame(timeout=timeout)
        except AudioError as e:
            logger.error("AudioSource error during frame retrieval: %s", type(e).__name__)
            return PipelineResult(
                status=PipelineStatus.SOURCE_ERROR,
                error_message=f"Audio source error: {e}",
            )
        except Exception as e:
            logger.error("Unexpected error reading audio frame: %s", type(e).__name__)
            return PipelineResult(
                status=PipelineStatus.SOURCE_ERROR,
                error_message=f"Unexpected source error: {e}",
            )

        if frame is None:
            return None

        # Feed frame into utterance segmenter
        try:
            utterance = self.segmenter.process_frame(frame)
        except Exception as e:
            logger.error("Segmenter exception processing frame: %s", type(e).__name__)
            self.segmenter.reset()
            return None

        if utterance is None:
            return None

        return self.process_utterance(utterance)

    def flush(self) -> Optional[PipelineResult]:
        """Flushes in-progress utterance on stream stop if minimum duration was met."""
        utterance = self.segmenter.flush()
        if utterance is not None:
            return self.process_utterance(utterance)
        return None

    def reset(self) -> None:
        """Resets segmenter state and drains any pending frames from the audio source."""
        self.segmenter.reset()
        self.source.drain()
